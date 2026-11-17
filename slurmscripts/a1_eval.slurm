#!/bin/bash
# ---------------------------------------------------------------------------
# Optional GPU re-eval of a saved model. You usually do NOT need this --
# a1_run.slurm already wrote baseline and fine-tuned numbers into metrics.json;
# read them with a1_report.py (CPU, instant).
#
# Use this to eval a mid-training checkpoint, a different k, or a different
# concept file. Encoding the full 133k-doc corpus with the 8B model for all six
# pair types is slow, hence normal QOS and 4 h.
#
#   sbatch --export=ALL,RUN=mv3_qwen8b_a1_ep2 a1_eval.slurm
#   sbatch --export=ALL,RUN=mv3_qwen8b_a1_ep2,PRIMARY_ONLY=1,QOS=debug a1_eval.slurm
#   sbatch --export=ALL,RUN=mv3_qwen8b_a1_ep2,MODEL_PATH=checkpoints/ckpt_mv3_qwen8b_a1_ep2/checkpoint-8000,TAG=step8000 a1_eval.slurm
#
# Add --account=<account> to the sbatch line if 'mathai' is rejected.
# ---------------------------------------------------------------------------
#SBATCH --job-name=mv3_eval
#SBATCH --account=mathai
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH -o logs/%x_%j.out

set -euo pipefail

cd /gpfs/scrubbed/$USER/mathlib-ft
module load conda/Miniforge3-25.3.1-3
set +u; conda activate /gpfs/scrubbed/$USER/conda-envs/mathlib-ft; set -u

export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
export HF_DATASETS_CACHE=$HF_HOME/datasets
export TRANSFORMERS_CACHE=$HF_HOME/transformers
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TORCH_HOME=$HF_HOME/torch
export XDG_CACHE_HOME=$HF_HOME
export TMPDIR=/gpfs/scrubbed/$USER/tmp
export TOKENIZERS_PARALLELISM=false
mkdir -p "$TMPDIR" logs

RUN=${RUN:?set RUN=<run name>, e.g. --export=ALL,RUN=mv3_qwen8b_a1_ep2}
TAG=${TAG:-recheck}
EXTRA_ARGS=()
[ -n "${MODEL_PATH:-}" ] && EXTRA_ARGS+=(--model_path "$MODEL_PATH")
[ -n "${PRIMARY_ONLY:-}" ] && EXTRA_ARGS+=(--primary_only)
[ -n "${K:-}" ] && EXTRA_ARGS+=(--k "$K")
[ -n "${DATA:-}" ] && EXTRA_ARGS+=(--data "$DATA")

echo "=== node $(hostname) | job $SLURM_JOB_ID | $(date) ==="
echo "RUN=$RUN TAG=$TAG ${EXTRA_ARGS[*]:-}"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

python repo/slurmscripts/a1_eval_checkpoint.py \
  --run_dir "checkpoints/$RUN" \
  --trainer train_qwen_mnrl_multiview_v3_tg.py \
  --tag "$TAG" \
  --device cuda \
  "${EXTRA_ARGS[@]}"

echo "=== finished $(date) ==="
