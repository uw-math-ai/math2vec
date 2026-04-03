#!/bin/bash
#SBATCH --job-name=cached_4b
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH -o logs/%x_%j.out

set -euo pipefail

cd /gpfs/scrubbed/$USER/mathlib-ft
source .venv/bin/activate

export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
export HF_DATASETS_CACHE=$HF_HOME/datasets
export TRANSFORMERS_CACHE=$HF_HOME/transformers
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TORCH_HOME=$HF_HOME/torch
export XDG_CACHE_HOME=$HF_HOME
export TMPDIR=/gpfs/scrubbed/$USER/tmp
export TOKENIZERS_PARALLELISM=false

mkdir -p "$HF_HOME" "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE" "$HUGGINGFACE_HUB_CACHE" "$TORCH_HOME" "$TMPDIR"

python train_qwen_mnrl_v2.py \
  --device cuda \
  --model_name Qwen/Qwen3-Embedding-8B \
  --wrap_query \
  --max_rows 200000 \
  --epochs 1 \
  --batch_size 16 \
  --max_seq_len 128 \
  --eval_batch_size 8 \
  --output_dir checkpoints/cached_mnrl_qwen8b_r200k_ep1 \
  --checkpoint_dir checkpoints/cached_mnrl_qwen8b_r200k_ep1


# cached_mnrl_{model}_r{# rows}_ep{# epochs}
