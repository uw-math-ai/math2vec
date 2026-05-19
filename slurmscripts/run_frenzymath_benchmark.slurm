#!/bin/bash -l
#SBATCH --job-name=frenzymath_benchmark
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --output=%x_%j.out

set -euo pipefail

# Clear inherited Conda state from the submission shell so the cluster module
# can be loaded cleanly inside the batch job.
unset CONDA_PREFIX || true
unset CONDA_DEFAULT_ENV || true
unset CONDA_EXE || true
unset CONDA_PROMPT_MODIFIER || true
unset CONDA_PYTHON_EXE || true
unset CONDA_SHLVL || true
unset _CE_CONDA || true
unset _CE_M || true

module load conda
conda activate /gpfs/projects/mathai/math2vec/envs/math2vec

REPO_DIR="${REPO_DIR:-/gpfs/projects/mathai/math2vec}"
cd "${REPO_DIR}"

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

if [[ -n "${HF_TOKEN_FILE:-}" && -f "${HF_TOKEN_FILE}" ]]; then
  HF_TOKEN="$(tr -d '\r\n' < "${HF_TOKEN_FILE}")"
  export HF_TOKEN
fi

if [[ -n "${HF_TOKEN:-}" ]]; then
  export HUGGING_FACE_HUB_TOKEN="${HF_TOKEN}"
  export HUGGINGFACE_HUB_TOKEN="${HF_TOKEN}"
fi

# Override these at submission time if needed, for example:
# sbatch --export=ALL,MODEL_NAME=microsoft/harrier-oss-v1-0.6b,LEAN_FIELD=signature,BATCH_SIZE=8,RESULTS_DIR=/gpfs/projects/mathai/math2vec/runs/$USER/frenzymath slurmscripts/run_frenzymath_benchmark.slurm
MODEL_NAME="${MODEL_NAME:-microsoft/harrier-oss-v1-0.6b}"
LEAN_FIELD="${LEAN_FIELD:-type}"
QUERY_SPLIT="${QUERY_SPLIT:-test}"
CORPUS_SPLITS="${CORPUS_SPLITS:-train,val,test}"
DIRECTIONS="${DIRECTIONS:-informal_to_lean}"
BATCH_SIZE="${BATCH_SIZE:-16}"
RESULTS_DIR="${RESULTS_DIR:-/gpfs/projects/mathai/math2vec/runs/$USER/frenzymath}"
RUN_LABEL="${RUN_LABEL:-}"
REUSE_RUN_DIR="${REUSE_RUN_DIR:-}"
DTYPE_FLAG="${DTYPE_FLAG:-}"
MAX_QUERY_ITEMS_FLAG="${MAX_QUERY_ITEMS_FLAG:-}"
MAX_CORPUS_ITEMS_FLAG="${MAX_CORPUS_ITEMS_FLAG:-}"
QUERY_PROMPT_NAME_FLAG="${QUERY_PROMPT_NAME_FLAG:-}"
INFORMAL_TO_LEAN_QUERY_PROMPT_FLAG="${INFORMAL_TO_LEAN_QUERY_PROMPT_FLAG:-}"
LEAN_TO_INFORMAL_QUERY_PROMPT_FLAG="${LEAN_TO_INFORMAL_QUERY_PROMPT_FLAG:-}"
SAVE_RANKINGS_FLAG="${SAVE_RANKINGS_FLAG:-}"
SAVE_EMBEDDINGS_FLAG="${SAVE_EMBEDDINGS_FLAG:-}"
NO_SAVE_MANIFESTS_FLAG="${NO_SAVE_MANIFESTS_FLAG:-}"

if [[ -n "${RUN_LABEL}" ]]; then
  RUN_LABEL_FLAG="--run-label ${RUN_LABEL}"
else
  RUN_LABEL_FLAG=""
fi

if [[ -n "${REUSE_RUN_DIR}" ]]; then
  REUSE_RUN_DIR_FLAG="--reuse-run-dir ${REUSE_RUN_DIR}"
else
  REUSE_RUN_DIR_FLAG=""
fi

mkdir -p "${RESULTS_DIR}"

echo "Job started at: $(date -u)"
echo "Hostname: $(hostname)"
echo "Repo dir: ${REPO_DIR}"
echo "Results dir: ${RESULTS_DIR}"
echo "Run label: ${RUN_LABEL:-none}"
echo "Model: ${MODEL_NAME}"
echo "Directions: ${DIRECTIONS}"
echo "Lean field: ${LEAN_FIELD}"
echo "Query split: ${QUERY_SPLIT}"
echo "Corpus splits: ${CORPUS_SPLITS}"
echo "Batch size: ${BATCH_SIZE}"
echo "Reuse run dir: ${REUSE_RUN_DIR:-none}"
if command -v nvidia-smi >/dev/null 2>&1; then
  nvidia-smi
fi

python benchmarking/src/frenzymath_benchmark.py \
  --model-name "${MODEL_NAME}" \
  --directions "${DIRECTIONS}" \
  --lean-field "${LEAN_FIELD}" \
  --query-split "${QUERY_SPLIT}" \
  --corpus-splits "${CORPUS_SPLITS}" \
  --batch-size "${BATCH_SIZE}" \
  --device cuda \
  --results-dir "${RESULTS_DIR}" \
  ${RUN_LABEL_FLAG} \
  ${REUSE_RUN_DIR_FLAG} \
  ${DTYPE_FLAG} \
  ${MAX_QUERY_ITEMS_FLAG} \
  ${MAX_CORPUS_ITEMS_FLAG} \
  ${QUERY_PROMPT_NAME_FLAG} \
  ${INFORMAL_TO_LEAN_QUERY_PROMPT_FLAG} \
  ${LEAN_TO_INFORMAL_QUERY_PROMPT_FLAG} \
  ${SAVE_RANKINGS_FLAG} \
  ${SAVE_EMBEDDINGS_FLAG} \
  ${NO_SAVE_MANIFESTS_FLAG}
