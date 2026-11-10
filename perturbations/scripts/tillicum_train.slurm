#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/tillicum_train.slurm — fine-tune the embedding model on certified
# perturbations, then score the base and fine-tuned models on held-out projects.
#
# Prerequisites, from perturbations/ on the login node:
#     bash scripts/tillicum_setup.sh            # env, models, retention dataset
#     sbatch scripts/tillicum_blueprint.slurm   # produces certified.jsonl
#
# Usage (submit from the perturbations/ directory):
#     sbatch scripts/tillicum_train.slurm
#     WIGGLE_TRAIN_ARGS="--epochs 1 --retention_rows 2000" \
#         sbatch --qos=debug --time=01:00:00 scripts/tillicum_train.slurm   # trial
#
# Steps ($WIGGLE_TRAIN_STEPS, default all, in this order):
#     export  pipeline/export_training_data.py: certified.jsonl → train/dev
#             anchors, split by blueprint project
#     train   ../finetune/train_perturbation_mnrl.py: [anchor, equivalent,
#             hard negatives] plus NL→Lean retention pairs; writes metrics.json
#             with baseline and fine-tuned scores
#     eval    pipeline/mteb_perturbation_eval.py on the dev projects, base model
#             vs. fine-tuned checkpoint
#
# Knobs (env vars, all optional):
#     WIGGLE_TRAIN_STEPS   subset of "export train eval"
#     WIGGLE_BP_OUT        perturbation run holding certified.jsonl
#                          (default data/blueprint-review)
#     WIGGLE_BASE_MODEL    model to fine-tune (default Qwen/Qwen3-Embedding-8B)
#     WIGGLE_RUN_NAME      checkpoint name (default pert_<model>_<job id>)
#     WIGGLE_TRAIN_ARGS    extra arguments for train_perturbation_mnrl.py
# Checkpoints go to $TILLICUM_BASE/checkpoints/ (an 8B checkpoint is ~16 GB).
# ─────────────────────────────────────────────────────────────────────────────

#SBATCH --job-name=wiggle-train
#SBATCH --account=mathai
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=180G
#SBATCH --time=12:00:00
#SBATCH -o %x_%j.out

set -eo pipefail
JOB_START=$(date +%s)

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
FINETUNE_DIR="$(cd "$PROJECT_ROOT/../finetune" && pwd)"

# shellcheck source=tillicum_env.sh
source scripts/tillicum_env.sh
if ! wiggle_activate; then
    echo "error: could not activate $WIGGLE_ENV; run scripts/tillicum_setup.sh first" >&2
    exit 2
fi
export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TOKENIZERS_PARALLELISM=false

STEPS="${WIGGLE_TRAIN_STEPS:-export train eval}"
RUN="${WIGGLE_BP_OUT:-data/blueprint-review}"
DATA="$RUN/training"
BASE_MODEL="${WIGGLE_BASE_MODEL:-Qwen/Qwen3-Embedding-8B}"
RUN_NAME="${WIGGLE_RUN_NAME:-pert_$(basename "$BASE_MODEL")_${SLURM_JOB_ID:-local}}"
CKPT="$TILLICUM_BASE/checkpoints/$RUN_NAME"
read -r -a TRAIN_ARGS <<< "${WIGGLE_TRAIN_ARGS:-}"

# The setup script downloads the model at the revision mteb pins, which is not
# necessarily `main`; offline, only that snapshot exists, so load it by path.
BASE_PATH="$(python - "$BASE_MODEL" <<'EOF'
import sys
import mteb
from huggingface_hub import snapshot_download

name = sys.argv[1]
print(snapshot_download(name, revision=mteb.get_model_meta(name).revision, local_files_only=True))
EOF
)"

echo "──────────────────────────────────────────────────────────────────────"
echo " Wiggle perturbation fine-tuning on Tillicum"
echo " host       : $(hostname)"
echo " job id     : ${SLURM_JOB_ID:-<none — running outside slurm>}"
echo " steps      : $STEPS"
echo " data       : $PROJECT_ROOT/$RUN/certified.jsonl"
echo " base model : $BASE_MODEL ($BASE_PATH)"
echo " checkpoint : $CKPT"
echo "──────────────────────────────────────────────────────────────────────"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader || true

has_step() { [[ " $STEPS " == *" $1 "* ]]; }

if has_step export; then
    echo; echo "══ export training data"
    python -u pipeline/export_training_data.py --run "$RUN"
fi

if has_step train; then
    echo; echo "══ train"
    mkdir -p "$CKPT"
    (cd "$FINETUNE_DIR" && python -u train_perturbation_mnrl.py \
        --train_jsonl "$PROJECT_ROOT/$DATA/train.jsonl" \
        --dev_jsonl "$PROJECT_ROOT/$DATA/dev.jsonl" \
        --model_name "$BASE_PATH" \
        --device cuda \
        --wrap_query \
        --output_dir "$CKPT" \
        --checkpoint_dir "$CKPT/steps" \
        "${TRAIN_ARGS[@]}")
fi

if has_step eval; then
    echo; echo "══ MTEB eval on the dev projects: base vs fine-tuned"
    python -u pipeline/mteb_perturbation_eval.py \
        --results "$DATA/dev_certified.jsonl" \
        --models "$BASE_MODEL" "$CKPT" \
        --base-model "$BASE_MODEL" \
        --out "$DATA/mteb-$RUN_NAME"
fi

echo
echo "Done in $(( ($(date +%s) - JOB_START) / 60 )) min."
echo "    $CKPT/metrics.json            baseline vs fine-tuned (dev projects + NL→Lean retrieval)"
echo "    $PROJECT_ROOT/$DATA/mteb-$RUN_NAME/   MTEB scores, base vs fine-tuned"
