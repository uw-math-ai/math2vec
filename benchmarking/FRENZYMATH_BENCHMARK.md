# FrenzyMath Benchmark

This document describes exactly what the FrenzyMath benchmark in this repo does, what decisions it makes, what results it produces, and how to run it safely on a laptop or on a GPU cluster.

The benchmark entrypoint is:

[`benchmarking/src/frenzymath_benchmark.py`](C:/Users/kedar/OneDrive/Desktop/OneDrive%20All%20Files/Documents/Playground/math2vec/benchmarking/src/frenzymath_benchmark.py)

## Purpose

This benchmark is designed to test whether a text embedding model places:

- informal mathematical language
- formal Lean mathematical text

into the same embedding space strongly enough that aligned pairs retrieve each other.

The benchmark is aimed at the split dataset:

- Hugging Face dataset: [`saharshb/mathlib-informal-split`](https://huggingface.co/datasets/saharshb/mathlib-informal-split)

## Exact Task Definition

Each dataset row is treated as exactly one aligned pair.

By default the pair is:

- informal side: `informal_description`
- Lean side: `type`

If `--lean-field signature` is used, then the pair becomes:

- informal side: `informal_description`
- Lean side: `signature`

The benchmark embeds both sides separately and then runs exact nearest-neighbor retrieval in the shared embedding space.

It can evaluate:

1. informal -> Lean
2. Lean -> informal
3. both directions in one run

The current default is:

- `informal_to_lean` only

That default was chosen so the first Tilicum pilot run can directly match the
requested “statement -> Lean type/signature” task without extra CLI changes.

## Query Space vs Retrieval Space

This benchmark now separates:

- the query split
- the retrieval corpus

Default behavior:

- query split: `test`
- retrieval corpus splits: `train,val,test`
- directions: `informal_to_lean`

That means:

- benchmark queries come only from the held-out `test` split
- each query retrieves against the full corpus built from all three splits

This is now the default because it is closer to how retrieval would typically be used in practice.

### Is retrieving against the full dataset reasonable?

Yes. The full dataset size is on the order of a few hundred thousand rows, which is large enough to matter but still small enough to be realistic for exact embedding retrieval on modern hardware.

The main cost is encoding, not FAISS lookup.

Why:

- corpus encoding cost scales linearly with the number of corpus rows
- exact FAISS retrieval over a few hundred thousand vectors is still very manageable compared with model forward passes, especially on a cloud GPU workflow
- embedding storage is also still reasonable for typical embedding dimensions used by these models

So using `train+val+test` as the retrieval corpus is a sensible default for the real cluster benchmark.

Ground truth is defined strictly as row identity:

- row `i` on one side is considered relevant only to row `i` on the other side
- any other retrieved row is counted as wrong, even if it is mathematically related

This is a very important design decision. It makes the benchmark easy to define and reproduce, but it also means the benchmark measures exact pair recovery rather than general mathematical semantic relevance.

## What This Benchmark Measures

It measures whether a model can recover the exact aligned pair from the opposite modality.

That means it is good for evaluating:

- shared-space alignment quality between informal and Lean text
- cross-modal retrieval strength
- whether the model can identify the correct formal statement for a given informal statement
- whether the model can identify the correct informal statement for a given formal statement

## What This Benchmark Does Not Measure

It does not directly measure:

- many-to-many semantic similarity
- graded relevance
- premise usefulness
- proof retrieval
- equivalence classes of multiple acceptable answers
- downstream theorem proving performance

If a model retrieves a different but semantically similar theorem, this benchmark still counts that as an error.

## Default Experimental Choices

These defaults are built into the implementation and should be considered part of the experiment unless overridden.

### Dataset

- dataset name: `saharshb/mathlib-informal-split`
- query split: `test`
- retrieval corpus splits: `train,val,test`

Why this matters:

- `test` is still the held-out query split and should usually be the one reported for final comparisons
- the retrieval space is larger and more realistic because it includes train/val/test by default

### Lean Field

- default Lean field: `type`

Why this matters:

- `type` is usually richer than `signature`
- `signature` is typically shorter and may change the difficulty of the task
- results from `type` and `signature` should not be mixed together without explicitly stating which was used

### Similarity and Retrieval

- embeddings are L2-normalized by default
- retrieval uses inner product on the encoded vectors
- with normalized embeddings, this is equivalent to cosine similarity
- retrieval is exact nearest-neighbor retrieval
- FAISS is used when available
- if FAISS is not installed, the code falls back to an exact NumPy similarity computation
- instruction-aware models receive direction-and-task-specific default query prompts

Default prompts:

- `informal_to_lean` with `--lean-field type`:
  `Instruct: Find the most mathematically similar Lean type to this statement`
- `informal_to_lean` with `--lean-field signature`:
  `Instruct: Find the most mathematically similar Lean signature to this statement`
- `lean_to_informal` with `--lean-field type`:
  `Instruct: Find the most mathematically similar statement as a Lean type`
- `lean_to_informal` with `--lean-field signature`:
  `Instruct: Find the most mathematically similar statement as a Lean signature`

Why this matters:

- normalization can materially affect rankings
- exact search means scores are not confounded by approximate ANN settings
- FAISS vs NumPy fallback should not change correctness, only performance
- instruction-aware models can behave materially differently depending on the query instruction

### Metrics

The benchmark reports:

- `ExactMatch@1`
- `Recall@1`
- `Recall@5`
- `Recall@10`
- `MRR`

for whichever directions you ask it to run.

Because there is exactly one relevant item per query in this setup:

- `ExactMatch@1` and `Recall@1` are equivalent in spirit
- `MRR` is especially useful because it shows whether the correct pair tends to appear near the top even when not ranked first

## Interpretation Caveats

These are the main things that affect how results should be interpreted.

### 1. Row-Identity Ground Truth

This is the biggest caveat.

The benchmark assumes there is one correct partner row and only that row is correct.
If the dataset contains closely related, duplicated, overlapping, or near-paraphrase statements, the benchmark may under-credit models that retrieve a mathematically similar but differently indexed row.

### 2. `type` vs `signature`

Changing `--lean-field` changes the task definition.

If you compare models across runs, you should only compare runs that used the same Lean field.

### 3. Query Split and Corpus Splits

Changing `--query-split` changes which rows become queries.

Changing `--corpus-splits` changes the retrieval difficulty and realism.

For benchmark reporting, the main setting should generally be:

- `--query-split test`
- `--corpus-splits train,val,test`

### 4. `--max-items`

Using `--max-items` changes the retrieval pool size and therefore changes the difficulty.

A run with `--max-items 1000` should not be directly compared to a full-split run unless you explicitly mean it as a smaller-scale experiment.

### 5. `--shuffle`

If `--shuffle` is used together with `--max-items`, the evaluated subset depends on `--seed`.

That is useful for reproducible sampling, but again it changes the evaluated population.

## Important CLI Arguments

These are the arguments the person running the benchmark most needs to pay attention to.

### `--model-name`

This is the main model selection argument.

Example:

```bash
python benchmarking/src/frenzymath_benchmark.py --model-name sentence-transformers/all-MiniLM-L6-v2
```

### `--lean-field`

This determines whether the formal side is `type` or `signature`.

Examples:

```bash
python benchmarking/src/frenzymath_benchmark.py --lean-field type
python benchmarking/src/frenzymath_benchmark.py --lean-field signature
```

### `--query-split`

This determines where the benchmark queries come from.

Example:

```bash
python benchmarking/src/frenzymath_benchmark.py --query-split test
```

### `--corpus-splits`

This determines the retrieval search space.

Examples:

```bash
python benchmarking/src/frenzymath_benchmark.py --corpus-splits train,val,test
python benchmarking/src/frenzymath_benchmark.py --corpus-splits test
```

### `--directions`

This determines which retrieval direction(s) run.

Examples:

```bash
python benchmarking/src/frenzymath_benchmark.py --directions informal_to_lean
python benchmarking/src/frenzymath_benchmark.py --directions lean_to_informal
python benchmarking/src/frenzymath_benchmark.py --directions informal_to_lean,lean_to_informal
```

### The 4 prompt args

These control the raw instructions used for the 4 specific task variants:

- `--informal-to-lean-type-query-prompt`
- `--informal-to-lean-signature-query-prompt`
- `--lean-type-to-informal-query-prompt`
- `--lean-signature-to-informal-query-prompt`

In most cases you should leave them alone unless you are intentionally changing
 the task phrasing.

### `--informal-to-lean-query-prompt-name` and `--lean-to-informal-query-prompt-name`

These are optional sentence-transformers `prompt_name` settings. They are most
 useful when a model ships with preconfigured prompt names and you want to use
 those instead of raw custom instructions.

### `--batch-size`

This affects speed and memory usage.

- larger batch sizes are faster
- larger batch sizes also use more GPU memory

For large models on GPUs, this is one of the main knobs to adjust first if you hit memory issues.

### `--device`

This lets the runner force `cpu` or `cuda`.

Examples:

```bash
python benchmarking/src/frenzymath_benchmark.py --device cpu
python benchmarking/src/frenzymath_benchmark.py --device cuda
```

### `--max-query-items` and `--max-corpus-items`

These are mainly for smoke tests and debugging, not final reporting.

Example:

```bash
python benchmarking/src/frenzymath_benchmark.py --max-query-items 100 --max-corpus-items 1000
```

## Less Important Arguments

These usually do not need to be changed unless you know why you want them.

- `--informal-field`
- `--dataset-name`
- `--dtype`
- `--shuffle`
- `--seed`
- `--save-rankings`
- `--results-dir`
- `--no-normalize`

## Output Artifacts

Every run creates a new run directory under:

[`benchmarking/results/frenzymath`](C:/Users/kedar/OneDrive/Desktop/OneDrive%20All%20Files/Documents/Playground/math2vec/benchmarking/results/frenzymath)

unless overridden with `--results-dir`.

Each run directory contains:

- `config.json`
- `invocation.json`
- `run.log`
- `results.json`
- `summary.json`

and optionally:

- `rankings.json` if `--save-rankings` is used

The results root also contains:

- `LATEST_RUN.json`
- `LATEST_RUN.txt`

These point to the most recent completed run, so the person running the benchmark does not have to guess where the newest results were written.

If a run fails after the run directory is created, it writes:

- `failure.json`

instead of only failing silently.

## What Each Artifact Means

### `config.json`

The normalized benchmark configuration used for the run.

### `invocation.json`

The command-line invocation and run directory metadata.

### `run.log`

Human-readable run progress and stack traces if the run fails.

### `results.json`

The main structured output. This includes:

- config
- dataset metadata
- selected row count before empty-value filtering
- dropped row count due to missing or empty text
- query rows dropped because their aligned partner was not present in the retrieval corpus
- design decisions
- environment information
- package versions when available
- metrics
- timing

### `summary.json`

A smaller file containing just the metric summaries.

### `rankings.json`

This contains the top-k retrieved row indices and similarity scores per query in each direction.
It is useful for error analysis but can be large for big runs.

### `failure.json`

A structured record of the exception type, message, traceback, and config.

## Local Usage

From the repo root:

```bash
pip install -r benchmarking/requirements.txt
python benchmarking/src/frenzymath_benchmark.py --model-name sentence-transformers/all-MiniLM-L6-v2
```

Small smoke test:

```bash
python benchmarking/src/frenzymath_benchmark.py \
  --model-name sentence-transformers/all-MiniLM-L6-v2 \
  --query-split test \
  --corpus-splits train,val,test \
  --lean-field type \
  --max-query-items 100 \
  --max-corpus-items 1000 \
  --batch-size 16
```

Run on `signature` instead of `type`:

```bash
python benchmarking/src/frenzymath_benchmark.py \
  --model-name sentence-transformers/all-MiniLM-L6-v2 \
  --lean-field signature
```

Models such as Harrier are instruction-tuned for query encoding. For those, you may want:

```bash
python benchmarking/src/frenzymath_benchmark.py \
  --model-name microsoft/harrier-oss-v1-0.6b \
  --directions informal_to_lean \
  --query-split test \
  --corpus-splits train,val,test \
  --lean-field type
```

## Cluster / Slurm Usage

There is a dedicated example Slurm script:

[`slurmscripts/run_frenzymath_benchmark.slurm`](C:/Users/kedar/OneDrive/Desktop/OneDrive%20All%20Files/Documents/Playground/math2vec/slurmscripts/run_frenzymath_benchmark.slurm)

The most likely cluster-time adjustments are:

- `--model-name`
- `--batch-size`
- `--device cuda`
- optional `--dtype float16` or `--dtype bfloat16`

If a large model OOMs, first reduce `--batch-size`.

## Recommended Reporting Practice

For serious model comparison, record at least:

- model name
- Lean field
- split
- normalization setting
- batch size
- dtype
- exact command used
- git commit

This benchmark already saves most of that automatically.

## Recommended Final Benchmark Settings

For a main benchmark table intended for comparison across models, a good default is:

- `--split test`
- `--query-split test`
- `--corpus-splits train,val,test`
- `--directions informal_to_lean` for the first pilot requested here
- `--lean-field type`
- no `--max-query-items`
- no `--max-corpus-items`
- normalization enabled
- exact retrieval

If you also want a second table, the most natural companion experiment is:

- `--split test`
- `--lean-field signature`

That cleanly separates the two task variants.

## Testing

The automated test suite is under:

[`benchmarking/tests`](C:/Users/kedar/OneDrive/Desktop/OneDrive%20All%20Files/Documents/Playground/math2vec/benchmarking/tests)

Run it with:

```bash
pytest benchmarking/tests -q
```

## Failure Handling

The benchmark tries to fail in a way that is fast and debuggable.

Notable behaviors:

- invalid CLI values are rejected early
- dataset import problems surface as explicit import errors
- missing or empty usable pairs raise a clear error
- every started run gets a run directory
- failures write `failure.json` and `run.log`

That way a failed cloud job should still leave a useful artifact trail for debugging.
