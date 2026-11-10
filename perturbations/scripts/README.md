# Scripts

Operational helpers that aren't part of the main `pipeline/` runners:
benchmarking and cluster-job scripts. For the production runners that walk a
corpus and write JSONL, see [`pipeline/`](../pipeline/) instead.

To check a tactic after editing [`Wiggle.lean`](../Wiggle.lean), run the live
Lean tests (`WIGGLE_RUN_LEAN_INTEGRATION=1`, see
[`tests/README.md`](../tests/README.md)) or `python pipeline/run_demo.py
--singles-only`.

## Operational scripts

| File | Purpose |
|---|---|
| `bench_backends.py` | Wallclock comparison of the two Lean execution backends (`server` vs `subprocess`). Runs 5 `run_lean` calls each, prints first-call and warm-average timings. Use after editing `src/wiggle/lean_server.py` to confirm the persistent server still gives the ~70x warm speedup. |
| `wiggle.sbatch` | Generic Slurm batch script for `pipeline/run_hf_corpus.py`. Sized for a 32-core / 64 GB / 24 h job by default; tweak the `#SBATCH` block for your cluster. Forwards `SIGUSR1` from Slurm to the Python child 5 minutes before walltime so the run drains cleanly and writes its last shard. |
| `tillicum_setup.sh` | One-time Tillicum login-node setup: elan, conda env from `requirements.txt`, prebuilt Mathlib cache, all under `/gpfs/projects/mathai/$USER`. |
| `tillicum_tests.slurm` | Runs the test suites on Tillicum (build, mocked pytest, live-Lean pytest, typeclass smoke, demo run, optional benchmark review). See [`docs/TILLICUM_SETUP.md`](../docs/TILLICUM_SETUP.md). |
| `tillicum_env.sh` | Shared paths + conda activation, sourced by the two Tillicum scripts. |

### Benchmarking

```bash
python scripts/bench_backends.py
```

Expected on a 2024 M-series Mac (warm cache):

```
── backend = server ──
  total       :  ~45s
  per-call    : ['~45s', '~0.2s', '~0.2s', '~0.2s', '~0.2s']
  warm avg    :   ~0.2s (after first call)

── backend = subprocess ──
  total       :  ~76s
  per-call    : ['~16s', '~16s', '~15s', '~15s', '~15s']
  warm avg    :   ~15s (after first call)
```

The server's first call pays Mathlib's import; everything after is ~70x faster
than spawning a fresh `lake env lean` per call.

### Running under Slurm

The `wiggle.sbatch` script is intended to be submitted via `sbatch`, but it's
written so the SBATCH directives are no-ops outside Slurm — you can dry-run it
in the foreground on any machine:

```bash
# Dry-run on a local machine (Slurm directives ignored; runs with whatever
# defaults the env vars provide):
bash scripts/wiggle.sbatch

# On a real Slurm cluster:
sbatch scripts/wiggle.sbatch

# Override knobs via env vars without editing the file:
WIGGLE_LIMIT=10000 sbatch scripts/wiggle.sbatch
```

After submission, watch progress with `tail -F logs/<jobid>/heartbeat.jsonl`.
See [`docs/HYAK_SETUP.md`](../docs/HYAK_SETUP.md) for a complete walkthrough
including environment bootstrap, dataset pre-download, and resume semantics
after a walltime kill.

## What to put here vs `pipeline/`

The two directories are similar enough that the boundary is worth spelling out:

- **`pipeline/`** holds the *runners* — Python entry points that walk an input
  corpus (curated theorems, HF dataset slice) and emit JSONL. They depend on
  `src/wiggle/`.
- **`scripts/`** holds *operational helpers* (benchmark, Slurm/Tillicum
  wrappers) that are conceptually separate from the corpus runners.

If you're writing something that produces dataset records, it goes under
`pipeline/`. If you're writing a debugging tool or a job-submission helper, it
goes here.
