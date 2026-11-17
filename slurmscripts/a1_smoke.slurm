#!/bin/bash
# ---------------------------------------------------------------------------
# SMOKE TEST for the A1-docstrings experiment. debug QOS, 1 GPU, ~15-25 min.
# Proves the --extra_train_jsonl path works end to end before spending ~8-10
# GPU-hours on the real run.
#
# ITS METRICS ARE MEANINGLESS: 0.6B model, 2k base rows, 1 epoch, and 700
# warmup steps spread over only ~1.3k batches. Read the [extra] counts and the
# PASS/FAIL lines, nothing else.
#
#   sbatch a1_smoke.slurm
#   sbatch --account=<account-from-setup-step-1> a1_smoke.slurm   # if rejected
#
# No --partition: Tillicum assigns it automatically (as run_benchmarking.slurm
# already relies on).
# ---------------------------------------------------------------------------
#SBATCH --job-name=mv3_smoke_a1
#SBATCH --account=mathai
#SBATCH --qos=debug
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=00:50:00
#SBATCH -o logs/%x_%j.out

set -euo pipefail

cd /gpfs/scrubbed/$USER/mathlib-ft
module load conda/Miniforge3-25.3.1-3
# the conda shell function trips `set -u`, so guard just the activate
set +u; conda activate /gpfs/scrubbed/$USER/conda-envs/mathlib-ft; set -u

export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
export HF_DATASETS_CACHE=$HF_HOME/datasets
export TRANSFORMERS_CACHE=$HF_HOME/transformers
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TORCH_HOME=$HF_HOME/torch
export XDG_CACHE_HOME=$HF_HOME
export TMPDIR=/gpfs/scrubbed/$USER/tmp
export TOKENIZERS_PARALLELISM=false
mkdir -p "$HF_HOME" "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE" \
         "$HUGGINGFACE_HUB_CACHE" "$TORCH_HOME" "$TMPDIR" logs

echo "=== node $(hostname) | job $SLURM_JOB_ID | $(date) ==="
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

RUN=smoke_a1
LOG=logs/${SLURM_JOB_NAME}_${SLURM_JOB_ID}.out

# Paper-recipe flags; only model, rows and epochs are reduced.
python train_qwen_mnrl_multiview_v3_tg.py \
  --device cuda \
  --local_jsonl data/MathlibViews.jsonl \
  --extra_train_jsonl data/a1_kept_concepts_v4.19.0.jsonl \
  --model_name Qwen/Qwen3-Embedding-0.6B \
  --max_rows 2000 \
  --epochs 1 \
  --wrap_query \
  --batch_size 16 \
  --max_seq_len 128 \
  --warmup_steps 700 \
  --n_hard_negs 1000 \
  --eval_batch_size 8 \
  --pair_loss_batch_size 16 \
  --output_dir checkpoints/$RUN \
  --checkpoint_dir checkpoints/ckpt_$RUN

echo
echo "=== SMOKE CHECKS ==="
if grep -q '^\[extra\]' "$LOG"; then
  echo "PASS: [extra] line present"; grep -m1 '^\[extra\]' "$LOG"
else
  echo "FAIL: no [extra] line -- extra data was not loaded"
fi
if [ -f "checkpoints/$RUN/metrics.json" ]; then
  echo "PASS: metrics.json written"
  python -c "import json;d=json.load(open('checkpoints/$RUN/metrics.json'));print('counts.extra_train =',json.dumps(d['counts']['extra_train'],indent=2))"
else
  echo "FAIL: no metrics.json"
fi
echo "=== finished $(date) ==="
