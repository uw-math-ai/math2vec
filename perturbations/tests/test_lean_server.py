"""
Tests for the persistent Lean LSP server backend.

Two layers:

  * **Protocol unit tests** — pure-Python, no subprocess. Exercise the
    framing/format helpers directly and drive a full ``LeanLspServer``
    against a fake transport that auto-responds with canned JSON-RPC frames.

  * **Live integration test** — actually spawns ``lake env lean --server``
    against a trivial snippet. Skipped unless ``WIGGLE_RUN_LEAN_INTEGRATION=1``
    is set, because the cold first call easily takes >60s.

The fake transport intentionally avoids ``os.pipe`` to stay cross-platform;
it implements just enough of ``subprocess.Popen``'s interface (``stdin``
with ``write``/``flush``, ``stdout`` with ``readline``/``read``, ``stderr``,
``poll``/``wait``/``kill``) for the reader thread to work unchanged.
"""

from __future__ import annotations

import io
import json
import os
import re
import threading
import time
from typing import Any, Callable
from unittest import mock

import pytest

from wiggle.lean_server import (
    LeanLspServer,
    LeanServerCrash,
    _encode_frame,
    _read_frame,
    format_diagnostics,
)


# ─── Pure helpers ───────────────────────────────────────────────────────────────


class TestFraming:
    def test_encode_then_read_round_trip(self) -> None:
        msg = {"jsonrpc": "2.0", "id": 7, "result": {"capabilities": {}}}
        frame = _encode_frame(msg)
        assert frame.startswith(b"Content-Length: ")
        assert b"\r\n\r\n" in frame
        assert _read_frame(io.BytesIO(frame)) == msg

    def test_encode_handles_unicode(self) -> None:
        msg = {"jsonrpc": "2.0", "method": "x", "params": {"text": "α + β = ∞"}}
        assert _read_frame(io.BytesIO(_encode_frame(msg))) == msg

    def test_read_frame_returns_none_on_eof(self) -> None:
        assert _read_frame(io.BytesIO(b"")) is None

    def test_read_frame_returns_none_on_truncated_body(self) -> None:
        # Header promises 100 bytes; we only provide 5.
        truncated = b"Content-Length: 100\r\n\r\nhello"
        assert _read_frame(io.BytesIO(truncated)) is None

    def test_read_frame_rejects_missing_content_length(self) -> None:
        with pytest.raises(ValueError):
            _read_frame(io.BytesIO(b"\r\n"))

    def test_read_frame_rejects_bad_content_length(self) -> None:
        with pytest.raises(ValueError):
            _read_frame(io.BytesIO(b"Content-Length: not-a-number\r\n\r\n"))


class TestFormatDiagnostics:
    def test_empty_list_is_empty_string(self) -> None:
        assert format_diagnostics([]) == ""

    def test_severities_get_labelled(self) -> None:
        out = format_diagnostics(
            [
                {"severity": 1, "message": "type mismatch"},
                {"severity": 2, "message": "unused variable"},
                {"severity": 3, "message": "info body"},
                {"severity": 4, "message": "consider rewriting"},
            ]
        )
        assert "error:\ntype mismatch" in out
        assert "warning:\nunused variable" in out
        assert "info:\ninfo body" in out
        assert "hint:\nconsider rewriting" in out

    def test_missing_severity_defaults_to_error(self) -> None:
        out = format_diagnostics([{"message": "something broke"}])
        assert out.startswith("error:")

    def test_compile_lean_substring_check_works(self) -> None:
        """``compile_lean`` returns ``"error:" not in output`` — must hold."""
        good = format_diagnostics([{"severity": 3, "message": "fyi"}])
        bad = format_diagnostics([{"severity": 1, "message": "boom"}])
        assert "error:" not in good
        assert "error:" in bad

    def test_extract_goal_regex_matches_info_payload(self) -> None:
        """``extract_goal`` regex needs ``^theorem`` at line-start; our format
        puts the message body on its own line so it does."""
        msg = (
            "theorem wiggle_demo.extracted_1_1 {i j : ℕ} : "
            "i + j = j + i := sorry"
        )
        out = format_diagnostics([{"severity": 3, "message": msg}])
        regex = re.compile(r"^theorem .*extracted.*$", re.MULTILINE)
        assert regex.search(out) is not None


# ─── Fake transport ─────────────────────────────────────────────────────────────


class _BlockingStream:
    """File-like blocking stream backed by a buffer + condition variable.

    Implements only ``readline()`` and ``read(n)`` — enough for ``_read_frame``.
    """

    def __init__(self) -> None:
        self._buf = bytearray()
        self._cond = threading.Condition()
        self._closed = False

    def feed(self, data: bytes) -> None:
        with self._cond:
            self._buf.extend(data)
            self._cond.notify_all()

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def readline(self) -> bytes:
        with self._cond:
            while True:
                idx = self._buf.find(b"\n")
                if idx >= 0:
                    line = bytes(self._buf[: idx + 1])
                    del self._buf[: idx + 1]
                    return line
                if self._closed:
                    return b""
                self._cond.wait()

    def read(self, n: int) -> bytes:
        with self._cond:
            while True:
                if len(self._buf) >= n:
                    data = bytes(self._buf[:n])
                    del self._buf[:n]
                    return data
                if self._closed:
                    data = bytes(self._buf)
                    self._buf.clear()
                    return data
                self._cond.wait()


class _AutoRespondingStdin:
    """Stdin-side fake. Parses LSP frames as they're written, dispatches to
    the parent fake process for auto-response."""

    def __init__(self, parent: "_FakeLeanProcess") -> None:
        self._parent = parent
        self._buf = bytearray()
        self._lock = threading.Lock()
        self.closed = False

    def write(self, b: bytes) -> int:
        with self._lock:
            self._buf.extend(b)
            self._drain()
        return len(b)

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def _drain(self) -> None:
        while True:
            hdr_end = self._buf.find(b"\r\n\r\n")
            if hdr_end < 0:
                return
            headers = bytes(self._buf[:hdr_end]).decode("ascii", errors="replace")
            content_length: int | None = None
            for line in headers.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    content_length = int(line.split(":", 1)[1].strip())
                    break
            if content_length is None:
                return
            total = hdr_end + 4 + content_length
            if len(self._buf) < total:
                return
            body = bytes(self._buf[hdr_end + 4 : total])
            del self._buf[:total]
            try:
                msg = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            self._parent._on_client_message(msg)


class _FakeLeanProcess:
    """Subset of ``subprocess.Popen`` sufficient for ``LeanLspServer``.

    Each test wires up its own ``handlers``/``post_notifications`` so it can
    script exactly the LSP exchange under test.
    """

    def __init__(self) -> None:
        self.stdout = _BlockingStream()
        self.stderr = _BlockingStream()
        self.stdin = _AutoRespondingStdin(self)
        self.returncode: int | None = None

        self.handlers: dict[str, Callable[[Any], Any]] = {
            "initialize": lambda _params: {"capabilities": {}},
            "shutdown": lambda _params: None,
        }
        # Notifications to publish *after* a request is received, keyed by
        # the request method. (e.g. emit publishDiagnostics + fileProgress
        # after a textDocument/waitForDiagnostics.)
        self.post_notifications: dict[str, list[dict[str, Any]]] = {}
        # Notifications to publish *after* a client notification is received,
        # keyed by method (e.g. emit publishDiagnostics after didOpen).
        self.post_notifications_for_notifications: dict[str, list[dict[str, Any]]] = {}

        self.received_requests: list[dict[str, Any]] = []
        self.received_notifications: list[dict[str, Any]] = []

    # ─ LSP wire layer ─

    def _send(self, msg: dict[str, Any]) -> None:
        self.stdout.feed(_encode_frame(msg))

    def _on_client_message(self, msg: dict[str, Any]) -> None:
        if "id" in msg and "method" in msg:
            self.received_requests.append(msg)
            method = msg["method"]
            req_id = msg["id"]
            handler = self.handlers.get(method)
            if handler is not None:
                try:
                    result = handler(msg.get("params"))
                    self._send({"jsonrpc": "2.0", "id": req_id, "result": result})
                except Exception as exc:
                    self._send(
                        {
                            "jsonrpc": "2.0",
                            "id": req_id,
                            "error": {"code": -32000, "message": str(exc)},
                        }
                    )
            for n in self.post_notifications.get(method, []):
                self._send(n)
        elif "method" in msg:
            self.received_notifications.append(msg)
            for n in self.post_notifications_for_notifications.get(msg["method"], []):
                self._send(n)
        # Else: response. (Server-as-client; we don't expect any.)

    # ─ Popen surface ─

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        # The real ``close`` calls ``shutdown``+``exit``; the test's exit
        # handler bumps returncode for us. If still None, pretend it exited.
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def kill(self) -> None:
        self.returncode = -9
        self.stdout.close()


def _make_server(
    proc: _FakeLeanProcess,
    *,
    tmp_path,
    warmup: bool = True,
) -> LeanLspServer:
    """Construct a ``LeanLspServer`` whose subprocess is replaced by ``proc``.

    Wires up sensible defaults so the constructor's
    ``initialize`` + ``didOpen`` + warmup ``waitForDiagnostics`` round-trip
    completes. Tests override these handlers *after* construction when they
    want to exercise per-call behaviour.
    """
    proc.handlers.setdefault(
        "textDocument/waitForDiagnostics", lambda _p: {}
    )

    # Flip returncode on ``exit`` notification so ``close()`` doesn't block.
    original = proc._on_client_message

    def patched(msg: dict[str, Any]) -> None:
        original(msg)
        if msg.get("method") == "exit":
            proc.returncode = 0
            proc.stdout.close()

    proc._on_client_message = patched  # type: ignore[assignment]

    with mock.patch("subprocess.Popen", return_value=proc):
        return LeanLspServer(tmp_path, startup_timeout=5.0, warmup=warmup)


# ─── End-to-end protocol tests against the fake transport ──────────────────────


class TestServerProtocol:
    def test_initialize_handshake(self, tmp_path) -> None:
        proc = _FakeLeanProcess()
        srv = _make_server(proc, tmp_path=tmp_path)
        try:
            methods = [r["method"] for r in proc.received_requests]
            assert "initialize" in methods
            notif_methods = [n["method"] for n in proc.received_notifications]
            assert "initialized" in notif_methods
        finally:
            srv.close()

    def test_run_round_trip_returns_formatted_diagnostics(self, tmp_path) -> None:
        proc = _FakeLeanProcess()

        diagnostics = [
            {
                "severity": 3,
                "message": (
                    "theorem wiggle_demo.extracted_1_1 {i : ℕ} : i = i := sorry"
                ),
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 0},
                },
            }
        ]

        srv = _make_server(proc, tmp_path=tmp_path)

        # After warmup, hook didChange so the next call gets back diagnostics.
        original_on = proc._on_client_message

        def patched(msg: dict[str, Any]) -> None:
            original_on(msg)
            if msg.get("method") == "textDocument/didChange":
                uri = (msg.get("params") or {}).get("textDocument", {}).get("uri")
                proc._send(
                    {
                        "jsonrpc": "2.0",
                        "method": "textDocument/publishDiagnostics",
                        "params": {"uri": uri, "diagnostics": diagnostics},
                    }
                )

        proc._on_client_message = patched  # type: ignore[assignment]

        try:
            output = srv.run("example : True := by trivial\n", timeout=5.0)
            assert "info:" in output
            regex = re.compile(r"^theorem .*extracted.*$", re.MULTILINE)
            assert regex.search(output) is not None

            # Document lifecycle: ONE didOpen (warmup) + repeated didChange.
            notif_methods = [n["method"] for n in proc.received_notifications]
            assert notif_methods.count("textDocument/didOpen") == 1
            assert "textDocument/didChange" in notif_methods
        finally:
            srv.close()

    def test_error_diagnostic_makes_compile_lean_substring_check_fail(
        self, tmp_path
    ) -> None:
        proc = _FakeLeanProcess()
        srv = _make_server(proc, tmp_path=tmp_path)

        original_on = proc._on_client_message

        def patched(msg: dict[str, Any]) -> None:
            original_on(msg)
            if msg.get("method") == "textDocument/didChange":
                uri = (msg.get("params") or {}).get("textDocument", {}).get("uri")
                proc._send(
                    {
                        "jsonrpc": "2.0",
                        "method": "textDocument/publishDiagnostics",
                        "params": {
                            "uri": uri,
                            "diagnostics": [
                                {"severity": 1, "message": "unknown identifier"}
                            ],
                        },
                    }
                )

        proc._on_client_message = patched  # type: ignore[assignment]

        try:
            output = srv.run("example : Foo := rfl\n", timeout=5.0)
            assert "error:" in output
        finally:
            srv.close()

    def test_fatal_file_progress_marks_server_crashed(self, tmp_path) -> None:
        proc = _FakeLeanProcess()
        srv = _make_server(proc, tmp_path=tmp_path)

        # After warmup, swap out waitForDiagnostics so it never replies; the
        # fatal-progress handler is what should wake the waiter.
        proc.handlers["textDocument/waitForDiagnostics"] = lambda _p: (_ for _ in ()).throw(
            RuntimeError("should not be called")
        )
        # Actually we want it to silently never reply, not raise. Remove it.
        del proc.handlers["textDocument/waitForDiagnostics"]

        original_on = proc._on_client_message

        def patched(msg: dict[str, Any]) -> None:
            original_on(msg)
            if msg.get("method") == "textDocument/didChange":
                uri = (msg.get("params") or {}).get("textDocument", {}).get("uri")
                proc._send(
                    {
                        "jsonrpc": "2.0",
                        "method": "$/lean/fileProgress",
                        "params": {
                            "textDocument": {"uri": uri, "version": 2},
                            "processing": [
                                {
                                    "range": {
                                        "start": {"line": 0, "character": 0},
                                        "end": {"line": 0, "character": 0},
                                    },
                                    "kind": 2,  # fatalError
                                }
                            ],
                        },
                    }
                )

        proc._on_client_message = patched  # type: ignore[assignment]

        try:
            with pytest.raises(LeanServerCrash):
                srv.run("example : True := by trivial\n", timeout=5.0)
        finally:
            srv.close()

    def test_timeout_raises_lean_server_crash(self, tmp_path) -> None:
        proc = _FakeLeanProcess()
        # Warmup succeeds via the default waitForDiagnostics handler.
        srv = _make_server(proc, tmp_path=tmp_path)
        # Now nuke the handler so per-call waitForDiagnostics never replies.
        del proc.handlers["textDocument/waitForDiagnostics"]
        try:
            with pytest.raises(LeanServerCrash):
                srv.run("example : True := by trivial\n", timeout=0.2)
        finally:
            srv.close()

    def test_subprocess_exit_during_call_raises(self, tmp_path) -> None:
        proc = _FakeLeanProcess()
        srv = _make_server(proc, tmp_path=tmp_path)
        try:
            proc.returncode = 1
            proc.stdout.close()
            with pytest.raises(LeanServerCrash):
                srv.run("example : True := by trivial\n", timeout=1.0)
        finally:
            srv.close()


# ─── Module-level singleton ─────────────────────────────────────────────────────


class TestSingleton:
    def test_get_server_returns_none_when_lake_missing(
        self, monkeypatch
    ) -> None:
        """If ``lake`` is not on PATH, ``get_server()`` swallows the failure
        so ``lean_runner.run_lean`` can fall back to the subprocess backend
        without a traceback."""
        from wiggle import lean_server as ls

        ls.reset_server()
        monkeypatch.setattr(
            "subprocess.Popen",
            mock.Mock(side_effect=FileNotFoundError("lake not found")),
        )
        try:
            assert ls.get_server() is None
        finally:
            ls.reset_server()


# ─── Live integration test (gated) ──────────────────────────────────────────────


@pytest.mark.skipif(
    os.environ.get("WIGGLE_RUN_LEAN_INTEGRATION") != "1",
    reason="set WIGGLE_RUN_LEAN_INTEGRATION=1 to spawn a real `lake env lean --server`",
)
class TestRealLeanServer:
    def test_compile_trivial_example(self) -> None:
        from wiggle.lean_runner import compile_lean

        # A statement that obviously type-checks against Mathlib.
        assert compile_lean("triv", "True") is True

    def test_compile_rejects_garbage(self) -> None:
        from wiggle.lean_runner import compile_lean

        assert compile_lean("bad", "NotARealType") is False

    def test_extract_goal_returns_theorem_text(self) -> None:
        from wiggle.lean_runner import extract_goal

        result = extract_goal("intro h", "True → True")
        # Don't assert the exact string (depends on Lean version), but it
        # should at least parse into a (sig, type) pair.
        assert result is not None
        sig, type_str = result
        assert isinstance(sig, str) and isinstance(type_str, str)
