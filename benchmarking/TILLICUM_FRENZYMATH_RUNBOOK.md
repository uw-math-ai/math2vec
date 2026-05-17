# Tillicum FrenzyMath Runbook

This runbook is the exact operational guide for running the FrenzyMath benchmark
matrix on Tillicum for the current model list.

It is intentionally concrete. Every shell command below is meant to be pasted
directly into a terminal on Tillicum unless explicitly labeled otherwise.

## What One Job Measures

Each submitted job fixes exactly one Lean-side modality:

- `type`
- `signature`

and runs both retrieval directions for that same modality:

- `informal_to_lean`
- `lean_to_informal`

This is correct for instruction-aware models because the benchmark uses
different query prompts for the two directions and re-encodes the query side
separately for each direction.

For `lean_field=type`, the default query prompts are:

- `informal_to_lean`:
  `Instruct: Find the most mathematically similar Lean type to this statement`
- `lean_to_informal`:
  `Instruct: Find the most mathematically similar statement as a Lean type`

For `lean_field=signature`, the default query prompts are:

- `informal_to_lean`:
  `Instruct: Find the most mathematically similar Lean signature to this statement`
- `lean_to_informal`:
  `Instruct: Find the most mathematically similar statement as a Lean signature`

Within one job:

- the corpus informal embeddings are encoded once without a query prompt
- the corpus Lean embeddings are encoded once without a query prompt
- the query informal embeddings are encoded once with the direction-specific
  `informal_to_lean` prompt
- the query Lean embeddings are encoded once with the direction-specific
  `lean_to_informal` prompt

So a `type` job computes:

- natural language query embeddings for `natural -> type`
- type query embeddings for `type -> natural`
- type corpus embeddings
- natural-language corpus embeddings

and a `signature` job computes the analogous four artifacts for signature.

## Fixed Benchmark Configuration

Unless you intentionally override it, the benchmark matrix here uses:

- dataset: `saharshb/mathlib-informal-split`
- query split: `test`
- retrieval corpus splits: `train,val,test`
- normalization: enabled
- retrieval backend: exact inner product on normalized embeddings
- saved rankings: enabled
- saved manifests: enabled
- saved embeddings: enabled
- saved embedding dtype on disk: `float16`

Outputs per successful run:

- `config.json`
- `invocation.json`
- `run.log`
- `results.json`
- `summary.json`
- `query_manifest.jsonl`
- `corpus_manifest.jsonl`
- `rankings.json`
- one or more `*.npy` embedding files

## Where to Run the Commands

All shell commands in this file should be run:

1. after logging into Tillicum
2. from the repository root:
   `/gpfs/projects/mathai/math2vec`

To get there:

```bash
cd /gpfs/projects/mathai/math2vec
```

## One-Time Session Setup

Run each of the following shell commands exactly once per login session.

Command:

```bash
cd /gpfs/projects/mathai/math2vec
```

What it does:

- moves you into the repository root

Command:

```bash
module load conda
```

What it does:

- loads the Conda module on Tillicum

Command:

```bash
conda activate /gpfs/projects/mathai/math2vec/envs/math2vec
```

What it does:

- activates the benchmark environment used by the Slurm jobs

Command:

```bash
mkdir -p /gpfs/projects/mathai/math2vec/runs/$USER/frenzymath
```

What it does:

- creates the directory where benchmark run folders will be written

Command:

```bash
mkdir -p /gpfs/projects/mathai/math2vec/logs/frenzymath
```

What it does:

- creates the directory where Slurm stdout logs will be written

Command:

```bash
mkdir -p /gpfs/projects/mathai/math2vec/hf_cache /gpfs/projects/mathai/math2vec/hf_cache/hub /gpfs/projects/mathai/math2vec/hf_cache/transformers /gpfs/projects/mathai/math2vec/st_cache
```

What it does:

- creates shared cache directories for Hugging Face and sentence-transformers

Command:

```bash
export HF_HOME=/gpfs/projects/mathai/math2vec/hf_cache
```

What it does:

- points the Hugging Face home cache to project storage

Command:

```bash
export HUGGINGFACE_HUB_CACHE=/gpfs/projects/mathai/math2vec/hf_cache/hub
```

What it does:

- points the hub cache to project storage

Command:

```bash
export TRANSFORMERS_CACHE=/gpfs/projects/mathai/math2vec/hf_cache/transformers
```

What it does:

- points the Transformers model cache to project storage

Command:

```bash
export SENTENCE_TRANSFORMERS_HOME=/gpfs/projects/mathai/math2vec/st_cache
```

What it does:

- points the sentence-transformers cache to project storage

## Choose Full Runs or 100-Query Test Runs

You must choose one of the following two shell commands.

If you want full held-out benchmark runs:

```bash
unset MAX_QUERY_ITEMS
```

If you want 100-query test runs comparable to the earlier Harrier pilot:

```bash
export MAX_QUERY_ITEMS=100
```

Meaning:

- if `MAX_QUERY_ITEMS` is unset, each run uses the full `test` query split
- if `MAX_QUERY_ITEMS=100`, each run uses only the first 100 test queries
- in both cases, the retrieval corpus still defaults to `train,val,test`

## Submit the Whole Model Matrix

This repository includes a submission helper script:

- file:
  `/gpfs/projects/mathai/math2vec/slurmscripts/submit_frenzymath_model_matrix.sh`

It submits:

- one `type` job and one `signature` job per model
- both directions inside each job
- skips a submission if an exactly matching successful run already exists in
  the configured results directory

Command:

```bash
bash /gpfs/projects/mathai/math2vec/slurmscripts/submit_frenzymath_model_matrix.sh
```

What it does:

- submits up to 12 Slurm jobs
- each job requests `1` GPU and `8` CPUs
- each job writes a Slurm log to:
  `/gpfs/projects/mathai/math2vec/logs/frenzymath`
- each job writes benchmark outputs to:
  `/gpfs/projects/mathai/math2vec/runs/$USER/frenzymath`
- jobs are skipped if `config.json` and `results.json` show a matching prior
  successful run

## Exactly Which Jobs Are Submitted

The helper script submits these exact configurations.

### Harrier 0.6B type

- model name: `microsoft/harrier-oss-v1-0.6b`
- lean field: `type`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `32`
- dtype flag: `--dtype bfloat16`
- time limit: `04:00:00`

### Harrier 0.6B signature

- model name: `microsoft/harrier-oss-v1-0.6b`
- lean field: `signature`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `32`
- dtype flag: `--dtype bfloat16`
- time limit: `04:00:00`

### Qwen3-Embedding-4B type

- model name: `Qwen/Qwen3-Embedding-4B`
- lean field: `type`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `12`
- dtype flag: `--dtype bfloat16`
- time limit: `08:00:00`

### Qwen3-Embedding-4B signature

- model name: `Qwen/Qwen3-Embedding-4B`
- lean field: `signature`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `12`
- dtype flag: `--dtype bfloat16`
- time limit: `08:00:00`

### Qwen3-Embedding-8B type

- model name: `Qwen/Qwen3-Embedding-8B`
- lean field: `type`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `8`
- dtype flag: `--dtype bfloat16`
- time limit: `12:00:00`

### Qwen3-Embedding-8B signature

- model name: `Qwen/Qwen3-Embedding-8B`
- lean field: `signature`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `8`
- dtype flag: `--dtype bfloat16`
- time limit: `12:00:00`

### Llama-Embed-Nemotron-8B type

- model name: `nvidia/llama-embed-nemotron-8b`
- lean field: `type`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `8`
- dtype flag: `--dtype bfloat16`
- time limit: `12:00:00`

### Llama-Embed-Nemotron-8B signature

- model name: `nvidia/llama-embed-nemotron-8b`
- lean field: `signature`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `8`
- dtype flag: `--dtype bfloat16`
- time limit: `12:00:00`

### KaLM-Embedding-Gemma3-12B-2511 type

- model name: `tencent/KaLM-Embedding-Gemma3-12B-2511`
- lean field: `type`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `4`
- dtype flag: `--dtype bfloat16`
- time limit: `16:00:00`

### KaLM-Embedding-Gemma3-12B-2511 signature

- model name: `tencent/KaLM-Embedding-Gemma3-12B-2511`
- lean field: `signature`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `4`
- dtype flag: `--dtype bfloat16`
- time limit: `16:00:00`

### Harrier 27B type

- model name: `microsoft/harrier-oss-v1-27b`
- lean field: `type`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `1`
- dtype flag: `--dtype bfloat16`
- time limit: `24:00:00`

### Harrier 27B signature

- model name: `microsoft/harrier-oss-v1-27b`
- lean field: `signature`
- directions: `informal_to_lean,lean_to_informal`
- batch size: `1`
- dtype flag: `--dtype bfloat16`
- time limit: `24:00:00`

## How to Monitor Jobs

Command:

```bash
squeue -u $USER
```

What it does:

- shows all of your queued and running jobs

Command:

```bash
watch -n 10 squeue -u $USER
```

What it does:

- refreshes your job list every 10 seconds

Command:

```bash
sacct -j <JOBID> --format=JobID,JobName,State,Elapsed,ExitCode,MaxRSS
```

What it does:

- shows the state and resource summary for one specific job

Replace `<JOBID>` with the numeric job id returned by `sbatch`.

Command:

```bash
tail -f /gpfs/projects/mathai/math2vec/logs/frenzymath/<JOB_NAME>_<JOBID>.out
```

What it does:

- follows the Slurm stdout log for one job

Replace:

- `<JOB_NAME>` with the Slurm job name such as `frz_qwen4_type`
- `<JOBID>` with the numeric job id returned by `sbatch`

Inside that Slurm log you will see the benchmark run directory path.

Command:

```bash
tail -f /gpfs/projects/mathai/math2vec/runs/$USER/frenzymath/<RUN_DIR>/run.log
```

What it does:

- follows the benchmark's own progress log
- shows encoding progress checkpoints for the long stages
- shows the resolved query-encoding settings written by the benchmark

## Where Results Are Saved

Every successful run creates a new run directory under:

- `/gpfs/projects/mathai/math2vec/runs/$USER/frenzymath`

The run directory name format is:

- `<timestamp>_test_vs_train-val-test_<lean_field>_<model_slug>`

Examples:

- `20260517T012345Z_test_vs_train-val-test_type_microsoft_harrier-oss-v1-0.6b`
- `20260517T045500Z_test_vs_train-val-test_signature_Qwen_Qwen3-Embedding-4B`

The results root also contains:

- `LATEST_RUN.json`
- `LATEST_RUN.txt`

These point to the most recently completed run in that results directory.

## What Saved Embedding Files Mean

If `--save-embeddings` is enabled, a `type` run can save:

- `corpus_informal_embeddings.npy`
- `corpus_lean_embeddings.npy`
- `query_informal_embeddings.npy`
- `query_lean_embeddings.npy`

For `lean_field=type`, these correspond to:

- corpus natural language embeddings
- corpus Lean type embeddings
- query natural language embeddings used for `natural -> type`
- query Lean type embeddings used for `type -> natural`

For `lean_field=signature`, they correspond to:

- corpus natural language embeddings
- corpus Lean signature embeddings
- query natural language embeddings used for `natural -> signature`
- query Lean signature embeddings used for `signature -> natural`

## Time Estimates

These are rough one-GPU estimates for the full-query setting.

- Harrier 0.6B: `1` to `3` hours per job
- Qwen3-Embedding-4B: `3` to `6` hours per job
- Qwen3-Embedding-8B: `5` to `10` hours per job
- Llama-Embed-Nemotron-8B: `5` to `10` hours per job
- KaLM-Embedding-Gemma3-12B-2511: `8` to `14` hours per job
- Harrier 27B: `14` to `24` hours per job

If `MAX_QUERY_ITEMS=100`, runtime drops only modestly because the full retrieval
corpus is still encoded.

## Embedding Storage Estimates

These estimates assume:

- full test queries
- full `train,val,test` corpus
- saved embedding dtype `float16`
- four saved arrays per job

Approximate upper bounds per job:

- Harrier 0.6B, 1024-dim: about `0.89 GiB`
- Qwen3-Embedding-4B, 2560-dim: about `2.22 GiB`
- Qwen3-Embedding-8B, 4096-dim: about `3.54 GiB`
- Llama-Embed-Nemotron-8B, 4096-dim: about `3.54 GiB`
- KaLM-Embedding-Gemma3-12B-2511, 3840-dim: about `3.31 GiB`
- Harrier 27B, 5376-dim: about `4.64 GiB`

Actual `signature` jobs may be somewhat smaller if rows are dropped for empty
signature values.

## Known Caution

The `tencent/KaLM-Embedding-Gemma3-12B-2511` model card shows a
`trust_remote_code=True` example. If the current environment fails to load that
model without it, the model wrapper will need a small code update before the
KaLM jobs can run successfully.
