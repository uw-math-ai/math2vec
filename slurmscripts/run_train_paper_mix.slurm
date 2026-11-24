#!/bin/bash
#SBATCH --job-name=mv3_qwen8b_mix1120
#SBATCH --account=mathai
#SBATCH --partition=gpu-h200
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=16:00:00
#SBATCH -o logs/%x_%j.out

# Paper recipe (v3 multi-view, 2 epochs, batch 16, len 128, 700 warmup, constant LR)
# + the 2000 medium-difficulty rows ("11-20 training run.json") as training-only data,
#   converted to finetune/11-20_extra_v3.jsonl (see convert_to_v3_extra.py).
# The extra concepts' NL hard negatives feed the hard-negative loader; base Mathlib
# concepts stay hard-negative-free, as in the paper.
#
# Submit from finetune/ (one-time setup: env, data/MathlibViews.jsonl, model download):
#   cd /gpfs/scrubbed/$USER/math2vec/finetune
#   sbatch ../slurmscripts/run_train_paper_mix.slurm

set -euo pipefail

cd "${SLURM_SUBMIT_DIR:-.}"
mkdir -p logs

module load conda/Miniforge3-25.3.1-3
conda activate /gpfs/scrubbed/$USER/conda-envs/mathlib-ft

export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
export HF_DATASETS_CACHE=$HF_HOME/datasets
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TORCH_HOME=$HF_HOME/torch
export XDG_CACHE_HOME=$HF_HOME
export TMPDIR=/gpfs/scrubbed/$USER/tmp
export TOKENIZERS_PARALLELISM=false
mkdir -p "$HF_HOME" "$TMPDIR"

DATA=${DATA:-data/MathlibViews.jsonl}
EXTRA=${EXTRA:-11-20_extra_v3.jsonl}
RUN=${RUN:-mv3_qwen8b_mix1120_ep2}
MODEL=${MODEL:-Qwen/Qwen3-Embedding-8B}

echo "DATA=$DATA EXTRA=$EXTRA RUN=$RUN MODEL=$MODEL"
test -s "$DATA" || { echo "missing $DATA"; exit 1; }
test -s "$EXTRA" || { echo "missing $EXTRA"; exit 1; }

time python train_qwen_mnrl_multiview_v3_tg.py \
  --device cuda \
  --local_jsonl "$DATA" \
  --extra_train_jsonl "$EXTRA" \
  --hn_from_extra_only \
  --n_hard_negs 1 \
  --hard_neg_batch_size 16 \
  --model_name "$MODEL" \
  --wrap_query \
  --epochs 2 \
  --batch_size 16 \
  --max_seq_len 128 \
  --warmup_steps 700 \
  --eval_batch_size 8 \
  --pair_loss_batch_size 16 \
  --output_dir checkpoints/$RUN \
  --checkpoint_dir checkpoints/ckpt_$RUN
