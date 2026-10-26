#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/tillicum_blueprint.slurm — perturb the leanblueprint corpus
# (../dataset/blueprints.json) once per perturbation, score embedding models on
# the result as an MTEB reranking task, and draw the diagrams.
#
# Prerequisite: bash scripts/tillicum_setup.sh (once, on the login node; re-run
# it after pulling, to pick up new requirements and embedding models).
#
# Usage (submit from the perturbations/ directory):
#     sbatch scripts/tillicum_blueprint.slurm
#     WIGGLE_BP_LIMIT=40 WIGGLE_BP_OUT=data/blueprint-trial \
#         sbatch --qos=debug --gpus=1 --cpus-per-task=8 --mem=180G \
#         --time=00:30:00 scripts/tillicum_blueprint.slurm          # trial
#     WIGGLE_BP_STEPS="eval plot" sbatch --gpus=1 --cpus-per-task=8 \
#         --mem=180G --time=01:00:00 scripts/tillicum_blueprint.slurm  # redo eval
#
# Steps ($WIGGLE_BP_STEPS, default all, in this order):
#     build    lake build Wiggle
#     prepare  pipeline/prepare_blueprint_anchors.py: theorem/lemma sources → anchors
#     perturb  pipeline/run_benchmark_review.py --skip-noncompiling: every anchor
#              is checked against plain Mathlib (autoImplicit off); those that
#              elaborate get each of the 28 perturbations applied once
#     eval     pipeline/mteb_perturbation_eval.py with $WIGGLE_EMBED_MODELS
#     plot     pipeline/plot_eval.py → $WIGGLE_BP_OUT/figures/
#
# The perturb step stops starting new anchors once it has used up the job's
# time limit minus a reserve ($WIGGLE_EVAL_RESERVE_MIN), so eval and plot run on
# whatever finished. Everything is resumable: submit again to perturb the
# remaining anchors and redo eval/plot on the larger set. To start over,
# delete $WIGGLE_BP_OUT.
#
# Tillicum bills per GPU-hour and gives 8 CPUs per GPU, so 4 GPUs buys 32
# Lean workers at the same cost per unit of work as 1. The GPUs are only used
# by eval. Each worker keeps a Lean server with Mathlib loaded (several GB),
# hence the memory request.
#
# Knobs (env vars, all optional):
#     WIGGLE_BP_STEPS          subset of "build prepare perturb eval plot"
#     WIGGLE_BP_LIMIT          only the first N anchors (for trial runs)
#     WIGGLE_BP_OUT            output directory (default data/blueprint-review)
#     WIGGLE_EVAL_RESERVE_MIN  minutes kept back for eval + plot (default: a
#                              quarter of the time limit, at most 90)
#     WIGGLE_EMBED_MODELS      see scripts/tillicum_env.sh
#     WIGGLE_PROJECT           project root, if not submitting from perturbations/
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
JOB_START=$(date +%s)

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

STEPS="${WIGGLE_BP_STEPS:-build prepare perturb eval plot}"
CPUS="${SLURM_CPUS_PER_TASK:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
OUT="${WIGGLE_BP_OUT:-data/blueprint-review}"
ANCHORS="$OUT/blueprint_anchors.jsonl"
LIMIT_ARGS=()
[[ -n "${WIGGLE_BP_LIMIT:-}" ]] && LIMIT_ARGS=(--limit "$WIGGLE_BP_LIMIT")
read -r -a MODELS <<< "$WIGGLE_EMBED_MODELS"
mkdir -p "$OUT"

# Job time limit in seconds, from Slurm ("D-HH:MM:SS", "HH:MM:SS" or "MM:SS").
time_limit_seconds() {
    local t d=0 h=0 m=0 s=0
    t="$(squeue -h -j "${SLURM_JOB_ID:-0}" -o %l 2>/dev/null || true)"
    [[ -z "$t" || "$t" == UNLIMITED || "$t" == INVALID ]] && return 1
    [[ "$t" == *-* ]] && { d="${t%%-*}"; t="${t#*-}"; }
    IFS=: read -r -a parts <<< "$t"
    case ${#parts[@]} in
        3) h=${parts[0]}; m=${parts[1]}; s=${parts[2]} ;;
        2) m=${parts[0]}; s=${parts[1]} ;;
        1) m=${parts[0]} ;;
    esac
    echo $(( 10#$d * 86400 + 10#$h * 3600 + 10#$m * 60 + 10#$s ))
}
DEADLINE_ARGS=()
if LIMIT_S="$(time_limit_seconds)"; then
    RESERVE_MIN="${WIGGLE_EVAL_RESERVE_MIN:-$(( LIMIT_S / 240 < 90 ? LIMIT_S / 240 : 90 ))}"
    DEADLINE=$(( JOB_START + LIMIT_S - RESERVE_MIN * 60 ))
    DEADLINE_ARGS=(--deadline-epoch "$DEADLINE")
fi

echo "──────────────────────────────────────────────────────────────────────"
echo " Wiggle blueprint perturbations on Tillicum"
echo " host     : $(hostname)"
echo " job id   : ${SLURM_JOB_ID:-<none — running outside slurm>}"
echo " project  : $PROJECT_ROOT"
echo " cpus     : $CPUS"
echo " steps    : $STEPS"
echo " models   : ${MODELS[*]}"
echo " output   : $PROJECT_ROOT/$OUT"
[[ -n "${DEADLINE:-}" ]] && echo " perturb  : no new anchors after $(date -d "@$DEADLINE")"
echo "──────────────────────────────────────────────────────────────────────"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true
if ! python -c "import torch, sys; sys.exit(0 if torch.cuda.is_available() else 1)"; then
    echo "WARNING: torch cannot see a GPU; the eval will run on CPU and be very slow" \
         "for Qwen3-8B. Check WIGGLE_TORCH_INDEX in scripts/tillicum_env.sh." >&2
fi

has_step() { [[ " $STEPS " == *" $1 "* ]]; }

if has_step build; then
    echo; echo "══ build: lake build Wiggle"
    lake build Wiggle
fi

if has_step prepare; then
    echo; echo "══ prepare anchors"
    python -u pipeline/prepare_blueprint_anchors.py --out "$ANCHORS"
fi

if has_step perturb; then
    echo; echo "══ perturb (one layer, $CPUS workers)"
    python -u pipeline/run_benchmark_review.py \
        --anchors-file "$ANCHORS" "${LIMIT_ARGS[@]}" \
        --skip-noncompiling --resume "${DEADLINE_ARGS[@]}" \
        --num-workers "$CPUS" \
        --out "$OUT"
fi

if has_step eval; then
    echo; echo "══ MTEB eval"
    HF_HUB_OFFLINE=1 python -u pipeline/mteb_perturbation_eval.py \
        --results "$OUT/results.jsonl" \
        --models "${MODELS[@]}" \
        --out "$OUT/mteb"
fi

if has_step plot; then
    echo; echo "══ diagrams"
    python -u pipeline/plot_eval.py --run "$OUT"
fi

echo
echo "Done in $(( ($(date +%s) - JOB_START) / 60 )) min. Artifacts in $PROJECT_ROOT/$OUT:"
echo "    figures/summary.md + figures/*.png   scores table and diagrams"
echo "    mteb/<model>/                        raw MTEB scores and cosine tables"
echo "    review.md, results.jsonl             perturbations"
