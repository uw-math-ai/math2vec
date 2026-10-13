"""
Tests for ``wiggle.parallel`` — duration parsing, resume, drain, time budget,
and end-to-end shard splitting.

The end-to-end tests use ``mp_context="fork"`` so a parent-side monkey-patch
of ``wiggle.pipeline.run_pipeline`` propagates into the worker subprocesses
via copy-on-write. Marked skip on Windows (no fork).
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Iterator

import pytest

from wiggle.parallel import parse_duration, run_parallel
from wiggle.shards import scan_completed_anchors


# ─── parse_duration ─────────────────────────────────────────────────────────────


class TestParseDuration:
    def test_none_returns_none(self) -> None:
        assert parse_duration(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert parse_duration("") is None
        assert parse_duration("   ") is None

    def test_seconds_suffix(self) -> None:
        assert parse_duration("300s") == 300.0
        assert parse_duration("1.5s") == 1.5

    def test_minutes_suffix(self) -> None:
        assert parse_duration("5m") == 300.0
        assert parse_duration("0.5m") == 30.0

    def test_hours_suffix(self) -> None:
        assert parse_duration("2h") == 7200.0
        assert parse_duration("23h") == 23 * 3600.0

    def test_bare_number_is_seconds(self) -> None:
        assert parse_duration("60") == 60.0
        assert parse_duration(60) == 60.0
        assert parse_duration(60.5) == 60.5

    def test_case_insensitive(self) -> None:
        assert parse_duration("2H") == 7200.0
        assert parse_duration("5M") == 300.0


# ─── End-to-end via fork ────────────────────────────────────────────────────────

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")

requires_fork = pytest.mark.skipif(
    sys.platform == "win32" or os.name == "nt",
    reason="fork-based tests are POSIX-only",
)


def _fake_run_pipeline(
    anchors: Iterable[dict[str, Any]], **_kwargs: Any
) -> Iterator[dict[str, Any]]:
    """Drop-in for ``wiggle.pipeline.run_pipeline`` that doesn't touch Lean.

    Emits exactly one record per anchor with a stable shape that
    ``scan_completed_anchors`` can pick up via the ``anchor_signature`` key.
    """
    for a in anchors:
        sig = a.get("signature") or a.get("id", "")
        yield {
            "anchor_signature": sig,
            "anchor_type": a.get("type", ""),
            "variant_signature": f"{sig}_v",
            "variant_type": a.get("type", "") + "'",
            "perturbations_applied": ["fake"],
            "chain_depth": 1,
            "is_true": "unknown",
            "perturbation_description": "fake",
            "timestamp": "2024-01-01T00:00:00",
        }


@requires_fork
class TestRunParallel:
    def test_processes_all_anchors_split_across_workers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("wiggle.pipeline.run_pipeline", _fake_run_pipeline)

        anchors = [{"signature": f"anchor_{i}", "type": f"T{i}"} for i in range(8)]
        stats = run_parallel(
            anchors,
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=2,
            mp_context="fork",
            install_signal_handler=False,
            flush_every=1,
        )

        assert stats["anchors_total"] == 8
        assert stats["anchors_done"] == 8
        assert stats["anchors_failed"] == 0
        assert stats["records_written"] == 8

        shard_files = sorted((tmp_path / "shards").glob("part_*.jsonl"))
        # Two workers → up to two shards (sometimes one worker gets all the work
        # if the other lost the race; we assert <= num_workers, > 0).
        assert 1 <= len(shard_files) <= 2

        # Every anchor signature ended up *somewhere*.
        assert scan_completed_anchors(tmp_path / "shards") == {
            f"anchor_{i}" for i in range(8)
        }

    def test_resume_skips_previously_completed_anchors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("wiggle.pipeline.run_pipeline", _fake_run_pipeline)

        # First pass: process the first 4 anchors only.
        first_anchors = [
            {"signature": f"anchor_{i}", "type": f"T{i}"} for i in range(4)
        ]
        stats1 = run_parallel(
            first_anchors,
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=2,
            mp_context="fork",
            install_signal_handler=False,
            flush_every=1,
        )
        assert stats1["anchors_done"] == 4

        # Second pass: full 8 anchors. Resume should skip the first 4.
        full_anchors = [
            {"signature": f"anchor_{i}", "type": f"T{i}"} for i in range(8)
        ]
        stats2 = run_parallel(
            full_anchors,
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=2,
            mp_context="fork",
            install_signal_handler=False,
            flush_every=1,
        )
        assert stats2["anchors_total"] == 8
        assert stats2["anchors_skipped_resume"] == 4
        assert stats2["anchors_done"] == 4  # only the new 4

        # And the shard set covers every anchor end-to-end.
        assert scan_completed_anchors(tmp_path / "shards") == {
            f"anchor_{i}" for i in range(8)
        }

    def test_no_resume_flag_reprocesses_everything(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("wiggle.pipeline.run_pipeline", _fake_run_pipeline)

        anchors = [{"signature": f"anchor_{i}", "type": f"T{i}"} for i in range(3)]

        run_parallel(
            anchors,
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=1,
            mp_context="fork",
            install_signal_handler=False,
            flush_every=1,
        )
        stats2 = run_parallel(
            anchors,
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=1,
            mp_context="fork",
            install_signal_handler=False,
            resume=False,  # <-- the flag under test
            flush_every=1,
        )
        assert stats2["anchors_skipped_resume"] == 0
        assert stats2["anchors_done"] == 3

    def test_pre_set_drain_event_skips_all_submission(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("wiggle.pipeline.run_pipeline", _fake_run_pipeline)

        anchors = [{"signature": f"anchor_{i}", "type": f"T{i}"} for i in range(10)]
        drain = threading.Event()
        drain.set()  # drain BEFORE we start

        stats = run_parallel(
            anchors,
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=2,
            mp_context="fork",
            install_signal_handler=False,
            drain_event=drain,
            flush_every=1,
        )

        assert stats["drain_triggered"] is True
        # Initial seeding may submit ``num_workers`` anchors before the drain
        # check kicks in; we allow up to that many to complete.
        assert stats["anchors_done"] <= 2

    def test_zero_time_budget_short_circuits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # We have to let *some* time pass for the budget check to fire, since
        # it's evaluated after the initial seed. Use a tiny but non-zero budget
        # and a slow-ish fake.
        def slow_fake(anchors: Iterable[dict[str, Any]], **_kw: Any) -> Iterator[dict[str, Any]]:
            for a in anchors:
                time.sleep(0.05)
                yield from _fake_run_pipeline([a])

        monkeypatch.setattr("wiggle.pipeline.run_pipeline", slow_fake)

        anchors = [{"signature": f"anchor_{i}", "type": f"T{i}"} for i in range(20)]
        stats = run_parallel(
            anchors,
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=1,
            mp_context="fork",
            install_signal_handler=False,
            time_budget_seconds=0.01,
            flush_every=1,
        )

        assert stats["time_budget_exhausted"] is True
        # Some anchors processed before time ran out, but not all 20.
        assert stats["anchors_done"] < 20

    def test_empty_anchor_list_returns_immediately(self, tmp_path: Path) -> None:
        stats = run_parallel(
            [],
            shard_dir=tmp_path / "shards",
            log_dir=tmp_path / "logs",
            num_workers=4,
            mp_context="fork",
            install_signal_handler=False,
        )
        assert stats["anchors_total"] == 0
        assert stats["anchors_done"] == 0
        assert stats["records_written"] == 0


# ─── Heartbeat (parent-only, no subprocess) ─────────────────────────────────────


class TestHeartbeat:
    def test_heartbeat_writes_snapshot_and_history(self, tmp_path: Path) -> None:
        from wiggle.run_logging import Heartbeat

        hb = Heartbeat(tmp_path, interval_seconds=0.05)
        hb.update(anchors_done=3, records_written=7)
        hb.tick()
        hb.update(anchors_done=5, records_written=11)
        hb.tick()

        snap_path = tmp_path / "heartbeat.jsonl"
        hist_path = tmp_path / "heartbeat.history.jsonl"
        assert snap_path.exists()
        assert hist_path.exists()

        # Snapshot holds only the latest tick.
        import json
        latest = json.loads(snap_path.read_text().strip().splitlines()[-1])
        assert latest["anchors_done"] == 5
        assert latest["records_written"] == 11
        assert "elapsed_seconds" in latest
        assert "anchors_per_minute" in latest

        # History has both ticks (start/stop ticks may add more if start/stop
        # is used, but here we only called tick() twice).
        lines = hist_path.read_text().strip().splitlines()
        assert len(lines) >= 2
