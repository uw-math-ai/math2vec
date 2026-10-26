"""
Per-worker structured JSONL logging plus a parent-process heartbeat.

We avoid the stdlib ``logging`` name because we want this to be importable as
``wiggle.run_logging``; shadowing ``logging`` from inside our own package gets
sketchy fast.

Two pieces:

  * ``WorkerLogger`` — one per worker subprocess. Writes JSONL events to
    ``logs/<run-id>/worker-<NNN>.log.jsonl``. Append-only with line-buffering;
    crashes lose at most one in-flight line. Each line is a single JSON object
    with at least ``ts``, ``worker``, ``event``.

  * ``Heartbeat`` — one per orchestrator. Writes a single-record JSONL
    ``logs/<run-id>/heartbeat.jsonl`` (rewritten in place each tick) plus an
    appending ``heartbeat.history.jsonl`` for time-series tailing. Tick cadence
    defaults to 30s.

Both are intentionally minimal — no log levels, no filtering, no rotation.
The output is for ``tail -F`` plus offline analysis by ``pipeline/quality_report.py``.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

__all__ = [
    "WorkerLogger",
    "Heartbeat",
]


class WorkerLogger:
    """JSONL event log for one worker.

    Each call to :meth:`event` writes one line and flushes the file handle so
    a ``tail -F`` from another shell sees events promptly. We do not call
    ``os.fsync`` on every event — that would dominate the worker's wallclock.
    A clean ``close()`` does fsync, so anything written before a clean drain
    is durable.
    """

    def __init__(self, log_dir: Path | str, worker_id: int) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.worker_id = worker_id
        self._path = self.log_dir / f"worker-{worker_id:05d}.log.jsonl"
        # Line-buffered so each json line is flushed by the OS as we write.
        self._f = self._path.open("a", encoding="utf-8", buffering=1)

    @property
    def path(self) -> Path:
        return self._path

    def event(self, event: str, **fields: Any) -> None:
        """Write one JSON line to the worker's log."""
        record = {
            "ts": time.time(),
            "worker": self.worker_id,
            "event": event,
            **fields,
        }
        self._f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def close(self) -> None:
        try:
            self._f.flush()
            try:
                os.fsync(self._f.fileno())
            except OSError:
                pass
        finally:
            self._f.close()

    def __enter__(self) -> "WorkerLogger":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


class Heartbeat:
    """Parent-side periodic status snapshot.

    Writes two files in ``log_dir``:

      * ``heartbeat.jsonl`` — single-line file holding the *current* state.
        Rewritten atomically every tick. Cheap to ``cat`` for a status check.

      * ``heartbeat.history.jsonl`` — append-only time series of every tick.
        Useful for plotting throughput post-run.

    Designed to be driven from a background thread. Start with :meth:`start`,
    update fields by mutating :attr:`state`, stop with :meth:`stop`.
    """

    def __init__(self, log_dir: Path | str, interval_seconds: float = 30.0) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._snapshot_path = self.log_dir / "heartbeat.jsonl"
        self._history_path = self.log_dir / "heartbeat.history.jsonl"
        self.interval_seconds = interval_seconds

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        self.state: dict[str, Any] = {
            "started_ts": time.time(),
            "anchors_done": 0,
            "anchors_skipped": 0,
            "anchors_failed": 0,
            "records_written": 0,
            "workers_alive": 0,
            "drain_requested": False,
        }

    def update(self, **fields: Any) -> None:
        """Merge ``fields`` into the current state."""
        with self._lock:
            self.state.update(fields)

    def tick(self) -> dict[str, Any]:
        """Take one snapshot and append it to history. Returns the snapshot dict."""
        now = time.time()
        with self._lock:
            snap = dict(self.state)
        snap["ts"] = now
        elapsed = max(0.001, now - snap.get("started_ts", now))
        snap["elapsed_seconds"] = elapsed
        snap["anchors_per_minute"] = round(
            snap.get("anchors_done", 0) * 60.0 / elapsed, 2
        )

        tmp = self._snapshot_path.with_suffix(self._snapshot_path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")
        os.replace(tmp, self._snapshot_path)

        with self._history_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(snap, ensure_ascii=False) + "\n")
        return snap

    def start(self) -> None:
        """Launch the background tick thread."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._loop, name="wiggle-heartbeat", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        """Stop ticking and emit one final snapshot."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.interval_seconds + 5.0)
            self._thread = None
        self.tick()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.tick()
            # Sleep in small slices so stop() doesn't have to wait a full tick.
            slept = 0.0
            while slept < self.interval_seconds and not self._stop.is_set():
                step = min(0.5, self.interval_seconds - slept)
                self._stop.wait(step)
                slept += step
