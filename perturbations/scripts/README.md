# Scripts

Standalone CLIs that aren't part of the main `pipeline/` runners. They split
into two groups:

1. **Per-tactic Lean demos** — minimal subprocess wrappers around each Lean
   tactic in `Wiggle.lean`. Used for fast tactic-level debugging without
   booting the full Python pipeline.
2. **Operational scripts** — benchmarking and cluster-job helpers. These do
   go through `src/wiggle/`.

For the production runners that walk a corpus and write JSONL, see
[`pipeline/`](../pipeline/) instead.

## Per-tactic Lean demos

| File | Lean tactic | What it does |
|---|---|---|
| `negate_theorem.py` | `negate_state` | Hard-coded Lean snippet, runs `lake env lean`, prints the negated `extract_goal` line. |
| `contrapose_theorem.py` | `contrapositive` | Same shape as above, for contrapositive. |
| `converse_theorem.py` | `converse` | Same shape, for converse. |
| `generalize_theorem.py` | `drop_unused_hyp` (historical name `generalize`) | Same shape; strips unused Prop-valued hypotheses. |
| `specialize.py` | (none — specialisation experiment) | Self-contained Lean snippet for substituting specific types. |

These scripts intentionally **do not** import from `src/wiggle/`. They each
embed a Lean snippet as a Python string, spawn `subprocess.run(["lake", "env",
"lean", tmp_path], ...)`, and regex-grep the output for
`^theorem .*extracted.*$`. The point is that when you edit a tactic macro in
[`Wiggle.lean`](../Wiggle.lean) you can verify it in 15 seconds without
threading through the registry, transform wrappers, and chain runner.

```bash
# Smoke-test a single tactic after editing Wiggle.lean:
python scripts/negate_theorem.py
python scripts/contrapose_theorem.py
```

Each is around 40 lines. If you want to add a new tactic-level demo, copy
`negate_theorem.py`, change the `LEAN_CODE` string, and you're done.

## Operational scripts

| File | Purpose |
|---|---|
| `bench_backends.py` | Wallclock comparison of the two Lean execution backends (`server` vs `subprocess`). Runs 5 `run_lean` calls each, prints first-call and warm-average timings. Use after editing `src/wiggle/lean_server.py` to confirm the persistent server still gives the ~70x warm speedup. |
| `wiggle.sbatch` | Generic Slurm batch script for `pipeline/run_hf_corpus.py`. Sized for a 32-core / 64 GB / 24 h job by default; tweak the `#SBATCH` block for your cluster. Forwards `SIGUSR1` from Slurm to the Python child 5 minutes before walltime so the run drains cleanly and writes its last shard. |

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
- **`scripts/`** holds *one-off CLIs* — Lean-tactic demos that bypass the
  library entirely, plus operational helpers (benchmark, Slurm wrapper) that
  are conceptually separate from the corpus runners.

If you're writing something that produces dataset records, it goes under
`pipeline/`. If you're writing a debugging tool or a job-submission helper, it
goes here.
