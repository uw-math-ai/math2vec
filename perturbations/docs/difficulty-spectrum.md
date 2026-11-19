# Which perturbations should a model find hard?

Contrastive training on natural-language math pairs underperformed, and the
working theory is that the model learned token overlap rather than logic. If
that is right, a Lean perturbation dataset only helps where surface overlap and
logical content **disagree** — everywhere else the model can keep word matching
and still score well.

This document ranks the 28 perturbations along two axes:

| Axis | What it asks | Where it comes from |
|---|---|---|
| **Hidden signal** | How much of the change is invisible to word matching? | **Measured** — [`analyze_geometry.py`](../pipeline/analyze_geometry.py) |
| **Knowledge required** | What must a model *know* to get the change right? | **Predicted** — argued below, not yet tested |

The first says which pairs are worth training on. The second says in what order
a model is likely to learn them. They are not the same: a perturbation can be
completely invisible to surface matching (high signal) and still be trivial for
a model that has the right knowledge, or vice versa.

---

## Axis 1 — hidden signal (measured)

Method: embed every anchor and variant with purely lexical representations
(TF-IDF over Lean tokens, character n-grams, token-set overlap, sequence
alignment — see [`src/wiggle/lexical.py`](../src/wiggle/lexical.py)). No neural
model is involved, deliberately: these numbers are the *floor*, what a model
gets for free without understanding anything.

Two quantities per perturbation:

* **surface Δ** — how far the variant moved, rescaled so `0.0` is "sitting on
  the anchor" and `1.0` is "as far away as an unrelated theorem".
* **meaning Δ** — logical distance, read off the truth-propagation table:
  `0.0` equivalent, `0.34` entailed, `0.67` graded, `1.0` contradictory.

**signal = meaning Δ − surface Δ.** Positive means the meaning moved further
than the words did.

### The headline

Across the 298 depth-1 variants from 24 shape-sampled Mathlib anchors:

* variants sit at **collapse 0.90** — that is, 90% of the way from "unrelated
  theorem" to "the identical string". They do essentially lie on the anchor,
  which is what we expected.
* **284/298 (95%)** of variants still retrieve their own anchor as nearest
  neighbour. Of the 14 that do not, 10 are `alpha_rename` — every other
  perturbation leaves the statement in its own neighbourhood.
* among pairs where an equivalence-preserving rewrite actually rewrote
  something, a *logically different* variant was lexically **closer** to the
  anchor than a *logically identical* one **90% of the time** (373/416).

That last number is the one that matters. Surface similarity is not merely
uninformative about logical similarity here — it is **anti-correlated**. A
model scoring by word overlap is not just failing to learn; it is being pulled
in the wrong direction. That is a concrete mechanism for the natural-language
result.

The other two runs reproduce it: 82% on the original 10 benchmark anchors, and
on the deep run 96% against `alpha_rename` positives and 63% against
`de_morgan_rewrite` positives.

> Only the breadth run has been regenerated since `alpha_rename` was reworked
> (see below). `data/benchmark-review` and `data/deep-chains` still contain
> `wv0`-style variants, so their `alpha_rename` rows describe the old
> transform. Every other perturbation is unaffected.

### Measured ranking

Three runs, all reproducible from the repo:

* **breadth run** — 298 variants, 24 Mathlib anchors sampled for syntactic
  shape, one perturbation each (`data/mathlib-review`). **The primary
  measurement**: 20 of the 28 perturbations fire, most of them 10–24 times.
* **depth-1 review** — 49 variants, 10 benchmark anchors
  (`data/benchmark-review`). The original run, now superseded in coverage but
  useful as an independent sample.
* **deep run** — 158 variants from a *single* anchor
  (`MeasureTheory.tendstoInMeasure_iff_tendsto_Lp_finite`), perturbations
  composed up to depth 3 (`data/deep-chains`). Narrow but deep; the only run
  that says anything about *composing* perturbations.

> **How surface Δ is measured.** Each perturbation is scored against the
> statement it was applied to, not against the anchor. That distinction only
> matters for the deep run, and it matters a lot: charging every step for the
> drift its ancestors caused inflated `strictness_swap` from 0.008 to 0.108 and
> made the deep run look like it disagreed with the other two. Measured per
> step, all three runs agree.

Numbers below are from the breadth run; `n` refers to it.

| Band | Perturbations | signal | Reading |
|---|---|---|---|
| **Invisible negatives** | `connective_swap` (n=21), `strictness_swap` (18), `const_to_zero_one` (18), `eq_to_le` (12), `arith_op_swap` (13), `flip_bound` (18), `tc_sibling_swap` (11), `tc_weaken_hyp` (10), `quantifier_swap` (2), `bound_tighter` (2), `forall_to_exists` (1) | +0.64 … +0.67 | One-token edits with full semantic consequence, and a surface Δ of essentially **zero**. **The core training signal.** |
| **Visible negative** | `negate` (24) | +0.87 | Highest signal in the set, but only because its meaning Δ is maximal — its surface Δ (0.13, and 0.40 order-aware) is the largest of any negative. See below. |
| **Weak negative** | `tc_strengthen_hyp` (17) | +0.31 | Small logical move, small surface move. Low value either way. |
| **Aligned** | `specialize_type` (19), `premise_permute` (15), `implicit_explicit_toggle` (24), `uncurry` (19), `definitional_unfold` (6) | +0.10 … −0.06 | Surface change tracks meaning change. **Teaches nothing.** |
| **Moderate positive** | `de_morgan_rewrite` (24) | −0.12 | Same proposition, visibly different string. −0.19 on the deep run and −0.12 here, so it sits just under the hard-positive bar (−0.15) on this sample. |
| **Extreme positive** | `alpha_rename` (24) | −0.76 | Logically identical, lexically almost a different theorem. The hardest positive in the set by a wide margin — see below. |

The banding is much cleaner than the earlier read suggested. Once each step is
measured against its own parent, nearly every *graded* perturbation collapses
into a single band at surface Δ ≈ 0.00–0.03: **the one-token logical edits are
uniformly invisible**, and there is no "partly visible" middle group among them
at all. The spread that used to separate them was chain drift, not the
perturbations.

### Depth is what buys distance

A single perturbation does not move a statement anywhere. Composing them does.
This table is deliberately **anchor**-relative — the question here is how far
the chain as a whole has travelled, not what each step contributed:

| Depth | variants | mean collapse | closest-to-unrelated variant | still retrieves its own anchor |
|---|---|---|---|---|
| 1 | 12 | 0.940 | 0.722 | 12/12 (100%) |
| 2 | 40 | 0.885 | 0.041 | 40/40 (100%) |
| 3 | 106 | 0.768 | 0.039 | 106/106 (100%) |

By depth 2 some variants sit **as far from the anchor as an unrelated theorem
does** (collapse ≈ 0.04), and the mean drifts steadily outward. So the dataset
does not have to consist of near-copies; the depth-1 collapse of 0.87 is a
property of applying one perturbation, not a ceiling.

The last column is the caveat. Even the escapees still rank their own anchor
first among the ten — the cloud spreads out, but it does not overlap anything
else. That is the desirable shape for contrastive training (hard negatives
close to the anchor, not confusable with other theorems) and it means we
cannot use retrieval accuracy as a difficulty measure; it is saturated at 100%.

Chaining also **reaches shapes the anchor never had**: `curry`,
`premise_permute` and `eq_to_le` all fired in the deep run despite firing zero
times across the ten depth-1 anchors. An earlier perturbation rewrote the
statement into a form they apply to. That is a cheap way to exercise starved
perturbations without hunting for anchors of exactly the right shape.

### Two findings worth acting on

**`alpha_rename` had an artefact, and fixing it did not change the geometry.**
The transform used to rename every binder to `wv0`, `wv1`, …, which is out of
distribution for Mathlib: a model trained on that learns "`wv` means perturbed"
rather than "renaming preserves meaning". It now draws replacements per binder
*kind* (Greek letters for types, `m n k` for discrete quantities, `x y z` for
continuous ones, `h`-names for hypotheses), rotates the choice by a hash of the
statement so the names vary across theorems, and leaves instance binders alone.

Two things came out of that, and only one was predicted.

*Predicted, and wrong:* this document previously claimed that realistic names
would "turn the single most extreme hard positive in the set into a genuine
one" — implying the extremeness itself was the artefact. It is not. Measured
before and after, collapse went from 0.35 to **0.24** and the inversion rate
stayed pinned at **100%** (186/186). The distance was never about the names
being weird; it is about *how many* tokens change. Identifiers are rare tokens
and therefore carry high IDF weight, so renaming all of them rewrites most of
what TF-IDF is looking at, whatever you rename them to. No naming scheme fixes
that, because there is nothing to fix.

*Unpredicted, and the actual win:* skipping instance binders removed the
compile failures that renaming `inst` used to cause, so the perturbation now
fires on **24/24 anchors instead of 13/24**. That nearly doubles the supply of
substantial positive pairs, which was the scarcest thing in the dataset.

The reframing matters more than either number. An α-renamed statement is
logically identical to its anchor and lexically about as far away as a random
theorem — it even retrieves the *wrong* anchor 10 times out of 24. That is not
a defect to be engineered away; it is the definition of a hard positive, and it
is the one pair type in the set that forces a model to read structure instead
of identifiers. The old version was unusable because of the `wv` shortcut. The
new one is the most valuable positive we have.

**Our `negate` is more surface-visible than expected.** The prior was that
negation would be hard to tell apart. Measured, it has the *largest* surface Δ
of any negative (0.13 on the breadth run, 0.24 on the deep run, and 0.40/0.55
once word order is taken into account) — because `extract_goal` pushes the
negation all the way in, turning `∀ … ↔ …` into `∃ … ∧ ¬…`, which rewrites much
of the string. The deep-negation implementation is a genuine strength for
statement quality, but it means `negate` is partly detectable without
understanding negation. It tops the signal ranking only because its *meaning* Δ
is maximal; on surface change alone it is the most visible negative we have.
If we want a pure test of negation, we also want a surface-minimal variant of
it — and the one-token swaps above already show what that would score.

---

## Axis 2 — knowledge required (predicted)

This axis is an argument, not a measurement. It asks what a model would have to
have internalised to get a pair right, and orders the perturbations by how much
of that knowledge lives outside the statement itself. Five tiers, easiest first.

### Tier 0 — notation only

`implicit_explicit_toggle`, `alpha_rename`, `premise_permute`

The rewrite is a mechanical operation on binders. Nothing mathematical is
involved and the invariance is learnable from surface statistics alone.

*Prediction:* learned almost immediately, and then contributes nothing.
`implicit_explicit_toggle` already measures at signal ≈ 0, and it fired on
24/24 breadth anchors — it is the single most-produced perturbation in the set
and the least informative. **Downweight it in any training mix**, or its
abundance over the interesting perturbations will dominate the loss.

`alpha_rename` is the exception that shows the two axes really are independent.
It needs no mathematical knowledge whatsoever — it belongs in this tier by
construction — and yet it is the most valuable pair in the dataset, because
knowing that renaming is irrelevant is worthless *unless* the representation
also survives most of its tokens changing. Low knowledge, extreme signal.
Do not downweight this one.

`premise_permute` is the sharpest illustration of the tier being worthless as
*training* signal. Like `quantifier_swap` it preserves the token multiset
exactly, so its collapse is a literal 1.000 — and because it is also logically
equivalent, it was beaten by a non-equivalent variant in **0 of 112**
comparisons, the only perturbation in the set to score zero. A positive pair
that a bag-of-words model already gets right, every time, at no cost. It is a
perfectly good *test* that reordering is being handled, and it teaches nothing.

### Tier 1 — propositional logic

`de_morgan_rewrite`, `curry`, `uncurry`, `contrapose`, `negate`,
`connective_swap`, `converse`, `inverse`

Requires a fixed, closed, statement-independent rule set: De Morgan, currying,
contraposition, negation-pushing. The rules do not depend on what the theorem
is about.

*Prediction:* the first tier where the model must go beyond bag-of-words, and
the one it should crack first, because the rule set is small and every example
reinforces the same handful of rules. **Best value per example early in
training.** Note the asymmetry inside the tier: `contrapose`/`converse`/
`inverse` need implication structure and have fired **0 times across all three
runs**, and `curry` has fired once. The tier is in practice represented by
`de_morgan_rewrite`, `negate` and `uncurry` alone — see the root-cause section
at the end, which is a Lean-side bug rather than a sampling shortfall.

### Tier 2 — quantifier scope

`quantifier_swap`, `forall_to_exists`, `exists_to_forall`

The edit is one character (`∀` → `∃`) but its meaning depends entirely on the
binder's *position* relative to the others. `∀x ∃y` and `∃y ∀x` share every
token.

*Prediction:* harder than Tier 1. A bag-of-words model cannot represent the
distinction even in principle, and an order-aware model still has to track
scope rather than adjacency.

Barely measured, but no longer unmeasured: shape sampling got `quantifier_swap`
to fire twice and `forall_to_exists` once, and the first data point is a clean
confirmation. `quantifier_swap` scores surface Δ **exactly 0.000** under bag of
words — it permutes binders, so the token multiset is *identical* to the
anchor's — against 0.150 order-aware.

Exactly two perturbations have that property, and the contrast between them is
the argument for this whole tier. `premise_permute` also leaves the multiset
untouched, but it is *equivalence-preserving*: the blind spot costs nothing,
because there was nothing to see. `quantifier_swap` leaves the multiset
untouched while **changing what the theorem asserts**. Same blind spot, opposite
consequence. Every other hidden negative in the set is hidden because TF-IDF
happens to down-weight the token that changed — a threshold artefact that a
better-weighted lexical model could partly fix. This one is hidden because a bag
of words has no representation of the distinction at all.

With n=3 across the three quantifier perturbations this is still an anecdote.
**Raising their hit rate remains the highest-value gap in the registry**, and it
is now a gap with a demonstrated payoff rather than a speculative one.

### Tier 3 — order and arithmetic semantics

`strictness_swap`, `eq_to_le`, `flip_bound`, `bound_tighter`, `arith_op_swap`,
`const_to_zero_one`

Requires knowing what the relation or operator means. All six measure at the top
of the signal ranking (+0.66 … +0.67) because the edit is a single token — and
because they land within 0.01 of each other, this tier is currently
indistinguishable from the inside by lexical means.

*Prediction:* high signal but **noisy labels**, which is a different problem
from difficulty. Swapping `≤` for `<` sometimes falsifies a theorem and
sometimes changes nothing that matters; the truth-propagation table can only
say `unknown` for the whole family. A model trained on a `graded` label that is
sometimes really "equivalent" and sometimes really "false" will learn a blurred
distinction. Expect these to help less than their signal score suggests until
the labels are sharpened.

### Tier 4 — library knowledge

`tc_weaken_hyp`, `tc_strengthen_hyp`, `tc_strengthen_conc`, `tc_weaken_conc`,
`tc_sibling_swap`, `specialize_type`, `definitional_unfold`, `drop_unused_hyp`

The distinction is **not recoverable from the statement at all**. Whether
`CommRing` → `Field` weakens or strengthens a hypothesis is a fact about
Mathlib's hierarchy, not about the string. `definitional_unfold` needs the
definition of `Function.Injective`. `drop_unused_hyp` needs to know a
hypothesis is genuinely unused, which is a property of the *proof*, not the
statement.

*Prediction:* the hardest tier, matching the prior that typeclass mutations are
theoretically hardest. Two consequences:

1. A single-token swap `CommRing` → `Field` at signal 0.65 is **unlearnable**
   unless the model has the hierarchy. It will look like label noise until the
   model has seen enough of the lattice to infer the partial order from
   co-occurrence.
2. That means coverage, not volume, is the constraint. A thousand perturbations
   all touching `Ring`/`CommRing` teach the model one edge. The typeclass
   perturbations need to be sampled to **cover many (class, parent, sibling)
   triples** across the hierarchy, or the model will memorise specific pairs
   rather than learn the order. We already have the hierarchy in
   `data/class_hierarchy.jsonl`, so this is a sampling change, not a new
   capability.

---

## Putting the two axes together

Signal is signed, so the grid needs three rows rather than two: a large
*negative* signal is not a weak hard negative, it is a hard **positive**, and
those are what a contrastive objective pairs the negatives against.

| | Tier 0–2 (little knowledge) | Tier 3–4 (much knowledge) |
|---|---|---|
| **Hidden negatives** (signal ≫ 0) | `negate`, `connective_swap`, `quantifier_swap` — *learn these first* | `strictness_swap`, `const_to_zero_one`, `flip_bound`, `eq_to_le`, `arith_op_swap`, `tc_sibling_swap`, `tc_weaken_hyp` — *the eventual target* |
| **Hidden positives** (signal ≪ 0) | `alpha_rename` (−0.76), `de_morgan_rewrite` (−0.12) — *the whole positive supply* | *(none)* — `definitional_unfold` at −0.06 barely rewrites anything |
| **Aligned** (signal ≈ 0) | `implicit_explicit_toggle`, `premise_permute`, `uncurry` — *downweight* | `specialize_type`, `tc_strengthen_hyp` — *low priority* |

Positives remain the thin side of the dataset. Two perturbations supply all of
them, they are both Tier 0–1, and they are very far apart in difficulty —
`alpha_rename` at −0.76 and `de_morgan_rewrite` at −0.12, with nothing in
between. A contrastive objective would be training on either "identifiers do
not matter" or "almost nothing changed", with no middle. **A positive that
rewrites a moderate amount of a statement for a real mathematical reason is the
clearest remaining gap**, alongside quantifier coverage.

A curriculum falls straight out of this, and it is a testable claim rather than
a hunch:

1. **Propositional** (`de_morgan_rewrite`, `curry`, `uncurry`, `negate`,
   `contrapose`) — closed rule set, high signal, no external knowledge.
2. **Quantifier scope** (`quantifier_swap`, `forall_to_exists`) — needs
   structure but still no library knowledge.
3. **Order and arithmetic** (`strictness_swap`, `flip_bound`,
   `const_to_zero_one`) — high signal, but sharpen the labels first.
4. **Typeclass and definitional** (`tc_*`, `definitional_unfold`) — needs the
   hierarchy; sample for coverage.

**The prediction to falsify:** accuracy on held-out pairs should saturate in
tier order, and tier-4 accuracy should stay near chance until the training mix
covers enough of the typeclass lattice. If instead tier 4 is learned as fast as
tier 1, the model is matching class *names* rather than reasoning about the
hierarchy — the same word-matching failure, one level up. Holding out entire
subtrees of the hierarchy at training time is the clean way to check.

---

## What the current dataset cannot tell us

Being explicit about the gaps, because most of them are fixable:

* **5 of 28 perturbations have still never fired** across all three runs:
  `contrapose`, `converse`, `inverse`, `exists_to_forall`, `tc_weaken_conc`.
  See the next section — for three of them the cause is now known and is not a
  sampling problem.
* **Coverage is uneven where it matters most.** The tier-2 quantifier
  perturbations fired 3 times *in total*; `curry`, `tc_strengthen_conc` and
  `drop_unused_hyp` fired only outside the breadth run. The perturbations we
  have the most data on are the ones we predict are least useful.
* **The deep run's 158 variants all descend from a single theorem**, so its
  numbers are precise but not necessarily representative of Mathlib. It is the
  only evidence about composition, and it rests on one anchor.
* **`meaning Δ` is inferred, not proven.** It comes from the propagation table;
  no variant has been proved or disproved. For the `graded` family in
  particular the true label varies per instance.
* **Lexical ≠ neural.** These measurements bound what word matching can see.
  A real embedder will do better; the claim is only that the pairs where
  lexical similarity fails are the pairs where it has to.

---

## Why the logical tactics never fire

Sampling 24 Mathlib anchors chosen specifically for implication shape
(`data/mathlib-review`) raised total yield from 49 variants to **298**, and
lifted single-run coverage from 16 of 28 perturbations to 20. Four of those had
never fired in *any* run before — `definitional_unfold` 6/24, `quantifier_swap`
2/24, `bound_tighter` 2/24, `forall_to_exists` 1/24 — taking coverage across all
three runs from 19/28 to **23/28**. But `contrapose`, `converse`, `inverse` and
`curry`
failed on **all 24**, which is too clean to be a shape problem. Running them by
hand gives two distinct root causes.

**`contrapose` / `converse` / `inverse` — dependent arrow.** On
`sign_cases_of_C_mul_pow_nonneg`, Lean reports:

```
Tactic `contrapose` failed: the goal
  ∀ {R : Type u_1} [inst : Semiring R] … , (PosMulStrictMono R ∧ …) → a = 0 ∨ …
is a dependent arrow
```

`revert_props` pulls the Prop hypotheses back into the goal, but the implicit
type binders `{R}`, `{a b}` and the instance binders stay in front of the
arrow. `contrapose` needs a non-dependent `P → Q` at the head and refuses a
`∀`-telescope. Nearly every Mathlib statement has implicit type binders, so
**these three can essentially never fire as currently written** — that is why
they scored 0/10 and 0/24 rather than "sometimes". The fix is a Lean-side one:
`intro` the non-Prop binders, contrapose the residual implication, then
re-generalise. Until then, Tier 1 rests on `de_morgan_rewrite`, `negate` and
`uncurry` alone.

**`curry` — the conjunction is in the wrong place.** Lean reports `simp made
no progress`. `curry` rewrites `(P ∧ Q) → R` via `and_imp`, so the `∧` has to
be in *hypothesis* position; the anchors we picked had conjunctions in the
*conclusion* (`a = 0 ∨ 0 < a ∧ 0 ≤ b`). That was a bug in the sampler's shape
predicate, which tested only for `∧` and `→` appearing somewhere in the same
statement; it now requires the `∧` to precede the first top-level `→`. Worth
re-sampling on.

The distinction matters: one of these is a broken transform and the other was a
broken measurement. Only the second is fixed.

---

Reproduce with:

```bash
# depth-1 review over the benchmark anchors
python pipeline/analyze_geometry.py --run data/benchmark-review

# the deep run: one theorem, perturbations composed to depth 3
python pipeline/run_deep_chains.py --anchor bench_000 --depth 3 --max-nodes 40
python pipeline/analyze_geometry.py --run data/deep-chains

# breadth: 24 shape-sampled Mathlib anchors, 298 variants
python pipeline/sample_mathlib_anchors.py --limit 24 --verify
python pipeline/run_benchmark_review.py --anchors-file data/anchors/mathlib-24.jsonl \
    --out data/mathlib-review
python pipeline/analyze_geometry.py --run data/mathlib-review
```
