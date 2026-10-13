# Hackathon demo

The frozen demo presented for the DALAB May 2026 Lean Hackathon. Everything
here was produced by `demo.ipynb` running against the perturbation library in
`../src/`, and is preserved as-is for reference.

## Files

| File | Purpose |
|---|---|
| `demo.ipynb` | The notebook. Runs all 10 perturbation types on 10 curated theorems plus 8 chained combinations, then writes `demo_perturbations.jsonl`. |
| `demo_executed.ipynb` | The same notebook with cached cell outputs from the hackathon run. |
| `_generate_demo_notebook.py` | Regenerates `demo.ipynb` from a single source file. Run with `python _generate_demo_notebook.py` from this directory. |
| `demo_perturbations.jsonl` | 180 records from the demo run: 100 not-applicable + 80 with output (18 true · 27 false · 20 unknown). |
| `wiggle_dict.json` | Reference dictionary of every perturbation tactic, its mechanism, applicability, and truth-value semantics. Consumed by `index.html`. |
| `index.html` | Self-contained web viewer for any output JSONL. Open in a browser and upload `demo_perturbations.jsonl`. |

## Running the demo

From the project root (the directory containing `Wiggle.lean`):

```bash
jupyter notebook hackathon-demo/demo.ipynb
```

The notebook walks up the directory tree until it finds `Wiggle.lean`, so it
works from any CWD as long as it lives somewhere inside the project. It
imports `typeclass_mutate` and `bounds` from `../src/` and writes its output
back to `demo_perturbations.jsonl` in this directory.

Expected runtime: roughly 5–30 seconds per Lean call × ~160 Lean-invoking
calls = 15–80 minutes on a laptop.

## What is *not* here

This directory deliberately does **not** contain any of the scaling work
(parallel runner, HuggingFace push, dedup, evaluation metrics, embedder
training). That lives in `../pipeline/` and is under active development.
