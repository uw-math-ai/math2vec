#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/tillicum_blueprint.slurm — perturb the leanblueprint corpus
# (../dataset/blueprints.json) once per perturbation, then score an embedding
# model on the result as an MTEB reranking task.
#
# Prerequisite: bash scripts/tillicum_setup.sh (once, on the login node; re-run
# it after pulling, to pick up new requirements and the embedding model).
#
# Usage (submit from the perturbations/ directory):
#     sbatch scripts/tillicum_blueprint.slurm
#     WIGGLE_BP_LIMIT=40 sbatch --qos=debug --gpus=1 --cpus-per-task=8 \
#         --mem=180G --time=00:30:00 scripts/tillicum_blueprint.slurm   # trial
#
# Steps:
#     1. lake build Wiggle
#     2. pipeline/prepare_blueprint_anchors.py: theorem/lemma sources → anchors
#     3. pipeline/run_benchmark_review.py --skip-noncompiling: every anchor is
#        checked against plain Mathlib (autoImplicit off); those that
#        elaborate get each of the 28 perturbations applied once
#     4. pipeline/mteb_perturbation_eval.py with $WIGGLE_EMBED_MODEL
#
# Output goes to $WIGGLE_BP_OUT (default data/blueprint-review). Step 3 writes
# each anchor as it finishes and resumes from there, so if the job hits its
# time limit just submit it again. To start over, delete that directory.
#
# Tillicum bills per GPU-hour and gives 8 CPUs per GPU, so 4 GPUs buys 32
# Lean workers at the same cost per unit of work as 1. The GPUs themselves are
# only used by step 4. Each worker keeps a Lean server with Mathlib loaded
# (several GB), hence the memory request.
#
# Knobs (env vars, all optional):
#     WIGGLE_BP_LIMIT      only the first N anchors (for trial runs)
#     WIGGLE_BP_OUT        output directory (default data/blueprint-review)
#     WIGGLE_EMBED_MODEL   see scripts/tillicum_env.sh
#     WIGGLE_PROJECT       project root, if not submitting from perturbations/
# ─────────────────────────────────────────────────────────────────────────────

#SBATCH --job-name=wiggle-blueprint
#SBATCH --account=mathai
#SBATCH --qos=normal
#SBATCH --gpus=4
#SBATCH --cpus-per-task=32
#SBATCH --mem=600G
#SBATCH --time=12:00:00
#SBATCH -o %x_%j.out

set -eo pipefail

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

CPUS="${SLURM_CPUS_PER_TASK:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
OUT="${WIGGLE_BP_OUT:-data/blueprint-review}"
ANCHORS="$OUT/blueprint_anchors.jsonl"
LIMIT_ARGS=()
[[ -n "${WIGGLE_BP_LIMIT:-}" ]] && LIMIT_ARGS=(--limit "$WIGGLE_BP_LIMIT")
mkdir -p "$OUT"

echo "──────────────────────────────────────────────────────────────────────"
echo " Wiggle blueprint perturbations on Tillicum"
echo " host    : $(hostname)"
echo " job id  : ${SLURM_JOB_ID:-<none — running outside slurm>}"
echo " project : $PROJECT_ROOT"
echo " cpus    : $CPUS"
echo " model   : $WIGGLE_EMBED_MODEL"
echo " output  : $PROJECT_ROOT/$OUT"
echo "──────────────────────────────────────────────────────────────────────"

echo; echo "══ 1/4 lake build Wiggle"
lake build Wiggle

echo; echo "══ 2/4 prepare anchors"
python -u pipeline/prepare_blueprint_anchors.py --out "$ANCHORS"

echo; echo "══ 3/4 perturb (one layer, $CPUS workers)"
python -u pipeline/run_benchmark_review.py \
    --anchors-file "$ANCHORS" "${LIMIT_ARGS[@]}" \
    --skip-noncompiling --resume \
    --num-workers "$CPUS" \
    --out "$OUT"

echo; echo "══ 4/4 MTEB eval"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader || true
HF_HUB_OFFLINE=1 python -u pipeline/mteb_perturbation_eval.py \
    --results "$OUT/results.jsonl" \
    --model "$WIGGLE_EMBED_MODEL" \
    --out "$OUT/mteb"

echo
echo "Done. Artifacts in $PROJECT_ROOT/$OUT:"
echo "    review.md, results.jsonl, anchors.jsonl, mteb/mteb_scores.json,"
echo "    mteb/similarity_by_perturbation.csv"
