#!/bin/bash
# ---------------------------------------------------------------------------
# Does the +MathLibDocstrings model retrieve better from DOCSTRING-style queries?
#
# The main experiment only ever asked base-style (verbose LaTeX) questions and
# found +MathLibDocstrings slightly worse. This evaluates both SAVED models on the 1,497 MathLibDocstrings
# docstrings whose theorems landed in the dev set -- held out from training by
# the dev-leakage filter, so no model has seen them -- plus a base-NL control
# on exactly the same theorems.
#
# No retraining. One GPU, mostly corpus encoding (~133k docs x 2 models).
#
#   sbatch docstring_eval.slurm
#   sbatch --account=<account> docstring_eval.slurm      # if 'mathai' rejected
# ---------------------------------------------------------------------------
#SBATCH --job-name=mv3_docstring_eval
#SBATCH --account=mathai
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=03:00:00
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

PAPER=${PAPER:-checkpoints/mv3_qwen8b_paper_ep2}
DOCSTRINGS_MODEL=${DOCSTRINGS_MODEL:-checkpoints/mv3_qwen8b_docstrings_ep2}
OUT=${OUT:-docstring_eval.json}

echo "=== node $(hostname) | job $SLURM_JOB_ID | $(date) ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

python repo/finetune/MathLibDocstrings/docstring_eval.py \
  --models "$PAPER" "$DOCSTRINGS_MODEL" \
  --base data/MathlibViews.jsonl \
  --docstrings   data/MathLibDocstrings_v4.19.0.jsonl \
  --trainer train_qwen_mnrl_multiview_v3_tg.py \
  --device cuda \
  --out "$OUT"

echo "=== finished $(date) ==="
echo "results: $OUT"
