"""
Sharded JSONL output with per-anchor completion markers + resume support.

One ``ShardWriter`` per worker. Each writer owns ``part_<worker_id>.jsonl``
and ``part_<worker_id>.done`` exclusively — no inter-worker lock needed
because every worker writes to different files.

Records are buffered in memory and *appended* on flush (``write -> fsync``),
so each record hits the disk once no matter how large the shard grows.

Completion is tracked separately from the records: after every record of an
anchor has been flushed, ``commit_anchor`` appends the anchor's signature to
the ``.done`` file. Resume trusts only that file, so:

  * an anchor that failed or was killed half-way is re-run, even if some of
    its records reached the shard;
  * an anchor that legitimately produced zero records is still marked done.

When a writer reopens an existing shard it drops any records whose anchor
isn't in the ``.done`` file (one atomic ``write -> fsync -> os.replace``
rewrite at startup), so a re-run anchor never leaves duplicates behind. A
crash mid-append leaves at most a truncated last line, which every reader
skips.

Shards written before ``.done`` files existed have no marker file; for those,
``scan_completed_anchors`` falls back to the signatures found in the records.
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
    """Append-only JSONL writer for one shard, with anchor completion markers.

    Usage::

        with ShardWriter(shard_dir, worker_id=3) as w:
            for record in anchor_records:
                w.write(record)
            w.commit_anchor(anchor_signature)
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
        self._done_path = self.shard_dir / f"part_{worker_id:05d}.done"

        self._pending: list[dict[str, Any]] = []
        self._n_on_disk = 0
        if self._done_path.exists():
            self._n_on_disk = self._drop_uncommitted()
        elif self._path.exists():
            # Legacy shard (no markers): keep it as-is.
            self._n_on_disk = sum(1 for _ in _iter_jsonl(self._path))
        # Created up front so a crash before the first commit can't make this
        # shard look like a legacy one.
        self._done_path.touch()

    @property
    def path(self) -> Path:
        """The on-disk shard file (without the ``.tmp`` suffix)."""
        return self._path

    @property
    def done_path(self) -> Path:
        """The file listing this shard's completed anchor signatures."""
        return self._done_path

    def write(self, record: dict[str, Any]) -> None:
        """Buffer a record. Triggers a flush every ``flush_every`` writes."""
        self._pending.append(record)
        if len(self._pending) >= self.flush_every:
            self.flush()

    def flush(self) -> None:
        """Append buffered records to the shard and fsync. No-op when empty."""
        if not self._pending:
            return
        payload = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in self._pending)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            _fsync(f)
        self._n_on_disk += len(self._pending)
        self._pending = []

    def commit_anchor(self, anchor_signature: str) -> None:
        """Flush, then durably record ``anchor_signature`` as complete."""
        self.flush()
        with self._done_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(anchor_signature, ensure_ascii=False) + "\n")
            f.flush()
            _fsync(f)

    def close(self) -> None:
        """Final flush. Idempotent — safe to call from a finally block."""
        self.flush()

    def __enter__(self) -> "ShardWriter":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def __len__(self) -> int:
        return self._n_on_disk + len(self._pending)

    def _drop_uncommitted(self) -> int:
        """Rewrite the shard without records of uncommitted anchors.

        Returns the number of records kept. Records without an
        ``anchor_signature`` can't be attributed to an anchor and are kept.
        """
        if not self._path.exists():
            return 0
        done = _read_done(self._done_path)
        kept = [
            r for r in _iter_jsonl(self._path)
            if r.get("anchor_signature") is None or r["anchor_signature"] in done
        ]
        with self._tmp_path.open("w", encoding="utf-8") as f:
            for r in kept:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            _fsync(f)
        os.replace(self._tmp_path, self._path)
        return len(kept)


def scan_completed_anchors(shard_dir: Path | str) -> set[str]:
    """Return the set of anchor signatures that finished in any shard.

    Reads the ``part_*.done`` marker files. A ``part_*.jsonl`` without a
    sibling ``.done`` file predates the markers; its record signatures are
    used instead. Robust to:

      * the shard directory not existing yet (returns empty set),
      * orphaned ``.tmp`` files (ignored — we glob ``part_*.jsonl`` only),
      * partially-truncated last lines (decoder errors are swallowed).
    """
    shard_dir = Path(shard_dir)
    seen: set[str] = set()
    if not shard_dir.is_dir():
        return seen
    for done_path in sorted(shard_dir.glob("part_*.done")):
        seen |= _read_done(done_path)
    for path in sorted(shard_dir.glob("part_*.jsonl")):
        if path.with_suffix(".done").exists():
            continue
        for record in _iter_jsonl(path):
            sig = record.get("anchor_signature")
            if sig:
                seen.add(sig)
    return seen


def iter_shard_records(shard_dir: Path | str) -> Iterator[dict[str, Any]]:
    """Yield every record across every shard, in deterministic file order.

    Used by post-processing tools (parquet conversion, dataset card preview,
    etc.). Same robustness guarantees as ``scan_completed_anchors``. Records
    of anchors that never committed are skipped.
    """
    shard_dir = Path(shard_dir)
    if not shard_dir.is_dir():
        return
    for path in sorted(shard_dir.glob("part_*.jsonl")):
        done_path = path.with_suffix(".done")
        if not done_path.exists():
            yield from _iter_jsonl(path)
            continue
        done = _read_done(done_path)
        for r in _iter_jsonl(path):
            if r.get("anchor_signature") is None or r["anchor_signature"] in done:
                yield r


def _read_done(path: Path) -> set[str]:
    return {sig for sig in _iter_jsonl(path) if isinstance(sig, str) and sig}


def _iter_jsonl(path: Path) -> Iterator[Any]:
    """Yield JSON-decoded values from a JSONL file, skipping bad lines."""
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _fsync(f: Any) -> None:
    try:
        os.fsync(f.fileno())
    except OSError:
        # Some filesystems (e.g. tmpfs) don't support fsync; we just lose
        # the durability guarantee on crash.
        pass
