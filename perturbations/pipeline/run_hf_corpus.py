#!/usr/bin/env python3
"""
run_hf_corpus.py — apply perturbation chains to a slice of a HuggingFace dataset.

Replaces the archived ``hackathon-demo/perturb.ipynb`` notebook with a plain
Python CLI that:

    1. pulls anchors from a HuggingFace dataset (``FrenzyMath/mathlib_informal_v4.19.0``
       by default),
    2. samples N random permutations of the registered perturbations per anchor,
    3. walks each permutation, emitting one record per successful intermediate,
    4. writes the result as sharded JSONL — one shard per worker process.

Designed to run for hours on a Slurm compute node. Key cluster-friendly
features:

  * ``--num-workers N`` parallelises across CPU cores via
    ``ProcessPoolExecutor``; each worker owns its own persistent Lean LSP
    server. With Mathlib warm, throughput is roughly ``N * 2`` anchors/sec.

  * Output is sharded: shard ``part_<worker_id>.jsonl`` is owned exclusively
    by one worker. On resubmit, the orchestrator scans existing shards and
    skips anchors already present (``--no-resume`` to opt out).

  * ``--time-budget`` accepts ``"23h"``/``"90m"``/``"3600s"`` etc. The
    orchestrator stops submitting once exceeded; in-flight workers finish
    their current anchor cleanly.

  * SIGUSR1 triggers a clean drain. Slurm's ``--signal=B:USR1@300`` sends
    this 5 minutes before walltime; combined with ``scripts/wiggle.sbatch``
    you get a graceful shutdown instead of a forced kill.

Usage:
    # Local smoke test (4 anchors, 2 workers):
    python pipeline/run_hf_corpus.py --limit 4 --num-workers 2

    # A real cluster job (Slurm sets SLURM_CPUS_PER_TASK):
    python pipeline/run_hf_corpus.py --limit 50000 \\
        --num-workers $SLURM_CPUS_PER_TASK \\
        --shard-dir data/shards/$SLURM_JOB_ID \\
        --time-budget 23h

    # Pull specific HF indices (handy for reproducing a bug):
    python pipeline/run_hf_corpus.py --indices 5145,181597,196429
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "Wiggle.lean").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ── Backend selection: must run BEFORE importing wiggle ──────────────────────-
def _early_set_backend() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--backend", choices=("server", "subprocess"))
    known, _ = parser.parse_known_args()
    if known.backend is not None:
        os.environ["WIGGLE_LEAN_BACKEND"] = known.backend


_early_set_backend()

from wiggle.parallel import parse_duration, run_parallel  # noqa: E402
from wiggle.shards import iter_shard_records  # noqa: E402


DEFAULT_DATASET = "hf://datasets/FrenzyMath/mathlib_informal_v4.19.0/data.jsonl"


def _parse_indices(s: str) -> list[int]:
    return [int(x) for x in s.split(",") if x.strip()]


def _default_run_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def _concat_shards(shard_dir: Path, output: Path) -> int:
    """Stream every record across every shard into a single JSONL file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with output.open("w", encoding="utf-8") as out:
        for record in iter_shard_records(shard_dir):
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1
    return n


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])

    # ── Input source ─────────────────────────────────────────────────────-
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=f"HF dataset URI (default: {DEFAULT_DATASET})",
    )
    src_grp = parser.add_mutually_exclusive_group()
    src_grp.add_argument(
        "--indices",
        type=_parse_indices,
        help="Comma-separated row indices to pull from the dataset.",
    )
    src_grp.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Take the first N rows of the dataset.",
    )

    # ── Output / run identity ────────────────────────────────────────────-
    parser.add_argument(
        "--run-id",
        default=os.environ.get("WIGGLE_RUN_ID") or _default_run_id(),
        help="Run identifier; defaults to a YYYYMMDD-HHMMSS timestamp.",
    )
    parser.add_argument(
        "--shard-dir",
        type=Path,
        default=None,
        help=(
            "Directory for sharded JSONL output. Defaults to "
            "data/shards/<run-id>/. Workers write to part_<NNNNN>.jsonl here."
        ),
    )
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=None,
        help=(
            "Directory for per-worker JSONL logs + heartbeat.jsonl. "
            "Defaults to logs/<run-id>/."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Optional: after the run finishes, concatenate all shards into "
            "this single JSONL file. Leave unset to keep sharded output only."
        ),
    )

    # ── Parallelism / budget ─────────────────────────────────────────────-
    parser.add_argument(
        "--num-workers",
        type=int,
        default=int(os.environ.get("SLURM_CPUS_PER_TASK") or (os.cpu_count() or 1)),
        help=(
            "Worker subprocesses (default: SLURM_CPUS_PER_TASK or "
            "os.cpu_count()). Each worker owns one Lean LSP server."
        ),
    )
    parser.add_argument(
        "--time-budget",
        default=None,
        help=(
            "Wallclock budget; accepts 23h/90m/3600s. Workers in flight when "
            "the budget is exceeded still finish their current anchor."
        ),
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help=(
            "Re-process every anchor even if its signature already appears "
            "in the shard dir. Resume is on by default."
        ),
    )

    # ── Perturbation knobs ───────────────────────────────────────────────-
    parser.add_argument(
        "--n-permutations",
        type=int,
        default=6,
        help="Random orderings per anchor (default 6).",
    )
    parser.add_argument(
        "--max-chain-depth",
        type=int,
        default=4,
        help="Max chain length (default 4).",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=42,
        help="Seed for the permutation sampler (default 42).",
    )
    parser.add_argument(
        "--no-verify-compile",
        action="store_true",
        help="Skip the per-variant Lean compile check (faster but unsafe).",
    )

    # ── Backend selection ────────────────────────────────────────────────-
    parser.add_argument(
        "--backend",
        choices=("server", "subprocess"),
        default=os.environ.get("WIGGLE_LEAN_BACKEND", "server"),
        help=(
            "Lean execution backend. 'server' (default) reuses one persistent "
            "lake env lean --server process; 'subprocess' spawns a fresh lean "
            "per call (slower, kept for debugging)."
        ),
    )

    args = parser.parse_args(argv)
    os.environ["WIGGLE_LEAN_BACKEND"] = args.backend

    if args.shard_dir is None:
        args.shard_dir = PROJECT_ROOT / "data" / "shards" / args.run_id
    if args.log_dir is None:
        args.log_dir = PROJECT_ROOT / "logs" / args.run_id

    # Lazy import — keeps `--help` snappy.
    try:
        import pandas as pd
    except ImportError:
        print(
            "error: pandas is required. Install with `pip install pandas`.",
            file=sys.stderr,
        )
        return 1

    print(f"Project root  : {PROJECT_ROOT}")
    print(f"Run ID        : {args.run_id}")
    print(f"Dataset       : {args.dataset}")
    print(f"Shard dir     : {args.shard_dir}")
    print(f"Log dir       : {args.log_dir}")
    if args.output is not None:
        print(f"Concat output : {args.output}")
    print(f"Backend       : {args.backend}")
    print(f"Workers       : {args.num_workers}")
    print(f"Permutations  : {args.n_permutations}    Max chain depth: {args.max_chain_depth}")
    print(f"Verify compile: {not args.no_verify_compile}")
    if args.time_budget:
        print(f"Time budget   : {args.time_budget}")
    print(f"Resume        : {'off' if args.no_resume else 'on'}")
    print()

    # ── Pull anchors ─────────────────────────────────────────────────────-
    print("Loading dataset... ", end="", flush=True)
    df = pd.read_json(args.dataset, lines=True)
    print(f"{len(df):,} rows")

    if args.indices:
        df = df.iloc[args.indices]
    elif args.limit is not None:
        df = df.iloc[: args.limit]

    if "signature" not in df.columns or "type" not in df.columns:
        print(
            "error: dataset must have 'signature' and 'type' columns; got "
            + ", ".join(df.columns),
            file=sys.stderr,
        )
        return 1

    df = df[["signature", "type"]].reset_index(drop=True)
    anchors = df.to_dict(orient="records")
    print(f"Running on {len(anchors)} anchors")
    print()

    # ── Run the parallel pipeline ─────────────────────────────────────────
    args.shard_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.monotonic()
    stats = run_parallel(
        anchors,
        shard_dir=args.shard_dir,
        log_dir=args.log_dir,
        num_workers=args.num_workers,
        time_budget_seconds=parse_duration(args.time_budget),
        n_permutations=args.n_permutations,
        max_chain_depth=args.max_chain_depth,
        random_seed=args.random_seed,
        verify_compile=not args.no_verify_compile,
        resume=not args.no_resume,
    )
    elapsed = time.monotonic() - t0

    print()
    print("═" * 70)
    print("Run complete")
    print("─" * 70)
    print(f"  anchors_total          : {stats['anchors_total']}")
    print(f"  anchors_skipped_resume : {stats['anchors_skipped_resume']}")
    print(f"  anchors_done           : {stats['anchors_done']}")
    print(f"  anchors_failed         : {stats['anchors_failed']}")
    print(f"  records_written        : {stats['records_written']}")
    print(f"  drain_triggered        : {stats['drain_triggered']}")
    print(f"  time_budget_exhausted  : {stats['time_budget_exhausted']}")
    print(f"  elapsed                : {elapsed:.1f}s")
    print(f"  shards                 : {args.shard_dir}/part_*.jsonl")
    print(f"  logs                   : {args.log_dir}/")

    if args.output is not None:
        n = _concat_shards(args.shard_dir, args.output)
        print(f"  concatenated           : {n} records -> {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
