#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/wiggle.sbatch — run pipeline/run_hf_corpus.py under Slurm.
#
# Designed to be generic across Slurm clusters (UW Hyak, generic compute, etc.)
# Adjust the SBATCH block and the env-setup section to fit your site. The
# SBATCH directives are no-ops when this script is invoked outside Slurm
# (e.g. `bash scripts/wiggle.sbatch` on a laptop for a smoke test).
#
# Usage:
#     sbatch scripts/wiggle.sbatch              # default knobs
#     WIGGLE_LIMIT=10000 sbatch scripts/wiggle.sbatch   # override anchor count
#     WIGGLE_LIMIT=4 bash scripts/wiggle.sbatch          # foreground dry-run
#
# Override knobs (env vars; all optional):
#     WIGGLE_LIMIT             # number of anchors (default 50000)
#     WIGGLE_WORKERS           # workers (default SLURM_CPUS_PER_TASK or nproc)
#     WIGGLE_RUN_ID            # run id (default $SLURM_JOB_ID or timestamp)
#     WIGGLE_SHARD_DIR         # shard output dir
#     WIGGLE_LOG_DIR           # log output dir
#     WIGGLE_TIME_BUDGET       # e.g. 23h, default = walltime - 10 min
#     WIGGLE_EXTRA_ARGS        # any other args appended to the python call
# ─────────────────────────────────────────────────────────────────────────────

#SBATCH --job-name=wiggle
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --cpus-per-task=32
#SBATCH --mem=64G
#SBATCH --output=logs/slurm-%j.out
#SBATCH --signal=B:USR1@300

set -euo pipefail

# ── Resolve project root regardless of cwd ───────────────────────────────────
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/.." && pwd)"
cd "$PROJECT_ROOT"

# ── Site-specific env setup — edit for your cluster ──────────────────────────
# Examples (uncomment whichever apply):
#   module load gcc/11.2.0
#   source /gscratch/<group>/envs/wiggle/bin/activate
#   export PATH="$HOME/.elan/bin:$PATH"

# ── Resolve runtime knobs ────────────────────────────────────────────────────
RUN_ID="${WIGGLE_RUN_ID:-${SLURM_JOB_ID:-$(date +%Y%m%d-%H%M%S)}}"
WORKERS="${WIGGLE_WORKERS:-${SLURM_CPUS_PER_TASK:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}}"
LIMIT="${WIGGLE_LIMIT:-50000}"
SHARD_DIR="${WIGGLE_SHARD_DIR:-data/shards/${RUN_ID}}"
LOG_DIR="${WIGGLE_LOG_DIR:-logs/${RUN_ID}}"

# Time budget: default = (walltime - 10 minutes), so the drain has a margin
# beyond the 5-minute SIGUSR1 warning.
if [[ -n "${WIGGLE_TIME_BUDGET:-}" ]]; then
    TIME_BUDGET="$WIGGLE_TIME_BUDGET"
elif [[ -n "${SLURM_JOB_END_TIME:-}" && -n "${SLURM_JOB_START_TIME:-}" ]]; then
    REMAINING=$((SLURM_JOB_END_TIME - SLURM_JOB_START_TIME - 600))
    if (( REMAINING > 60 )); then
        TIME_BUDGET="${REMAINING}s"
    else
        TIME_BUDGET=""
    fi
else
    TIME_BUDGET=""
fi

mkdir -p "$SHARD_DIR" "$LOG_DIR"

echo "──────────────────────────────────────────────────────────────────────"
echo " Wiggle Slurm job"
echo " host        : $(hostname)"
echo " project     : $PROJECT_ROOT"
echo " run id      : $RUN_ID"
echo " job id      : ${SLURM_JOB_ID:-<none — running outside slurm>}"
echo " workers     : $WORKERS"
echo " limit       : $LIMIT"
echo " shard dir   : $SHARD_DIR"
echo " log dir     : $LOG_DIR"
echo " time budget : ${TIME_BUDGET:-<unlimited>}"
echo "──────────────────────────────────────────────────────────────────────"

# ── Forward SIGUSR1 from Slurm to the Python child ───────────────────────────
PID=""
trap 'if [[ -n "$PID" ]]; then echo "Forwarding SIGUSR1 to PID $PID"; kill -USR1 "$PID" 2>/dev/null || true; fi' USR1
trap 'if [[ -n "$PID" ]]; then echo "Forwarding SIGTERM to PID $PID"; kill -TERM "$PID" 2>/dev/null || true; fi' TERM

# ── Run ──────────────────────────────────────────────────────────────────────
EXTRA_ARGS="${WIGGLE_EXTRA_ARGS:-}"
TIME_BUDGET_ARG=()
if [[ -n "$TIME_BUDGET" ]]; then
    TIME_BUDGET_ARG=(--time-budget "$TIME_BUDGET")
fi

python -u pipeline/run_hf_corpus.py \
    --limit "$LIMIT" \
    --num-workers "$WORKERS" \
    --run-id "$RUN_ID" \
    --shard-dir "$SHARD_DIR" \
    --log-dir "$LOG_DIR" \
    ${TIME_BUDGET_ARG[@]+"${TIME_BUDGET_ARG[@]}"} \
    ${EXTRA_ARGS} &
PID=$!
wait "$PID"
EXIT_CODE=$?

echo "──────────────────────────────────────────────────────────────────────"
echo " Wiggle exited with $EXIT_CODE"
echo " To resume: resubmit with WIGGLE_RUN_ID=$RUN_ID (resume is automatic)."
echo "──────────────────────────────────────────────────────────────────────"
exit "$EXIT_CODE"
