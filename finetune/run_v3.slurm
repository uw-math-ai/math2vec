#!/bin/bash
#SBATCH --job-name=mv3_qwen8b
#SBATCH --account=mathai
#SBATCH --partition=gpu-h200
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH -o logs/%x_%j.out

# Multi-view v3 fine-tuning with the paper recipe.
# Two runs, identical except for EXTRA:
#   sbatch --export=ALL,RUN=mv3_qwen8b_paper_ep2 run_v3.slurm                                # paper repro
#   sbatch --export=ALL,RUN=mv3_qwen8b_tg_ep2,EXTRA=data/tg_concepts.jsonl run_v3.slurm     # + TheoremGraph
# Base data = MathlibViews.jsonl (paper's 133,621 concepts; v3 splits it by module, seed 42).
# EXTRA is added to training only, after the split, so both runs share the same dev set.

set -euo pipefail

cd /gpfs/scrubbed/$USER/mathlib-ft
module load conda/Miniforge3-25.3.1-3
conda activate /gpfs/scrubbed/$USER/conda-envs/mathlib-ft

export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
export HF_DATASETS_CACHE=$HF_HOME/datasets
export TRANSFORMERS_CACHE=$HF_HOME/transformers
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TORCH_HOME=$HF_HOME/torch
export XDG_CACHE_HOME=$HF_HOME
export TMPDIR=/gpfs/scrubbed/$USER/tmp
export TOKENIZERS_PARALLELISM=false
mkdir -p "$HF_HOME" "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE" "$HUGGINGFACE_HUB_CACHE" "$TORCH_HOME" "$TMPDIR" logs

DATA=${DATA:-data/MathlibViews.jsonl}
EXTRA=${EXTRA:-}
RUN=${RUN:-mv3_qwen8b_paper_ep2}
MODEL=${MODEL:-Qwen/Qwen3-Embedding-8B}
EXTRA_ARGS=()
if [ -n "$EXTRA" ]; then EXTRA_ARGS=(--extra_train_jsonl "$EXTRA"); fi

echo "DATA=$DATA EXTRA=${EXTRA:-none} RUN=$RUN MODEL=$MODEL"

# Paper recipe: batch 16, max len 128, 2 epochs, 700 warmup steps, constant LR (v3 default).
# --n_hard_negs 1000 disables the hard-negative loader: the paper excluded hard negatives,
# and 2 epochs x 7,395 batches = 14,790 steps matches the paper only with the base loader alone.
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
