#!/bin/bash
#SBATCH --job-name=frenzymath_benchmark
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --output=%x_%j.out

set -euo pipefail

source ~/.bashrc
module load conda
conda activate /gpfs/projects/mathai/math2vec/envs/math2vec

cd /gpfs/projects/mathai/math2vec/math2vec

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

# Override these at submission time if needed, for example:
# sbatch --export=ALL,MODEL_NAME=BAAI/bge-large-en-v1.5,LEAN_FIELD=signature,BATCH_SIZE=8 slurmscripts/run_frenzymath_benchmark.slurm
MODEL_NAME="${MODEL_NAME:-sentence-transformers/all-MiniLM-L6-v2}"
LEAN_FIELD="${LEAN_FIELD:-type}"
QUERY_SPLIT="${QUERY_SPLIT:-test}"
CORPUS_SPLITS="${CORPUS_SPLITS:-train,val,test}"
BATCH_SIZE="${BATCH_SIZE:-16}"
DTYPE_FLAG="${DTYPE_FLAG:-}"
MAX_QUERY_ITEMS_FLAG="${MAX_QUERY_ITEMS_FLAG:-}"
MAX_CORPUS_ITEMS_FLAG="${MAX_CORPUS_ITEMS_FLAG:-}"
QUERY_PROMPT_NAME_FLAG="${QUERY_PROMPT_NAME_FLAG:-}"
SAVE_RANKINGS_FLAG="${SAVE_RANKINGS_FLAG:-}"

python benchmarking/src/frenzymath_benchmark.py \
  --model-name "${MODEL_NAME}" \
  --lean-field "${LEAN_FIELD}" \
  --query-split "${QUERY_SPLIT}" \
  --corpus-splits "${CORPUS_SPLITS}" \
  --batch-size "${BATCH_SIZE}" \
  --device cuda \
  ${DTYPE_FLAG} \
  ${MAX_QUERY_ITEMS_FLAG} \
  ${MAX_CORPUS_ITEMS_FLAG} \
  ${QUERY_PROMPT_NAME_FLAG} \
  ${SAVE_RANKINGS_FLAG}
