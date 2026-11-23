# Where do the perturbed statements sit?

298 variants across 24 anchors, scored with 4 lexical (non-neural) similarity views. No model is involved: these numbers are what pure word matching can see.

## Baseline — two unrelated theorems

Similarity between *different* anchors. This is the zero point: any two statements drawn from the benchmark sit about this far apart, so it is the scale against which 'close to the anchor' has to be read.

| View | mean | std | min | max |
|---|---|---|---|---|
| TF-IDF over Lean tokens (bag of words) | **0.231** | 0.183 | 0.048 | 0.986 |
| TF-IDF over character 3–5-grams (subword surface form) | **0.105** | 0.157 | 0.007 | 0.995 |
| Token-set overlap (order-blind word matching) | **0.344** | 0.112 | 0.174 | 1.000 |
| Token-sequence alignment (order-aware) | **0.292** | 0.122 | 0.068 | 0.971 |

_(276 anchor pairs.)_

## Variants against their own anchor

`collapse` rescales the raw similarity so that **0.0 means the variant is as far from its anchor as an unrelated theorem is, and 1.0 means it sits on the same point**.

| View | raw similarity | collapse |
|---|---|---|
| TF-IDF over Lean tokens (bag of words) | 0.919 ± 0.176 | **0.895** ± 0.228 |
| TF-IDF over character 3–5-grams (subword surface form) | 0.907 ± 0.147 | **0.896** ± 0.164 |
| Token-set overlap (order-blind word matching) | 0.905 ± 0.106 | **0.856** ± 0.161 |
| Token-sequence alignment (order-aware) | 0.919 ± 0.105 | **0.886** ± 0.148 |

## Retrieval — does a variant still find its own anchor?

**284/298 (95%)** of variants rank their own anchor first among all 24 anchors under tf-idf over lean tokens (bag of words).

## Per-perturbation

Grouped by the last step of the path. `surface Δ` is `1 − collapse`: how far that one perturbation moved the statement in surface terms, measured against **the statement it was applied to** rather than the anchor — otherwise a step deep in a chain is charged for all the drift its ancestors caused. `meaning Δ` is the logical distance implied by the truth-propagation table (0 equivalent, 0.34 entailed, 0.67 graded, 1.0 contradictory).

`signal` is `meaning Δ − surface Δ`, the whole point of the exercise: **how much of the change is invisible to word matching**. Large positive means the meaning moved and the surface did not (a hard negative — the model has to read the logic). Large negative means the surface moved and the meaning did not (a hard positive). Near zero means surface overlap already gives away the answer, so the pair teaches an embedder nothing it doesn't already know.

| Perturbation | class | n | collapse | surface Δ | surface Δ (order-aware) | meaning Δ | signal | verdict |
|---|---|---|---|---|---|---|---|---|
| `negate` | contradictory | 24 | 0.874 | 0.126 | 0.403 | 1.00 | **+0.87** | **hard negative** — looks the same, means something else |
| `quantifier_swap` | graded | 2 | 1.000 | 0.000 | 0.150 | 0.67 | **+0.67** | **hard negative** — looks the same, means something else |
| `eq_to_le` | graded | 12 | 0.997 | 0.003 | 0.021 | 0.67 | **+0.67** | **hard negative** — looks the same, means something else |
| `connective_swap` | graded | 21 | 0.997 | 0.003 | 0.022 | 0.67 | **+0.67** | **hard negative** — looks the same, means something else |
| `const_to_zero_one` | graded | 18 | 0.996 | 0.004 | 0.022 | 0.67 | **+0.67** | **hard negative** — looks the same, means something else |
| `strictness_swap` | graded | 18 | 0.996 | 0.004 | 0.021 | 0.67 | **+0.67** | **hard negative** — looks the same, means something else |
| `forall_to_exists` | graded | 1 | 0.994 | 0.006 | 0.031 | 0.67 | **+0.66** | **hard negative** — looks the same, means something else |
| `arith_op_swap` | graded | 13 | 0.994 | 0.006 | 0.023 | 0.67 | **+0.66** | **hard negative** — looks the same, means something else |
| `bound_tighter` | graded | 2 | 0.994 | 0.006 | 0.027 | 0.67 | **+0.66** | **hard negative** — looks the same, means something else |
| `flip_bound` | graded | 18 | 0.986 | 0.014 | 0.021 | 0.67 | **+0.66** | **hard negative** — looks the same, means something else |
| `tc_sibling_swap` | graded | 11 | 0.978 | 0.022 | 0.021 | 0.67 | **+0.65** | **hard negative** — looks the same, means something else |
| `tc_weaken_hyp` | graded | 10 | 0.970 | 0.030 | 0.021 | 0.67 | **+0.64** | **hard negative** — looks the same, means something else |
| `tc_strengthen_hyp` | entailed | 17 | 0.974 | 0.026 | 0.021 | 0.34 | **+0.31** | moderate negative — surface hints at the change |
| `specialize_type` | entailed | 19 | 0.758 | 0.242 | 0.290 | 0.34 | **+0.10** | aligned — surface overlap already gives the answer |
| `premise_permute` | equivalent | 15 | 1.000 | 0.000 | 0.069 | 0.00 | **+0.00** | aligned — surface overlap already gives the answer |
| `implicit_explicit_toggle` | equivalent | 24 | 0.996 | 0.004 | 0.043 | 0.00 | **-0.00** | aligned — surface overlap already gives the answer |
| `uncurry` | equivalent | 19 | 0.976 | 0.024 | 0.077 | 0.00 | **-0.02** | aligned — surface overlap already gives the answer |
| `definitional_unfold` | equivalent | 6 | 0.937 | 0.063 | 0.173 | 0.00 | **-0.06** | aligned — surface overlap already gives the answer |
| `de_morgan_rewrite` | equivalent | 24 | 0.882 | 0.118 | 0.155 | 0.00 | **-0.12** | aligned — surface overlap already gives the answer |
| `alpha_rename` | equivalent | 24 | 0.235 | 0.765 | 0.296 | 0.00 | **-0.76** | **extreme positive** — further away than an unrelated theorem |

The `order-aware` column repeats the measurement under token-sequence alignment instead of a bag of words, which separates two very different reasons a perturbation can score near zero.

**Pure reorderings** — `premise_permute`, `quantifier_swap` produce variants with *exactly* the anchor's token multiset. A bag-of-words model cannot distinguish them at any threshold; only the order-aware column sees anything.

**Single-token substitutions** stay near zero in *both* columns. These swap one common symbol for another (`≤` for `<`, `0` for `1`); common symbols carry almost no IDF weight and almost no alignment cost, so they are hidden from lexical matching however it is measured. What that is worth depends entirely on whether the meaning moved with them:

* meaning *did* move — `arith_op_swap`, `bound_tighter`, `connective_swap`, `const_to_zero_one`, `eq_to_le`, `flip_bound`, `forall_to_exists`, `strictness_swap`, `tc_sibling_swap`, `tc_strengthen_hyp`, `tc_weaken_hyp`. **The most reliable hard negatives in the set.**
* meaning did *not* move — `implicit_explicit_toggle`. Invisible and equivalent, so the pair asserts something the model already believes. No training signal either way.

## Inversion — is surface similarity even pointing the right way?

Across 868 (equivalent, non-equivalent) variant pairs sharing an anchor, the **non-equivalent** variant was lexically closer to the anchor **517 times (60%)**.

> Surface similarity is **anti-correlated** with logical similarity here. A model scoring by word overlap does not merely fail to learn the logic — it is actively pulled the wrong way, which is a plausible explanation for the natural-language training result.

The aggregate hides most of the story, because it is dominated by whichever equivalence-preserving perturbation fires most often. Split by the positive side of the pair:

| Equivalent variant | pairs | beaten by a non-equivalent variant |
|---|---|---|
| `alpha_rename` | 186 | **186 (100%)** |
| `definitional_unfold` | 44 | **39 (89%)** |
| `de_morgan_rewrite` | 186 | **148 (80%)** |
| `uncurry` | 154 | **79 (51%)** |
| `implicit_explicit_toggle` | 186 | **65 (35%)** |
| `premise_permute` | 112 | **0 (0%)** |

A row near 100% is a perturbation whose *positive* pair a lexical model would rank below a *negative* pair of the same anchor — the exact case where word matching gives the wrong answer and logic gives the right one.

Dropping positives that barely edit the string at all (`implicit_explicit_toggle`, `premise_permute`, `uncurry` — a positive that changes nothing cannot be beaten), the rate is **373/416 (90%)**. That is the number to quote: among pairs where the equivalence-preserving rewrite actually rewrote something, surface similarity points the wrong way most of the time.

## Figures

![spectrum.png](spectrum.png)

![surface-vs-meaning.png](surface-vs-meaning.png)

![collapse-by-perturbation.png](collapse-by-perturbation.png)

![cloud.png](cloud.png)
