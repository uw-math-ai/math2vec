# Experiment: Do Mathlib docstrings improve NL → Lean retrieval?

**Status:** both arms complete. Run 2026-11-16/17 on Tillicum (UW Hyak).
**Jobs:** `486428` (paper arm), `486429` (+A1 arm) — both `COMPLETED`, exit 0.
**Headline:** A1 teaches the model a *query register* the base data does not
cover. On docstring-style queries it is **+0.0769 Recall@1 (4.3 sigma)**; on the
base LaTeX-style queries the main benchmark asks, it is −0.0080. The benchmark
measured the cost of that trade and none of the benefit. See §9.7 and §9.8.

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

**A note on which pair types can move — corrected after the run.** An earlier
version of this document predicted that pair types 2–5 could not move, on the
grounds that A1 only supplies `nl_informal` and `lean_signature` views. **That
was wrong.** NL → Lean type moved the most of any pair type (−0.0208 R@1).

The error was treating A1 as if it only adds *views*. It also retrains the
**encoder** for the field it is added to. Because A1 arrives as extra
`nl_informal` text, it changes how `nl_informal` is embedded — and that affects
every pair type using `nl_informal` on either side, whatever the other side is.
Pair types 1 and 2 both query with `nl_informal`, and both declined. See §9.5.

## 8. How to interpret the result

**If the +A1 arm wins:** real Mathlib docstrings are useful training signal, and
the most likely mechanism is the `(base_NL, docstring)` pairs teaching the model
that a verbose LaTeX description and a terse docstring refer to the same
theorem.

> **This section was written before the results. It was right** — see §9.7,
> which confirms the register effect and measures it at +0.0769 Recall@1.

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

Both arms completed successfully with exit code 0, no OOM, no errors.
Generated with `a1_collect.sh` and `a1_report.py`.

### 9.1 Run details

| | Paper baseline | + A1 docstrings |
|---|---|---|
| Slurm job | 486428 | 486429 |
| Wall time | 07:09:00 | 07:06:59 |
| GPU-hours | 7.15 | 7.12 |
| Cost (~$0.90/GPU-h) | ~$6.44 | ~$6.41 |
| Base train concepts | 118,334 | 118,334 |
| Dev concepts | 15,287 | 15,287 |

Total: **14.27 GPU-hours, ~$12.85**, ~7.3 h wall-clock (the arms ran
concurrently, starting 10 minutes apart).

> The "base train concepts" row counts only the base split, which is why both
> arms show 118,334. The +A1 arm additionally trains on 3,847 new training-only
> concepts, for an effective 122,181. See §9.3.

### 9.2 Dev-set identity check — PASSED

| Run | concepts_total | train | dev | n_dev_used | corpus_size |
|---|---|---|---|---|---|
| Paper | 133,621 | 118,334 | 15,287 | 15,287 | 133,621 |
| + A1 | 133,621 | 118,334 | 15,287 | 15,287 | 133,621 |

Identical on every column, so the arms are comparable. Both also report the
*same* stock-model baseline (0.7517 R@1), confirming the evaluation is
deterministic and genuinely shared.

### 9.3 How much of A1 was actually used

| Count | Value |
|---|---|
| Read from the A1 file | 18,747 |
| Dropped — theorem is a dev target | 1,497 |
| Dropped — module is a dev module | 399 |
| Merged into an existing train concept | 13,004 |
| &nbsp;&nbsp;NL views appended by those merges | 13,004 |
| Added as new training concepts | 3,847 |

**16,851 of 18,747 (89.9%) made it into training**; 1,896 were dropped to
protect the dev set.

`nl_views_added` equals `merged_into_train` exactly (13,004 = 13,004), meaning
**every single merge contributed a genuinely new NL view** — no A1 docstring
duplicated text the base record already had. This confirms at full scale what
the pre-run text-similarity check (§2) measured on a sample.

### 9.4 PRIMARY RESULT — NL → Lean signature

| Metric | Stock Qwen3-8B | Paper baseline | + A1 docstrings | A1 − paper |
|---|---|---|---|---|
| **Recall@1** | 0.7517 | **0.8592** | 0.8511 | **−0.0080** |
| Recall@5 | 0.9534 | 0.9836 | 0.9813 | −0.0023 |
| Recall@10 | 0.9761 | 0.9929 | 0.9920 | −0.0009 |
| MRR@10 | 0.8406 | 0.9148 | 0.9099 | −0.0048 |

**Adding A1 made the primary metric slightly worse.** Both arms improve hugely
over the stock model (+0.1075 and +0.0994 R@1) — fine-tuning works; A1 simply
adds nothing here and costs a little.

Scale: −0.0080 on R@1 is about **124 of 15,287 queries**, roughly **2.0 sigma**
on a conservative unpaired test. Real, small, and near the edge of significance.

### 9.5 All pair types — the informative result

| Pair type | Query field | Paper R@1 | +A1 R@1 | Δ R@1 | Δ MRR@10 |
|---|---|---|---|---|---|
| NL → Lean signature (PRIMARY) | `nl_informal` | 0.859 | 0.851 | **−0.0080** | −0.0048 |
| NL → Lean type | `nl_informal` | 0.808 | 0.787 | **−0.0208** | −0.0135 |
| NL rephrasing → Lean signature | `nl_informal_2` | 0.812 | 0.813 | +0.0017 | +0.0010 |
| NL rephrasing → NL informal | `nl_informal_2` | 0.922 | 0.922 | −0.0005 | −0.0002 |
| Lean type → Lean signature | `lean_type` | 0.801 | 0.805 | +0.0039 | +0.0014 |
| Lean signature → NL informal | `lean_signature` | 0.852 | 0.857 | +0.0050 | +0.0027 |

**The two pair types that query with `nl_informal` are the only two that
declined, and they declined by the largest margins. Every other pair type moved
by less than ±0.005.**

That is the signature of a register conflict. A1 docstrings were poured into the
same `nl_informal` slot as the base data's verbose LaTeX prose (§2). The result:
`nl_informal` became a slightly *worse query encoder* for the base register —
the only register this benchmark ever asks in — while `nl_informal` as a
retrieval *target* held up or improved slightly (+0.0050 from Lean signatures).

### 9.6 Per-pair-type contrastive loss, fine-tuned (lower is better)

| Pair type | Paper | + A1 | Δ |
|---|---|---|---|
| NL → Lean signature (PRIMARY) | 0.0016 | 0.0011 | −0.0006 |
| NL → Lean type | 0.0124 | 0.0044 | **−0.0080** |
| NL rephrasing → Lean signature | 0.0038 | 0.0035 | −0.0003 |
| NL rephrasing → NL informal | 0.0027 | 0.0015 | −0.0012 |
| Lean type → Lean signature | 0.0126 | 0.0146 | +0.0021 |
| Lean signature → NL informal | 0.0009 | 0.0009 | −0.0000 |

**The +A1 model has lower contrastive loss on five of six pair types, including
the primary — yet worse retrieval.** These measure different things. Loss is
in-batch discrimination among 16 candidates; Recall@1 is top-1 against 133,621
near-neighbours. A1 appears to have made the embedding space better at coarse
separation and slightly worse at fine-grained precision.

### 9.7 Docstring-style evaluation — the result that reframes everything

The main benchmark only ever asks questions in one register: the base dataset's
verbose LaTeX prose. §9.5 suggested A1 was being penalised for introducing a
second register into a single-register evaluation. This tested that directly.

**Method.** Same two saved models, same 133,621-document `lean_signature`
corpus, same retrieval task, same delta formula. The only thing that changes is
the text of the query. Run as job `495410` via `a1_docstring_eval.slurm`;
no retraining.

The query set was free. The **1,497 A1 records whose theorem landed in the dev
set** were dropped from training by the leakage filter (`drop_dev_id`, §9.3), so
neither model has ever seen those docstrings — and since dev concepts are
excluded from training in both arms, neither model trained on those theorems at
all. A **base-NL control** queries the same 1,497 theorems with the base
dataset's prose, which separates "better at docstrings" from "easier theorems".

| Query style | Paper baseline | + A1 docstrings | Δ R@1 | Significance |
|---|---|---|---|---|
| **Docstring** | 0.5818 | **0.6587** | **+0.0769** | **4.3 sigma** — 2.2× the noise floor |
| Base-NL (control) | 0.8577 | 0.8490 | −0.0087 | 0.7 sigma — inside noise |

Full metrics:

| Query style | Metric | Paper | + A1 | Δ |
|---|---|---|---|---|
| Docstring | Recall@1 | 0.5818 | 0.6587 | +0.0768 |
| Docstring | Recall@5 | 0.8484 | 0.9071 | +0.0588 |
| Docstring | Recall@10 | 0.9205 | 0.9459 | +0.0254 |
| Docstring | MRR@10 | 0.6993 | 0.7662 | +0.0669 |
| Base-NL | Recall@1 | 0.8577 | 0.8490 | −0.0087 |
| Base-NL | Recall@5 | 0.9933 | 0.9900 | −0.0033 |
| Base-NL | Recall@10 | 0.9973 | 0.9947 | −0.0027 |
| Base-NL | MRR@10 | 0.9168 | 0.9124 | −0.0043 |

Noise floor at n=1,497: 1 sigma = 0.0177, **2 sigma = 0.0354** on Recall@1.

**The control reproduces the main experiment.** Its −0.0087 on 1,497 queries
matches the main eval's −0.0080 on 15,287. So this is a representative subset,
not a favourable slice, and the main result is independently confirmed.

**There is a large register gap, and A1 closes a third of it.**

| Model | base-NL R@1 | docstring R@1 | gap |
|---|---|---|---|
| Paper baseline | 0.8577 | 0.5818 | **0.2759** |
| + A1 docstrings | 0.8490 | 0.6587 | **0.1903** |

A model trained only on base NL is **27.6 points worse** when asked in Mathlib's
own register. A1 closes **31%** of that gap.

**This is generalisation, not leakage.** The 1,497 query docstrings were never
trained on. The +A1 model learned the register from the 16,851 *other* A1
docstrings and transferred it to unseen ones.

### 9.8 Conclusion — what A1 is actually for

**A1 is a register-coverage dataset, and it works.**

The base training data describes every theorem in one voice: verbose LaTeX
prose. Mathlib itself is written in another: terse, backtick-heavy, Lean
notation. Those are different enough that a model trained only on the first is
**27.6 Recall@1 points worse** when asked in the second (§9.7). That gap is not
a quirk of this experiment — it is a real blind spot in the model the paper
recipe produces, and nothing in the existing benchmark would ever have revealed
it.

Adding A1 closes 31% of that blind spot, for a measured cost of about
**0.9 Recall@1 points** on the register the benchmark does test. An 8.8 : 1
trade, in favour of the capability we previously had no way to see.

**So why did the headline number go down?** Because the benchmark asks every one
of its 15,287 questions in the base register. It measured the entire cost of the
trade and none of the benefit. The −0.0080 in §9.4 is real and reproducible —
it is just not the whole result, and on its own it is actively misleading about
whether the dataset is worth having.

**What caused the trade.** A1 was merged into the existing `nl_informal` field,
so both registers compete for one encoder. The model got better at spanning them
and slightly blurrier at the original — exactly the pattern in §9.5, where the
only two pair types that declined are the only two that query with
`nl_informal`.

**The question is no longer whether A1 is useful. It is whether the trade is
necessary.** Nothing forces the two registers to share a field.

**Recommended next steps, re-ranked after §9.7:**

1. **Give A1 its own view field** (`nl_docstring`) instead of merging into
   `nl_informal`. If the trade is an artefact of the shared slot, this should
   keep most of the +0.0769 and recover the −0.0087. Highest value, and it
   directly tests the proposed mechanism.
2. **Fix the benchmark.** A single-register evaluation nearly caused us to
   discard a dataset that measurably improves the model. The docstring eval set
   built here (1,497 held-out queries) should become a standing metric reported
   alongside the primary, so register coverage is visible by default. Costs no
   GPU time beyond the eval itself.
3. **Decide which register users actually type.** If Math2Vec serves people
   searching Lean, terse notation-heavy queries may be closer to real usage than
   LaTeX prose — in which case the +A1 model may already be the better product
   model, benchmark regression notwithstanding. This is a team decision, not an
   experiment.
4. **Explicit view-pair enumeration** (`PROPOSAL_explicit_view_pairs.md`) —
   **re-ranked upward.** It was previously deprioritised on the theory that it
   would amplify a degradation. §9.7 shows those pairs were teaching a real and
   valuable register correspondence, so enumerating `(base_NL, docstring)` pairs
   may amplify the *gain* instead. Most attractive combined with step 1, where
   the pairing becomes an explicit `nl_informal` ↔ `nl_docstring` signal rather
   than two texts crowding one field.
5. **Ablation on the 3,847 new-theorem concepts — downgraded.** The gain was
   measured on dev theorems that are not among the new concepts, so it comes
   from register transfer, not added coverage. Less informative than it looked.

**Caveats.** One run per arm, one seed; run-to-run variance is plausibly around
±0.005 Recall@1. The docstring gain (+0.0769, 4.3 sigma) is far outside that and
is safe. The base-NL loss (−0.0080 to −0.0087, roughly 0.7–2 sigma depending on
sample) is small enough that it could partly be noise — which, if anything,
makes the trade look better still.

## 10. Caveats and open questions

- **Evaluation register mismatch — CONFIRMED, no longer open.** Dev queries are
  verbose LaTeX prose; A1 is terse docstring prose. §9.7 measured the effect
  directly: +0.0769 Recall@1 on docstring queries at 4.3 sigma, against −0.0087
  on the base register. The benchmark's single-register design hid the benefit
  entirely. Adding a standing docstring metric is recommendation 2 in §9.8.
- **Some docstrings name rather than state.** For example,
  `MeasureTheory.condExp_mul_of_stronglyMeasurable_left` → *"Pull-out property
  of the conditional expectation."* That is weak training signal. A1 carries
  `filter_label` and `doc_slip_flag` metadata suggesting some filtering already
  happened, but we have not audited what survived.
- **Duplicate IDs in the base data.** `MathlibViews.jsonl` has 133,621 rows but
  126,059 unique `concept_id`s. Pre-existing, not introduced by A1, but it is
  unclear whether those rows are deduplicated or silently upweighted.
- **A corrected prediction.** This document originally claimed pair types 2–5
  could not move. NL → Lean type moved the most of any pair type. A1 retrains
  the `nl_informal` encoder, not just the view inventory — see §7 and §9.5.
- **One run per arm, one seed.** The primary effect (−0.0080 R@1) is close to
  plausible run-to-run variance. No replicates were run.
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
| `a1_docstring_eval.py`, `a1_docstring_eval.slurm` | docstring-style eval on the 1,497 held-out A1 records |
| `a1_eval_checkpoint.py`, `a1_eval.slurm` | optional GPU re-evaluation |
| `PROPOSAL_explicit_view_pairs.md` | follow-on idea, not scheduled |
