"""
Sharded JSONL output with atomic rename + resume support.

One ``ShardWriter`` per worker. Each writer owns ``part_<worker_id>.jsonl``
exclusively — no inter-worker lock needed because every worker writes to a
different file.

Atomicity is achieved by buffering records in memory and rewriting the entire
shard on every flush via a ``write -> fsync -> os.replace`` sequence:

    1. Serialize the full in-memory record list to ``part_NNNNN.jsonl.tmp``.
    2. ``fsync`` to push bytes to disk.
    3. ``os.replace(.tmp, .jsonl)`` — atomic on POSIX, atomic on Windows since
       Python 3.3.

If the process is killed mid-flush, the ``.tmp`` file is orphaned and the
previous ``.jsonl`` (one flush old) is intact and resumable. The crash loses
at most ``flush_every`` records of work per worker.

Memory cost is the in-memory record list — bounded by the shard size. With
~150k records × ~500 bytes/record per worker, that's ~75 MB per worker, which
is fine even at 32 workers.

Resume model: at startup we scan every ``part_*.jsonl`` in the shard dir and
collect ``anchor_signature`` values into a set. Anchors in that set are
skipped. Orphaned ``.tmp`` files and partially-corrupt JSONL lines are simply
ignored (decoder errors swallowed).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterator

__all__ = [
    "ShardWriter",
    "scan_completed_anchors",
    "iter_shard_records",
]


class ShardWriter:
    """Atomic-rewrite JSONL writer for one shard.

    Usage::

        with ShardWriter(shard_dir, worker_id=3, flush_every=50) as w:
            for record in records:
                w.write(record)
        # close() implicitly flushes on exit

    A ``ShardWriter`` is *not* thread-safe — each worker process owns one.
    """

    def __init__(
        self,
        shard_dir: Path | str,
        worker_id: int,
        *,
        flush_every: int = 50,
    ) -> None:
        self.shard_dir = Path(shard_dir)
        self.worker_id = worker_id
        self.flush_every = max(1, int(flush_every))
        self.shard_dir.mkdir(parents=True, exist_ok=True)

        self._path = self.shard_dir / f"part_{worker_id:05d}.jsonl"
        self._tmp_path = self.shard_dir / f"part_{worker_id:05d}.jsonl.tmp"

        # If the shard already exists (resume case), load it so subsequent
        # flushes don't lose what was there.
        self._records: list[dict[str, Any]] = []
        if self._path.exists():
            self._records = list(_iter_jsonl(self._path))

        self._pending_since_flush = 0

    @property
    def path(self) -> Path:
        """The on-disk shard file (without the ``.tmp`` suffix)."""
        return self._path

    def write(self, record: dict[str, Any]) -> None:
        """Append a record. Triggers a flush every ``flush_every`` writes."""
        self._records.append(record)
        self._pending_since_flush += 1
        if self._pending_since_flush >= self.flush_every:
            self.flush()

    def flush(self) -> None:
        """Persist all buffered records atomically.

        Writes the full in-memory list to a ``.tmp`` sibling, fsyncs, then
        ``os.replace``s onto the real path. Safe to call when nothing is
        pending (becomes a no-op).
        """
        if self._pending_since_flush == 0 and self._path.exists():
            return
        with self._tmp_path.open("w", encoding="utf-8") as f:
            for r in self._records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # Some filesystems (e.g. tmpfs) don't support fsync. The
                # os.replace below is still atomic; we just lose the
                # durability guarantee on crash.
                pass
        os.replace(self._tmp_path, self._path)
        self._pending_since_flush = 0

    def close(self) -> None:
        """Final flush. Idempotent — safe to call from a finally block."""
        self.flush()
        # Clean up any leftover .tmp from a half-finished flush — won't exist
        # under normal flow because os.replace atomically removed it.
        try:
            if self._tmp_path.exists():
                self._tmp_path.unlink()
        except OSError:
            pass

    def __enter__(self) -> "ShardWriter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def __len__(self) -> int:
        return len(self._records)


def scan_completed_anchors(shard_dir: Path | str) -> set[str]:
    """Return the set of ``anchor_signature`` values present in any shard.

    Used at startup to decide which anchors to skip. Robust to:

      * the shard directory not existing yet (returns empty set),
      * orphaned ``.tmp`` files (ignored — we glob ``part_*.jsonl`` only),
      * partially-truncated last lines (decoder errors are swallowed).

    The ``anchor_signature`` key is the one ``run_pipeline`` writes into every
    record; if a record is missing the key (e.g. malformed) it's silently
    skipped.
    """
    shard_dir = Path(shard_dir)
    seen: set[str] = set()
    if not shard_dir.is_dir():
        return seen
    for path in sorted(shard_dir.glob("part_*.jsonl")):
        for record in _iter_jsonl(path):
            sig = record.get("anchor_signature")
            if sig:
                seen.add(sig)
    return seen


def iter_shard_records(shard_dir: Path | str) -> Iterator[dict[str, Any]]:
    """Yield every record across every shard, in deterministic file order.

    Used by post-processing tools (parquet conversion, dataset card preview,
    etc.). Same robustness guarantees as ``scan_completed_anchors``.
    """
    shard_dir = Path(shard_dir)
    if not shard_dir.is_dir():
        return
    for path in sorted(shard_dir.glob("part_*.jsonl")):
        yield from _iter_jsonl(path)


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield JSON-decoded records from a JSONL file, skipping bad lines."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue
