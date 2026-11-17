# A1 Mathlib-docstrings fine-tuning experiment

Adds `a1_kept_concepts_v4.19.0.jsonl` (18,747 Mathlib v4.19.0 theorem/docstring
pairs) to the paper training recipe as **training-only** data, and compares
against the paper baseline on an identical dev set.

Target: Tillicum (UW Hyak), NVIDIA H200, Slurm.

**This is the current experiment: a 2-arm comparison.**

| Arm | RUN | Trains on |
|---|---|---|
| Paper baseline | `mv3_qwen8b_paper_ep2` | MathlibViews.jsonl (133,621 concepts) |
| + A1 docstrings | `mv3_qwen8b_a1_ep2` | MathlibViews.jsonl **+ A1 added to training only** |

Both start from stock `Qwen/Qwen3-Embedding-8B`, use the identical recipe, and
share a byte-identical dev set. The only difference is the extra training data,
which is what makes the comparison mean anything. ~8.3 h and ~$7.50 per arm.

> **New to this experiment?** Read `a1_EXPERIMENT_SUMMARY.md` first -- it
> explains what the two arms are, how the overlapping theorems are handled, and
> how to read the results. This file is the operational how-to.

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
| `a1_collect.sh` | none (login node) | wall time, GPU-hours, `[extra]` counts; `--archive` copies results to the project folder |
| `a1_report.py` | none (CPU) | builds the comparison tables from `metrics.json` |
| `a1_eval_checkpoint.py` | - | optional re-eval, imports the trainer's own eval functions |
| `a1_eval.slurm` | `normal` | GPU wrapper for `a1_eval_checkpoint.py` |

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

## Getting the results after the job finishes

The trainer evaluates the **base model and the fine-tuned model itself** and
writes both into `checkpoints/<RUN>/metrics.json`. You do not need to run a
separate eval for the primary comparison.

```bash
cd /gpfs/scrubbed/$USER/mathlib-ft

# 1. is it done?
squeue -u $USER -o '%.10i %.14j %.8T %.10M %.6D %R'
grep -l "RUN=mv3_qwen8b_a1_ep2" logs/*.out     # both arms share the job name
tail -f logs/mv3_qwen8b_*.out

# 2. wall time, GPU-hours, [extra] counts -> writes runinfo.json
bash repo/slurmscripts/a1_collect.sh mv3_qwen8b_a1_ep2

# 3. the tables (CPU, instant)
python repo/slurmscripts/a1_report.py checkpoints/mv3_qwen8b_a1_ep2

# 4. once the baseline arm also finishes, the real comparison
python repo/slurmscripts/a1_report.py \
  checkpoints/mv3_qwen8b_paper_ep2 checkpoints/mv3_qwen8b_a1_ep2

# 5. markdown for the writeup
python repo/slurmscripts/a1_report.py --markdown \
  checkpoints/mv3_qwen8b_paper_ep2 checkpoints/mv3_qwen8b_a1_ep2 > results.md

# 6. archive to the backed-up project folder (scratch is purged after 60 days)
bash repo/slurmscripts/a1_collect.sh --archive \
  mv3_qwen8b_a1_ep2 mv3_qwen8b_paper_ep2
```

`a1_report.py` prints a **dev-set identity check** first: both arms must show the
same `concepts_total` / `train` / `dev` / `n_dev_used` / `corpus_size`. If they
do not, it says so loudly and the cross-run comparison is invalid -- that is the
one result worth checking before you believe any delta.

### Optional: re-eval a saved model on a GPU

`a1_eval_checkpoint.py` + `a1_eval.slurm` re-run the eval against a saved model,
importing `eval_retrieval` / `eval_all_pair_types` / `group_split_records` from
the trainer so numbers stay comparable. Only needed for a mid-training
checkpoint, a different `k`, a different concept file, or a run that died after
training but before eval.

```bash
sbatch --export=ALL,RUN=mv3_qwen8b_a1_ep2 a1_eval.slurm
sbatch --export=ALL,RUN=mv3_qwen8b_a1_ep2,PRIMARY_ONLY=1 a1_eval.slurm
```

The split is reproducible because `group_split_records` shuffles the sorted
module list with `random.Random(seed)`, so the same data + seed + dev_frac +
max_rows always gives the same dev set. `EXTRA` is applied after the split and
never changes it.

## Possible follow-on

`PROPOSAL_explicit_view_pairs.md` sketches a *possible later* run on this same
A1 dataset: enumerate view pairs explicitly instead of sampling two views at
random per epoch. **An idea only -- not solidified, not scheduled, and not the
run described above.**

## Known wrinkle

`a1_run.slurm` keeps `--job-name=mv3_qwen8b` from `run_v3.slurm`, so both arms
log to `logs/mv3_qwen8b_<jobid>.out` and cannot be told apart by filename.
`a1_collect.sh` resolves the right log by grepping for the `RUN=` line the
script echoes. To avoid the ambiguity on future submissions, override the name:

```bash
sbatch --job-name=mv3_qwen8b_a1_ep2 \
  --export=ALL,RUN=mv3_qwen8b_a1_ep2,EXTRA=data/a1_kept_concepts_v4.19.0.jsonl \
  a1_run.slurm
```

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
