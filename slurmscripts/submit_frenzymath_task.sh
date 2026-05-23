#!/bin/bash

set -euo pipefail

if [[ $# -lt 4 || $# -gt 5 ]]; then
  echo "Usage:"
  echo "  bash slurmscripts/submit_frenzymath_task.sh <model_name> <task_preset> <batch_size> <time_limit> [run_label]"
  echo
  echo "Example:"
  echo "  bash slurmscripts/submit_frenzymath_task.sh Qwen/Qwen3-Embedding-4B informal_to_type 256 04:00:00 FULL"
  exit 1
fi

MODEL_NAME="$1"
TASK_PRESET="$2"
BATCH_SIZE="$3"
TIME_LIMIT="$4"
RUN_LABEL="${5:-FULL}"

case "${TASK_PRESET}" in
  informal_to_type|type_to_informal|informal_to_signature|signature_to_informal|type_to_signature|signature_to_type) ;;
  *)
    echo "Invalid task_preset: ${TASK_PRESET}"
    exit 1
    ;;
esac

REPO_DIR="${REPO_DIR:-/gpfs/projects/mathai/math2vec}"
RESULTS_DIR="${RESULTS_DIR:-/gpfs/projects/mathai/math2vec/runs/$USER/frenzymath}"
LOG_DIR="${LOG_DIR:-/gpfs/projects/mathai/math2vec/logs/frenzymath}"
HF_HOME="${HF_HOME:-/gpfs/projects/mathai/math2vec/hf_cache}"
HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-/gpfs/projects/mathai/math2vec/hf_cache/hub}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-/gpfs/projects/mathai/math2vec/hf_cache/transformers}"
SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/gpfs/projects/mathai/math2vec/st_cache}"
HF_TOKEN_FILE="${HF_TOKEN_FILE:-$HOME/hf_token.txt}"
QUERY_SPLIT="${QUERY_SPLIT:-test}"
CORPUS_SPLITS="${CORPUS_SPLITS:-train,val,test}"
SAVE_RANKINGS_FLAG="${SAVE_RANKINGS_FLAG:---save-rankings}"
SAVE_EMBEDDINGS_FLAG="${SAVE_EMBEDDINGS_FLAG:---save-embeddings --save-embeddings-dtype float16}"
DTYPE_FLAG="${DTYPE_FLAG:---dtype bfloat16}"
DISABLE_DEFAULT_DIRECTION_PROMPTS_FLAG="${DISABLE_DEFAULT_DIRECTION_PROMPTS_FLAG:---disable-default-direction-prompts}"
EMBEDDING_CACHE_DIR="${EMBEDDING_CACHE_DIR:-${RESULTS_DIR}/_embedding_cache}"

mkdir -p "${RESULTS_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${HF_HOME}"
mkdir -p "${HUGGINGFACE_HUB_CACHE}"
mkdir -p "${TRANSFORMERS_CACHE}"
mkdir -p "${SENTENCE_TRANSFORMERS_HOME}"
mkdir -p "${EMBEDDING_CACHE_DIR}"

MODEL_SLUG="$(printf '%s' "${MODEL_NAME}" | tr '/:' '__')"
JOB_NAME="frz_${RUN_LABEL}_${TASK_PRESET}_${MODEL_SLUG}"
JOB_NAME="${JOB_NAME,,}"
JOB_NAME="${JOB_NAME//[^a-z0-9._-]/_}"

echo "Submitting one FrenzyMath task job:"
echo "  job_name=${JOB_NAME}"
echo "  model_name=${MODEL_NAME}"
echo "  task_preset=${TASK_PRESET}"
echo "  batch_size=${BATCH_SIZE}"
echo "  time_limit=${TIME_LIMIT}"
echo "  run_label=${RUN_LABEL}"
echo "  results_dir=${RESULTS_DIR}"
echo "  embedding_cache_dir=${EMBEDDING_CACHE_DIR}"

export REPO_DIR
export RESULTS_DIR
export LOG_DIR
export HF_HOME
export HUGGINGFACE_HUB_CACHE
export TRANSFORMERS_CACHE
export SENTENCE_TRANSFORMERS_HOME
export HF_TOKEN_FILE
export QUERY_SPLIT
export CORPUS_SPLITS
export SAVE_RANKINGS_FLAG
export SAVE_EMBEDDINGS_FLAG
export DTYPE_FLAG
export MODEL_NAME
export TASK_PRESET
export BATCH_SIZE
export TIME_LIMIT
export RUN_LABEL
export EMBEDDING_CACHE_DIR
export DISABLE_DEFAULT_DIRECTION_PROMPTS_FLAG

sbatch \
  --job-name="${JOB_NAME}" \
  --qos=normal \
  --gpus=1 \
  --cpus-per-task=8 \
  --time="${TIME_LIMIT}" \
  --output="${LOG_DIR}/%x_%j.out" \
  --export=ALL,TASK_PRESET \
  "${REPO_DIR}/slurmscripts/run_frenzymath_benchmark.slurm"
