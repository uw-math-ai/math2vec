# Perturbation Catalogue

Reference for every perturbation registered in
[`src/wiggle/registry.py`](../src/wiggle/registry.py) — what it does, what it's
worth, where it shines, and where it falls down.

**28 perturbations across 7 layers** — logical (5), connective (4), quantifier
(3), typeclass (6), bounds (2), structure (3), relation (5). Every one has the
same interface:

```python
(sig: str, type_str: str) -> tuple[str, str] | None
```

`None` means "does not apply here" and the chain runner treats it as a clean
stop. Two families implement that contract differently:

- **Tactic-driven** — run a Lean macro from [`Wiggle.lean`](../Wiggle.lean),
  then read the rewritten statement back with `extract_goal`. Lean itself
  guarantees the output is well-formed.
- **Text + oracle** — rewrite the type string in Python, then call
  `compile_lean` as a validity oracle and discard anything that doesn't
  type-check.

Both guarantee **well-formed Lean**. Neither guarantees **truth** — that comes
from the propagation table, which is a symbolic rule, not a proof. See
[Truth labelling](#truth-labelling-what-the-labels-do-and-dont-mean).

---

## Table 1 — Master index

Truth column reads: given a **true** anchor, what is the variant?
"Lean calls" is the cost per successful application.

| # | Name | Layer | Mechanism | Transformation | Truth | Lean calls | Pair role |
|---|---|---|---|---|---|---|---|
| 1 | `negate` | logical | tactic `negate_state` | `P` ↦ `¬P`, negation pushed inward | **false** | 1 | guaranteed negative |
| 2 | `contrapose` | logical | tactic `contrapositive` | `P → Q` ↦ `¬Q → ¬P` | **true** | 1 | positive |
| 3 | `converse` | logical | tactic `converse` | `P → Q` ↦ `Q → P` | unknown | 1 | hard negative |
| 4 | `inverse` | logical | tactic `inverse` | `P → Q` ↦ `¬P → ¬Q` | unknown | 1 | hard negative |
| 5 | `drop_unused_hyp` | logical | tactic `drop_unused_hyp` | remove Prop hypotheses the goal never uses | **true** | 1 | positive (generalisation) |
| 6 | `de_morgan_rewrite` | connective | `simp only` × 7 lemmas | `¬(P ∧ Q)` ↦ `¬P ∨ ¬Q`, `P → Q` ↦ `¬P ∨ Q`, … | **true** | 1 | positive |
| 7 | `curry` | connective | `simp only [and_imp]` | `(P ∧ Q) → R` ↦ `P → Q → R` | **true** | 1 | positive |
| 8 | `uncurry` | connective | `simp only [← and_imp]` | `P → Q → R` ↦ `(P ∧ Q) → R` | **true** | 1 | positive |
| 9 | `definitional_unfold` | connective | `simp only` × 9 defs | `Function.Injective f` ↦ `∀ a b, f a = f b → a = b` | **true** | 1 | positive (strongest) |
| 10 | `quantifier_swap` | quantifier | text + oracle | `∀x ∃y, P` ↦ `∃y ∀x, P` | unknown | 1 | hard negative |
| 11 | `forall_to_exists` | quantifier | text + oracle | `∀ (x…), P` ↦ `∃ (x…), P` | unknown | 1 | weakening |
| 12 | `exists_to_forall` | quantifier | text + oracle | `∃ x, P` ↦ `∀ x, P` | unknown | 1 | hard negative |
| 13 | `tc_weaken_hyp` | typeclass | hierarchy + oracle | `[AddCommMonoid α]` ↦ `[AddMonoid α]` | unknown | 1–N | hard negative |
| 14 | `tc_strengthen_hyp` | typeclass | hierarchy + oracle | `[AddCommMonoid α]` ↦ `[AddCommGroup α]` | **true** | 1–N | positive (specialisation) |
| 15 | `tc_strengthen_conc` | typeclass | hierarchy + oracle | `IsDomain R` ↦ `EuclideanDomain R` in conclusion | unknown | 1–N | hard negative |
| 16 | `tc_weaken_conc` | typeclass | hierarchy + oracle | `IsDomain R` ↦ `Nontrivial R` in conclusion | **true** | 1–N | positive |
| 17 | `tc_sibling_swap` | typeclass | hierarchy + oracle | swap for an incomparable class under the same parent | unknown | 1–8 | hard negative |
| 18 | `specialize_type` | typeclass | text + oracle | `{α : Type*} [Ring α]` ↦ `ℤ`, drop the instance binder | **true** | 1–5 | positive |
| 19 | `flip_bound` | bounds | regex only | first `≤`↦`≥`, `<`↦`>` (direction flip) | unknown | 0 | hard negative |
| 20 | `bound_tighter` | bounds | regex only | `≥ n` ↦ `≥ n+1`, `≤ n` ↦ `≤ n−1` | unknown | 0 | hard negative |
| 21 | `alpha_rename` | structure | text + oracle | rename bound variables to other Mathlib-idiomatic names of the same kind | **true** | 1 | positive |
| 22 | `premise_permute` | structure | text + oracle | `P → Q → R` ↦ `Q → P → R` | **true** | 1 | positive |
| 23 | `implicit_explicit_toggle` | structure | text + oracle | first `{x : T}` ↦ `(x : T)`, else `(x : T)` ↦ `{x : T}` | **true** | 1 | positive (trivial) |
| 24 | `strictness_swap` | relation | text + oracle | first ` < ` ↦ ` ≤ `, ` > ` ↦ ` ≥ ` (direction kept) | unknown | 1 | hard negative |
| 25 | `eq_to_le` | relation | text + oracle | first ` = ` ↦ ` ≤ ` | unknown | 1 | hard negative |
| 26 | `connective_swap` | relation | text + oracle | first ` ∧ ` ↦ ` ∨ ` (or reverse) | unknown | 1 | hard negative |
| 27 | `arith_op_swap` | relation | text + oracle | first ` + `↦` * `, ` * `↦` + `, ` - `↦` + ` | unknown | 1 | hard negative |
| 28 | `const_to_zero_one` | relation | text + oracle | first numeric literal → `0` (or `1` if it was `0`) | unknown | 1 | hard negative |

Row order follows `PERTURBATIONS` grouped by layer, not registry declaration
order (`curry`, `uncurry`, `definitional_unfold`, and the quantifier-kind flips
were appended to the list later but belong to earlier layers).

---

## Table 2 — The big table: value, strengths, limitations

| Name | Value (why it's in the set) | Performs well on | Limitations |
|---|---|---|---|
| **`negate`** | The only perturbation with a *guaranteed* false label from a true anchor. Every other negative is "unknown". That certainty makes it the backbone of any supervised true/false split. | Anything. `revert_all` + `push_neg` handles ∀/∃/∧/∨/→ uniformly, so the hit rate is near-universal. Especially clean on quantified arithmetic where `push_neg` produces idiomatic `∃ n, ¬P n` output. | `push_neg` normalisation is best-effort (`try`), so on statements with custom predicates the negation can stay as a bare `¬(…)` prefix — syntactically shallow, exactly the "just prepend ¬" output we criticise LLMs for. Chaining `negate` twice returns to the anchor (a duplicate that only dedup will catch). |
| **`contrapose`** | Historically the project's *only* equivalence-preserving transform, and still the most reliable positive pair. Textbook FOL, so the truth rule is beyond dispute. | Implications with a clean Prop antecedent — `h : a ≤ b → …`. The `simp only [not_and_or, not_le, not_lt]` post-pass produces natural output on order/arithmetic goals (`¬(a ≤ b)` becomes `b < a`). | Requires implication structure. On a bare equation with no hypotheses, `contrapose` produces the degenerate `¬goal → False` shape. Applying it twice is an identity round-trip. Statements whose hypotheses are dependent (later hypothesis mentions an earlier one's variable) can fail `revert_props`. |
| **`converse`** | Completes the classical foursome with `inverse`. Generates a statement that is well-typed, plausible, and *usually* false — the profile of a genuinely hard negative that surface heuristics can't detect. | Two-part implications where hypothesis and conclusion are both substantive (`Prime p → Odd p ∨ p = 2`). Swapping produces something a model must actually reason about. | **Known failure**: on statements with leading non-Prop binders like `∀ n, P n → Q n`, the underlying `apply` produces 3 goals instead of 1, `guard_goal_nums 1` fires, and the wrapper returns `None`. That's a large slice of Mathlib. Also genuinely *true* for iff-like statements, so the "unknown" label is doing real work. |
| **`inverse`** | Fills the last cell of {original, contrapositive, converse, inverse}. Logically equivalent to the converse but *syntactically* very different, so the two make an interesting equivalent-pair on their own. | Same profile as `converse` — clean `P → Q` with Prop antecedents. | Inherits `converse`'s multi-goal failure on `∀ n, P n → Q n` verbatim (same macro shape, same `guard_goal_nums 1`). Produces output equivalent to `converse`, so emitting both from one anchor gives two variants that are logically identical to each other — dedup should be aware. |
| **`drop_unused_hyp`** | Truth-preserving *generalisation*: the variant is strictly more widely applicable than the anchor. Distinct from the equivalence-preserving positives because the proposition genuinely changes. | Statements carrying decorative hypotheses — `(h : True)`, unused `Nonempty` or `DecidableEq` assumptions. Common in Mathlib where a hypothesis is kept for uniformity across a lemma family. | Silent no-op whenever every hypothesis is load-bearing, which is the common case in a well-curated corpus, so the hit rate is low. `clear` fails (caught and skipped) on hypotheses other hypotheses depend on. Only touches Prop-valued binders — never removes an unused *data* argument. |
| **`de_morgan_rewrite`** | The workhorse positive-pair generator: semantically identical, syntactically distant. That combination is precisely the regime where contrastive training beats lexical retrieval. | Statements mixing `¬`, `∧`, `∨`, `→` — negated conjunctions, material implications, negated quantifiers. The 7-lemma set covers De Morgan, quantifier De Morgan, `imp_iff_not_or`, `and_imp`, and double-negation. | `simp only` normalises to a fixed normal form, so it is **idempotent**: applying it twice is a guaranteed no-op, capping chain depth. Statements with no propositional connectives (a bare equation) don't fire at all. The rewrite direction is fixed by the lemma set — you can't ask for the reverse. |
| **`curry`** | Splits a conjunctive hypothesis into successive arrows. Cheap, mechanically safe positive pair on a shape Mathlib produces constantly. | Statements written with an explicit `∧` in hypothesis position: `(hp : 0 < p ∧ p < 1) → …`. | Needs a top-level `∧` on the *left* of an arrow; `simp only [and_imp]` makes no progress otherwise and the wrapper's no-op guard suppresses the record. Exact inverse of `uncurry`, so chaining the two cycles back to the anchor. Partially overlaps `de_morgan_rewrite`, which also carries `and_imp` — the same anchor can yield the same variant by two routes. |
| **`uncurry`** | The reverse direction, and the more commonly applicable one since Mathlib statements are usually curried. Turns `P → Q → R` into a single conjunctive premise. | Any statement with two or more arrow-separated Prop hypotheses — very common. | Same overlap concern with `de_morgan_rewrite` (which carries `and_imp` in the forward direction) and exact-inverse relationship with `curry`. Only bundles hypotheses reachable by `revert_props`; hypotheses bound as `∀`-binders with dependencies won't fold. |
| **`definitional_unfold`** | The strongest positive pair in the set: `Function.Injective f` and `∀ a b, f a = f b → a = b` share almost no tokens yet denote the same proposition. Exactly the signal a lexical baseline cannot capture. | Statements mentioning one of the 9 predicates in the lemma set: `Function.Injective`, `Surjective`, `Bijective`, `LeftInverse`, `RightInverse`, `Monotone`, `Antitone`, `StrictMono`, `StrictAnti`. | The lemma set is **hardcoded and small**, so the hit rate across a general Mathlib slice is low. It is also the most Mathlib-version-fragile perturbation in the set: if any of those 9 definitions is restated upstream, the unfolded output shifts. Unfolding is one-way and idempotent — no chaining. |
| **`quantifier_swap`** | The canonical quantifier-scope error, called out in the theorem-proving literature as a frequent LM failure mode. Well-typed, minimally different, usually false. Very high value per record. | Statements literally shaped `∀ x…, ∃ y…, body` — analysis and number theory (`∀ ε > 0, ∃ δ, …`). | Only fires at the **head** of the statement; a `∀∃` nested inside a hypothesis is invisible to it. `∃` cannot bind implicit `{…}` or instance `[…]` binders, so those anchors are skipped. Genuinely true when the anchor happens to be uniform (a δ independent of ε), which is why the label is "unknown" rather than "false" — you can't assume a negative. |
| **`forall_to_exists`** | Weakening along the quantifier axis rather than the typeclass axis. Cheap to compute, and the truth question ("is the domain inhabited?") is a distinct kind of reasoning from the rest of the set. | Statements opening with explicit `∀ (x : T),` over a concrete inhabited type. | Skips any leading binder block containing `{`, `[`, or `⦃`, which rules out most polymorphic Mathlib statements. Labelled "unknown" only because inhabitation isn't guaranteed — over an obviously nonempty type the variant is in fact true, so this label is conservative and loses information. |
| **`exists_to_forall`** | Strengthening `∃` to `∀` is a large semantic jump with a small textual one — a good hard negative. | Statements beginning with `∃`. | Mathlib statements overwhelmingly begin with `∀`, so this fires rarely in practice. Head position only, same as its sibling. |
| **`tc_weaken_hyp`** | Strengthens the *statement* by demanding it hold over a wider class of types. The typeclass hierarchy is a real mathematical structure, so these negatives are principled rather than random. | Algebraic statements with an explicit instance binder — `[CommRing α]`, `[AddCommMonoid α]`. Rich hierarchy means many candidates. | Expensive: tries each ancestor up to depth 2 and calls Lean per candidate until one compiles (**1–N calls**). Type-checking is not truth-checking — a variant can compile fine and be flatly false, which is intended but means the "unknown" label carries all the risk. The hierarchy comes from a dumped Mathlib graph, so it drifts with Mathlib versions. |
| **`tc_strengthen_hyp`** | Truth-preserving specialisation: narrowing the hypothesis class keeps a true statement true. A positive pair that changes real mathematical content, unlike the syntactic positives. | Same anchors as `tc_weaken_hyp` — anything with an instance binder over a class that has descendants. | Same 1–N Lean-call cost. Descendant enumeration at depth 2 can produce a very narrow class (e.g. jumping from `Monoid` to something quite exotic), giving a technically-true but unnatural statement that may not resemble real mathematics. |
| **`tc_strengthen_conc`** | Applies the same hierarchy machinery to the conclusion, where strengthening flips the truth direction. Doubles the yield of the typeclass hierarchy work. | Statements whose conclusion is itself a typeclass membership claim — `… → IsDomain R`. | Requires the conclusion to *be* a typeclass claim, which is a much narrower shape than having a typeclass in the hypotheses. Depends on `_split_hyps_conclusion` correctly finding the conclusion boundary. Same per-candidate Lean cost. |
| **`tc_weaken_conc`** | The truth-preserving counterpart in conclusion position: claiming less stays true. | Same narrow shape as `tc_strengthen_conc`. | Same shape restriction and cost. Weakening far enough up the hierarchy can reach a near-trivial conclusion (`Nontrivial R`), producing a true but uninteresting statement. |
| **`tc_sibling_swap`** | The subtlest typeclass negative: a sibling is neither stronger nor weaker, so no ordering argument settles the truth. Harder than the up/down moves. | Classes sitting in a densely populated part of the hierarchy, where several children share a parent. | Most expensive in the set — up to **8 compile attempts** per anchor. Siblings can be mathematically unrelated, in which case the result is an *easy* negative rather than a hard one, undermining the point. Success depends entirely on the accuracy of the dumped parent/child graph. |
| **`specialize_type`** | Opens an axis orthogonal to every typeclass mutation: instead of moving through the class hierarchy, it leaves it entirely by picking a concrete type. Truth-preserving. | Polymorphic statements with a single leading `{α : Type*}` and instance binders that ℤ or ℝ satisfy — the bulk of Mathlib algebra. | Only the **first** type variable, and only the 5 concrete types `ℕ ℤ ℚ ℝ ℂ`, tried in order (**1–5 Lean calls**). Drops every instance binder mentioning that variable, so if the concrete type lacks the needed structure the candidate simply fails to compile and the next is tried. Multi-parameter statements are only partially specialised. |
| **`flip_bound`** | Zero Lean calls — free to compute. Reverses an inequality, producing a near-miss that is very often false. Good throughput-per-CPU-second. | Statements with an explicit inequality, especially arithmetic bounds. | **No compile check inside the transform** — validity is deferred to the chain runner, so a malformed variant surfaces later than for other perturbations. Naive regex with no bracket awareness: it flips the *first* `≤`/`<`/`≥`/`>` anywhere in the string, including inside a hypothesis you didn't mean to touch. Flipping a symmetric relation can be a silent no-op semantically. |
| **`bound_tighter`** | The mutation-testing "off-by-one" operator. Tightening is the direction more likely to produce a false statement, which is what makes it useful. | Statements with a literal numeric bound: `n ≥ 2`, `k ≤ 10`. | **Known edge case**: `max(0, n−1)` clamps at zero, so `≤ 0` maps to `≤ 0` — an unchanged variant emitted as a record, because neither `bounds.py` nor its wrapper has the no-op guard the other layers use. Only the first literal, no compile check in-transform, and tightening by exactly ±1 can be a no-op over ℝ where the bound isn't discrete. |
| **`alpha_rename`** | The cheapest substantial positive pair, and a genuine diagnostic: an embedder that scores an α-renamed statement as dissimilar is keying on identifier surface form. With `de_morgan_rewrite` it is one of only two positives that rewrite enough of the string to be worth training on. | Any statement with named binders — essentially universal coverage. | Replacement names are drawn per binder *kind* (Greek letters for types, `m n k` for discrete quantities, `x y z` for continuous ones, `h`-names for hypotheses) and never reuse an identifier already in the statement, so capture is impossible by construction. Instance binders are skipped. The remaining risk is that a kind is misread — the "is this a hypothesis?" test looks for a relation symbol in the binder's type, which will mislabel an exotic binder now and then. Harmless: the name is still plausible, just not the most idiomatic one. |
| **`premise_permute`** | Hypothesis order is semantically irrelevant but textually salient — a clean positive that tests order-invariance specifically. | Statements with two or more independent hypotheses written as arrow antecedents. | Only swaps hypotheses in **arrow position**; Mathlib frequently binds hypotheses as named `(h : P)` binders instead, which this doesn't touch, so the hit rate is well below what the shape suggests. Fails (correctly, via the compile oracle) when the second hypothesis depends on the first. Swapping exactly two means no richer permutations. |
| **`implicit_explicit_toggle`** | Lean-specific surface variation that leaves the proposition untouched. Tests whether the embedder is sensitive to binder syntax noise. | Statements with a leading `{α : Type*}` or explicit `(x : T)` binder — very common. | Arguably the weakest signal in the set: the change is a single brace. Making a previously-inferable variable explicit changes how the lemma would be *applied* even though the proposition is identical, so calling it a pure positive is a slight simplification. Only the first eligible binder; instance binders `[…]` deliberately untouched. |
| **`strictness_swap`** | Distinguishes `<` from `≤` — a distinction models routinely blur, and one that flips truth at boundary cases. Direction is preserved, so it isolates strictness from orientation (unlike `flip_bound`). | Statements where the strict/non-strict choice is load-bearing, e.g. positivity conditions `0 < ε`. | Requires **space-padded** operators (` < `), matching Lean's pretty-printer but brittle against any other formatting. First occurrence only. Frequently a no-op semantically — over ℤ, `n < 5` and `n ≤ 5` differ, but in many contexts the weakened form is still true, so the negative is soft. |
| **`eq_to_le`** | Weakens an equation into an inequality — a small edit with real semantic content in ordered structures. | Statements over ordered types with a top-level equality. | Needs an order instance on the type or the variant won't compile, which the oracle catches but only after paying a Lean call. **The truth label looks conservative**: if `a = b` holds then `a ≤ b` holds by reflexivity, so from a true anchor this should arguably propagate to *true*, not *unknown* — see [Open questions](#open-questions). No reverse direction (`≤` → `=`) exists. |
| **`connective_swap`** | Swapping `∧` for `∨` is a one-character edit with a large meaning change — the ideal hard-negative profile. | Statements with a top-level conjunction or disjunction. | Space-padded, first occurrence only. Weakening `∧` to `∨` from a true anchor yields a statement that is still **true** (a conjunction implies each disjunct), so half the time this produces a true "negative" — the `unknown` label is correct but the perturbation is much weaker in that direction than in the `∨ → ∧` direction. |
| **`arith_op_swap`** | The mutation-testing AOR operator. Produces statements that look almost right and are almost always wrong. | Arithmetic identities with explicit operators. | Mapping is **not symmetric**: `-` maps to `+` but nothing maps to `-`, so subtraction is under-generated. Space-padded and first-occurrence only. Swapping `+` for `*` often breaks type-checking or produces something trivially false rather than subtly wrong. |
| **`const_to_zero_one`** | Constant mutation, the other classical mutation-testing operator. Trivially cheap to compute. | Statements with meaningful numeric literals. | Highest risk of producing a **degenerate** statement: mutating a bound to `0` over ℕ frequently yields something vacuously true (`n ≥ 0`) or obviously false, neither of which is a hard negative. Regex ignores context, so it can hit a literal inside an index or a numeral that isn't a bound at all. |

---

## Layer notes

### Logical (5) — the classical core
Tactic-driven, one Lean call each, high hit rates. `negate` is the only source
of a certain false label. `converse` and `inverse` share a structural weakness:
both use the `apply (by admit : …)` + `guard_goal_nums 1` pattern, which breaks
on leading non-Prop binders. Fixing that one macro pattern would materially
raise the yield of both.

### Connective (4) — the positive-pair engine
Everything here is truth-preserving and produced by `simp only`. That's the
strength (Lean guarantees correctness) and the weakness (`simp` normalises, so
all four are idempotent and several overlap — `and_imp` appears in
`de_morgan_rewrite`, `curry`, *and* `uncurry`). Overlap means the same anchor
can reach the same variant by different routes, so dedup matters most in this
layer.

### Quantifier (3) — scope errors
`quantifier_swap` is the highest-value member: it targets a documented LM
failure mode. All three operate on the head of the statement only, which is the
single biggest limitation of the layer.

### Typeclass (6) — the mathematically deepest
The only layer that consults a real mathematical structure (Mathlib's `extends`
graph, dumped by `#wiggle_dump_class_hierarchy`). Also the most expensive:
these are the perturbations that make a corpus run take hours, since each tries
candidates until one compiles. `specialize_type` is the odd one out — it leaves
the hierarchy for concrete types.

### Bounds (2) — free but blunt
The only perturbations that make **zero** Lean calls, so effectively free.
Pure regex with no in-transform validation and no no-op guard; `bound_tighter`'s
clamp-at-zero duplicate is the one concrete bug in the catalogue.

### Structure (3) — surface-only positives
Pure text edits validated by the oracle. Truth-preserving by construction, and
the only real source of positive pairs in the set — `premise_permute` and
`implicit_explicit_toggle` barely change the string, so `alpha_rename` carries
most of the weight.

### Relation (5) — graded near-misses
Single surgical edits on space-padded operators. Low hit rates by design: most
single edits break type-checking, and the oracle keeps only well-formed
survivors. The trade-off is that survivors are excellent hard negatives.

---

## Truth labelling: what the labels do and don't mean

Two separate guarantees, often conflated:

1. **Well-formedness is verified.** Every emitted variant either came out of
   `extract_goal` (Lean built it) or passed `compile_lean`. There are no
   syntactically invalid statements in the output.
2. **Truth is inferred, not proven.** The `is_true` field comes from composing
   the per-perturbation propagation rules in
   [`src/wiggle/propagation.py`](../src/wiggle/propagation.py) over the chain.
   Nothing runs a prover.

Consequences worth internalising before using the labels downstream:

- `unknown` dominates. Any chain touching one unknown-producing perturbation is
  unknown from that point on, so deep chains are almost all unknown.
- `false` is rare and precious — effectively only `negate` produces it directly.
- Truth-preserving chains (`contrapose` → `alpha_rename` → `uncurry`) stay
  `true` and stack cleanly. These are the highest-confidence positive pairs.
- A `true`-labelled variant of a Mathlib theorem is true *because the rule says
  so*, not because anyone checked. The rules are sound classical logic, but the
  implementations can under-deliver — see `eq_to_le` below.

---

## Cost model

Rough per-application costs. Lean calls dominate everything else; with a warm
LSP server each is on the order of a few hundred milliseconds, versus ~15
seconds on the subprocess backend (see
[`scripts/bench_backends.py`](../scripts/bench_backends.py)).

| Cost tier | Perturbations | Lean calls |
|---|---|---|
| Free | `flip_bound`, `bound_tighter` | 0 |
| Single call | all 9 tactic-driven, plus the 3 quantifier, 3 structure, and 5 relation transforms | 1 |
| Search | `tc_weaken_hyp`, `tc_strengthen_hyp`, `tc_strengthen_conc`, `tc_weaken_conc` | 1–N candidates |
| Search (bounded) | `specialize_type` (≤ 5), `tc_sibling_swap` (≤ 8) | 1–8 |

If a run is CPU-bound, the typeclass layer is where the time goes. Capping
hierarchy depth or the sibling try-count is the fastest lever.

---

## Open questions

Things I'd want resolved before publishing a dataset built from this set. None
block generation; all affect label quality.

- **`eq_to_le` is probably mislabelled.** From a true `a = b`, the variant
  `a ≤ b` follows by `le_of_eq`. The registry says `unknown`; `true` looks
  correct in any preorder. Conservative labels lose usable positive pairs.
- **`forall_to_exists` is conservative for the same reason.** Over an obviously
  nonempty type, `∀ x, P x` true implies `∃ x, P x` true. The `unknown` is only
  needed for possibly-empty domains.
- **`connective_swap` is asymmetric in strength.** `∧ → ∨` from a true anchor
  stays true; `∨ → ∧` is the genuinely hard direction. Splitting them into two
  perturbations with different propagation rules would sharpen both.
- **`bound_tighter` can emit a duplicate.** The zero-clamp makes `≤ 0` a no-op
  that still produces a record. Adding the standard no-op guard used by the
  other layers fixes it.
- **`converse` / `inverse` yield is capped by a macro bug**, not by mathematics.
  The multi-goal failure on `∀ n, P n → Q n` costs real coverage.
- **Overlap and dedup.** `curry`/`uncurry`/`de_morgan_rewrite` can produce the
  same variant from the same anchor; `converse` and `inverse` produce mutually
  equivalent variants. The `dedup` roadmap item covers this.
- **Hit rates are unmeasured.** The "performs well on" column above is derived
  from each transform's trigger condition, not from a counted corpus run. A
  measurement pass over a few thousand anchors would turn this into real data.

---

## Adding a perturbation

Two edits, per [`src/wiggle/registry.py`](../src/wiggle/registry.py):

1. A function in `src/wiggle/transforms/<layer>.py` with the standard
   signature, returning `None` when it doesn't apply.
2. One `Perturbation(...)` entry in `PERTURBATIONS`.

Module-level assertions catch a missing or malformed propagation table at
import time. Then add a test — see
[`tests/README.md`](../tests/README.md) for the recipe and the mocking pattern.
