# A2 — Explicit view-pair enumeration

**Status:** planned, not implemented. Nothing here has been run.
**Depends on:** the A1 run (`a1_README.md`) finishing, so A2 has a baseline.
**Author's note:** written at the end of the A1 setup session, 2026-11-16.

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

**A2 changes coverage from random to exhaustive. It does not add new data.**
For a concept with `n` views, rows go from 1 to `C(n, 2)`.

## 3. Why "this should increase performance no matter what" is not safe

It is a reasonable hypothesis, but there are three concrete ways it can lose.
Design around them or the run is wasted.

### 3.1 In-batch false negatives — the serious one

`CachedMultipleNegativesRankingLoss` treats **every other item in the batch as a
negative**. If two rows from the *same concept* land in the same batch, the loss
explicitly pushes apart two descriptions of the same theorem. That is a direct
training signal *against* what we want.

Today this is nearly impossible: one row per concept means a concept cannot
collide with itself. Under A2 a concept occupies up to `C(n,2)` rows, so
collisions become likely — and worse, consecutive rows from the same concept
will sit in the same batch unless shuffling separates them.

**Mitigation (required, not optional):** guarantee no two rows of the same
concept share a batch. Either
  * a custom `BatchSampler` that is concept-aware, or
  * `sentence_transformers` `BatchSamplers.NO_DUPLICATES`, which exists for
    exactly this — but note the trainer uses the legacy `model.fit()` API, so
    check whether that path accepts a batch sampler before assuming it works.
    If it does not, `model.fit()` may have to be replaced with
    `SentenceTransformerTrainer`, which is a much larger change.

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
5. **Baseline.** A2 must be compared against the **A1 arm**, not the paper arm,
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
an A2 run from an A1 run without reading the log.

**Leave eval completely alone.** `eval_retrieval` / `eval_all_pair_types` /
`group_split_records` must not change, or A2 is not comparable to A1.

## 6. Required GitHub updates

| File | Change |
|---|---|
| `finetune/train_qwen_mnrl_multiview_v3_tg.py` | the three flags, `ExplicitPairDataset`, concept-aware batch sampler, extra `metrics.json` counts |
| `slurmscripts/a2_run.slurm` | new; A1 recipe + `--explicit_view_pairs` |
| `slurmscripts/a2_smoke.slurm` | new; debug QOS, 0.6B, `--max_rows 2000`, asserts pair counts and no-duplicate batching |
| `slurmscripts/a1_report.py` | print `pairs_total` / `pairs_per_concept_avg` when present; treat A2 as a third arm |
| `slurmscripts/a1_README.md` | link to this plan |
| `slurmscripts/a2_explicit_pairs_PLAN.md` | mark implemented, record results |

Branch: continue on `trainingdata-mathlibdocstring`, or cut
`experiment-a2-explicit-pairs` off it. Commit and push before touching Tillicum —
the cluster pulls from `origin`.

## 7. Tillicum commands (after the code is pushed)

```bash
# refresh the working copy
cd /gpfs/scrubbed/$USER/mathlib-ft/repo && git pull --ff-only && cd ..
cp repo/finetune/train_qwen_mnrl_multiview_v3_tg.py .
cp repo/slurmscripts/a2_run.slurm repo/slurmscripts/a2_smoke.slurm .

# 1. smoke test FIRST -- debug QOS, ~20 min, ~$0.75
sbatch a2_smoke.slurm
grep -E '^\[pairs\]|PASS:|FAIL:' logs/mv3_smoke_a2_*.out

# 2. the real A2 arm -- only after the smoke test passes
sbatch --job-name=mv3_qwen8b_a2_ep2 \
  --export=ALL,RUN=mv3_qwen8b_a2_ep2,EXTRA=data/a1_kept_concepts_v4.19.0.jsonl \
  a2_run.slurm

# 3. results: A2 vs A1 vs paper, all on the same dev set
squeue -u $USER -o '%.10i %.14j %.8T %.10M %R'
bash repo/slurmscripts/a1_collect.sh mv3_qwen8b_a2_ep2
python repo/slurmscripts/a1_report.py \
  checkpoints/mv3_qwen8b_paper_ep2 \
  checkpoints/mv3_qwen8b_a1_ep2 \
  checkpoints/mv3_qwen8b_a2_ep2
```

Cost: expect **more** than A1's ~8.3 h, since steps scale with pair count.
Cap rows per concept to keep it inside the 12 h request, or raise `--time`.
At ~$0.90/GPU-hour, budget **$9-13** for the A2 arm.

Account is `mathai`; QOS available: `debug`, `interactive`, `normal`.

## 8. Known facts carried over from A1

* A1 overlap: 14,501 / 18,747 concept_ids (77.4%) already in base; 4,246 (22.6%) new.
* A1 docstrings are **not** restatements: 0 byte-identical, median text
  similarity 0.129, near-duplicate share 0.1%.
* Base `nl_informal` is verbose LaTeX prose; A1 is terse Mathlib docstrings with
  Lean notation. Two different registers for the same theorem — which is exactly
  why `(nl_base, nl_a1)` NL↔NL pairs may matter, and why A2's cross-modal-only
  default deserves an all-pairs ablation.
* Base file: 133,621 rows but 126,059 unique `concept_id`s (~7,562 duplicate ids).
* Eval is 6 pair types; A1/A2 data only has `nl_informal` + `lean_signature`, so
  only pair types 1 and 6 can move. Types 2-5 stay flat by construction.

---

## 9. Prompt to paste into a new Claude Code session

> I'm on the Math2Vec project (UW Math AI Lab), working in the `math2vec` repo on
> branch `trainingdata-mathlibdocstring`. Read
> `slurmscripts/a2_explicit_pairs_PLAN.md` first — it has the full context.
>
> I want to implement experiment A2: explicit view-pair enumeration. Right now
> `MultiViewBaseDataset` in `finetune/train_qwen_mnrl_multiview_v3_tg.py` emits
> one row per concept and picks 2 views at random per epoch. I want each concept
> to emit one row per view pair instead, so a Lean statement with two different
> NL descriptions becomes two explicit training examples.
>
> Before writing code, tell me how you'll handle in-batch false negatives —
> `CachedMultipleNegativesRankingLoss` uses in-batch negatives, so two rows from
> the same concept in one batch would train the model to push apart two
> descriptions of the same theorem. Section 3.1 of the plan covers this. Check
> whether the legacy `model.fit()` path can take a no-duplicates batch sampler,
> and if it can't, tell me what switching to `SentenceTransformerTrainer` costs
> before you start.
>
> Then:
> 1. Implement it behind `--explicit_view_pairs`, `--explicit_pairs_cross_modal`
>    and `--max_pairs_per_concept`, so the paper recipe is unchanged by default.
>    Record `pairs_total` / `pairs_per_concept_avg` / `pairs_capped` in
>    `metrics.json`. Do not touch `eval_retrieval`, `eval_all_pair_types` or
>    `group_split_records` — A2 must stay comparable to A1 on the same dev set.
> 2. Write `slurmscripts/a2_smoke.slurm` (debug QOS, 0.6B, `--max_rows 2000`,
>    under 30 min) and `slurmscripts/a2_run.slurm` (normal QOS, 8B, A1 recipe
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
