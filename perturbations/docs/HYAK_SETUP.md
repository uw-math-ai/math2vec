# Running Wiggle on Hyak (or any Slurm cluster)

End-to-end guide for setting up and submitting a Wiggle batch job on UW Hyak.
Most of this transfers verbatim to any other Slurm cluster (Cori, Bridges,
Frontera, ...) — site-specific bits are called out below.

> **CPU-only workload.** Wiggle does Lean type-checking, which is pure CPU
> work. Don't request a GPU node — it'll be wasted hardware sitting idle.
> Target a CPU partition with as many cores as your group's allocation
> permits.

## 1. One-time setup on a login node

Run this once per cluster, ideally on a login node (compute nodes typically
have no outbound internet on Hyak).

### 1.1 Install elan (the Lean toolchain manager)

```bash
# elan installs to ~/.elan by default; on Hyak put it on /gscratch so
# it's visible from compute nodes and large enough for Mathlib caches.
export ELAN_HOME=/gscratch/<your-group>/elan
mkdir -p "$ELAN_HOME"
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y --no-modify-path

# Persist on PATH for future sessions:
echo 'export ELAN_HOME=/gscratch/<your-group>/elan' >> ~/.bashrc
echo 'export PATH="$ELAN_HOME/bin:$PATH"'           >> ~/.bashrc
source ~/.bashrc

# Sanity:
elan --version
lean --version
```

### 1.2 Clone the repo and build the Lean tactics

```bash
cd /gscratch/<your-group>
git clone <repo-url> DALAB-May-2026-Lean-wiggle-wiggle
cd DALAB-May-2026-Lean-wiggle-wiggle

# Pulls Mathlib + builds Wiggle.lean. The first run is ~10-30 minutes
# (Mathlib download + compile). Subsequent runs are seconds.
lake build Wiggle
```

### 1.3 Python virtualenv

```bash
# Hyak provides several Python builds via modules; pick one >= 3.10.
module load python/3.11   # or whatever your site offers

python -m venv /gscratch/<your-group>/envs/wiggle
source /gscratch/<your-group>/envs/wiggle/bin/activate
pip install --upgrade pip
pip install pandas pyarrow   # + any other deps your runner needs
```

### 1.4 Pre-download the HuggingFace dataset

Compute nodes on Hyak (and most clusters) don't have outbound internet.
Pull the dataset once from a login node:

```bash
python -c "
import pandas as pd
df = pd.read_json('hf://datasets/FrenzyMath/mathlib_informal_v4.19.0/data.jsonl', lines=True)
df.to_json('/gscratch/<your-group>/datasets/mathlib_informal_v4.19.0.jsonl',
           orient='records', lines=True)
print(f'cached {len(df):,} rows')
"
```

Then point the runner at the local copy with
`--dataset /gscratch/<your-group>/datasets/mathlib_informal_v4.19.0.jsonl`.

## 2. Edit `scripts/wiggle.sbatch` for your site

The shipped script ([`scripts/wiggle.sbatch`](../scripts/wiggle.sbatch))
contains a commented "site-specific env setup" block. Edit those lines:

```bash
# module load gcc/11.2.0
# source /gscratch/<group>/envs/wiggle/bin/activate
# export PATH="$HOME/.elan/bin:$PATH"
```

Hyak-specific tweaks worth considering:

* Replace `--partition` if your group has a dedicated partition
  (`#SBATCH --partition=cpu-g2`).
* Add `#SBATCH --account=<your-group>` so the job is billed correctly.
* If your group has access to high-memory nodes, bump `--mem=128G` and
  `--cpus-per-task=64` for a 2x throughput boost on a single job.

## 3. Submit a job

```bash
# Default: 50,000 anchors, 32 workers, 24h walltime.
sbatch scripts/wiggle.sbatch

# Smaller smoke test first (always do this on a new cluster):
WIGGLE_LIMIT=200 sbatch scripts/wiggle.sbatch

# A full 200k-anchor run, split into two jobs that chain via resume:
WIGGLE_LIMIT=200000 WIGGLE_RUN_ID=mainrun-001 sbatch scripts/wiggle.sbatch
# (after the first job ends at walltime, resubmit the SAME command —
# resume picks up where it left off.)
WIGGLE_LIMIT=200000 WIGGLE_RUN_ID=mainrun-001 sbatch scripts/wiggle.sbatch
```

Every knob is overridable via env var without editing the script. See the
header of [`scripts/wiggle.sbatch`](../scripts/wiggle.sbatch) for the full
list.

## 4. Watch it run

In a separate shell on the login node:

```bash
# Slurm queue + state:
squeue -u "$USER"

# Live heartbeat (anchors per minute, drain state, ...):
tail -F logs/$SLURM_JOB_ID/heartbeat.jsonl

# Per-worker event stream:
tail -F logs/$SLURM_JOB_ID/worker-00000.log.jsonl

# Standard out from the job (banner + final summary):
tail -F logs/slurm-$SLURM_JOB_ID.out
```

The `heartbeat.jsonl` file is rewritten in place every 30 seconds. The
`heartbeat.history.jsonl` file in the same directory appends, so you can plot
throughput vs time post-run.

## 5. Resume after walltime / preempt

The default sbatch script asks Slurm to send `SIGUSR1` five minutes before
the walltime kill (`--signal=B:USR1@300`). The runner catches that, stops
submitting new anchors, lets workers finish their in-flight anchor, flushes
shards atomically, and exits 0.

To pick up where it stopped: resubmit with the **same** `WIGGLE_RUN_ID`. The
shard directory already contains every completed anchor; on startup the
runner scans it and skips them automatically:

```bash
WIGGLE_RUN_ID=mainrun-001 sbatch scripts/wiggle.sbatch
```

If you didn't set `WIGGLE_RUN_ID` on the first run, look at
`logs/slurm-<jobid>.out` — the banner prints the run id used.

## 6. Sizing — how long will it take?

Throughput depends on per-anchor Lean time, which dominates everything else.
On a warm Lean LSP server (`scripts/bench_backends.py` figures), expect
roughly **0.5 seconds per perturbation call**, times ~25 calls per anchor =
**~13 seconds per anchor per worker**.

| Cores | Anchors/hour | 24h coverage | 200k-anchor target |
|---|---|---|---|
| 16  | ~4,400   | ~106k  | needs 2 x 24h jobs |
| 32  | ~8,800   | ~210k  | one 24h job        |
| 64  | ~17,600  | ~420k  | half a day         |
| 128 | ~35,000  | ~840k  | a few hours        |

These are warm-cache numbers. The first ~30s per worker is the Mathlib
import; with 32 workers that's a one-time hit of ~1 min before steady state.

## 7. Faster I/O via per-node scratch (optional)

Hyak compute nodes have local NVMe at `/scr/<jobid>` (much faster than
`/gscratch`). If you don't need the output to survive job termination, point
shards + logs at scratch and rsync the survivors at the end:

```bash
# Add inside scripts/wiggle.sbatch after the env-setup block:
export WIGGLE_SHARD_DIR="/scr/$SLURM_JOB_ID/shards"
export WIGGLE_LOG_DIR="/scr/$SLURM_JOB_ID/logs"

# ... run ...

# After the python call returns:
rsync -av "/scr/$SLURM_JOB_ID/shards/" "data/shards/${RUN_ID}/"
rsync -av "/scr/$SLURM_JOB_ID/logs/"   "logs/${RUN_ID}/"
```

For a 32-worker run that emits ~3M records, you'll save ~10 minutes of I/O
total. Not free, but a nice optimisation once everything else works.

## 8. Post-job concatenation and publishing

After the run finishes (or after several chained runs all share a `RUN_ID`),
you have a directory of shards:

```
data/shards/mainrun-001/
├── part_00000.jsonl
├── part_00001.jsonl
├── ...
└── part_00031.jsonl
```

To get a single JSONL file:

```bash
python -c "
from pathlib import Path
from wiggle.shards import iter_shard_records
import json
out = Path('data/mainrun-001.jsonl')
n = 0
with out.open('w', encoding='utf-8') as f:
    for r in iter_shard_records('data/shards/mainrun-001'):
        f.write(json.dumps(r, ensure_ascii=False) + '\\n')
        n += 1
print(f'wrote {n} records')
"
```

Or run with `--output data/mainrun-001.jsonl` and the concatenation happens
automatically at the end of the last submission.

The next planned step in the project roadmap is converting to parquet and
pushing to HuggingFace; see the roadmap items `parquet`, `hf_push`,
`dataset_card`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| First call hangs >5 min | Mathlib not built | `lake build Wiggle` on a login node, then resubmit |
| `No such file or directory: lake` | elan not on PATH for compute nodes | Add `export PATH="$ELAN_HOME/bin:$PATH"` to the sbatch script's env-setup block |
| Workers OOM | `--mem` too low | Bump to `--mem=64G` minimum (~2 GB per worker) |
| Job dies with `SIGTERM` instead of clean drain | Slurm didn't deliver SIGUSR1 (older Slurm versions, custom config) | Reduce `--time-budget` so workers stop submitting well before walltime |
| `pandas` not found in worker | Workers spawn fresh Python; venv not activated | Make sure `source <venv>/bin/activate` is in the sbatch env-setup block |
| Run ID collision overwrites previous data | Explicit `WIGGLE_RUN_ID` reused after a non-resume scenario | Pick a new run id; or accept that resume will skip already-done anchors and append new shards |

If something blocks you that isn't on the table above, attach
`logs/slurm-<jobid>.out` and `logs/<runid>/heartbeat.jsonl` to your bug
report — those two together usually narrow it down quickly.
