# Multi-View Contrastive Fine-tuning for Mathematical Retrieval

Multi-view contrastive fine-tuning of `Qwen/Qwen3-Embedding-8B` on mathlib4 
concepts. Code for Does My Embedding Reflect That \(A = B\)? Evaluating Mathematical Equivalence in Embedding Models.

## Quick start

Reproduce the final model (~6h on a single H200):

```bash
# Setup
git clone <repo>
cd fintune
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Download
https://anonymous-hf.up.railway.app/a/xczmsjlqejkf/
```

The script auto-runs in-domain evaluation at the end of training and writes 
results to `<output_dir>/metrics.json`.

## Training

### Loss

`CachedMultipleNegativesRankingLoss` (Gao et al., 2021) — in-batch contrastive 
loss with scaled cosine similarities (scale = 20, τ = 0.05). The cached 
variant chunks forward passes so 8B models fit at batch_size = 16 on a 
single H200.

### Multi-view contrastive

Each mathlib concept in the dataset has up to four views:
- `nl_informal` — informal NL description
- `nl_informal_2` — LLM-generated NL rephrasing
- `lean_type` — Lean 4 type signature
- `lean_signature` — full Lean 4 declaration

The base data loader samples random view pairs per concept, implicitly 
covering six retrieval directions across NL and Lean modalities.

### Train/dev split

Module-level group split (seed = 42, dev_frac = 0.1) yielding 118,334 train 
and 15,287 dev concepts. Splitting by mathlib module prevents leakage of 
structurally related theorems.

## Running the training

Minimal command:

```bash
python train_qwen_mnrl_multiview.py \
  --local_jsonl data/merge_all_v1.jsonl \
  --model_name Qwen/Qwen3-Embedding-8B \
  --wrap_query \
  --epochs 2 \
  --batch_size 16 \
  --max_seq_len 128 \
  --warmup_steps 700 \
  --loss cached \
  --output_dir checkpoints/math2vec_8b
```

Full args: `python train_qwen_mnrl_multiview.py --help`.

### Important args

| Arg | Default | Notes |
|---|---|---|
| `--local_jsonl` | — | path to dataset JSONL |
| `--model_name` | `Qwen/Qwen3-Embedding-8B` | base model |
| `--wrap_query` | off | wrap queries with instruction template |
| `--epochs` | 1 | recommend 2 for the full 133k dataset |
| `--batch_size` | 64 | use 16 for 8B models on H200 |
| `--max_seq_len` | 128 | mathlib statements rarely need more |
| `--warmup_steps` | 200 | scale with total steps (~5% is good) |
| `--loss` | `cached` | use `plain` only on CPU for smoke tests |
| `--seed` | 42 | identical seed across runs keeps dev set stable |
| `--dev_frac` | 0.1 | held-out fraction by mathlib module |

Ablation knobs (see paper Appendix for details and results):

| Arg | Default |
|---|---|
| `--n_hard_negs` | 3 |
| `--hard_neg_batch_size` | 16 |

## Evaluation

In-domain six-direction R@1 / R@5 / MRR@10 runs automatically at the end 
of training. Results go to `<output_dir>/metrics.json`.

For OOD evaluation on MIRB, see the separate `mirb/` directory (different 
venv to avoid dependency conflicts):

```bash
cd mirb/
source .venv/bin/activate
python run_qwen8b.py --model_path <path-to-trained-checkpoint>
```

## Compute requirements

- 1 × GPU with ≥ 80GB VRAM (H100 / H200 / A100-80GB)
- ~48GB system RAM
- ~50GB disk per checkpoint
- ~6h for the final config on H200

For lower-memory GPUs, reduce `--batch_size` and reduce `--hard_neg_batch_size` 
correspondingly.

## Reproducibility

All runs use `--seed 42` and `--dev_frac 0.1` by default, which produces 
the identical 15,287-concept held-out dev set used in the paper. Changing 
either of these will change the split.

## Released models

The final model and ablation variants are available on HuggingFace:

- **Final model**: [Qwen]( https://anonymous-hf.up.railway.app/a/pv25ongyl2qb/)
[Octen]( https://anonymous-hf.up.railway.app/a/9n9cngyu38hk/)
- Ablations: see paper Appendix for full results

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("uw-math-ai/Math2Vec-Embedding-8B")
```

## File layout

```
finetune/
├── train_qwen_mnrl_multiview.py   # main training + in-domain eval
├── requirements.txt
└── README.md
```

## License

Apache 2.0.

## Acknowledgments

Built on FrenzyMath/mathlib_informal_v4.19.0. Uses sentence-transformers
(Reimers & Gurevych) and CachedMNRL (Gao et al.).
