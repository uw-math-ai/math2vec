#!/bin/bash

set -euo pipefail

if [[ $# -lt 5 || $# -gt 7 ]]; then
  echo "Usage:"
  echo "  bash slurmscripts/submit_frenzymath_single.sh <model_name> <lean_field> <direction> <batch_size> <time_limit> [run_label] [reuse_run_dir]"
  echo
  echo "Example:"
  echo "  bash slurmscripts/submit_frenzymath_single.sh microsoft/harrier-oss-v1-0.6b type informal_to_lean 32 04:00:00 FULL"
  exit 1
fi

MODEL_NAME="$1"
LEAN_FIELD="$2"
DIRECTION="$3"
BATCH_SIZE="$4"
TIME_LIMIT="$5"
RUN_LABEL="${6:-FULL}"
REUSE_RUN_DIR="${7:-}"

case "${LEAN_FIELD}" in
  type|signature) ;;
  *)
    echo "Invalid lean_field: ${LEAN_FIELD}. Use type or signature."
    exit 1
    ;;
esac

case "${DIRECTION}" in
  informal_to_lean|lean_to_informal) ;;
  *)
    echo "Invalid direction: ${DIRECTION}. Use informal_to_lean or lean_to_informal."
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

mkdir -p "${RESULTS_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${HF_HOME}"
mkdir -p "${HUGGINGFACE_HUB_CACHE}"
mkdir -p "${TRANSFORMERS_CACHE}"
mkdir -p "${SENTENCE_TRANSFORMERS_HOME}"

MODEL_SLUG="$(printf '%s' "${MODEL_NAME}" | tr '/:' '__')"
JOB_NAME="frz_${RUN_LABEL}_${DIRECTION}_${LEAN_FIELD}_${MODEL_SLUG}"
JOB_NAME="${JOB_NAME,,}"
JOB_NAME="${JOB_NAME//[^a-z0-9._-]/_}"

echo "Submitting one FrenzyMath job:"
echo "  job_name=${JOB_NAME}"
echo "  model_name=${MODEL_NAME}"
echo "  lean_field=${LEAN_FIELD}"
echo "  direction=${DIRECTION}"
echo "  batch_size=${BATCH_SIZE}"
echo "  time_limit=${TIME_LIMIT}"
echo "  run_label=${RUN_LABEL}"
echo "  reuse_run_dir=${REUSE_RUN_DIR:-none}"
echo "  results_dir=${RESULTS_DIR}"

sbatch \
  --job-name="${JOB_NAME}" \
  --qos=normal \
  --gpus=1 \
  --cpus-per-task=8 \
  --time="${TIME_LIMIT}" \
  --output="${LOG_DIR}/%x_%j.out" \
  --export=ALL,REPO_DIR="${REPO_DIR}",RESULTS_DIR="${RESULTS_DIR}",MODEL_NAME="${MODEL_NAME}",LEAN_FIELD="${LEAN_FIELD}",QUERY_SPLIT="${QUERY_SPLIT}",CORPUS_SPLITS="${CORPUS_SPLITS}",DIRECTIONS="${DIRECTION}",BATCH_SIZE="${BATCH_SIZE}",DTYPE_FLAG="${DTYPE_FLAG}",RUN_LABEL="${RUN_LABEL}",REUSE_RUN_DIR="${REUSE_RUN_DIR}",SAVE_RANKINGS_FLAG="${SAVE_RANKINGS_FLAG}",SAVE_EMBEDDINGS_FLAG="${SAVE_EMBEDDINGS_FLAG}",HF_HOME="${HF_HOME}",HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE}",TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE}",SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME}",HF_TOKEN_FILE="${HF_TOKEN_FILE}" \
  "${REPO_DIR}/slurmscripts/run_frenzymath_benchmark.slurm"
