#!/bin/bash

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(cd "${SCRIPT_DIR}/.." && pwd)}"
RESULTS_DIR="${RESULTS_DIR:-/gpfs/scrubbed/$USER/math2vec_runs/frenzymath}"
LOG_DIR="${LOG_DIR:-/gpfs/scrubbed/$USER/math2vec_logs/frenzymath}"
HF_HOME="${HF_HOME:-/gpfs/scrubbed/$USER/math2vec_hf_cache}"
HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-/gpfs/scrubbed/$USER/math2vec_hf_cache/hub}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-/gpfs/scrubbed/$USER/math2vec_hf_cache/transformers}"
SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/gpfs/scrubbed/$USER/math2vec_st_cache}"
HF_TOKEN_FILE="${HF_TOKEN_FILE:-$HOME/hf_token.txt}"
EMBEDDING_CACHE_DIR="${EMBEDDING_CACHE_DIR:-${RESULTS_DIR}/_embedding_cache}"
RUN_LABEL="${RUN_LABEL:-FULL}"
TASK_PRESET="informal_to_type"

mkdir -p "${RESULTS_DIR}" "${LOG_DIR}" "${HF_HOME}" "${HUGGINGFACE_HUB_CACHE}" "${TRANSFORMERS_CACHE}" "${SENTENCE_TRANSFORMERS_HOME}" "${EMBEDDING_CACHE_DIR}"

MODELS=(
  "Qwen/Qwen3-Embedding-8B|1024|06:00:00"
  "nvidia/llama-embed-nemotron-8b|1024|06:00:00"
  "tencent/KaLM-Embedding-Gemma3-12B-2511|1024|08:00:00"
  "codefuse-ai/F2LLM-v2-14B|1024|08:00:00"
  "microsoft/harrier-oss-v1-27b|768|12:00:00"
)

echo "Submitting remaining prompted informal_to_type jobs."
echo "Repo dir: ${REPO_DIR}"
echo "Results dir: ${RESULTS_DIR}"
echo "Log dir: ${LOG_DIR}"
echo "Embedding cache dir: ${EMBEDDING_CACHE_DIR}"
echo

success_submissions=0
failed_submissions=0

for spec in "${MODELS[@]}"; do
  IFS="|" read -r model_name batch_size time_limit <<< "${spec}"
  echo "Submitting model=${model_name} batch_size=${batch_size} time_limit=${time_limit}"
  if REPO_DIR="${REPO_DIR}" \
     RESULTS_DIR="${RESULTS_DIR}" \
     LOG_DIR="${LOG_DIR}" \
     HF_HOME="${HF_HOME}" \
     HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE}" \
     TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE}" \
     SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME}" \
     HF_TOKEN_FILE="${HF_TOKEN_FILE}" \
     EMBEDDING_CACHE_DIR="${EMBEDDING_CACHE_DIR}" \
     RUN_LABEL="${RUN_LABEL}" \
     bash "${REPO_DIR}/slurmscripts/submit_frenzymath_task.sh" "${model_name}" "${TASK_PRESET}" "${batch_size}" "${time_limit}" "${RUN_LABEL}"; then
    success_submissions=$((success_submissions + 1))
  else
    echo "Submission failed for ${model_name}, continuing to next model." >&2
    failed_submissions=$((failed_submissions + 1))
  fi
  echo
done

echo "Submission summary:"
echo "  successful_submissions=${success_submissions}"
echo "  failed_submissions=${failed_submissions}"
echo
echo "Check live queue with:"
echo "  squeue -u $USER"
