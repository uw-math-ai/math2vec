# PROPOSAL — Explicit view-pair enumeration

**Status: an idea, not a solidified experiment. Nothing here is scheduled.**

## Where this sits in the sequence

| # | Run | Status |
|---|---|---|
| 1 | **Smoke test** — 0.6B, 2k rows, 1 epoch, debug QOS | done (job 486063, PASSED) |
| 2 | **The 2-arm comparison** — paper recipe vs. paper + A1 dataset, 8B, 2 epochs | **the current run — see `a1_README.md`** |
| 3 | *This proposal* — explicit view-pair enumeration | not solidified, not scheduled |

The 2-arm comparison (row 2) is the real experiment and the thing to do next:

```bash
sbatch --job-name=mv3_qwen8b_paper_ep2 \
  --export=ALL,RUN=mv3_qwen8b_paper_ep2 a1_run.slurm

sbatch --job-name=mv3_qwen8b_a1_ep2 \
  --export=ALL,RUN=mv3_qwen8b_a1_ep2,EXTRA=data/a1_kept_concepts_v4.19.0.jsonl \
  a1_run.slurm
```

**This document is about something else entirely** — a possible *third* run,
after the 2-arm comparison reports. It proposes changing how training pairs are
built: give each concept one row per view pair, so a Lean statement with two
different NL descriptions (the pre-existing `nl_informal` and the A1 docstring)
becomes two explicit training examples rather than two random draws.

It uses the same A1 dataset. No new data is involved.

**Open questions:** see §10. Nothing is blocking; Q3 (implicit reweighting) is
the one that most deserves attention.
**Depends on:** the 2-arm comparison finishing, so this has a baseline.
**Author's note:** written 2026-11-16, at the end of the A1 setup session.

---

## 1. The idea

Today a concept contributes **one training row per epoch**, whatever its view
count. The proposal: give each concept **one row per view pair**, so a Lean
statement paired with two different NL descriptions becomes two explicit
training examples instead of one randomly-drawn example.

## 2. What the trainer does today (read this before changing anything)

`finetune/train_qwen_mnrl_multiview_v3_tg.py`, `MultiViewBaseDataset`:

```python
def __len__(self):                       # one row per CONCEPT
    return len(self.records)

def __getitem__(self, idx):
    r = self.records[idx]
    all_views = ([(v, "nl") for v in r.nl_views] +
                 [(v, "lean") for v in r.lean_views])
    (anchor, mod), (positive, _) = random.sample(all_views, 2)
```

So for a concept with 3 views (2 NL + 1 Lean) the three possible pairs are

| pair | currently |
|---|---|
| `(nl_base, lean_sig)` | drawn at random |
| `(nl_a1,   lean_sig)` | drawn at random |
| `(nl_base, nl_a1)`    | drawn at random |

With 2 epochs the concept gets **2 draws out of 3 possible pairs**. Coverage is
stochastic and incomplete, and resampling per epoch is deliberate — the
docstring calls it "SimCLR-style stochastic pairing."

**This changes coverage from random to exhaustive. It does not add new data.**
For a concept with `n` views, rows go from 1 to `C(n, 2)`.

## 3. Why "this should increase performance no matter what" is not safe

It is a reasonable hypothesis, but there are three concrete ways it can lose.
Design around them or the run is wasted.

### 3.1 In-batch false negatives — real, but quantified as negligible

`CachedMultipleNegativesRankingLoss` treats every other item in the batch as a
negative. If two rows from the *same concept* land in one batch, the loss pushes
apart two descriptions of the same theorem — a gradient directly against the
objective.

Today this is impossible: one row per concept means a concept cannot collide
with itself. Explicit enumeration makes it possible. **But at this batch size it
is rare enough to ignore:**

```
rows (enumerated)          149,002      batches/epoch   9,313
P(two given rows collide)  1.01e-04     batch_size      16
P(a merged concept collides) 3.02e-04
expected collisions/epoch  4.4          = 0.047% of batches
```

Roughly 4 affected batches per epoch out of 9,313. This was initially written up
as blocking; the arithmetic says it is not. No concept-aware batch sampler is
required, and no migration off `model.fit()` is needed on these grounds.

Two caveats worth keeping: the estimate assumes a uniform shuffle (verify rows
of one concept are not left adjacent in the dataset before shuffling), and it
scales with batch size — raising `--batch_size` well above 16, or using
GradCache to make the effective negative pool much larger, would make this
matter again.

### 3.2 Implicit reweighting

Rows per concept become `C(n,2)`, so concepts with more views are upweighted.
A1-merged concepts (3 views → 3 rows) get 3x the weight of a plain 2-view
concept (1 row). That is a silent change to the data distribution, and it
correlates with *which theorems happened to have docstrings* — not with
importance. Consider capping rows per concept, or sampling `min(C(n,2), cap)`.

### 3.3 Compute and epoch semantics

Steps per epoch rise with total pair count. "2 epochs" stops meaning what it
meant in the paper recipe, so step-matched and epoch-matched comparisons
diverge. Decide which one the comparison holds fixed, and say so in the writeup.

## 4. Design decisions to settle first

1. **Pair scope.** All `C(n,2)` pairs, or only cross-modal `(NL, Lean)` pairs?
   Cross-modal only keeps the objective aligned with the NL→Lean eval and
   avoids inflating NL↔NL pairs. Recommended default: **cross-modal only**,
   with a flag for all-pairs.
2. **Cap.** Max rows per concept, to bound 3.2. Suggest `--max_pairs_per_concept 4`.
3. **Batching.** How no-duplicates batching is enforced (3.1). **Blocking.**
4. **Epoch budget.** Match epochs (simpler) or match total steps (fairer)?
   Recommended: run epoch-matched, and record total steps in `metrics.json`
   so a step-matched reading is still possible.
5. **Baseline.** This must be compared against the **A1 arm of the 2-arm run**, not the paper arm,
   on the **same dev set** — so same `--local_jsonl`, `--seed 42`, `--dev_frac 0.1`,
   no `--max_rows`.

## 5. Implementation sketch

Add to `train_qwen_mnrl_multiview_v3_tg.py`, behind a flag so the paper recipe
is untouched by default:

```
--explicit_view_pairs            enumerate pairs instead of sampling (default off)
--explicit_pairs_cross_modal     restrict to (NL, Lean) pairs (default on when above is set)
--max_pairs_per_concept N        cap rows per concept (default 4)
```

New `ExplicitPairDataset(Dataset)` alongside `MultiViewBaseDataset`:
build a flat list of `(record_idx, view_i, view_j)` at construction, have
`__len__` return its length and `__getitem__` return that fixed pair. Keep a
`concept_id` per row so a concept-aware batch sampler can use it.

Record in `metrics.json` under `counts`: `pairs_total`, `pairs_per_concept_avg`,
`pairs_capped`, plus `batch_sampler` under `lr_schedule`, so a reader can tell
an explicit-pairs run from a 2-arm run without reading the log.

**Leave eval completely alone.** `eval_retrieval` / `eval_all_pair_types` /
`group_split_records` must not change, or this is not comparable to the 2-arm run.

## 6. Required GitHub updates

| File | Change |
|---|---|
| `finetune/train_qwen_mnrl_multiview_v3_tg.py` | the three flags, `ExplicitPairDataset`, concept-aware batch sampler, extra `metrics.json` counts |
| `slurmscripts/explicit_pairs_run.slurm` | new; A1 recipe + `--explicit_view_pairs` |
| `slurmscripts/explicit_pairs_smoke.slurm` | new; debug QOS, 0.6B, `--max_rows 2000`, asserts pair counts and no-duplicate batching |
| `slurmscripts/a1_report.py` | print `pairs_total` / `pairs_per_concept_avg` when present; treat explicit-pairs as a third arm |
| `slurmscripts/a1_README.md` | link to this plan |
| `slurmscripts/PROPOSAL_explicit_view_pairs.md` | mark implemented, record results |

Branch: continue on `trainingdata-mathlibdocstring`, or cut
`experiment-explicit-pairs` off it. Commit and push before touching Tillicum —
the cluster pulls from `origin`.

## 7. Tillicum commands (after the code is pushed)

```bash
# refresh the working copy
cd /gpfs/scrubbed/$USER/mathlib-ft/repo && git pull --ff-only && cd ..
cp repo/finetune/train_qwen_mnrl_multiview_v3_tg.py .
cp repo/slurmscripts/explicit_pairs_run.slurm repo/slurmscripts/explicit_pairs_smoke.slurm .

# 1. smoke test FIRST -- debug QOS, ~20 min, ~$0.75
sbatch explicit_pairs_smoke.slurm
grep -E '^\[pairs\]|PASS:|FAIL:' logs/mv3_smoke_pairs_*.out

# 2. the real explicit-pairs arm -- only after its smoke test passes
sbatch --job-name=mv3_qwen8b_a1_pairs_ep2 \
  --export=ALL,RUN=mv3_qwen8b_a1_pairs_ep2,EXTRA=data/a1_kept_concepts_v4.19.0.jsonl \
  explicit_pairs_run.slurm

# 3. results: explicit-pairs vs A1 arm vs paper arm, all on the same dev set
squeue -u $USER -o '%.10i %.14j %.8T %.10M %R'
bash repo/slurmscripts/a1_collect.sh mv3_qwen8b_a1_pairs_ep2
python repo/slurmscripts/a1_report.py \
  checkpoints/mv3_qwen8b_paper_ep2 \
  checkpoints/mv3_qwen8b_a1_ep2 \
  checkpoints/mv3_qwen8b_a1_pairs_ep2
```

Cost: expect **more** than A1's ~8.3 h, since steps scale with pair count.
Cap rows per concept to keep it inside the 12 h request, or raise `--time`.
At ~$0.90/GPU-hour, budget **$9-13** for the explicit-pairs arm.

Account is `mathai`; QOS available: `debug`, `interactive`, `normal`.

## 8. Known facts carried over from the A1 setup session

* A1 overlap: 14,501 / 18,747 concept_ids (77.4%) already in base; 4,246 (22.6%) new.
* A1 docstrings are **not** restatements: 0 byte-identical, median text
  similarity 0.129, near-duplicate share 0.1%.
* Base `nl_informal` is verbose LaTeX prose; A1 is terse Mathlib docstrings with
  Lean notation. Two different registers for the same theorem — which is exactly
  why `(nl_base, nl_a1)` NL↔NL pairs may matter, and why the cross-modal-only
  default deserves an all-pairs ablation.
* Base file: 133,621 rows but 126,059 unique `concept_id`s (~7,562 duplicate ids).
* Eval is 6 pair types; the A1 dataset only has `nl_informal` + `lean_signature`, so
  only pair types 1 and 6 can move. Types 2-5 stay flat by construction.

## 10. Open questions

Nothing here is settled. Q1-Q4 are design questions for this proposal (Q1 is now resolved); Q5-Q9 came out of the A1 session
and apply to the project generally. **Deferred by decision: revisit after the
first multi-arm run (paper vs A1) completes** — the results may answer or
reprioritise several of them.

### Q1. In-batch false negatives — resolved as negligible, not blocking

Measured, not assumed: with `batch_size=16` and ~149,002 enumerated rows, two
rows of one concept share a batch about **4.4 times per epoch out of 9,313
batches (0.047%)**. See §3.1 for the arithmetic.

**Consequence:** no concept-aware batch sampler is needed, and the question of
whether the legacy `model.fit()` path accepts `BatchSamplers.NO_DUPLICATES` is
moot. The feared migration to `SentenceTransformerTrainer` is not required.

Revisit only if `--batch_size` rises substantially above 16, or if the effective
negative pool grows (e.g. GradCache across mini-batches). Also confirm the
dataset is uniformly shuffled, so a concept's rows are not left adjacent.

### Q2. Pair scope: all `C(n,2)` pairs, or cross-modal `(NL, Lean)` only?

Cross-modal only keeps the objective aligned with the NL→Lean eval. All-pairs
adds NL↔NL pairs, which §8 argues may be the most valuable part of A1 (teaching
the model that verbose LaTeX prose and a terse docstring describe the same
theorem). Recommended: cross-modal default, all-pairs as an ablation.

### Q3. Implicit reweighting — the question that actually matters

Enumeration is not a neutral change in coverage; it is a **3x upweighting** of
every concept that gained a second NL view:

```
merged concepts          14,501   = 12.1% of train concepts
rows they contribute     43,503   = 29.2% of all training rows
```

So 12.1% of concepts would supply 29.2% of the training signal — and which
theorems get that boost is arbitrary. It tracks *which ones happened to have a
Mathlib docstring*, not which ones are important or hard. That could help
(docstring-bearing theorems may be better documented and more central) or skew
the model toward a lopsided slice of Mathlib. Untested either way.

Mitigation: `--max_pairs_per_concept N` to cap rows. `N` is a guess until the
view-count distribution across the base data is measured, which nobody has done.

Cost note: enumeration is **1.24x the steps**, so ~10.3 h and ~$9.28 per arm
instead of 8.3 h and ~$7.50.

### Q4. Epoch-matched or step-matched comparison?

Steps per epoch scale with pair count, so "2 epochs" stops meaning what it meant
in the paper recipe. Recommended: run epoch-matched and record total steps, so a
step-matched reading stays possible after the fact.

### Q5. What are the 7,562 duplicate `concept_id`s in the base data?

`MathlibViews.jsonl` has 133,621 rows but 126,059 unique `concept_id`s. Unknown
whether `load_concepts` dedupes, merges views, or keeps both rows — and
therefore whether some concepts are silently upweighted in the paper recipe
itself. Pre-existing, not introduced by A1, but it affects how pair counts are
computed in this proposal.

*Resolve by:* reading `load_concepts` and counting, no GPU.

### Q6. Do uninformative A1 docstrings need filtering?

Some Mathlib docstrings name a theorem rather than state it, e.g.
`MeasureTheory.condExp_mul_of_stronglyMeasurable_left` → *"Pull-out property of
the conditional expectation."* That is weak training signal and, as an NL
anchor, close to unlearnable. The A1 metadata carries `filter_label: KEEP` and
`doc_slip_flag`, which suggests some filtering already happened, but we never
checked what those fields mean or how many short docstrings survived.

*Resolve by:* length distribution over A1 `nl_informal`, plus inspecting what
`doc_slip_flag` was computed from. No GPU.

### Q7. Does the eval register mismatch cap the measurable benefit?

Dev queries come from the base data — verbose LaTeX prose. A1 docstrings are
terse with Lean notation, and A1 is training-only, so it never appears in dev.
The model may genuinely improve at docstring-style retrieval while the eval,
which only asks LaTeX-style questions, shows nothing.

If A1 comes back flat, this is the first hypothesis to test — not "the data is
bad." Would need a held-out docstring-style eval set, which does not exist yet
and would have to come out of the dev modules to stay honest.

### Q8. Should A1 concepts get `lean_type` and `nl_informal_2` views?

The eval suite has 6 pair types, but A1 supplies only `nl_informal` and
`lean_signature`, so pair types 2-5 are flat by construction. Generating the
missing views for A1 concepts would make the full suite meaningful — at the cost
of synthesising data, which changes what the experiment is testing.

### Q9. Are hard negatives a missed opportunity for A1?

`a1_kept_concepts_v4.19.0.jsonl` has empty `hard_negatives.nl` / `.lean` arrays,
and the paper recipe disables the hard-negative loader anyway
(`--n_hard_negs 1000`). Whether mining hard negatives for the A1 concepts would
help is untested and orthogonal to this proposal.

### Resolved during the A1 session (recorded so they are not re-litigated)

* Slurm account is `mathai`; QOS `debug`, `interactive`, `normal` all available.
* `--partition` is not needed on Tillicum and is omitted from all scripts.
* A1 docstrings are not restatements: 0 byte-identical of 14,501 overlapping,
  median similarity 0.129, near-duplicate share 0.1%. Experiment is well-posed.
* Training is a **full** fine-tune of all 8B parameters — no LoRA, no PEFT, no
  frozen layers.
* `--extra_train_jsonl` leaves the dev set byte-identical, verified by the smoke
  test and enforced by `a1_report.py`'s dev-set identity check.

---

## 11. Prompt to paste into a new Claude Code session

> I'm on the Math2Vec project (UW Math AI Lab), working in the `math2vec` repo on
> branch `trainingdata-mathlibdocstring`. Read
> `slurmscripts/PROPOSAL_explicit_view_pairs.md` first — it has the full context.
>
> I want to implement the explicit view-pair enumeration proposal. Right now
> `MultiViewBaseDataset` in `finetune/train_qwen_mnrl_multiview_v3_tg.py` emits
> one row per concept and picks 2 views at random per epoch. I want each concept
> to emit one row per view pair instead, so a Lean statement with two different
> NL descriptions becomes two explicit training examples.
>
> Two things already settled, so don't re-derive them. In-batch false negatives
> were measured and are negligible at batch 16 (~4.4 collisions per epoch out of
> 9,313 batches, 0.047%) — see §3.1 and Q1. No concept-aware batch sampler is
> needed and no migration off `model.fit()` is required. The real design question
> is Q3: enumeration is a 3x upweighting of merged concepts, so 12.1% of concepts
> would supply 29.2% of training rows. Tell me how you want to handle that — a
> cap via `--max_pairs_per_concept`, or accept the reweighting — before writing
> code.
>
> Then:
> 1. Implement it behind `--explicit_view_pairs`, `--explicit_pairs_cross_modal`
>    and `--max_pairs_per_concept`, so the paper recipe is unchanged by default.
>    Record `pairs_total` / `pairs_per_concept_avg` / `pairs_capped` in
>    `metrics.json`. Do not touch `eval_retrieval`, `eval_all_pair_types` or
>    `group_split_records` — this must stay comparable to the 2-arm run on the same dev set.
> 2. Write `slurmscripts/explicit_pairs_smoke.slurm` (debug QOS, 0.6B, `--max_rows 2000`,
>    under 30 min) and `slurmscripts/explicit_pairs_run.slurm` (normal QOS, 8B, A1 recipe
>    plus the new flags), modelled on the `a1_*` scripts. Account `mathai`, no
>    `--partition` line.
> 3. Update `slurmscripts/a1_report.py` to show the pair counts and handle a
>    third arm.
> 4. Verify what you can without a GPU — syntax, a unit check that pair
>    enumeration and the cap produce the counts you expect, and a check that no
>    batch contains two rows of the same concept. Show me the evidence.
> 5. Commit and push to `origin/trainingdata-mathlibdocstring`.
> 6. Give me the exact commands to paste into Tillicum, smoke test first.
>
> Constraints: I'm on the Tillicum cluster (UW Hyak, H200, Slurm), account
> `mathai`, QOS `debug`/`interactive`/`normal`. Work from
> `/gpfs/scrubbed/$USER/mathlib-ft`. Show me every command before running
> anything that costs GPU time, and never submit an sbatch job without my
> explicit "yes". You're running on my laptop and cannot reach the cluster — I
> paste output back to you.
