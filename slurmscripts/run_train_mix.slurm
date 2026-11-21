#!/bin/bash
#SBATCH --job-name=Qwen3_Embedding_mix_1120
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --time=06:00:00
#SBATCH -o %x_%j.out

# Run from the repo root:  sbatch slurmscripts/run_train_mix.slurm

# Load your bash config so 'conda' becomes available
source ~/.bashrc

# Activate your environment
module load conda
conda activate /gpfs/projects/mathai/math2vec/envs/math2vec

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TOKENIZERS_PARALLELISM=false

# Fine-tune Qwen3-Embedding on Mathlib pairs + the 2000 medium-difficulty rows
cd finetune
time python train_qwen_mnrl_mix_extra.py \
--device cuda \
--model_name Qwen/Qwen3-Embedding-8B \
--extra_json "11-20 training run.json" \
--wrap_query \
--max_rows 200000 \
--epochs 1 \
--batch_size 16 \
--max_seq_len 128 \
--eval_batch_size 8 \
--output_dir checkpoints/mix_1120_qwen8b \
--checkpoint_dir checkpoints/ckpt_mix_1120_qwen8b
