# Running the Wiggle tests on Tillicum

How to run every Wiggle test suite on UW's Tillicum cluster under the lab's
`mathai` account. Follows the conventions of the UW-IT
[Tillicum onboarding](https://github.com/UWrc/tillicum-onboarding) and the
other math2vec Slurm scripts (`slurmscripts/`, `finetune/`).

Three files do the work:

| File | Where it runs | What it does |
|---|---|---|
| [`scripts/tillicum_setup.sh`](../scripts/tillicum_setup.sh) | login node, once | elan, conda env, prebuilt Mathlib cache |
| [`scripts/tillicum_tests.slurm`](../scripts/tillicum_tests.slurm) | compute node, per test run | builds `Wiggle.lean`, runs the test stages |
| [`scripts/tillicum_env.sh`](../scripts/tillicum_env.sh) | sourced by both | shared paths + conda activation |

## Tillicum constraints that shape this setup

- **No CPU-only jobs.** Every job must request at least 1 GPU. Wiggle is
  pure-CPU Lean work, so the job asks for the minimum: 1 GPU, which comes
  with 8 CPUs (and up to 200 GB RAM). That costs $0.90 per GPU-hour, so a
  30-minute debug run costs about $0.45.
- **Storage.** `$HOME` is capped at 10 GB. Mathlib (about 5 GB) plus the
  elan toolchain won't fit there. `/gpfs/scrubbed` is purged after 60 days
  of inactivity, which breaks conda envs. So everything goes under
  `/gpfs/projects/mathai/$USER` (override with `TILLICUM_BASE`).
- **Login nodes are for setup, not compute.** Downloads (`lake exe cache get`,
  `pip install`) happen on the login node. Compiling `Wiggle.lean` and running
  Lean happen inside the job.
- **QOS.** `debug` (30 min, 1 GPU) is the default and fits the default stages.
  Use `normal` (up to 24 h) for the `review` stage or anything bigger.

## 1. Get the code onto Tillicum

Clone math2vec into project storage, on the branch that carries
`perturbations/`:

```bash
ssh NETID@tillicum.hyak.uw.edu
mkdir -p /gpfs/projects/mathai/$USER && cd /gpfs/projects/mathai/$USER
git clone https://github.com/uw-math-ai/math2vec.git
cd math2vec/perturbations
```

Use `git clone -b <branch>` if `perturbations/` isn't on `main` yet. For
uncommitted local changes, rsync the directory instead (password + Duo):

```bash
# from the math2vec/ directory on your machine
rsync -av --exclude .lake --exclude logs --exclude __pycache__ \
    perturbations/ NETID@tillicum.hyak.uw.edu:/gpfs/projects/mathai/NETID/math2vec/perturbations/
```

## 2. One-time setup (login node)

```bash
ssh NETID@tillicum.hyak.uw.edu
cd /gpfs/projects/mathai/$USER/math2vec/perturbations
bash scripts/tillicum_setup.sh
```

The first run takes about 10–20 minutes, mostly the Mathlib download. The
script is safe to re-run. Re-run it after bumping `lean-toolchain` or Mathlib
in `lakefile.toml`, or after editing `requirements.txt`.

## 3. Run the tests

```bash
cd /gpfs/projects/mathai/$USER/math2vec/perturbations
sbatch scripts/tillicum_tests.slurm
squeue -u $USER                 # watch it
cat wiggle-tests_<jobid>.out    # banner, per-stage output, final summary
```

The job ends with a summary block, and exits non-zero if any stage failed:

```
 Summary (job 123456)
   build      PASS     <n>s
   fast       PASS     <n>s
   live       PASS     <n>s
   typeclass  PASS     <n>s
   demo       PASS     <n>s
```

Artifacts (JUnit XML for both pytest stages, demo/review JSONL) land in
`logs/tillicum-tests/<jobid>/`.

### Stages

| Stage | What runs | Lean? |
|---|---|---|
| `build` | `lake build Wiggle` (fast once the Mathlib cache is in place) | yes |
| `fast` | `pytest tests/ --ignore=tests/test_typeclass_mutate.py`, Lean mocked. Expect `134 passed, 3 skipped` | no |
| `live` | `WIGGLE_RUN_LEAN_INTEGRATION=1 pytest tests/test_lean_server.py::TestRealLeanServer` | yes |
| `typeclass` | `python tests/test_typeclass_mutate.py` (print-based smoke script) | yes |
| `demo` | `pipeline/run_demo.py --singles-only`: all 28 perturbations on the 10 curated theorems | yes |
| `review` | `run_benchmark_review.py --limit $WIGGLE_REVIEW_LIMIT` then `verify_variants.py`, using all 8 CPUs. Off by default | yes |

Default set: `build fast live typeclass demo`. Pick stages with
`WIGGLE_TEST_STAGES`:

```bash
# Just the mocked suite (seconds):
WIGGLE_TEST_STAGES=fast sbatch scripts/tillicum_tests.slurm

# Everything, including the audited benchmark review on 10 anchors:
WIGGLE_TEST_STAGES="build fast live typeclass demo review" WIGGLE_REVIEW_LIMIT=10 \
    sbatch --qos=normal --time=02:00:00 scripts/tillicum_tests.slurm

# Extra pytest flags for the fast + live stages:
WIGGLE_PYTEST_ARGS="-x -k shards" WIGGLE_TEST_STAGES=fast sbatch scripts/tillicum_tests.slurm
```

Command-line `sbatch` flags override the `#SBATCH` header. Use this if your
default account isn't `mathai`, e.g. `sbatch --account=<other> ...`.

### Interactive debugging

The same script runs outside `sbatch`:

```bash
salloc --qos=interactive --gpus=1 --cpus-per-task=8 --time=01:00:00
cd /gpfs/projects/mathai/$USER/math2vec/perturbations
WIGGLE_TEST_STAGES="build live" bash scripts/tillicum_tests.slurm
```

## 4. Blueprint perturbations + MTEB embedding eval

`scripts/tillicum_blueprint.slurm` runs the whole leanblueprint experiment in
one job:

1. It converts the 4,378 scraped declarations in `../dataset/blueprints.json`
   into about 2,800 unique theorem/lemma statements.
2. It keeps the ones that elaborate against plain Mathlib with
   `autoImplicit false`. Many blueprint statements use project-only
   definitions and are skipped.
3. It applies each of the 28 perturbations once to every kept statement.
4. It scores `sentence-transformers/all-MiniLM-L6-v2` on the result as an
   MTEB reranking task.

```bash
cd /gpfs/projects/mathai/$USER/math2vec && git pull
cd perturbations
bash scripts/tillicum_setup.sh          # login node; installs mteb + downloads the model
sbatch scripts/tillicum_blueprint.slurm # 4 GPUs → 32 Lean workers, ≤12 h
```

For a cheap trial first, run
`WIGGLE_BP_LIMIT=40 sbatch --qos=debug --gpus=1 --cpus-per-task=8 --mem=180G --time=00:30:00 scripts/tillicum_blueprint.slurm`.
Delete `data/blueprint-review` before the full run, or keep it and the full
run will resume from it.

The results land in `data/blueprint-review/`:

- `review.md` is the human audit.
- `results.jsonl` has one row per anchor × perturbation.
- `anchors.jsonl` is the resume log.
- `mteb/mteb_scores.json` has nDCG@10, MAP and MRR.
- `mteb/similarity_by_perturbation.csv` gives the mean anchor–variant cosine
  per perturbation.

If the job hits its time limit, submit it again: finished anchors are not
redone. Use a different model with `WIGGLE_EMBED_MODEL=<hf id>`, but run
`tillicum_setup.sh` with the same variable first so the model gets
downloaded.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `could not activate .../envs/wiggle` or `lake not on PATH` | Setup hasn't run for this `TILLICUM_BASE`: `bash scripts/tillicum_setup.sh` on the login node. |
| `cannot find Wiggle.lean` | Submit from `perturbations/` (or the math2vec root), or set `WIGGLE_PROJECT=/path/to/perturbations`. |
| `build` takes many minutes / compiles Mathlib | The prebuilt cache is missing or stale. Re-run `lake exe cache get` on the login node. |
| `Invalid account` at submit time | `sbatch --account=<your account> scripts/tillicum_tests.slurm`. |
| Job killed at 30 min | Too many stages for `debug`. Add `--qos=normal --time=01:00:00`. |
| `Disk quota exceeded` in `$HOME` | Something wrote a cache to `~`. Check `du -h -d 1 ~`. `tillicum_env.sh` redirects the Mathlib, pip, and conda caches to `$TILLICUM_BASE`. |

Corpus-scale runs (`scripts/wiggle.sbatch`) are covered by
[`HYAK_SETUP.md`](HYAK_SETUP.md). On Tillicum that script additionally needs
`--qos=normal --gpus=1 --account=mathai`, and it needs the same env setup as
`tillicum_tests.slurm`.
