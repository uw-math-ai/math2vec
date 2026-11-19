#!/bin/bash
# ---------------------------------------------------------------------------
# MathLibDocstrings-docstrings experiment -- LOGIN NODE SETUP. No GPU, no sbatch.
# Steps: orient, workspace, conda env, data + overlap check, model cache.
# Idempotent; only touches /gpfs/scrubbed/$USER.
#
# Bootstrap (from a Tillicum login node):
#   mkdir -p /gpfs/scrubbed/$USER/mathlib-ft && cd /gpfs/scrubbed/$USER/mathlib-ft
#   git clone -b trainingdata-mathlibdocstring \
#     https://github.com/uw-math-ai/math2vec.git repo
#   bash repo/finetune/MathLibDocstrings/setup_login.sh 2>&1 | tee logs/setup.log
# ---------------------------------------------------------------------------
set -euo pipefail

WORK=/gpfs/scrubbed/$USER/mathlib-ft
ENVDIR=/gpfs/scrubbed/$USER/conda-envs/mathlib-ft
BRANCH=trainingdata-mathlibdocstring
DOCSTRINGS_FILE=MathLibDocstrings_v4.19.0.jsonl
DOCSTRINGS_SRC=repo/dataset/MathLibDocstrings/$DOCSTRINGS_FILE
DOCSTRINGS_SHA=da823e1476c4b1b6dee9ba1efeaa320768ab5605f2b61796001828dc917345d3

echo "############ 1. ORIENT ############"
echo "user: $(whoami)"
echo "--- account,qos : USE THIS ACCOUNT IF 'mathai' IS REJECTED ---"
sacctmgr -nP show assoc user=$USER format=account,qos || echo "sacctmgr unavailable"
echo "--- /gpfs/projects/mathai/math2vec ---"
ls -la /gpfs/projects/mathai/math2vec || echo "cannot list shared project dir"

echo; echo "############ 2. WORKSPACE ############"
mkdir -p "$WORK"/{data,logs}
cd "$WORK"
if [ -d repo/.git ]; then
  git -C repo fetch origin "$BRANCH"
  git -C repo checkout "$BRANCH"
  git -C repo pull --ff-only
else
  git clone -b "$BRANCH" https://github.com/uw-math-ai/math2vec.git repo
fi
cp repo/finetune/train_qwen_mnrl_multiview_v3_tg.py .
cp repo/finetune/MathLibDocstrings/smoke.slurm repo/finetune/MathLibDocstrings/run.slurm .
echo "repo at $(git -C repo rev-parse --short HEAD) on $(git -C repo rev-parse --abbrev-ref HEAD)"
ls -la "$WORK"

echo; echo "############ 3. ENVIRONMENT ############"
module load conda/Miniforge3-25.3.1-3
if [ ! -d "$ENVDIR" ]; then
  # python 3.12: numpy==2.0.2 / scipy==1.13.1 in requirements.txt have no 3.13 wheels
  conda create -y -p "$ENVDIR" python=3.12
else
  echo "env exists: $ENVDIR"
fi
set +u; conda activate "$ENVDIR"; set -u
export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
python -m pip install --upgrade pip
python -m pip install -r repo/finetune/requirements.txt
python -c "import torch, sentence_transformers; print('torch', torch.__version__, '| ST', sentence_transformers.__version__)"

echo; echo "############ 4. DATA ############"
cd "$WORK"
cp -n "$DOCSTRINGS_SRC" "data/$DOCSTRINGS_FILE"
echo "$DOCSTRINGS_SHA  data/$DOCSTRINGS_FILE" | sha256sum -c -

if [ ! -f data/MathlibViews.jsonl ]; then
  if [ -f /gpfs/projects/mathai/math2vec/MathlibViews.jsonl ]; then
    echo "copying MathlibViews.jsonl from shared project folder"
    cp /gpfs/projects/mathai/math2vec/MathlibViews.jsonl data/
  else
    echo "not in project folder; downloading 387 MB from Hugging Face"
    huggingface-cli download uw-math-ai/Math2Vec-embedding-dataset MathlibViews.jsonl \
      --repo-type dataset --local-dir data/
  fi
fi
ls -la data/

echo; echo "--- schema + overlap check (no GPU) ---"
python - <<'PY'
import json
def load(p):
    ids=set(); mods=set(); n=0
    with open(p) as f:
        for line in f:
            r=json.loads(line); n+=1
            ids.add(r["concept_id"])
            mods.add(r.get("metadata",{}).get("module_name",""))
    return ids, mods, n
b,bm,bn = load("data/MathlibViews.jsonl")
a,am,an = load("data/MathLibDocstrings_v4.19.0.jsonl")
print(f"base : rows={bn:,} unique_ids={len(b):,} modules={len(bm):,}")
print(f"MathLibDocstrings   : rows={an:,} unique_ids={len(a):,} modules={len(am):,}")
print(f"MathLibDocstrings ids ALREADY in base : {len(a&b):,} ({100*len(a&b)/len(a):.1f}%) -> merge as extra NL views")
print(f"MathLibDocstrings ids NEW to base     : {len(a-b):,} ({100*len(a-b)/len(a):.1f}%) -> new training concepts")
print(f"MathLibDocstrings modules also in base: {len(am&bm):,} / {len(am):,}")
print(f"MathLibDocstrings module_name NOT 'Mathlib.*': {sum(1 for m in am if not m.startswith('Mathlib.'))}")
print("\nNOTE: the NEW-to-base share drives runtime. 0% -> ~8 h, 100% -> ~9.3 h.")
for p in ("data/MathlibViews.jsonl","data/MathLibDocstrings_v4.19.0.jsonl"):
    print(f"\n===== 2 rows of {p} =====")
    with open(p) as f:
        for _ in range(2):
            print(json.dumps(json.loads(f.readline()), indent=2, ensure_ascii=False)[:800])
PY

echo; echo "############ 5. MODEL CACHE ############"
export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
huggingface-cli download Qwen/Qwen3-Embedding-0.6B   # smoke test
huggingface-cli download Qwen/Qwen3-Embedding-8B     # real run
du -sh "$HF_HOME"

echo; echo "SETUP DONE. Next:  cd $WORK && sbatch smoke.slurm"
