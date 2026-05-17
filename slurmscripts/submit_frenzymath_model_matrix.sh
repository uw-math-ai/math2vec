#!/bin/bash

set -euo pipefail

REPO_DIR="${REPO_DIR:-/gpfs/projects/mathai/math2vec}"
RESULTS_DIR="${RESULTS_DIR:-/gpfs/projects/mathai/math2vec/runs/$USER/frenzymath}"
LOG_DIR="${LOG_DIR:-/gpfs/projects/mathai/math2vec/logs/frenzymath}"
HF_HOME="${HF_HOME:-/gpfs/projects/mathai/math2vec/hf_cache}"
HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE:-/gpfs/projects/mathai/math2vec/hf_cache/hub}"
TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE:-/gpfs/projects/mathai/math2vec/hf_cache/transformers}"
SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME:-/gpfs/projects/mathai/math2vec/st_cache}"

QUERY_SPLIT="${QUERY_SPLIT:-test}"
CORPUS_SPLITS="${CORPUS_SPLITS:-train,val,test}"
DIRECTIONS="${DIRECTIONS:-informal_to_lean,lean_to_informal}"
SAVE_RANKINGS_FLAG="${SAVE_RANKINGS_FLAG:---save-rankings}"
SAVE_EMBEDDINGS_FLAG="${SAVE_EMBEDDINGS_FLAG:---save-embeddings --save-embeddings-dtype float16}"
MAX_QUERY_ITEMS="${MAX_QUERY_ITEMS:-}"

mkdir -p "${RESULTS_DIR}"
mkdir -p "${LOG_DIR}"
mkdir -p "${HF_HOME}"
mkdir -p "${HUGGINGFACE_HUB_CACHE}"
mkdir -p "${TRANSFORMERS_CACHE}"
mkdir -p "${SENTENCE_TRANSFORMERS_HOME}"

if [[ -n "${MAX_QUERY_ITEMS}" ]]; then
  MAX_QUERY_ITEMS_FLAG="--max-query-items ${MAX_QUERY_ITEMS}"
else
  MAX_QUERY_ITEMS_FLAG=""
fi

run_exists() {
  local model_name="$1"
  local lean_field="$2"
  local directions="$3"
  local max_query_items="$4"
  local query_split="$5"
  local corpus_splits="$6"

  python - "$RESULTS_DIR" "$model_name" "$lean_field" "$directions" "$max_query_items" "$query_split" "$corpus_splits" <<'PY'
import json
import pathlib
import sys

results_dir = pathlib.Path(sys.argv[1])
model_name = sys.argv[2]
lean_field = sys.argv[3]
directions = [item.strip() for item in sys.argv[4].split(",") if item.strip()]
max_query_items_raw = sys.argv[5]
query_split = sys.argv[6]
corpus_splits = [item.strip() for item in sys.argv[7].split(",") if item.strip()]
max_query_items = None if max_query_items_raw == "" else int(max_query_items_raw)

if not results_dir.exists():
    print("0")
    raise SystemExit(0)

for run_dir in sorted(results_dir.iterdir()):
    config_path = run_dir / "config.json"
    results_path = run_dir / "results.json"
    if not config_path.exists() or not results_path.exists():
        continue
    try:
        config = json.loads(config_path.read_text())
        results = json.loads(results_path.read_text())
    except Exception:
        continue
    if results.get("run_status") != "success":
        continue
    if config.get("model_name") != model_name:
        continue
    if config.get("lean_field") != lean_field:
        continue
    if config.get("query_split") != query_split:
        continue
    if config.get("corpus_splits") != corpus_splits:
        continue
    if config.get("directions") != directions:
        continue
    if config.get("max_query_items") != max_query_items:
        continue
    print("1")
    raise SystemExit(0)

print("0")
PY
}

submit_one() {
  local job_name="$1"
  local model_name="$2"
  local lean_field="$3"
  local batch_size="$4"
  local dtype_flag="$5"
  local time_limit="$6"

  if [[ "$(run_exists "$model_name" "$lean_field" "$DIRECTIONS" "$MAX_QUERY_ITEMS" "$QUERY_SPLIT" "$CORPUS_SPLITS")" == "1" ]]; then
    echo "Skipping existing successful run: model=${model_name} lean_field=${lean_field} directions=${DIRECTIONS} max_query_items=${MAX_QUERY_ITEMS:-full}"
    return 0
  fi

  echo "Submitting ${job_name}"
  echo "  model_name=${model_name}"
  echo "  lean_field=${lean_field}"
  echo "  directions=${DIRECTIONS}"
  echo "  query_split=${QUERY_SPLIT}"
  echo "  corpus_splits=${CORPUS_SPLITS}"
  echo "  batch_size=${batch_size}"
  echo "  dtype_flag=${dtype_flag}"
  echo "  max_query_items=${MAX_QUERY_ITEMS:-full}"

  sbatch \
    --job-name="${job_name}" \
    --qos=normal \
    --gpus=1 \
    --cpus-per-task=8 \
    --time="${time_limit}" \
    --output="${LOG_DIR}/%x_%j.out" \
    --export=ALL,REPO_DIR="${REPO_DIR}",RESULTS_DIR="${RESULTS_DIR}",MODEL_NAME="${model_name}",LEAN_FIELD="${lean_field}",QUERY_SPLIT="${QUERY_SPLIT}",CORPUS_SPLITS="${CORPUS_SPLITS}",DIRECTIONS="${DIRECTIONS}",BATCH_SIZE="${batch_size}",DTYPE_FLAG="${dtype_flag}",MAX_QUERY_ITEMS_FLAG="${MAX_QUERY_ITEMS_FLAG}",SAVE_RANKINGS_FLAG="${SAVE_RANKINGS_FLAG}",SAVE_EMBEDDINGS_FLAG="${SAVE_EMBEDDINGS_FLAG}",HF_HOME="${HF_HOME}",HUGGINGFACE_HUB_CACHE="${HUGGINGFACE_HUB_CACHE}",TRANSFORMERS_CACHE="${TRANSFORMERS_CACHE}",SENTENCE_TRANSFORMERS_HOME="${SENTENCE_TRANSFORMERS_HOME}" \
    "${REPO_DIR}/slurmscripts/run_frenzymath_benchmark.slurm"
}

submit_one "frz_har06_type"  "microsoft/harrier-oss-v1-0.6b"           "type"      "32" "--dtype bfloat16" "04:00:00"
submit_one "frz_har06_sig"   "microsoft/harrier-oss-v1-0.6b"           "signature" "32" "--dtype bfloat16" "04:00:00"
submit_one "frz_qwen4_type"  "Qwen/Qwen3-Embedding-4B"                 "type"      "12" "--dtype bfloat16" "08:00:00"
submit_one "frz_qwen4_sig"   "Qwen/Qwen3-Embedding-4B"                 "signature" "12" "--dtype bfloat16" "08:00:00"
submit_one "frz_qwen8_type"  "Qwen/Qwen3-Embedding-8B"                 "type"      "8"  "--dtype bfloat16" "12:00:00"
submit_one "frz_qwen8_sig"   "Qwen/Qwen3-Embedding-8B"                 "signature" "8"  "--dtype bfloat16" "12:00:00"
submit_one "frz_nemo8_type"  "nvidia/llama-embed-nemotron-8b"          "type"      "8"  "--dtype bfloat16" "12:00:00"
submit_one "frz_nemo8_sig"   "nvidia/llama-embed-nemotron-8b"          "signature" "8"  "--dtype bfloat16" "12:00:00"
submit_one "frz_kalm12_type" "tencent/KaLM-Embedding-Gemma3-12B-2511"  "type"      "4"  "--dtype bfloat16" "16:00:00"
submit_one "frz_kalm12_sig"  "tencent/KaLM-Embedding-Gemma3-12B-2511"  "signature" "4"  "--dtype bfloat16" "16:00:00"
submit_one "frz_har27_type"  "microsoft/harrier-oss-v1-27b"            "type"      "1"  "--dtype bfloat16" "24:00:00"
submit_one "frz_har27_sig"   "microsoft/harrier-oss-v1-27b"            "signature" "1"  "--dtype bfloat16" "24:00:00"
