# Qwen3 Embedding Fine-tuning — Mathlib Informal Retrieval

Fine-tunes a sentence embedding model (`Qwen/Qwen3-Embedding-8B` by default) on the task of retrieving Lean theorem signatures from informal math descriptions, using Multiple Negatives Ranking Loss (MNRL) with in-batch negatives.

---

## Overview

Given an informal math description (query), the model learns to retrieve the corresponding Lean 4 theorem signature (document) from the Mathlib corpus. Training uses `CachedMultipleNegativesRankingLoss`, which treats every other example in the batch as a negative.

The pipeline does the following in one run:

1. Load `FrenzyMath/mathlib_informal_v4.19.0` from HuggingFace
2. Deduplicate pairs and split train/dev by Lean **module** (to avoid leakage)
3. Evaluate the base model (Recall@1/5/10, MRR@10)
4. Fine-tune with MNRL
5. Evaluate the fine-tuned model on the same dev set
6. Save the model and a `metrics.json` summary

---

## Requirements

```bash
pip install sentence-transformers datasets torch numpy
pip install faiss-gpu   # optional but recommended for faster eval
```

Python 3.9+ required. For the 8B model you need at least one GPU with ~24 GB VRAM (e.g. A100 40G, or two 3090s).

---

## Quick start (interactive)

```bash
python train_qwen_mnrl_v2.py \
    --wrap_query \
    --output_dir checkpoints/qwen3_mathlib \
    --checkpoint_dir checkpoints/ckpt_qwen3_mathlib
```

This runs with all defaults: full dataset, 1 epoch, batch size 64, max seq len 128.

For a quick smoke test on a small subset first:

```bash
python train_qwen_mnrl_v2.py \
    --max_rows 2000 \
    --epochs 1 \
    --batch_size 32 \
    --wrap_query \
    --output_dir checkpoints/smoke_test
```

---

## All arguments

### Dataset

| Argument | Default | Description |
|---|---|---|
| `--dataset_name` | `FrenzyMath/mathlib_informal_v4.19.0` | HuggingFace dataset to load |
| `--subset` | `default` | Dataset config/subset name |
| `--split` | `train` | Which split to load |
| `--max_rows` | `None` (all) | Cap number of rows, useful for debugging |
| `--query_field` | `informal_description` | Column used as the query |
| `--doc_field` | `signature` | Column used as the document |
| `--key_field` | `index` | Column used as the example key |
| `--group_field` | `module_name` | Column used for group-based train/dev split |

### Model

| Argument | Default | Description |
|---|---|---|
| `--model_name` | `Qwen/Qwen3-Embedding-8B` | Base model to fine-tune (HF model ID or local path) |
| `--output_dir` | `checkpoints/mnrl_mathlib_informal` | Where to save the final fine-tuned model |
| `--device` | `None` (auto) | Force a device, e.g. `cuda:0` |

### Query / document wrapping

| Argument | Default | Description |
|---|---|---|
| `--wrap_query` | off | Prepend instruction prefix to queries (recommended) |
| `--wrap_doc` | off | Prepend `--doc_prefix` to documents |
| `--doc_prefix` | `Document` | Prefix string used when `--wrap_doc` is set |
| `--instruction` | *(see below)* | Instruction text prepended to each query when `--wrap_query` is set |

Default instruction:
```
Retrieve the corresponding Lean theorem statement for the given informal math description.
```

### Data split

| Argument | Default | Description |
|---|---|---|
| `--seed` | `42` | Random seed for reproducibility |
| `--dev_frac` | `0.1` | Fraction of **modules** (not rows) to hold out as dev |

### Training

| Argument | Default | Description |
|---|---|---|
| `--epochs` | `1` | Number of training epochs |
| `--batch_size` | `64` | Training batch size (larger = more in-batch negatives = harder task) |
| `--max_seq_len` | `128` | Max token length for both queries and documents |
| `--warmup_steps` | `200` | Linear warmup steps |

### Evaluation

| Argument | Default | Description |
|---|---|---|
| `--k_eval` | `10` | Primary k for Recall@k and MRR@k (Recall@1 and @5 are always reported too) |
| `--eval_batch_size` | `256` | Batch size for encoding during eval |

### Checkpoints

| Argument | Default | Description |
|---|---|---|
| `--checkpoint_dir` | `checkpoints/ckpt_mnrl_mathlib_informal` | Directory for intermediate checkpoints |
| `--checkpoint_save_steps` | `2000` | Save a checkpoint every N steps |

---

## Output files

After a run, `--output_dir` will contain:

```
checkpoints/qwen3_mathlib/
├── config.json               # model config
├── tokenizer_config.json
├── tokenizer.json
├── special_tokens_map.json
├── pytorch_model.bin         # (or model.safetensors)
└── metrics.json              # eval results + run config
```

`metrics.json` example:

```json
{
  "baseline": { "recall@1": 0.12, "recall@5": 0.31, "recall@10": 0.41, "mrr@10": 0.21 },
  "finetuned": { "recall@1": 0.34, "recall@5": 0.57, "recall@10": 0.65, "mrr@10": 0.44 },
  "config": { ... },
  "counts": { "pairs_total": 98432, "train": 88600, "dev": 9832 }
}
```

---

## Submitting a SLURM job

Save the script below as `submit_finetune.sh` in the project root. The structure mirrors jobs we have run on this cluster before.

```bash
#!/bin/bash
#SBATCH --job-name=cached_4b
#SBATCH --qos=normal
#SBATCH --gpus=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH -o logs/%x_%j.out          # logs/<job-name>_<job-id>.out

set -euo pipefail

cd /gpfs/scrubbed/$USER/mathlib-ft
source .venv/bin/activate

# Point all HuggingFace / torch caches to scrubbed storage
export HF_HOME=/gpfs/scrubbed/$USER/hf_cache
export HF_DATASETS_CACHE=$HF_HOME/datasets
export TRANSFORMERS_CACHE=$HF_HOME/transformers
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export TORCH_HOME=$HF_HOME/torch
export XDG_CACHE_HOME=$HF_HOME
export TMPDIR=/gpfs/scrubbed/$USER/tmp
export TOKENIZERS_PARALLELISM=false

mkdir -p "$HF_HOME" "$HF_DATASETS_CACHE" "$TRANSFORMERS_CACHE" \
         "$HUGGINGFACE_HUB_CACHE" "$TORCH_HOME" "$TMPDIR" logs

python train_qwen_mnrl_v2.py \
  --device cuda \
  --model_name Qwen/Qwen3-Embedding-4B \
  --wrap_query \
  --epochs 1 \
  --batch_size 16 \
  --max_seq_len 128 \
  --eval_batch_size 8 \
  --output_dir checkpoints/mnrl_qwen4b \
  --checkpoint_dir checkpoints/ckpt_mnrl_qwen4b
```

Submit and monitor:

```bash
mkdir -p logs
sbatch submit_finetune.sh

squeue -u $USER                          # check job status
tail -f logs/cached_4b_<job_id>.out      # stream stdout live
```

### Adjusting the job for different experiments

**Quick smoke test** — add `--max_rows 10000` to cap the dataset and verify the job runs end to end before committing to a full run:
```bash
  --max_rows 10000 \
```

**Longer / fuller run** — increase epochs and remove the row cap:
```bash
  --epochs 3 \
```
Also bump `--time` accordingly, e.g. `06:00:00` for 3 epochs on the full dataset.

**8B model** — swap the model name and request more memory:
```bash
#SBATCH --mem=64G
  --model_name Qwen/Qwen3-Embedding-8B \
  --batch_size 8 \         # reduce if OOM
  --eval_batch_size 4 \
```

**OOM during training** — reduce `--batch_size` first (try 8, then 4). Note that smaller batches mean fewer in-batch negatives, which makes the training signal weaker. Reducing `--max_seq_len` to 64 is the next lever.

**Resuming from a checkpoint** — if a job times out mid-run, point `--model_name` at the latest checkpoint step directory:
```bash
  --model_name checkpoints/ckpt_mnrl_qwen4b/<step_number> \
```

**Shared cache** — the `HF_HOME` exports above point each user's cache to their own scrubbed directory. If you want to share a single downloaded copy of the base model across the group, change `HF_HOME` to a shared path everyone can read, e.g. `/gpfs/scrubbed/shared/hf_cache`.

---

## Reproducing a run

All hyperparameters are saved in `metrics.json` under the `config` key, so any run is fully reproducible:

```bash
python train_qwen_mnrl_v2.py $(python -c "
import json, sys
cfg = json.load(open('checkpoints/qwen3_mnrl_run1/metrics.json'))['config']
flags = []
for k, v in cfg.items():
    if isinstance(v, bool):
        if v: flags.append(f'--{k}')
    elif v is not None:
        flags.append(f'--{k} {v}')
print(' '.join(flags))
")
```
