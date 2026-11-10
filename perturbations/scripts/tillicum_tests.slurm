#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/tillicum_tests.slurm — run the Wiggle test suites on Tillicum.
#
# Prerequisite: bash scripts/tillicum_setup.sh (once, on the login node).
#
# Usage (submit from the perturbations/ directory):
#     sbatch scripts/tillicum_tests.slurm
#     WIGGLE_TEST_STAGES="fast" sbatch scripts/tillicum_tests.slurm
#     WIGGLE_TEST_STAGES="build fast live typeclass demo review" \
#         sbatch --qos=normal --time=02:00:00 scripts/tillicum_tests.slurm
#
# Or interactively on a compute node:
#     salloc --qos=interactive --gpus=1 --cpus-per-task=8 --time=01:00:00
#     bash scripts/tillicum_tests.slurm
#
# Stages (run in this order; a failing stage doesn't stop later ones):
#     build      lake build Wiggle
#     fast       pytest, Lean mocked (~seconds)
#     live       pytest against a real `lake env lean --server`
#     typeclass  tests/test_typeclass_mutate.py smoke script (real Lean)
#     demo       pipeline/run_demo.py --singles-only: every perturbation on
#                the 10 curated theorems
#     review     run_benchmark_review.py + verify_variants.py on
#                $WIGGLE_REVIEW_LIMIT benchmark anchors (not in the default set)
#
# Knobs (env vars, all optional):
#     WIGGLE_TEST_STAGES   default "build fast live typeclass demo"
#     WIGGLE_REVIEW_LIMIT  anchors for the review stage (default 5)
#     WIGGLE_PYTEST_ARGS   extra args for both pytest stages, e.g. "-x -k shards"
#     WIGGLE_PROJECT       project root, if not submitting from perturbations/
#     TILLICUM_BASE, ELAN_HOME, WIGGLE_ENV   see scripts/tillicum_env.sh
#
# Tillicum has no CPU-only jobs: the minimum is 1 GPU, which comes with 8 CPUs.
# Lean never touches the GPU; the 8 CPUs are what the Lean workers use. The
# debug QOS (30 min, 1 GPU) fits the default stages; use --qos=normal for
# `review` or larger runs. Billing is per GPU-hour.
# ─────────────────────────────────────────────────────────────────────────────

#SBATCH --job-name=wiggle-tests
#SBATCH --account=mathai
#SBATCH --qos=debug
#SBATCH --gpus=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=00:30:00
#SBATCH -o %x_%j.out

set -o pipefail

# Under sbatch, BASH_SOURCE points at Slurm's spooled copy of this script, so
# locate the project from the submit directory instead.
find_project_root() {
    local d
    for d in "${WIGGLE_PROJECT:-}" \
             "${SLURM_SUBMIT_DIR:-}" \
             "${SLURM_SUBMIT_DIR:-}/perturbations" \
             "${SLURM_SUBMIT_DIR:-}/.." \
             "$(dirname "${BASH_SOURCE[0]}")/.."; do
        if [[ -n "$d" && -f "$d/Wiggle.lean" ]]; then
            (cd "$d" && pwd)
            return 0
        fi
    done
    return 1
}

if ! PROJECT_ROOT="$(find_project_root)"; then
    echo "error: cannot find Wiggle.lean; submit from perturbations/ or set WIGGLE_PROJECT" >&2
    exit 2
fi
cd "$PROJECT_ROOT"

# shellcheck source=tillicum_env.sh
source scripts/tillicum_env.sh
if ! wiggle_activate; then
    echo "error: could not activate $WIGGLE_ENV; run scripts/tillicum_setup.sh first" >&2
    exit 2
fi
if ! command -v lake >/dev/null 2>&1; then
    echo "error: lake not on PATH (ELAN_HOME=$ELAN_HOME); run scripts/tillicum_setup.sh first" >&2
    exit 2
fi

STAGES="${WIGGLE_TEST_STAGES:-build fast live typeclass demo}"
CPUS="${SLURM_CPUS_PER_TASK:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
RUN_ID="${SLURM_JOB_ID:-$(date +%Y%m%d-%H%M%S)}"
OUT_DIR="logs/tillicum-tests/$RUN_ID"
mkdir -p "$OUT_DIR"
read -r -a PYTEST_ARGS <<< "${WIGGLE_PYTEST_ARGS:-}"

echo "──────────────────────────────────────────────────────────────────────"
echo " Wiggle tests on Tillicum"
echo " host    : $(hostname)"
echo " job id  : ${SLURM_JOB_ID:-<none — running outside slurm>}"
echo " project : $PROJECT_ROOT"
echo " python  : $(command -v python) ($(python --version 2>&1))"
echo " lean    : $(lake env lean --version 2>/dev/null || echo '<unavailable>')"
echo " cpus    : $CPUS"
echo " stages  : $STAGES"
echo " output  : $PROJECT_ROOT/$OUT_DIR"
echo "──────────────────────────────────────────────────────────────────────"

stage_build() {
    lake build Wiggle
}

stage_fast() {
    python -m pytest tests/ --ignore=tests/test_typeclass_mutate.py -q \
        --junitxml="$OUT_DIR/junit-fast.xml" "${PYTEST_ARGS[@]}"
}

stage_live() {
    WIGGLE_RUN_LEAN_INTEGRATION=1 python -m pytest \
        tests/test_lean_server.py::TestRealLeanServer -v \
        --junitxml="$OUT_DIR/junit-live.xml" "${PYTEST_ARGS[@]}"
}

stage_typeclass() {
    python -u tests/test_typeclass_mutate.py
}

stage_demo() {
    python -u pipeline/run_demo.py --singles-only --quiet \
        --output "$OUT_DIR/demo_perturbations.jsonl"
}

stage_review() {
    python -u pipeline/run_benchmark_review.py \
        --limit "${WIGGLE_REVIEW_LIMIT:-5}" \
        --num-workers "$CPUS" \
        --out "$OUT_DIR/benchmark-review" &&
    python -u pipeline/verify_variants.py \
        --run "$OUT_DIR/benchmark-review" \
        --num-workers "$CPUS"
}

SUMMARY=()
FAILED=0
for stage in $STAGES; do
    if ! declare -F "stage_$stage" >/dev/null; then
        echo "error: unknown stage '$stage'" >&2
        SUMMARY+=("$(printf '%-10s %-5s' "$stage" UNKNOWN)")
        FAILED=$((FAILED + 1))
        continue
    fi
    echo
    echo "══ stage: $stage ══════════════════════════════════════════════════════"
    start=$SECONDS
    if "stage_$stage"; then
        status=PASS
    else
        status=FAIL
        FAILED=$((FAILED + 1))
    fi
    SUMMARY+=("$(printf '%-10s %-5s %5ss' "$stage" "$status" "$((SECONDS - start))")")
done

echo
echo "──────────────────────────────────────────────────────────────────────"
echo " Summary (job ${SLURM_JOB_ID:-local})"
printf '   %s\n' "${SUMMARY[@]}"
echo " Artifacts: $PROJECT_ROOT/$OUT_DIR"
echo "──────────────────────────────────────────────────────────────────────"

if (( FAILED > 0 )); then
    exit 1
fi
exit 0
