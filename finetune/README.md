# Multi-View Contrastive Fine-tuning for Mathematical Retrieval

Fine-tuning code for Text Embeddings of Theorems from Mathematics. We fine-tune `Qwen/Qwen3-Embedding-8B`
on mathlib4 concepts using multi-view contrastive learning.

The final model uses `n_hard_negs = 0` based on the ablation findings:
**multi-view contrastive supervision alone improves all six retrieval
directions; adding LLM-generated hard negatives degrades same-modality
retrieval.**

## Quick start

Reproduce the final model:

```bash
# 1. Setup
git clone <repo>
cd mathlib-ft
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Download dataset
# Hosted on HuggingFace:
#   <org>/<dataset-name> (raw and judge-filtered configs)
# Default merge_all_v1.jsonl is the raw 133,621-concept set.

# 3. Train (final model, n_HN=0)
sbatch slurm/run_mnrl_mv_133k_v3_hn0.slurm

# 4. Evaluate on MIRB
sbatch slurm/run_qwen8b_v3_hn0.slurm
```

Training takes ~6h on a single H200 GPU.

## Dataset

We use `merge_all_v1.jsonl`, a derivative of
[FrenzyMath/mathlib_informal_v4.19.0](https://huggingface.co/datasets/FrenzyMath/mathlib_informal_v4.19.0)
enriched with:

- **LLM-generated rephrasings** (`nl_informal_2`, ~85% of concepts)
- **LLM-generated hard negatives** (3 per concept) via hypothesis/conclusion
  substitution
- **Statement decomposition** (hypotheses, conclusions, normalized form)

### Schema (per concept)

| Field | Description |
|---|---|
| `concept_id` | mathlib identifier (e.g., `Set.inv_zero`) |
| `views.nl_informal` | informal NL description |
| `views.nl_informal_2` | LLM-generated NL rephrasing (optional) |
| `views.lean_type` | Lean 4 type signature |
| `views.lean_signature` | full Lean 4 declaration |
| `hard_negatives.nl` | 3 NL hard negatives |
| `hard_negatives.lean` | (currently empty for most) |
| `metadata.kind` | theorem / lemma / definition |
| `metadata.module_name` | mathlib module path |

### Quality validation

An LLM judge evaluated rephrasings and a subsample of HN. Summary:

- **Rephrasings**: 85.84% equivalent (good), 11.68% not equivalent, rest under/null
- **Hard negatives** (6000 sampled): 78.38% true negatives, 11.78% false negatives
  (equivalent to positive), 96.68% of statements retain ≥1 true HN

The HuggingFace release includes raw and judge-filtered configs.

## Training

### Loss

We use `CachedMultipleNegativesRankingLoss` (Gao et al., 2021) — in-batch
contrastive loss with symmetric cross-entropy over scaled cosine similarities
(scale = 20.0, τ = 0.05). The cached variant chunks forward passes to fit
batch_size = 16 on Qwen3-Embedding-8B within H200 memory.

### Multi-view base loader

Each training step samples a random (anchor, positive) pair from the four
views of a randomly-chosen concept, implicitly covering all six retrieval
directions across NL and Lean modalities.

### Train/dev split

Module-level group split (seed = 42, dev_frac = 0.1) yielding 118,334 train
and 15,287 dev concepts. Splitting by mathlib module rather than by
concept prevents leakage of structurally related theorems.

### Key training args

```bash
python train_qwen_mnrl_multiview_v3.py \
  --local_jsonl /path/to/merge_all_v1.jsonl \
  --model_name Qwen/Qwen3-Embedding-8B \
  --wrap_query \
  --epochs 2 \
  --batch_size 16 \
  --hard_neg_batch_size 16 \
  --n_hard_negs {0|1|3} \
  --max_seq_len 128 \
  --warmup_steps 700 \
  --loss cached \
  --output_dir checkpoints/<name>
```

Full args: `python train_qwen_mnrl_multiview_v3.py --help`



## Evaluation

### In-domain (six retrieval directions, on held-out 15,287 dev concepts)

Run automatically at end of training. Results in
`<output_dir>/metrics.json`.

R@1 Δ (FT − Base) summary:

| Direction | hn0 | hn1 | hn3 |
|---|---|---|---|
| NL → Lean type | +0.169 | **+0.172** | +0.149 |
| NL → Lean sig (primary) | +0.109 | **+0.113** | +0.090 |
| NL rephrase → Lean sig | +0.119 | **+0.132** | +0.104 |
| Lean type → Lean sig | **+0.127** | +0.123 | +0.091 |
| NL rephrase → NL informal | **+0.069** | −0.010 | −0.072 |
| Lean sig → NL informal | **+0.197** | +0.026 | −0.092 |
| **Mean Δ** | **+0.132** | +0.096 | +0.012 |


### AMP (cross-presentation equivalence, paper-introduced)

[TBD: link to AMP eval script + numbers]



## File layout

```
mathlib-ft/
├── train_qwen_mnrl_multiview.py   # main training + in-domain eval
├── checkpoints/                   # trained models
├── logs/
├── requirement.txt
└── README.md
```

MIRB benchmarking lives in a separate directory with its own venv to avoid dependency conflicts with the training environment.

## Compute requirements

- 1 × H200 GPU (140GB VRAM) per training run
- ~48GB system RAM, 4 CPUs
- ~50GB disk per checkpoint

## Citation

```bibtex
[TBD on paper acceptance]
```

## Acknowledgments

Built on FrenzyMath/mathlib_informal_v4.19.0. Uses sentence-transformers
(Reimers & Gurevych) and CachedMNRL (Gao et al.).
