#!/bin/bash
#SBATCH --job-name=finetune_qwen4b
#SBATCH --account=mathai
#SBATCH --partition=gpu-h200
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH -o logs/%x_%j.out

# Fine-tune an embedding model with finetune/train_qwen_mnrl_v2.py (MNRL, in-batch negatives),
# then score the result on 100 FineLeanCorpus docstrings with finetune/validate_docstrings.py.
#
# Submit from the repo root:
#   sbatch slurmscripts/run_finetune.slurm                                  # Qwen3-Embedding-4B, FrenzyMath, 10k rows
#   sbatch --export=ALL,MAX_ROWS=200000,EPOCHS=1 slurmscripts/run_finetune.slurm
#   sbatch --export=ALL,MODEL=Qwen/Qwen3-Embedding-8B,BATCH_SIZE=8 slurmscripts/run_finetune.slurm
#   sbatch --export=ALL,CORPUS=fineleancorpus slurmscripts/run_finetune.slurm  # train on FineLeanCorpus
#   sbatch --export=ALL,VALIDATE=0 slurmscripts/run_finetune.slurm           # skip the docstring check
#
# For a quick end-to-end smoke test first:
#   sbatch --time=00:30:00 --export=ALL,MAX_ROWS=2000,RUN=smoke slurmscripts/run_finetune.slurm

set -euo pipefail

# Uses the conda env that was active when you ran sbatch (sbatch passes it through).
# No `module load conda` here: Tillicum's conda module refuses to load in a job that inherits CONDA_PREFIX.
# With no env active, falls back to the scrubbed env below.
ENV=${CONDA_PREFIX:-/gpfs/scrubbed/$USER/conda-envs/math2vec}
if [ ! -x "$ENV/bin/python" ]; then
  echo "No conda env at $ENV. Create it first: conda create -p $ENV python=3.11, then pip install -r finetune/requirements.txt" >&2
  exit 1
fi
export PATH=$ENV/bin:$PATH
export CONDA_PREFIX=$ENV
echo "python: $(which python)"

REPO=${SLURM_SUBMIT_DIR:-$PWD}
if [ ! -f "$REPO/finetune/train_qwen_mnrl_v2.py" ]; then
  echo "Can't find finetune/train_qwen_mnrl_v2.py under $REPO. Submit this job from the math2vec repo root." >&2
  exit 1
fi
cd "$REPO/finetune"

# Caches and checkpoints go to scrubbed storage: a 4B checkpoint is ~8 GB each save.
SCRATCH=/gpfs/scrubbed/$USER
export HF_HOME=$SCRATCH/hf_cache
export HF_DATASETS_CACHE=$HF_HOME/datasets
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TORCH_HOME=$HF_HOME/torch
export XDG_CACHE_HOME=$HF_HOME
export TMPDIR=$SCRATCH/tmp
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True  # lets PyTorch reuse fragmented GPU memory (fewer OOMs)

# ---- settings (override any of these with sbatch --export=ALL,NAME=value) ----
MODEL=${MODEL:-Qwen/Qwen3-Embedding-4B}
CORPUS=${CORPUS:-frenzymath}          # frenzymath | fineleancorpus
MAX_ROWS=${MAX_ROWS:-10000}
EPOCHS=${EPOCHS:-1}
BATCH_SIZE=${BATCH_SIZE:-16}          # more = more in-batch negatives; lower to 8 or 4 on OOM
MAX_SEQ_LEN=${MAX_SEQ_LEN:-128}
EVAL_BATCH_SIZE=${EVAL_BATCH_SIZE:-8}
VALIDATE=${VALIDATE:-1}

case "$CORPUS" in
  frenzymath)
    DATA_ARGS=(--dataset_name FrenzyMath/mathlib_informal_v4.19.0
               --query_field informal_description --doc_field signature
               --key_field index --group_field module_name) ;;
  fineleancorpus)
    # No module column, so train/dev is split by row id. Note: train_qwen_mnrl_v2.py
    # does not drop rows whose Lean failed to compile.
    DATA_ARGS=(--dataset_name m-a-p/FineLeanCorpus
               --query_field statement --doc_field lean_code
               --key_field id --group_field id) ;;
  *) echo "Unknown CORPUS=$CORPUS (use frenzymath or fineleancorpus)" >&2; exit 1 ;;
esac

MODEL_TAG=$(basename "$MODEL" | tr '[:upper:]' '[:lower:]' | sed 's/qwen3-embedding-/qwen/')
RUN=${RUN:-mnrl_${MODEL_TAG}_${CORPUS}_r$((MAX_ROWS / 1000))k_ep${EPOCHS}}
OUT_DIR=$SCRATCH/math2vec_checkpoints/$RUN
CKPT_DIR=$SCRATCH/math2vec_checkpoints/ckpt_$RUN
mkdir -p "$REPO/logs" "$HF_HOME" "$HF_DATASETS_CACHE" "$HUGGINGFACE_HUB_CACHE" "$TORCH_HOME" "$TMPDIR" "$OUT_DIR" "$CKPT_DIR"

echo "RUN=$RUN MODEL=$MODEL CORPUS=$CORPUS MAX_ROWS=$MAX_ROWS EPOCHS=$EPOCHS BATCH_SIZE=$BATCH_SIZE"
echo "OUT_DIR=$OUT_DIR"
nvidia-smi --query-gpu=name,memory.total --format=csv

# ---- train ----
time python train_qwen_mnrl_v2.py \
  --device cuda \
  --model_name "$MODEL" \
  "${DATA_ARGS[@]}" \
  --wrap_query \
  --max_rows "$MAX_ROWS" \
  --epochs "$EPOCHS" \
  --batch_size "$BATCH_SIZE" \
  --max_seq_len "$MAX_SEQ_LEN" \
  --eval_batch_size "$EVAL_BATCH_SIZE" \
  --output_dir "$OUT_DIR" \
  --checkpoint_dir "$CKPT_DIR"

echo "Training metrics:"
cat "$OUT_DIR/metrics.json" || true

# ---- validate on 100 docstrings ----
# A failing check is reported but doesn't mark the job failed: the model is already saved.
if [ "$VALIDATE" = "1" ]; then
  time python validate_docstrings.py \
    --device cuda \
    --model_name "$OUT_DIR" \
    --out_dir "$OUT_DIR/docstring_validation" \
    || echo "Docstring validation did not pass. See $OUT_DIR/docstring_validation/report.json"
fi
