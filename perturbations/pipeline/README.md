# Pipeline

CLI runners for the Wiggle perturbation library (`src/wiggle/`).

The library does the work; scripts in this directory just wire it up to a
corpus (curated theorems, HuggingFace dataset slice, etc.) and an output file.

## Scripts

| File | Purpose |
|---|---|
| `run_demo.py` | Apply every perturbation in the registry to a curated set of 10 theorems. Outputs JSONL. |
| `run_hf_corpus.py` | Pull anchors from a HuggingFace dataset (`FrenzyMath/mathlib_informal_v4.19.0`), run perturbation chains, and write JSONL. |
| `prepare_blueprint_anchors.py` | Turn the leanblueprint scrape (`../dataset/blueprints.json`) into anchors for `run_benchmark_review.py --anchors-file`. |
| `run_benchmark_review.py` | Apply every perturbation once (one layer) to each anchor; writes `results.jsonl` and an audit `review.md`. `--skip-noncompiling` drops anchors that don't elaborate against plain Mathlib; `--resume` continues an interrupted run. |
| `mteb_perturbation_eval.py` | Score embedding models (default Qwen3-Embedding-8B and MiniLM) on `results.jsonl` as an MTEB reranking task: rank each anchor's equivalent rewrites above its meaning-changing variants. |
| `plot_eval.py` | Draw the diagrams and `summary.md` for a run directory. |

## Usage

```bash
# From the project root.
python pipeline/run_demo.py                              # curated theorems -> stdout JSONL
python pipeline/run_demo.py --output data/demo.jsonl     # ...or to a file

python pipeline/run_hf_corpus.py --limit 50              # 50 random anchors
python pipeline/run_hf_corpus.py --indices 5145,181597   # specific HF indices
```

Both scripts require `lake env lean` on `PATH`. The first run will compile the
Lean tactics in `Wiggle.lean`; subsequent runs reuse the cache under `.lake/`.

## How to add a new perturbation

You don't touch the runners. Instead:

1. Implement the transform in `src/wiggle/transforms/<layer>.py`.
2. Register it in `src/wiggle/registry.py` (`PERTURBATIONS` list).
3. Add a test in `tests/test_<perturbation>.py`.

The runners pick it up automatically from the registry.
