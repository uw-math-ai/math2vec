"""
Parallel orchestrator over anchors.

One ``ProcessPoolExecutor`` worker per CPU core. Each worker is a separate
Python subprocess that lazily spawns its own ``LeanLspServer`` (paying the
Mathlib import cost once per worker, not per anchor) and writes records to
its own JSONL shard via :class:`wiggle.shards.ShardWriter`.

The orchestrator (the parent process) is responsible for:

  * Resume — scan existing shards, drop anchors whose signatures already
    appear so a job restarted after walltime picks up where it left off.
  * Walltime budget — stop submitting new tasks once a wallclock budget is
    exceeded.
  * Drain on ``SIGUSR1`` — Slurm's ``--signal=B:USR1@300`` arrives five
    minutes before the walltime kill; we stop submitting new tasks, let
    in-flight workers finish their current anchor, and shut down cleanly.
  * Heartbeat — write ``logs/<run-id>/heartbeat.jsonl`` every 30s so a
    ``tail -F`` reveals progress without ssh-ing into the compute node.

Workers do *not* handle ``SIGUSR1``; the parent owns the drain signal.
"""

from __future__ import annotations

import multiprocessing as mp
import os
import signal
import threading
import time
from concurrent.futures import (
    FIRST_COMPLETED,
    Future,
    ProcessPoolExecutor,
    wait,
)
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "run_parallel",
    "parse_duration",
]


# ── Worker-local state (set once by _worker_init) ─────────────────────────────
# Each subprocess has its own copy of these globals; the parent never touches
# them. Globals are the cleanest way to plumb state through
# ProcessPoolExecutor's stateless task model.

_WORKER_ID: int | None = None
_SHARD: Any | None = None  # ShardWriter
_LOGGER: Any | None = None  # WorkerLogger


def _worker_init(
    worker_id_queue: "mp.Queue[int]",
    shard_dir: str,
    log_dir: str,
    flush_every: int,
) -> None:
    """One-time setup per worker subprocess.

    Pulls a stable worker_id from the queue (each integer goes to exactly one
    worker), opens that worker's shard + log files, and resets SIGUSR1 so the
    drain signal is handled by the parent only.
    """
    global _WORKER_ID, _SHARD, _LOGGER

    # Lazy imports so the worker doesn't pay the full wiggle import cost
    # before it's been told who it is.
    from wiggle.run_logging import WorkerLogger
    from wiggle.shards import ShardWriter

    _WORKER_ID = worker_id_queue.get()
    _SHARD = ShardWriter(shard_dir, _WORKER_ID, flush_every=flush_every)
    _LOGGER = WorkerLogger(log_dir, _WORKER_ID)
    _LOGGER.event("worker_init", pid=os.getpid())

    # SIGUSR1 belongs to the parent. Resetting to SIG_DFL means the worker
    # would terminate on receipt — but we never send it to workers, so it's
    # effectively a no-op safety net.
    try:
        signal.signal(signal.SIGUSR1, signal.SIG_DFL)
    except (ValueError, AttributeError, OSError):
        # SIGUSR1 doesn't exist on Windows; not our use case but harmless.
        pass


def _process_anchor(
    anchor: dict[str, Any],
    *,
    n_permutations: int,
    max_chain_depth: int | None,
    random_seed: int,
    verify_compile: bool,
) -> dict[str, Any]:
    """Run every sampled permutation against one anchor; persist records.

    The inner loop is exactly :func:`wiggle.pipeline.run_pipeline` over a
    single-element iterable, so the parallel path emits records that are
    byte-for-byte identical to the single-process path.
    """
    assert _SHARD is not None and _LOGGER is not None

    from wiggle.pipeline import run_pipeline

    anchor_sig = anchor.get("signature") or anchor.get("id", "")
    t0 = time.monotonic()
    _LOGGER.event("anchor_start", anchor_id=anchor_sig)
    try:
        n_records = 0
        for record in run_pipeline(
            [anchor],
            n_permutations=n_permutations,
            max_chain_depth=max_chain_depth,
            random_seed=random_seed,
            verify_compile=verify_compile,
            verbose=False,
        ):
            _SHARD.write(record)
            n_records += 1
        # Per-anchor flush — guarantees we never lose more than the work for
        # the *currently in-flight* anchor on a hard kill.
        _SHARD.flush()
        _LOGGER.event(
            "anchor_done",
            anchor_id=anchor_sig,
            records=n_records,
            elapsed_s=round(time.monotonic() - t0, 3),
        )
        return {"status": "ok", "anchor_sig": anchor_sig, "records": n_records}
    except Exception as exc:  # noqa: BLE001 — log and keep going
        _LOGGER.event(
            "anchor_error",
            anchor_id=anchor_sig,
            error=type(exc).__name__ + ": " + str(exc),
        )
        return {
            "status": "error",
            "anchor_sig": anchor_sig,
            "error": f"{type(exc).__name__}: {exc}",
        }


# ── Duration parsing ──────────────────────────────────────────────────────────


def parse_duration(s: str | float | int | None) -> float | None:
    """Parse ``"23h"`` / ``"90m"`` / ``"300s"`` / ``"3600"`` into seconds.

    Returns ``None`` when input is ``None`` (meaning "no budget").
    """
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip().lower()
    if not s:
        return None
    if s.endswith("h"):
        return float(s[:-1]) * 3600.0
    if s.endswith("m"):
        return float(s[:-1]) * 60.0
    if s.endswith("s"):
        return float(s[:-1])
    return float(s)


# ── Public entry point ────────────────────────────────────────────────────────


def run_parallel(
    anchors: Iterable[dict[str, Any]],
    *,
    shard_dir: Path | str,
    log_dir: Path | str,
    num_workers: int | None = None,
    time_budget_seconds: float | None = None,
    n_permutations: int = 6,
    max_chain_depth: int | None = 4,
    random_seed: int = 42,
    verify_compile: bool = True,
    resume: bool = True,
    flush_every: int = 50,
    drain_event: threading.Event | None = None,
    mp_context: str = "spawn",
    install_signal_handler: bool = True,
) -> dict[str, Any]:
    """Run perturbations across ``anchors`` using a process pool.

    Args:
        anchors: dicts shaped like the HuggingFace dataset rows (must have
            ``signature`` or ``id``, and ``type``).
        shard_dir: directory for ``part_<N>.jsonl`` output files.
        log_dir: directory for ``worker-<N>.log.jsonl`` + ``heartbeat.jsonl``.
        num_workers: subprocess count. Defaults to ``os.cpu_count()`` capped
            by the number of pending anchors.
        time_budget_seconds: stop submitting after this wallclock; in-flight
            tasks are still awaited. ``None`` means unlimited.
        n_permutations / max_chain_depth / random_seed / verify_compile:
            forwarded into ``wiggle.pipeline.run_pipeline``.
        resume: if true (default), anchors whose signature already appears in
            any shard are skipped.
        flush_every: records per shard between atomic rewrites.
        drain_event: when set, the orchestrator stops submitting and drains.
            Used by tests; production wires ``SIGUSR1`` to this event.
        mp_context: ``"spawn"`` (default; cleanest on macOS) or ``"fork"``
            (faster startup on Linux but unsafe with threaded libraries).
        install_signal_handler: if true (default), install a SIGUSR1 handler
            that sets the drain event. Tests pass false to drive the event
            directly.

    Returns:
        A stats dict with keys ``anchors_total``, ``anchors_skipped_resume``,
        ``anchors_done``, ``anchors_failed``, ``records_written``,
        ``drain_triggered``, ``time_budget_exhausted``, ``elapsed_seconds``.
    """
    from wiggle.run_logging import Heartbeat
    from wiggle.shards import scan_completed_anchors

    anchors_list = list(anchors)
    shard_dir = Path(shard_dir)
    log_dir = Path(log_dir)
    shard_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # ── Resume: drop anchors that already have output ─────────────────────
    already_done: set[str] = scan_completed_anchors(shard_dir) if resume else set()
    pending = [
        a for a in anchors_list
        if _anchor_key(a) not in already_done
    ]

    if num_workers is None:
        num_workers = max(1, os.cpu_count() or 1)
    num_workers = max(1, min(num_workers, len(pending) or 1))

    # ── Drain wiring ──────────────────────────────────────────────────────
    drain = drain_event if drain_event is not None else threading.Event()
    previous_handler = None
    if install_signal_handler and drain_event is None:
        def _drain_on_signal(_signum: int, _frame: Any) -> None:
            drain.set()
        try:
            previous_handler = signal.signal(signal.SIGUSR1, _drain_on_signal)
        except (ValueError, AttributeError, OSError):
            previous_handler = None

    # ── Heartbeat ─────────────────────────────────────────────────────────
    hb = Heartbeat(log_dir)
    hb.update(
        anchors_total=len(anchors_list),
        anchors_skipped_resume=len(anchors_list) - len(pending),
        anchors_done=0,
        anchors_failed=0,
        records_written=0,
        workers_alive=num_workers,
    )
    hb.start()

    stats: dict[str, Any] = {
        "anchors_total": len(anchors_list),
        "anchors_skipped_resume": len(anchors_list) - len(pending),
        "anchors_done": 0,
        "anchors_failed": 0,
        "records_written": 0,
        "drain_triggered": False,
        "time_budget_exhausted": False,
        "elapsed_seconds": 0.0,
        "shard_dir": str(shard_dir),
        "log_dir": str(log_dir),
        "num_workers": num_workers,
    }

    if not pending:
        hb.stop()
        if install_signal_handler and previous_handler is not None:
            try:
                signal.signal(signal.SIGUSR1, previous_handler)
            except (ValueError, AttributeError, OSError):
                pass
        return stats

    # ── Worker ID queue ──────────────────────────────────────────────────-
    ctx = mp.get_context(mp_context)
    worker_id_queue: mp.Queue = ctx.Queue()
    for wid in range(num_workers):
        worker_id_queue.put(wid)

    t_start = time.monotonic()

    try:
        with ProcessPoolExecutor(
            max_workers=num_workers,
            mp_context=ctx,
            initializer=_worker_init,
            initargs=(worker_id_queue, str(shard_dir), str(log_dir), flush_every),
        ) as pool:
            anchor_iter = iter(pending)
            in_flight: dict[Future, dict[str, Any]] = {}

            def _maybe_submit_more() -> None:
                while len(in_flight) < num_workers and not _should_stop():
                    try:
                        a = next(anchor_iter)
                    except StopIteration:
                        return
                    fut = pool.submit(
                        _process_anchor,
                        a,
                        n_permutations=n_permutations,
                        max_chain_depth=max_chain_depth,
                        random_seed=random_seed,
                        verify_compile=verify_compile,
                    )
                    in_flight[fut] = a

            def _should_stop() -> bool:
                if drain.is_set():
                    stats["drain_triggered"] = True
                    return True
                if time_budget_seconds is not None:
                    if time.monotonic() - t_start > time_budget_seconds:
                        stats["time_budget_exhausted"] = True
                        return True
                return False

            _maybe_submit_more()

            while in_flight:
                done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
                for fut in done:
                    in_flight.pop(fut, None)
                    try:
                        result = fut.result()
                    except Exception:  # noqa: BLE001 — worker re-raises here
                        stats["anchors_failed"] += 1
                        hb.update(anchors_failed=stats["anchors_failed"])
                        continue
                    if result["status"] == "ok":
                        stats["anchors_done"] += 1
                        stats["records_written"] += int(result.get("records", 0))
                    else:
                        stats["anchors_failed"] += 1
                    hb.update(
                        anchors_done=stats["anchors_done"],
                        anchors_failed=stats["anchors_failed"],
                        records_written=stats["records_written"],
                        drain_requested=drain.is_set(),
                        elapsed_seconds=round(time.monotonic() - t_start, 3),
                    )
                _maybe_submit_more()
    finally:
        stats["elapsed_seconds"] = round(time.monotonic() - t_start, 3)
        hb.update(**stats)
        hb.stop()
        if install_signal_handler and previous_handler is not None:
            try:
                signal.signal(signal.SIGUSR1, previous_handler)
            except (ValueError, AttributeError, OSError):
                pass

    return stats


def _anchor_key(anchor: dict[str, Any]) -> str:
    """Match the key ``run_pipeline`` writes into ``anchor_signature``."""
    return str(anchor.get("signature") or anchor.get("id", ""))
