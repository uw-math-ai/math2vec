"""
Tests for ``wiggle.shards`` — append-only JSONL writer, completion markers, resume scan.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from wiggle.shards import ShardWriter, iter_shard_records, scan_completed_anchors


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_anchor(w: ShardWriter, sig: str, **fields: object) -> None:
    w.write({"anchor_signature": sig, **fields})
    w.commit_anchor(sig)


class TestShardWriter:
    def test_records_land_in_part_NNNNN_file(self, tmp_path: Path) -> None:
        with ShardWriter(tmp_path, worker_id=3) as w:
            w.write({"anchor_signature": "a", "x": 1})
            w.write({"anchor_signature": "b", "x": 2})

        path = tmp_path / "part_00003.jsonl"
        assert path.exists()
        assert _read_jsonl(path) == [
            {"anchor_signature": "a", "x": 1},
            {"anchor_signature": "b", "x": 2},
        ]

    def test_flush_every_triggers_flush(self, tmp_path: Path) -> None:
        w = ShardWriter(tmp_path, worker_id=0, flush_every=3)
        try:
            w.write({"anchor_signature": "a"})
            w.write({"anchor_signature": "b"})
            # Two writes haven't crossed flush_every yet — file might not exist.
            assert (tmp_path / "part_00000.jsonl").exists() is False

            w.write({"anchor_signature": "c"})
            # The third write triggers a flush.
            assert (tmp_path / "part_00000.jsonl").exists() is True
            assert len(_read_jsonl(tmp_path / "part_00000.jsonl")) == 3
        finally:
            w.close()

    def test_close_flushes_remaining_buffer(self, tmp_path: Path) -> None:
        w = ShardWriter(tmp_path, worker_id=1, flush_every=100)
        w.write({"anchor_signature": "only"})
        # 1 < flush_every, so nothing on disk yet.
        assert (tmp_path / "part_00001.jsonl").exists() is False

        w.close()
        # close() force-flushes.
        assert (tmp_path / "part_00001.jsonl").exists() is True
        assert _read_jsonl(tmp_path / "part_00001.jsonl") == [
            {"anchor_signature": "only"}
        ]

    def test_tmp_file_cleaned_after_successful_flush(self, tmp_path: Path) -> None:
        with ShardWriter(tmp_path, worker_id=2, flush_every=1) as w:
            w.write({"anchor_signature": "a"})
            w.flush()
        # No .tmp left around after a clean exit.
        assert list(tmp_path.glob("part_*.jsonl.tmp")) == []

    def test_reopening_loads_existing_records(self, tmp_path: Path) -> None:
        """Resume scenario: a worker re-instantiates ShardWriter over its
        existing shard. The pre-existing records must NOT be lost on the
        next flush."""
        with ShardWriter(tmp_path, worker_id=5) as w:
            _write_anchor(w, "old1")
            _write_anchor(w, "old2")

        # Reopen and append.
        with ShardWriter(tmp_path, worker_id=5) as w:
            _write_anchor(w, "new1")

        records = _read_jsonl(tmp_path / "part_00005.jsonl")
        sigs = [r["anchor_signature"] for r in records]
        assert sigs == ["old1", "old2", "new1"]

    def test_flush_appends_without_rewriting(self, tmp_path: Path) -> None:
        w = ShardWriter(tmp_path, worker_id=0, flush_every=1)
        try:
            w.write({"anchor_signature": "a"})
            with mock.patch("os.replace") as replace:
                w.write({"anchor_signature": "b"})
            replace.assert_not_called()
            assert _read_jsonl(tmp_path / "part_00000.jsonl") == [
                {"anchor_signature": "a"},
                {"anchor_signature": "b"},
            ]
        finally:
            w.close()

    def test_reopening_drops_records_of_uncommitted_anchors(self, tmp_path: Path) -> None:
        """A worker that died mid-anchor leaves partial records; the next
        writer over the same shard removes them so the re-run can't duplicate."""
        with ShardWriter(tmp_path, worker_id=0) as w:
            _write_anchor(w, "done")
            w.write({"anchor_signature": "partial", "i": 0})
            w.flush()

        with ShardWriter(tmp_path, worker_id=0) as w:
            assert len(w) == 1
        sigs = [r["anchor_signature"] for r in _read_jsonl(tmp_path / "part_00000.jsonl")]
        assert sigs == ["done"]


class TestScanCompletedAnchors:
    def test_empty_dir_returns_empty_set(self, tmp_path: Path) -> None:
        assert scan_completed_anchors(tmp_path) == set()

    def test_nonexistent_dir_returns_empty_set(self, tmp_path: Path) -> None:
        assert scan_completed_anchors(tmp_path / "nope") == set()

    def test_union_across_multiple_shards(self, tmp_path: Path) -> None:
        for wid, sigs in [(0, ["a", "b"]), (1, ["c"]), (2, ["d", "e"])]:
            with ShardWriter(tmp_path, worker_id=wid) as w:
                for s in sigs:
                    _write_anchor(w, s)

        assert scan_completed_anchors(tmp_path) == {"a", "b", "c", "d", "e"}

    def test_orphaned_tmp_files_are_ignored(self, tmp_path: Path) -> None:
        with ShardWriter(tmp_path, worker_id=0) as w:
            _write_anchor(w, "real")
        # Drop an orphan .tmp containing different data.
        (tmp_path / "part_00099.jsonl.tmp").write_text(
            json.dumps({"anchor_signature": "orphan"}) + "\n", encoding="utf-8"
        )
        assert scan_completed_anchors(tmp_path) == {"real"}

    def test_corrupt_jsonl_lines_are_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "part_00000.jsonl"
        path.write_text(
            '{"anchor_signature": "good"}\n'
            "this is not json\n"  # corrupt line
            '{"anchor_signature": "also_good"}\n',
            encoding="utf-8",
        )
        assert scan_completed_anchors(tmp_path) == {"good", "also_good"}

    def test_missing_anchor_signature_field_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "part_00000.jsonl"
        path.write_text(
            '{"anchor_signature": "kept"}\n'
            '{"some_other_key": "no_sig_field"}\n',
            encoding="utf-8",
        )
        assert scan_completed_anchors(tmp_path) == {"kept"}


    def test_uncommitted_anchor_is_not_complete(self, tmp_path: Path) -> None:
        with ShardWriter(tmp_path, worker_id=0) as w:
            _write_anchor(w, "finished")
            w.write({"anchor_signature": "timed_out"})
        assert scan_completed_anchors(tmp_path) == {"finished"}

    def test_anchor_with_zero_records_is_complete(self, tmp_path: Path) -> None:
        with ShardWriter(tmp_path, worker_id=0) as w:
            w.commit_anchor("nothing_applied")
        assert scan_completed_anchors(tmp_path) == {"nothing_applied"}

    def test_legacy_shard_without_done_file_uses_record_signatures(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "part_00000.jsonl").write_text(
            '{"anchor_signature": "old"}\n', encoding="utf-8"
        )
        assert scan_completed_anchors(tmp_path) == {"old"}


class TestIterShardRecords:
    def test_streams_all_records_in_file_order(self, tmp_path: Path) -> None:
        with ShardWriter(tmp_path, worker_id=0) as w:
            _write_anchor(w, "a", n=1)
            _write_anchor(w, "b", n=2)
        with ShardWriter(tmp_path, worker_id=1) as w:
            _write_anchor(w, "c", n=3)

        out = list(iter_shard_records(tmp_path))
        # Sorted by filename → shard 0 first, then shard 1.
        assert [r["n"] for r in out] == [1, 2, 3]

    def test_skips_records_of_uncommitted_anchors(self, tmp_path: Path) -> None:
        with ShardWriter(tmp_path, worker_id=0) as w:
            _write_anchor(w, "a", n=1)
            w.write({"anchor_signature": "partial", "n": 2})
        assert [r["n"] for r in iter_shard_records(tmp_path)] == [1]
