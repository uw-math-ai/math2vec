# A1 Mathlib-docstrings fine-tuning experiment

Adds `a1_kept_concepts_v4.19.0.jsonl` (18,747 Mathlib v4.19.0 theorem/docstring
pairs) to the paper training recipe as **training-only** data, and compares
against the paper baseline on an identical dev set.

Target: Tillicum (UW Hyak), NVIDIA H200, Slurm.

## Run order

```bash
# 0. bootstrap on a login node (editing / installs / data movement only)
mkdir -p /gpfs/scrubbed/$USER/mathlib-ft && cd /gpfs/scrubbed/$USER/mathlib-ft
git clone -b trainingdata-mathlibdocstring https://github.com/uw-math-ai/math2vec.git repo
mkdir -p logs
bash repo/slurmscripts/a1_setup_login.sh 2>&1 | tee logs/setup.log

# 1. smoke test -- debug QOS, ~15-25 min, proves the --extra_train_jsonl path
sbatch a1_smoke.slurm

# 2. real runs -- ~8-10 GPU-hours each
sbatch --export=ALL,RUN=mv3_qwen8b_a1_ep2,EXTRA=data/a1_kept_concepts_v4.19.0.jsonl a1_run.slurm
sbatch --export=ALL,RUN=mv3_qwen8b_paper_ep2 a1_run.slurm   # baseline, same dev set
```

If `--account=mathai` is rejected, take the account from the setup script's
step 1 and add `--account=<account>` to the `sbatch` line. No script sets
`--partition`; Tillicum assigns it.

## Files

| File | QOS | What it does |
|---|---|---|
| `a1_setup_login.sh` | none (login node) | orient, workspace, conda env, data + overlap check, model cache |
| `a1_smoke.slurm` | `debug` | 0.6B / 2k rows / 1 epoch sanity check |
| `a1_run.slurm` | `normal` | paper recipe on Qwen3-Embedding-8B; `RUN` and `EXTRA` select the arm |

## How EXTRA is folded in

`--extra_train_jsonl` is applied **after** the module-level train/dev split
(seed 42), so the dev set and eval corpus are byte-identical with and without
it. Per `add_extra_train_records`:

- `concept_id` in dev -> dropped (dev-target leak)
- `module_name` is a dev module -> dropped (module-level leak)
- `concept_id` already in train -> its NL views are appended to that concept
- otherwise -> new training-only concept

Counts print as a line starting `[extra]` and are saved to
`metrics.json` under `counts.extra_train`.

## Reading the results

Primary metric is **NL -> Lean signature** Recall@1/5/10 and MRR@10.
`metrics.json` holds `baseline` / `finetuned` plus `*_per_pair_type` for all six
pair types.

A1 supplies only `nl_informal` and `lean_signature`. It has no `lean_type` or
`nl_informal_2`, so it can only move pair types 1 (NL -> Lean signature) and
6 (Lean signature -> NL informal). Expect types 2-5 to be roughly flat --
that is the data shape, not a bug.

## Monitoring

```bash
squeue -u $USER -o '%.10i %.14j %.8T %.10M %.6D %R'
tail -f logs/mv3_qwen8b_*.out
grep -E '^\[extra\]|Recall@|MRR@' logs/mv3_qwen8b_*.out
```

## Notes

- Scratch (`/gpfs/scrubbed`) is **not backed up** and is purged after 60 days
  without modification. Copy `metrics.json` and logs to
  `/gpfs/projects/mathai/math2vec/experiments/<name>/a1_docstrings/` when done.
- Env is Python 3.12: `numpy==2.0.2` / `scipy==1.13.1` have no 3.13 wheels.
- `Qwen3-Embedding-0.6B` is cached alongside the 8B because the smoke test
  needs it and compute nodes may have no internet.
