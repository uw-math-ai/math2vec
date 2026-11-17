# Experiment: Do Mathlib docstrings improve NL → Lean retrieval?

**Status:** running. Submitted 2026-11-16 on Tillicum (UW Hyak).
**Jobs:** `486428` (paper arm), `486429` (+A1 arm).
**Results:** see §9 — to be filled in when both arms finish.

---

## 1. The question

The Math2Vec embedding model is trained to retrieve a Lean theorem statement
given a natural-language description of it. Our training data pairs each
concept with an NL description that was generated for this project.

Mathlib itself ships **human-written docstrings** for many theorems. This
experiment asks a simple question:

> If we add real Mathlib docstrings to the training data, does the model get
> better at retrieving Lean statements from natural language?

We answer it by training two models that differ in exactly one way, and
comparing them on an identical evaluation set.

## 2. The data

| Dataset | File | Size |
|---|---|---|
| **Base** (the paper's data) | `MathlibViews.jsonl` | 133,621 rows, 126,059 unique concepts, 5,553 modules |
| **A1** (new) | `a1_kept_concepts_v4.19.0.jsonl` | 18,747 rows, 18,747 unique concepts, 3,099 modules |

A1 was extracted from Mathlib v4.19.0 (commit `c44e0c8e`). Each record pairs a
Lean declaration with its actual Mathlib docstring. sha256
`da823e1476c4b1b6dee9ba1efeaa320768ab5605f2b61796001828dc917345d3`.

**The two datasets overlap heavily.** Of A1's 18,747 concepts:

- **14,501 (77.4%)** are theorems the base dataset *already contains*
- **4,246 (22.6%)** are theorems the base dataset does *not* contain

This overlap is the single most important fact about the experiment, and §4
explains how it is handled.

### The two datasets describe theorems very differently

Before running anything we checked whether A1's docstrings are just reworded
versions of the NL already in the base data. They are not:

- **0** of 14,501 overlapping docstrings are byte-identical to the base NL
- Median text similarity: **0.129**; near-duplicate share: **0.1%**

The reason the similarity is so low is that the two sources write in completely
different registers. For `Convex.add_smul_sub_mem_interior'`:

> **Base:** *Let $E$ be a vector space over an ordered scalar field
> $\mathbb{K}$, and let $s \subseteq E$ be a convex set. For any points
> $x \in \text{closure}(s)$ and $y \in \text{interior}(s)$...*
>
> **A1:** *If `x ∈ closure s` and `y ∈ interior s`, then the segment `(x, y]` is
> included in `interior s`.*

The base NL is verbose LaTeX prose; A1 is terse Mathlib-style prose using Lean
notation. Same theorem, two genuinely different descriptions. This matters for
interpreting the result — see §8.

## 3. The two arms

Both arms start from the same stock model, `Qwen/Qwen3-Embedding-8B`, and use
an identical training recipe. **The only difference is the training data.**

| | Arm 1 — paper baseline | Arm 2 — + A1 docstrings |
|---|---|---|
| RUN name | `mv3_qwen8b_paper_ep2` | `mv3_qwen8b_a1_ep2` |
| Slurm job | 486428 | 486429 |
| Trains on | base data only | base data **+ A1** |
| Evaluates on | the same dev set | the same dev set |

Recipe for both: full fine-tune of all 8B parameters (no LoRA, no frozen
layers), `CachedMultipleNegativesRankingLoss`, batch size 16, max sequence
length 128, 2 epochs, 700 warmup steps, constant LR, hard negatives disabled.
Train/dev split is **by module** with seed 42 and `dev_frac=0.1`, so related
theorems from one file cannot be split across train and dev.

**Why a baseline arm is necessary.** The trainer automatically reports how the
fine-tuned model compares to the *stock* model. But the stock comparison would
look good for either arm — fine-tuning on 133k theorems helps regardless of A1.
The only way to isolate A1's contribution is to train a model without it and
compare the two fine-tuned models directly.

## 4. How the 14,501 overlapping theorems are handled

This is the mechanical heart of the experiment.

A1 is supplied via `--extra_train_jsonl`, which folds it into the **training set
only, after the train/dev split has already been made**. Each A1 record takes
one of four paths:

| Situation | What happens |
|---|---|
| The theorem is in the **dev set** | **Dropped.** Including it would leak a test answer into training. |
| Its module is a **dev module** | **Dropped.** Module-level leakage. |
| The theorem is already in **train** | Its docstring is **added as a second NL description** of that concept. |
| The theorem is **new** | It becomes a **new training concept**. |

So for an overlapping theorem that survives into training, the concept now
carries **two NL descriptions of one Lean statement**: the base dataset's
generated description, and A1's Mathlib docstring.

### What the model actually trains on

The trainer builds **one training example per concept per epoch**, by picking
two of the concept's available "views" at random:

**Arm 1** — the concept has two views, so there is only one possible pair, and
it is used every epoch:

```
(base_NL, lean_signature)
```

**Arm 2** — the concept has three views, so there are three possible pairs, and
one is drawn at random each epoch:

```
(base_NL,  lean_signature)     the original pair
(docstring, lean_signature)    new: docstring → Lean
(base_NL,  docstring)          new: two descriptions of one theorem, matched to each other
```

**Both arms produce the same number of training examples.** Arm 2 does not train
on *more* data for these 14,501 concepts — it trains on *more varied* data. Over
2 epochs it draws 2 of the 3 possible pairs.

The one place the example count actually rises is the **4,246 genuinely new
theorems**, which add roughly **3.5%** more training concepts to Arm 2.

> A follow-on idea — enumerating all three pairs as explicit training examples
> rather than sampling two at random — is written up in
> `PROPOSAL_explicit_view_pairs.md`. It is not part of this run.

## 5. Why the comparison is valid

`--extra_train_jsonl` is applied **after** the train/dev split, and A1 records
that would touch dev are dropped. The evaluation set and retrieval corpus are
therefore byte-identical between the two arms.

This is verified rather than assumed: `a1_report.py` prints a **dev-set identity
check** as the first thing in its output. Both arms must agree on
`concepts_total`, `train`, `dev`, `n_dev_used` and `corpus_size`. If they do
not, the tool prints a warning and the comparison should be discarded.

## 6. What we verified before spending GPU time

| Check | Result |
|---|---|
| A1 file integrity | sha256 matches; 18,747 rows; 0 malformed; 0 duplicate IDs |
| Schema | every `module_name` starts with `Mathlib.`; no empty views |
| Docstrings are not restatements | 0 byte-identical; median similarity 0.129 |
| End-to-end plumbing | smoke test job `486063` passed (0.6B model, 2k rows, 1 epoch) |

## 7. How the models are evaluated

The model embeds a query and retrieves from a corpus of ~133k Lean statements.
The **primary metric is NL → Lean signature**, reported as Recall@1, Recall@5,
Recall@10 and MRR@10.

Five further pair types are also evaluated (NL → Lean type, NL rephrasing → Lean
signature, NL rephrasing → NL, Lean type → Lean signature, Lean signature → NL).

**Expect pair types 2–5 to be unchanged.** A1 only supplies `nl_informal` and
`lean_signature` views, so it cannot affect metrics that depend on `lean_type`
or `nl_informal_2`. Only the primary metric and the reverse direction
(Lean → NL) can move. This is a property of the data, not a bug.

## 8. How to interpret the result

**If the +A1 arm wins:** real Mathlib docstrings are useful training signal, and
the most likely mechanism is the `(base_NL, docstring)` pairs teaching the model
that a verbose LaTeX description and a terse docstring refer to the same
theorem.

**If the result is flat, that does not automatically mean the data is useless.**
The dev set is drawn from the base data, so every evaluation query is written in
the verbose LaTeX register. A1 is training-only and never appears in dev. The
model could genuinely improve at docstring-style retrieval while this evaluation,
which never asks docstring-style questions, shows nothing. Testing that would
need a held-out docstring-style eval set, which does not exist yet.

**Effect size expectation:** modest. 12% of training concepts gain a second
description and 3.5% more concepts are added. A swing of a few points on
Recall@1 would be a strong result; a change of under a point is within noise.

## 9. Results

> **To be filled in when both arms finish.** Generate with:
> ```bash
> bash repo/slurmscripts/a1_collect.sh mv3_qwen8b_paper_ep2 mv3_qwen8b_a1_ep2
> python repo/slurmscripts/a1_report.py --markdown \
>   checkpoints/mv3_qwen8b_paper_ep2 checkpoints/mv3_qwen8b_a1_ep2
> ```

### 9.1 Run details

| | Paper baseline | + A1 docstrings |
|---|---|---|
| Wall time | _TBD_ | _TBD_ |
| GPU-hours | _TBD_ | _TBD_ |
| Cost | _TBD_ | _TBD_ |
| Train concepts | _TBD_ | _TBD_ |
| Dev concepts | _TBD_ | _TBD_ |

### 9.2 Dev-set identity check

> Both arms must match on every column, or the comparison is void.

| Run | concepts_total | train | dev | n_dev_used | corpus_size |
|---|---|---|---|---|---|
| Paper | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| + A1 | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

### 9.3 How much of A1 was actually used

| Count | Value |
|---|---|
| Read from the A1 file | 18,747 |
| Dropped — theorem is a dev target | _TBD_ |
| Dropped — module is a dev module | _TBD_ |
| Merged into an existing train concept | _TBD_ |
| Added as new training concepts | _TBD_ |

### 9.4 PRIMARY RESULT — NL → Lean signature

| Metric | Stock Qwen3-8B | Paper baseline | + A1 docstrings | A1 − paper |
|---|---|---|---|---|
| Recall@1 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| Recall@5 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| Recall@10 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| MRR@10 | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

### 9.5 All pair types

| Pair type | Paper R@1 | +A1 R@1 | Δ R@1 | Paper MRR@10 | +A1 MRR@10 | Δ MRR@10 |
|---|---|---|---|---|---|---|
| NL → Lean signature (PRIMARY) | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| NL → Lean type | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| NL rephrasing → Lean signature | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| NL rephrasing → NL informal | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| Lean type → Lean signature | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
| Lean signature → NL informal | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |

### 9.6 Conclusion

_TBD — does adding Mathlib docstrings improve NL → Lean retrieval?_

## 10. Caveats and open questions

- **Evaluation register mismatch.** Dev queries are verbose LaTeX prose; A1 is
  terse docstring prose and never enters dev. A real improvement in
  docstring-style retrieval would be invisible to this evaluation. First
  hypothesis to test if the result is flat.
- **Some docstrings name rather than state.** For example,
  `MeasureTheory.condExp_mul_of_stronglyMeasurable_left` → *"Pull-out property
  of the conditional expectation."* That is weak training signal. A1 carries
  `filter_label` and `doc_slip_flag` metadata suggesting some filtering already
  happened, but we have not audited what survived.
- **Duplicate IDs in the base data.** `MathlibViews.jsonl` has 133,621 rows but
  126,059 unique `concept_id`s. Pre-existing, not introduced by A1, but it is
  unclear whether those rows are deduplicated or silently upweighted.
- **Pair types 2–5 cannot move**, as explained in §7.
- Further questions are tracked in §10 of `PROPOSAL_explicit_view_pairs.md`.

## 11. Reproducing this run

Full setup instructions are in `a1_README.md`. In brief, from a Tillicum login
node:

```bash
mkdir -p /gpfs/scrubbed/$USER/mathlib-ft && cd /gpfs/scrubbed/$USER/mathlib-ft
git clone -b trainingdata-mathlibdocstring \
  https://github.com/uw-math-ai/math2vec.git repo
mkdir -p logs && bash repo/slurmscripts/a1_setup_login.sh 2>&1 | tee logs/setup.log

sbatch a1_smoke.slurm                      # ~20 min sanity check first

sbatch --job-name=mv3_qwen8b_paper_ep2 \
  --export=ALL,RUN=mv3_qwen8b_paper_ep2 a1_run.slurm
sbatch --job-name=mv3_qwen8b_a1_ep2 \
  --export=ALL,RUN=mv3_qwen8b_a1_ep2,EXTRA=data/a1_kept_concepts_v4.19.0.jsonl \
  a1_run.slurm
```

Slurm account `mathai`; QOS `debug`, `interactive`, `normal`. No `--partition`
is needed. Each arm requests 1 GPU for 12 h and is expected to use ~8.3 h at
about $0.90/GPU-hour, so roughly $7.50 per arm and $15 for the pair.

Scratch is **not backed up** and is purged after 60 days without modification.
Archive results when the runs finish:

```bash
bash repo/slurmscripts/a1_collect.sh --archive \
  mv3_qwen8b_paper_ep2 mv3_qwen8b_a1_ep2
```

## 12. Files

| File | Purpose |
|---|---|
| `a1_EXPERIMENT_SUMMARY.md` | this document |
| `a1_README.md` | operational how-to |
| `a1_setup_login.sh` | login-node setup: workspace, env, data, model cache |
| `a1_smoke.slurm` | debug-QOS sanity check |
| `a1_run.slurm` | the real run; `RUN` and `EXTRA` select the arm |
| `a1_collect.sh` | wall time, GPU-hours, `[extra]` counts, archiving |
| `a1_report.py` | builds the comparison tables from `metrics.json` |
| `a1_overlap_text.py` | measures how novel A1 docstrings are vs the base NL |
| `a1_eval_checkpoint.py`, `a1_eval.slurm` | optional GPU re-evaluation |
| `PROPOSAL_explicit_view_pairs.md` | follow-on idea, not scheduled |
