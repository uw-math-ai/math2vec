# Math2Vec-wiggle-wiggle
Previously: DALAB-May-2026-Lean-wiggle-wiggle

> **Source:** This directory was copied from
> [Yd025/Math2Vec-wiggle-wiggle](https://github.com/Yd025/Math2Vec-wiggle-wiggle)
> at commit [`52275dc`](https://github.com/Yd025/Math2Vec-wiggle-wiggle/commit/52275dca30f528c73ee0626b7837459847e09448)
> (2026-10-12). The full development history (older version control) lives in
> that repository; see its [README](https://github.com/Yd025/Math2Vec-wiggle-wiggle/blob/main/README.md).

## Repository layout

```
.                                        # Lake project root
├── Wiggle.lean                          # Lean tactics (negate, contrapose, converse, inverse, de_morgan_rewrite, ...)
├── lakefile.toml, lean-toolchain, ...   # Lake build config (must stay at root)
│
├── docs/                                # Design documents
│   └── Final Design Doc.md              # End-to-end project design and goals
│
├── src/                                 # Python library — the importable core
│   ├── bounds.py                        # Inequality / numeric bound perturbations
│   ├── typeclass_mutate.py              # Typeclass perturbations; hierarchy is read
│   │                                    #   from data/class_hierarchy.jsonl (no hardcoding)
│   ├── instance_graph/                  # dump_class_hierarchy.py → class_hierarchy.jsonl
│   └── wiggle/                          # Phase 2: clean perturbation package
│       ├── lean_runner.py               # Single home for `lake env lean` invocations
│       ├── registry.py                  # Canonical PERTURBATIONS list (single source of truth)
│       ├── propagation.py               # Symbolic is_true / compose_truth
│       ├── chains.py                    # apply_chain — per-anchor chain runner
│       ├── pipeline.py                  # run_pipeline — corpus-level runner
│       └── transforms/                  # Per-layer transform implementations
│           ├── logical.py               #   negate, contrapose, converse, inverse, drop_unused_hyp
│           ├── connectives.py           #   de_morgan_rewrite
│           ├── quantifiers.py           #   quantifier_swap
│           ├── typeclass.py             #   tc_weaken_hyp, tc_strengthen_hyp, tc_*_conc
│           └── bounds.py                #   flip_bound, bound_tighter
│
│       ├── parallel.py                  #   ProcessPoolExecutor + drain + time-budget
│       ├── shards.py                    #   append-only JSONL shards + per-anchor done markers
│       ├── run_logging.py               #   per-worker JSONL logs + heartbeat
│       └── lexical.py                   #   non-neural similarity: what word matching sees
│
├── pipeline/                            # CLI runners on top of src/wiggle/
│   ├── run_demo.py                      # 10 curated theorems → JSONL
│   ├── run_hf_corpus.py                 # HuggingFace dataset slice → sharded JSONL
│   ├── run_benchmark_review.py          # benchmark-CSV anchors → audited depth-1 review
│   ├── run_deep_chains.py               # one anchor → whole perturbation tree
│   ├── sample_mathlib_anchors.py        # shape-diverse anchors sampled from Mathlib
│   ├── verify_variants.py               # re-elaborate every variant standalone
│   └── analyze_geometry.py              # where do the variants sit? (lexical geometry)
│
├── scripts/                             # Benchmark, Slurm + Tillicum job scripts
│   ├── bench_backends.py                # server vs subprocess wallclock comparison
│   ├── wiggle.sbatch                    # generic Slurm batch script for run_hf_corpus.py
│   └── tillicum_*.sh, tillicum_tests.slurm  # Tillicum setup + test job
├── tests/                               # Unit tests — see tests/README.md
├── docs/                                # Design docs + HYAK/TILLICUM setup guides
└── data/                                # Generated dumps (gitignored)
```

See each subdirectory's `README.md` for details:

- [`tests/README.md`](tests/README.md) — how to run the fast vs. live test suites, mocking pattern, recipe for adding a new perturbation test.
- [`scripts/README.md`](scripts/README.md) — benchmark, Slurm and Tillicum job scripts.
- [`pipeline/README.md`](pipeline/README.md) — corpus runners and dataset format.
- [`docs/perturbations.md`](docs/perturbations.md) — catalogue of all 28 perturbations: what each one does, its value, where it performs well, and its limitations.
- [`docs/difficulty-spectrum.md`](docs/difficulty-spectrum.md) — which perturbations a model should find hard, and why. Ranks all 28 by how much of the change is hidden from word matching (measured) and by how much knowledge is needed to get it right (predicted).
- [`docs/HYAK_SETUP.md`](docs/HYAK_SETUP.md) — end-to-end guide for running on UW Hyak (or any Slurm cluster): env bootstrap, dataset pre-download, submit/monitor, resume after walltime, sizing table.
- [`docs/TILLICUM_SETUP.md`](docs/TILLICUM_SETUP.md) — running the test suites on UW's Tillicum GPU cluster under the `mathai` account.
- [`docs/Final Design Doc.md`](docs/Final%20Design%20Doc.md) — overall scaling roadmap.

## What the perturbations look like so far

Measured over 298 Lean-verified variants of 24 Mathlib anchors, using purely
lexical similarity — no model — so the numbers are the floor that word matching
gets for free ([`analyze_geometry.py`](pipeline/analyze_geometry.py)):

- Variants land **90% of the way** from "unrelated theorem" to "identical
  string", and **95%** still retrieve their own anchor. Perturbing a statement
  does not move it, which is the intended shape for hard negatives.
- Where an equivalence-preserving rewrite actually rewrote something, the
  *logically different* variant is the lexically closer one **90%** of the time.
  Surface similarity is not just uninformative here, it is **anti-correlated**
  with logical similarity.
- The one-token logical edits (`strictness_swap`, `connective_swap`,
  `const_to_zero_one`, `flip_bound`, …) sit at a surface change of ≈0.00 while
  changing what the theorem says. Those are the pairs worth training on.
- Positives are the thin side: only `alpha_rename` and `de_morgan_rewrite`
  rewrite enough of a statement to be worth training on, and they sit at
  opposite extremes with nothing in between.
- Chaining perturbations is what buys distance: at depth 3 the mean collapse
  falls to 0.77, and some variants land as far out as an unrelated theorem.

Full write-up in [`docs/difficulty-spectrum.md`](docs/difficulty-spectrum.md);
generated reports and figures land in `<run>/geometry/`.

## Running

```bash
# Apply every registered perturbation to 10 curated theorems and write JSONL:
python pipeline/run_demo.py

# Sharded run over a HuggingFace dataset slice using N parallel workers:
python pipeline/run_hf_corpus.py --limit 1000 --num-workers 8

# Same, with a 23-hour wall-budget; SIGUSR1 (or `Ctrl-C` followed by re-run)
# drains cleanly and resumes on the next submission:
python pipeline/run_hf_corpus.py --limit 50000 --num-workers 32 \
    --shard-dir data/shards/run-001 --log-dir logs/run-001 \
    --time-budget 23h

# Submit the same as a Slurm job (see docs/HYAK_SETUP.md):
sbatch scripts/wiggle.sbatch

# Run the Python unit tests (no Lean required, < 5s):
python -m pytest tests/ --ignore=tests/test_typeclass_mutate.py
```

### Evaluating a run

```bash
# Audited depth-1 review over the benchmark CSV anchors:
python pipeline/run_benchmark_review.py --source Mathlib --num-workers 4
python pipeline/verify_variants.py --run data/benchmark-review

# Grow the whole perturbation tree around a single theorem:
python pipeline/run_deep_chains.py --anchor bench_000 --depth 3 --max-nodes 40

# Sample shape-diverse anchors from Mathlib, to exercise the perturbations
# the benchmark CSV never triggers:
python pipeline/sample_mathlib_anchors.py --limit 24 --verify
python pipeline/run_benchmark_review.py --anchors-file data/anchors/mathlib-24.jsonl \
    --out data/mathlib-review

# Where do the variants sit relative to their anchor? (no Lean, seconds)
# Writes report.md + figures to <run>/geometry/.
python pipeline/analyze_geometry.py --run data/mathlib-review
```

Key flags for [`pipeline/run_hf_corpus.py`](pipeline/run_hf_corpus.py):

| Flag | Default | Purpose |
|---|---|---|
| `--num-workers N` | `SLURM_CPUS_PER_TASK` or `os.cpu_count()` | Parallel subprocess count. Each worker keeps its own Lean LSP server warm. |
| `--shard-dir PATH` | `data/shards/<run-id>/` | Sharded JSONL output — one shard per worker; an anchor counts as done only once all its records are flushed. |
| `--log-dir PATH` | `logs/<run-id>/` | Per-worker JSONL logs + `heartbeat.jsonl`. |
| `--time-budget DUR` | unlimited | Wallclock budget — accepts `23h`/`90m`/`3600s`. Workers in-flight finish their current anchor. |
| `--run-id NAME` | timestamp | Resume by passing the same `--run-id` on resubmission. |
| `--no-resume` | off | Re-process every anchor even if its signature already appears in the shard dir. |

## What this project does

We perturb Lean theorem statements to create similar but distinct statements,
using a mix of Lean tactics and Python text manipulation. The current registry
exposes **28 perturbations** across 7 layers:

| Layer | Perturbations |
|---|---|
| Logical (Lean tactic) | `negate`, `contrapose`, `converse`, `inverse`, `drop_unused_hyp` |
| Connective rewriting (Lean tactic) | `de_morgan_rewrite`, `curry`, `uncurry`, `definitional_unfold` |
| Quantifier scope (Python + Lean validity oracle) | `quantifier_swap`, `forall_to_exists`, `exists_to_forall` |
| Typeclass / type mutation (Python + Lean validity oracle) | `tc_weaken_hyp`, `tc_strengthen_hyp`, `tc_strengthen_conc`, `tc_weaken_conc`, `tc_sibling_swap`, `specialize_type` |
| Bound mutation (regex) | `flip_bound`, `bound_tighter` |
| Structural rewrite (Python + Lean validity oracle) | `alpha_rename`, `premise_permute`, `implicit_explicit_toggle` |
| Relation / operator mutation (Python + Lean validity oracle) | `strictness_swap`, `eq_to_le`, `connective_swap`, `arith_op_swap`, `const_to_zero_one` |

Equivalence-preserving perturbations (`contrapose`, `de_morgan_rewrite`, `curry`,
`uncurry`, `definitional_unfold`, `alpha_rename`, `premise_permute`,
`implicit_explicit_toggle`) produce *positive* pairs (same meaning, different
surface syntax); the rest produce graded or hard-negative pairs. Three further
perturbations (`dual_full`, `sub_formula_negate`, `notation_unfold`) are designed
but deferred — they need dedicated Lean metaprogramming rather than text edits.

For a per-perturbation breakdown — mechanism, value, what it works well on, and
its limitations — see [`docs/perturbations.md`](docs/perturbations.md).

All peturbed Lean statements are checked by the Lean compiler to be valid Lean statements. However, many of them are mathematically incorrect. This project does not care whether a statement is true or not, just whether or not it is a valid Lean statement.

# Examples:

Original Statement:

∀ {α : Type*} [inst : CommRing α] (a b : α), a * b = b * a

Weakening the Hypothesis:

∀ {α : Type*} [inst : Field α] (a b : α), a * b = b * a


# Similar Existing Work
- LeanDojo
    - This contained a way to perturb Lean proof states
- Lean Error Correction (from the UW Math AI Lab)
    - This also contained a way to perturb Lean proof states
- Synthetic Theorem Generation in Lean
    - This used LLMs to generate theorem statements, then used a proof checker to ensure validity

We found that existing work on synthetic Lean generation perturbed Lean proof states instead of the full theorem statements. Also, existing work uses LLMs to perturb statements, instead of using Lean’s tactics and typechecker to ensure validity.

# Uses

This project was inspired by two projects in the UW Math AI Lab, 
- [TheoremSearch](https://github.com/uw-math-ai/TheoremSearch)
- [Math2Vec](https://github.com/uw-math-ai/math2vec)

Theorem Search does retrieval of mathematically similar theorems from ArXiv and The Stacks Project by embedding all theorems/lemmas/corollaries with a text embedder then finding the closest theorems to a query in the embedding space.

Math2Vec is attempting to improve the text embedding capability over both natural language math statements and Lean math statements, looking towards improving the Theorem Search project with a better text embedder for mathematical theorems. To better fine-tune a text embedder over Lean, this project could use a synthetic dataset of perturbed Lean statements to run constrastive loss -esque training 

Examples of Lean Theorem Search
- LeanFinder
    - Theorem Search for Lean theorems & proof states

# Bottlenecks, Downsides, and Next Steps

Running our code on a laptop, it takes about 5-30s per perturbation, primarily because using the Lean tactic itself is slow. This seems to be slower than asking frontier LLMs to perturb Lean statements.
- However, our statements seem to be more accurate or be of a deeper perturbation than the LLM version. For example, our negations fully embed the negation into the statement using a Lean tactic, instead of jsut inserting a negation sign onto the statement.

This project has only suceeded in making a small demo dataset (perturbing 10 theorems at a time). To make a full dataset of perturbed Lean theorem statements, we would need to find a massive speedup in the perturbation process and build infrstaurcture for the dataset.

Most of the speedup and scaling work is now in place — see [`docs/HYAK_SETUP.md`](docs/HYAK_SETUP.md) for the Slurm pipeline, [`scripts/bench_backends.py`](scripts/bench_backends.py) for the ~70× warm-call speedup from the persistent Lean LSP server, and the `--num-workers` / `--shard-dir` / `--time-budget` flags above for cluster-scale runs.

Next Steps:
- How can we make this faster?
- How do we scale our solution to compute for 200k theorems? (see FinalDesignDoc.md for more details)
- Are there more ways to perturb Lean statements we can add?
- Go train a text embedder usign contrastive loss (or something) with a dataset

# Fun Fact

This project is named "wiggle wiggle" as an alternate term for "perturbation", from a mysterious unnamed professor in the UW Math Department.

