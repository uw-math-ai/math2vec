#!/bin/bash
# ---------------------------------------------------------------------------
# REAL RUN: paper recipe, Qwen3-Embedding-8B. ~8-10 GPU-hours per run.
# Same as finetune/run_v3.slurm but with the --partition line dropped
# (Tillicum assigns partitions automatically).
#
# Run the MathLibDocstrings experiment and, for a same-dev-set comparison, the baseline:
#
#   sbatch --export=ALL,RUN=mv3_qwen8b_docstrings_ep2,EXTRA=data/MathLibDocstrings_v4.19.0.jsonl run.slurm
#   sbatch --export=ALL,RUN=mv3_qwen8b_paper_ep2 run.slurm
#
# Add --account=<account> to the sbatch line if 'mathai' is rejected.
#
# EXTRA is folded into TRAINING ONLY after the module-level split (seed 42), so
# both runs evaluate on an identical dev set. Runtime scales with how many MathLibDocstrings
# concept_ids are NEW to the base data: all-merge ~8 h, all-new ~9.3 h.
# normal QOS allows 16 GPUs / 24 h, so two runs can queue concurrently.
# ---------------------------------------------------------------------------
#SBATCH --job-name=mv3_qwen8b
#SBATCH --account=mathai
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=12:00:00
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
mkdir -p "$HF_HOME" "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE" \
         "$HUGGINGFACE_HUB_CACHE" "$TORCH_HOME" "$TMPDIR" logs

DATA=${DATA:-data/MathlibViews.jsonl}
EXTRA=${EXTRA:-}
RUN=${RUN:-mv3_qwen8b_paper_ep2}
MODEL=${MODEL:-Qwen/Qwen3-Embedding-8B}
EXTRA_ARGS=()
if [ -n "$EXTRA" ]; then EXTRA_ARGS=(--extra_train_jsonl "$EXTRA"); fi

echo "=== node $(hostname) | job $SLURM_JOB_ID | $(date) ==="
echo "DATA=$DATA EXTRA=${EXTRA:-none} RUN=$RUN MODEL=$MODEL"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader

# Paper recipe: batch 16, max len 128, 2 epochs, 700 warmup steps, constant LR.
# --n_hard_negs 1000 disables the hard-negative loader: the paper excluded hard
# negatives, and 2 epochs x 7,395 batches = 14,790 steps matches the paper only
# with the base loader alone.
python train_qwen_mnrl_multiview_v3_tg.py \
  --device cuda \
  --local_jsonl "$DATA" \
  "${EXTRA_ARGS[@]}" \
  --model_name "$MODEL" \
  --wrap_query \
  --epochs 2 \
  --batch_size 16 \
  --max_seq_len 128 \
  --warmup_steps 700 \
  --n_hard_negs 1000 \
  --eval_batch_size 8 \
  --pair_loss_batch_size 16 \
  --output_dir checkpoints/$RUN \
  --checkpoint_dir checkpoints/ckpt_$RUN

echo "=== finished $(date) ==="
echo "metrics: checkpoints/$RUN/metrics.json"
