# Pipeline

CLI runners for the Wiggle perturbation library (`src/wiggle/`).

The library does the work; scripts in this directory just wire it up to a
corpus (curated theorems, HuggingFace dataset slice, etc.) and an output file.

## Scripts

| File | Purpose |
|---|---|
| `run_demo.py` | Apply every perturbation in the registry to a curated set of 10 theorems. Mirrors what `hackathon-demo/demo.ipynb` did, but as plain Python. Outputs JSONL. |
| `run_hf_corpus.py` | Pull anchors from a HuggingFace dataset (`FrenzyMath/mathlib_informal_v4.19.0`), run perturbation chains, and write JSONL. Replacement for the archived `hackathon-demo/perturb.ipynb`. |

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

## What was here before

`perturb.ipynb` used to live in this directory as a notebook prototype. It has
been moved to `hackathon-demo/perturb.ipynb` as a frozen artifact of the
hackathon. All active work has moved to plain Python files.
