#!/bin/bash
#SBATCH --job-name=NL_Lean_Benchmark_all_MiniLM_L6_v2
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --time=10:00
#SBATCH -o %x_%j.out

# Load your bash config so 'conda' becomes available
source ~/.bashrc

# Activate your environment
module load conda
conda activate /gpfs/projects/mathai/math2vec/envs/math2vec

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True # idk what this does


time python benchmarking/src/main.py \
--model-name Qwen/Qwen3-Embedding-0.6B
--batch-size 4

# CLI flags here