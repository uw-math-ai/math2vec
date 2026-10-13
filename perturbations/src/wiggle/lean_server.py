"""
Persistent Lean LSP server backend.

Spawns ``lake env lean --server`` once per process, performs the LSP
``initialize`` handshake, then opens **one sticky document** that all
subsequent requests reuse via ``textDocument/didChange``. The document is
pre-populated with the imports our snippets need (``import Mathlib`` /
``import Wiggle``); Lean's snapshotter keeps the prefix-stable elaboration
state, so only the trailing ``example`` declaration is re-elaborated on
each request.

Why a sticky document and not a fresh URI per call?  Lean's LSP spawns a
dedicated file worker per open URI. A fresh URI therefore re-imports
Mathlib from scratch (~13s on macOS), which defeats the whole point. With
one document + ``didChange``, the same worker stays alive across calls,
the snapshot for ``import Mathlib`` is cached, and per-call latency drops
to roughly 0.1–0.5s.

Public surface kept deliberately small:

    LeanLspServer(project_root)          # spawn + handshake + warm-up
        .run(code, timeout=...) -> str   # one compile request
        .close()                         # graceful shutdown

    get_server() -> LeanLspServer | None # lazy module-level singleton
    reset_server()                       # kill + clear the singleton

    LeanServerCrash                      # raised on subprocess exit /
                                         # fatalError / timeout

The ``run`` method returns a *string* in the same shape that
``lake env lean <file>`` would print to stdout/stderr — each diagnostic on
its own line block, prefixed by ``error:`` / ``warning:`` / ``info:`` /
``hint:`` followed by a newline and the message body. That shape is what
``wiggle.lean_runner.compile_lean`` and ``wiggle.lean_runner.extract_goal``
already parse, so swapping in this backend is a drop-in replacement.

The class is intentionally **not** thread-safe. One worker process gets one
server; concurrency lives upstream in the ProcessPoolExecutor.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

__all__ = [
    "LeanLspServer",
    "LeanServerCrash",
    "get_server",
    "reset_server",
]


class LeanServerCrash(RuntimeError):
    """Raised when the Lean LSP server dies, times out, or reports a fatal error.

    Callers (typically :func:`wiggle.lean_runner.run_lean`) catch this to
    decide between restarting the server and falling back to the one-shot
    subprocess backend.
    """


# ---------------------------------------------------------------------------
# JSON-RPC framing helpers
# ---------------------------------------------------------------------------

def _encode_frame(payload: dict[str, Any]) -> bytes:
    """Encode a JSON-RPC message in LSP wire format (``Content-Length`` header)."""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


def _read_frame(stream: BinaryIO) -> dict[str, Any] | None:
    """Read one LSP-framed JSON-RPC message from ``stream``.

    Returns ``None`` on EOF / closed stream. Raises ``ValueError`` on malformed
    headers (which we treat as a server crash upstream).
    """
    content_length: int | None = None
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        if line.lower().startswith(b"content-length:"):
            try:
                content_length = int(line.split(b":", 1)[1].strip())
            except ValueError as exc:
                raise ValueError(f"bad Content-Length header: {line!r}") from exc
    if content_length is None:
        raise ValueError("missing Content-Length header")

    body = b""
    remaining = content_length
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        body += chunk
        remaining -= len(chunk)
    return json.loads(body.decode("utf-8"))


# ---------------------------------------------------------------------------
# Diagnostic formatting
# ---------------------------------------------------------------------------

# Lean LSP severities (LSP spec: 1=Error, 2=Warning, 3=Information, 4=Hint).
_SEVERITY_LABEL = {1: "error", 2: "warning", 3: "info", 4: "hint"}


def format_diagnostics(diagnostics: list[dict[str, Any]]) -> str:
    """Format a list of LSP ``Diagnostic`` dicts into the subprocess-style string.

    Each diagnostic becomes a two-line block::

        <severity>:
        <message body>

    matching the layout ``lake env lean <file>`` prints. The newline between
    the label and the body is critical: the existing ``extract_goal`` regex
    (``r"^theorem .*extracted.*$"`` with ``re.MULTILINE``) needs to see
    ``theorem`` at line-start, and ``compile_lean`` only checks for the
    ``error:`` substring.
    """
    parts: list[str] = []
    for d in diagnostics:
        sev = d.get("severity", 1)
        label = _SEVERITY_LABEL.get(sev, "error")
        msg = d.get("message", "")
        parts.append(f"{label}:\n{msg}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# LeanLspServer
# ---------------------------------------------------------------------------


@dataclass
class _PendingResponse:
    """Slot used by ``_send_request`` to block on a JSON-RPC response."""

    event: threading.Event = field(default_factory=threading.Event)
    result: Any = None
    error: Any = None


_PRELUDE = "import Mathlib\nimport Wiggle\n"


class LeanLspServer:
    """Owns a single ``lake env lean --server`` subprocess and talks LSP to it.

    Per-call cost is amortised by keeping one sticky document open across
    requests. Each ``run(code)`` invocation issues a ``textDocument/didChange``
    that replaces the document body wholesale; Lean's snapshotter keeps the
    elaboration state for any unchanged prefix (notably the ``import Mathlib``
    line), so only the trailing user snippet is re-elaborated.
    """

    def __init__(
        self,
        project_root: Path,
        *,
        startup_timeout: float = 240.0,
        lake_cmd: tuple[str, ...] = ("lake", "env", "lean", "--server"),
        prelude: str = _PRELUDE,
        warmup: bool = True,
    ) -> None:
        self.project_root = Path(project_root)
        self._lake_cmd = lake_cmd
        self._prelude = prelude
        self._proc: subprocess.Popen[bytes] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_reader = threading.Event()

        # Shared state guarded by ``_lock``.
        self._lock = threading.Lock()
        self._next_id = 1
        self._pending: dict[int, _PendingResponse] = {}
        self._diagnostics: dict[str, list[dict[str, Any]]] = {}
        self._fatal: str | None = None

        # Sticky document state. The URI is fixed for the life of the server;
        # the version is monotonically bumped on every ``run`` call so we can
        # match diagnostics to the request that produced them.
        self._doc_uri = self._path_to_uri(self.project_root / "_wiggle_session.lean")
        self._doc_version = 0

        self._spawn()
        self._initialize(timeout=startup_timeout)
        if warmup:
            self._open_sticky_document(timeout=startup_timeout)

    # ── lifecycle ──────────────────────────────────────────────────────────

    def _spawn(self) -> None:
        """Launch the LSP subprocess and start the reader thread."""
        self._proc = subprocess.Popen(
            list(self._lake_cmd),
            cwd=str(self.project_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name="lean-lsp-reader",
            daemon=True,
        )
        self._reader_thread.start()

    def _initialize(self, *, timeout: float) -> None:
        """Send ``initialize`` and ``initialized``, blocking on the response.

        The initialize response is what gates Mathlib import; this is where
        we pay the ~30s warm-cache cost (or up to ~2 min cold).
        """
        root_uri = self._path_to_uri(self.project_root)
        self._send_request(
            "initialize",
            {
                "processId": os.getpid(),
                "rootUri": root_uri,
                "rootPath": str(self.project_root),
                "capabilities": {
                    "textDocument": {
                        "publishDiagnostics": {"relatedInformation": False},
                    },
                },
                "trace": "off",
            },
            timeout=timeout,
        )
        self._send_notification("initialized", {})

    def _open_sticky_document(self, *, timeout: float) -> None:
        """Open the one document we'll keep around for the life of the server.

        Blocking on ``waitForDiagnostics`` here forces Mathlib's import to
        finish *now*, so the first user ``run()`` call benefits from the warm
        cache.
        """
        self._doc_version = 1
        self._send_notification(
            "textDocument/didOpen",
            {
                "textDocument": {
                    "uri": self._doc_uri,
                    "languageId": "lean4",
                    "version": self._doc_version,
                    "text": self._prelude,
                }
            },
        )
        self._send_request(
            "textDocument/waitForDiagnostics",
            {"uri": self._doc_uri, "version": self._doc_version},
            timeout=timeout,
        )
        # Discard any diagnostics from the warmup (there shouldn't be any, but
        # we don't want stale warnings leaking into the first user call).
        with self._lock:
            self._diagnostics.pop(self._doc_uri, None)

    def close(self) -> None:
        """Best-effort graceful shutdown. Idempotent."""
        if self._proc is None:
            return
        try:
            self._send_request("shutdown", None, timeout=10.0)
            self._send_notification("exit", None)
        except Exception:
            pass
        self._stop_reader.set()
        try:
            self._proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            try:
                self._proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                pass
        self._proc = None

    def __enter__(self) -> "LeanLspServer":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    # ── public per-call API ────────────────────────────────────────────────

    def run(self, code: str, *, timeout: float = 60.0) -> str:
        """Submit one snippet, wait for diagnostics, return them as a string.

        Uses ``textDocument/didChange`` to update the sticky document's text
        wholesale, then ``textDocument/waitForDiagnostics`` to block until
        publishing for the new version is stable. Lean reuses the elaboration
        snapshots for the unchanged ``import Mathlib`` prefix, so the only
        work is elaborating the user's trailing snippet — typically 0.1–0.5s
        once the worker is warm.

        The ``code`` argument should be a complete Lean source file (the
        existing helpers in :mod:`wiggle.lean_runner` prepend their own
        ``import`` lines, which is fine: identical prefixes share snapshots).
        """
        self._check_alive()

        with self._lock:
            self._doc_version += 1
            version = self._doc_version
            # Clear stale diagnostics from any earlier version before issuing
            # the change, so the read below never returns leftover entries.
            self._diagnostics.pop(self._doc_uri, None)

        self._send_notification(
            "textDocument/didChange",
            {
                "textDocument": {"uri": self._doc_uri, "version": version},
                "contentChanges": [{"text": code}],
            },
        )
        self._send_request(
            "textDocument/waitForDiagnostics",
            {"uri": self._doc_uri, "version": version},
            timeout=timeout,
        )
        with self._lock:
            diagnostics = list(self._diagnostics.get(self._doc_uri, []))
        return format_diagnostics(diagnostics)

    # ── reader thread ──────────────────────────────────────────────────────

    def _reader_loop(self) -> None:
        """Background thread: parse frames off stdout and dispatch them."""
        assert self._proc is not None and self._proc.stdout is not None
        stream = self._proc.stdout
        try:
            while not self._stop_reader.is_set():
                try:
                    msg = _read_frame(stream)
                except (ValueError, OSError) as exc:
                    self._mark_fatal(f"reader: bad frame: {exc}")
                    return
                if msg is None:
                    self._mark_fatal("reader: stdout closed")
                    return
                self._dispatch(msg)
        finally:
            self._stop_reader.set()

    def _dispatch(self, msg: dict[str, Any]) -> None:
        """Route one parsed JSON-RPC message to its handler."""
        if "id" in msg and ("result" in msg or "error" in msg):
            # Response to one of our requests.
            with self._lock:
                slot = self._pending.pop(msg["id"], None)
            if slot is not None:
                slot.result = msg.get("result")
                slot.error = msg.get("error")
                slot.event.set()
            return

        method = msg.get("method")
        if method == "textDocument/publishDiagnostics":
            params = msg.get("params") or {}
            uri = params.get("uri")
            diags = params.get("diagnostics") or []
            if uri is not None:
                with self._lock:
                    # Overwrite, not append: Lean republishes the full set
                    # for the document each time.
                    self._diagnostics[uri] = list(diags)
        elif method == "$/lean/fileProgress":
            params = msg.get("params") or {}
            for info in params.get("processing") or []:
                if info.get("kind") == 2:  # LeanFileProgressKind.fatalError
                    self._mark_fatal(
                        "fileProgress reported fatalError on "
                        + str(params.get("textDocument", {}).get("uri"))
                    )
                    return
        # Other notifications (window/logMessage, $/lean/ileanInfoUpdate, …)
        # are ignored.

    def _mark_fatal(self, reason: str) -> None:
        """Record a fatal error and wake every waiter so they bail out."""
        with self._lock:
            if self._fatal is None:
                self._fatal = reason
            pending = list(self._pending.items())
            self._pending.clear()
        for _id, slot in pending:
            slot.error = {"code": -32099, "message": reason}
            slot.event.set()

    # ── send helpers ───────────────────────────────────────────────────────

    def _check_alive(self) -> None:
        if self._fatal is not None:
            raise LeanServerCrash(self._fatal)
        if self._proc is None or self._proc.poll() is not None:
            raise LeanServerCrash("lean server is not running")

    def _send_notification(self, method: str, params: Any) -> None:
        self._check_alive()
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._write(payload)

    def _send_request(self, method: str, params: Any, *, timeout: float) -> Any:
        self._check_alive()
        with self._lock:
            req_id = self._next_id
            self._next_id += 1
            slot = _PendingResponse()
            self._pending[req_id] = slot
        payload: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        self._write(payload)
        if not slot.event.wait(timeout=timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            raise LeanServerCrash(
                f"timeout after {timeout}s waiting for response to {method}"
            )
        if slot.error is not None:
            raise LeanServerCrash(
                f"{method} returned error: {slot.error}"
            )
        return slot.result

    def _write(self, payload: dict[str, Any]) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise LeanServerCrash("stdin is closed")
        try:
            self._proc.stdin.write(_encode_frame(payload))
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._mark_fatal(f"write failed: {exc}")
            raise LeanServerCrash(str(exc)) from exc

    # ── misc ───────────────────────────────────────────────────────────────

    @staticmethod
    def _path_to_uri(path: Path) -> str:
        """Convert an absolute filesystem path to a ``file://`` URI."""
        p = Path(path).resolve()
        # Quick & dirty, but matches what Lean's LSP expects on macOS/Linux.
        return "file://" + str(p)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_singleton: LeanLspServer | None = None
_singleton_lock = threading.Lock()


def get_server() -> LeanLspServer | None:
    """Return the process-wide singleton, lazily spawning it on first call.

    Returns ``None`` (rather than raising) if the server fails to start so
    callers can transparently fall back to the subprocess backend without a
    visible traceback.
    """
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            return _singleton
        from wiggle.lean_runner import get_project_root  # local import: avoid cycles

        try:
            _singleton = LeanLspServer(get_project_root())
        except Exception:
            _singleton = None
        return _singleton


def reset_server() -> None:
    """Kill the current singleton; the next ``get_server()`` will respawn."""
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            try:
                _singleton.close()
            except Exception:
                pass
            _singleton = None
