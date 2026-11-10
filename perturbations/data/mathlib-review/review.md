# Perturbation review — benchmark anchors

Generated 2026-08-03T18:08:53+00:00  
24 anchors × 28 perturbations, depth 1  
Lean verification: **on**

Every variant marked `OK` was accepted by the Lean type-checker, either
because Lean itself generated it (`extract_goal`) or because
`example : <variant> := by sorry` elaborated. Truth labels are inferred
from the propagation table, **not** proven.

## Summary — hit rate per perturbation

| Perturbation | Layer | Applied | n/a | Rejected | Tactic failed | No-op | Lean calls |
|---|---|---|---|---|---|---|---|
| `negate` | logical | **24/24** | 0 | 0 | 0 | 0 | 24 |
| `contrapose` | logical | **0/24** | 0 | 0 | 24 | 0 | 24 |
| `converse` | logical | **0/24** | 0 | 0 | 24 | 0 | 24 |
| `inverse` | logical | **0/24** | 0 | 0 | 24 | 0 | 24 |
| `drop_unused_hyp` | logical | **0/24** | 0 | 0 | 0 | 24 | 24 |
| `de_morgan_rewrite` | connective | **24/24** | 0 | 0 | 0 | 0 | 24 |
| `quantifier_swap` | quantifier | **2/24** | 21 | 1 | 0 | 0 | 3 |
| `tc_weaken_hyp` | typeclass | **10/24** | 8 | 6 | 0 | 0 | 103 |
| `tc_strengthen_hyp` | typeclass | **17/24** | 7 | 0 | 0 | 0 | 17 |
| `tc_strengthen_conc` | typeclass | **0/24** | 23 | 1 | 0 | 0 | 8 |
| `tc_weaken_conc` | typeclass | **0/24** | 22 | 2 | 0 | 0 | 6 |
| `flip_bound` | bounds | **18/24** | 6 | 0 | 0 | 0 | 0 |
| `bound_tighter` | bounds | **2/24** | 21 | 0 | 0 | 1 | 0 |
| `alpha_rename` | structure | **24/24** | 0 | 0 | 0 | 0 | 24 |
| `premise_permute` | structure | **15/24** | 9 | 0 | 0 | 0 | 15 |
| `implicit_explicit_toggle` | structure | **24/24** | 0 | 0 | 0 | 0 | 24 |
| `curry` | connective | **0/24** | 0 | 0 | 24 | 0 | 24 |
| `uncurry` | connective | **19/24** | 0 | 0 | 5 | 0 | 24 |
| `definitional_unfold` | connective | **6/24** | 0 | 0 | 18 | 0 | 24 |
| `strictness_swap` | relation | **18/24** | 6 | 0 | 0 | 0 | 18 |
| `eq_to_le` | relation | **12/24** | 6 | 6 | 0 | 0 | 18 |
| `connective_swap` | relation | **21/24** | 3 | 0 | 0 | 0 | 21 |
| `arith_op_swap` | relation | **13/24** | 7 | 4 | 0 | 0 | 17 |
| `const_to_zero_one` | relation | **18/24** | 4 | 2 | 0 | 0 | 20 |
| `forall_to_exists` | quantifier | **1/24** | 23 | 0 | 0 | 0 | 1 |
| `exists_to_forall` | quantifier | **0/24** | 24 | 0 | 0 | 0 | 0 |
| `specialize_type` | typeclass | **19/24** | 4 | 1 | 0 | 0 | 28 |
| `tc_sibling_swap` | typeclass | **11/24** | 10 | 3 | 0 | 0 | 101 |

**298 variants produced** from 24 anchors.

---

## Anchors

### 1. `sign_cases_of_C_mul_pow_nonneg`

- **Module** — `Mathlib.Algebra.Order.Ring.Unbundled.Basic`
- **Source** — mathlib:70
- **Shapes** — `arith_op`, `conj_hypothesis`, `disjunction`, `equality`, `implication`, `inequality`, `numeral`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 27 Lean calls, 305.9s

**Original signature (as it appears in the sheet):**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀ (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

#### Variants produced (15/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (R : Type u_1) (inst : Semiring R) (inst_1 : LinearOrder R) (a : R) (b : R), PosMulStrictMono
    R ∧ (∀ (n : ℕ), 0 ≤ a * b ^ n) ∧ a ≠ 0 ∧ (0 < a → b < 0)
```

Change: `∀ {R` → `∃ (R`; `u_1} [inst` → `u_1) (inst`; `R] [inst_1` → `R) (inst_1`; `R] {a b` → `R) (a`; `R} [PosMulStrictMono R],` → `R) (b : R), PosMulStrictMono R ∧`; `→` → `∧`; …and 4 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R}, ¬PosMulStrictMono R ∨
    (∃ (x : ℕ), ¬0 ≤ a * b ^ x) ∨ a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `R} [PosMulStrictMono R], (∀ (n` → `R}, ¬PosMulStrictMono R ∨ (∃ (x`; `0` → `¬0`; `n) →` → `x) ∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : MonoidWithZero R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono
    R], (∀ (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `Semiring` → `MonoidWithZero`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono
    R], (∀ (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `Semiring` → `CommSemiring`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 0 ≥ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {γ : Type u_1} [inst : Semiring γ] [inst_1 : LinearOrder γ] {c d : γ} [PosMulStrictMono γ], (∀
    (n : ℕ), 0 ≤ c * d ^ n) → c = 0 ∨ 0 < c ∧ 0 ≤ d
```

Change: `{R` → `{γ`; `R]` → `γ]`; `R] {a b` → `γ] {c d`; `R}` → `γ}`; `R],` → `γ],`; `a` → `c`; …and 4 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (R : Type u_1) [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `{R` → `(R`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R}, (PosMulStrictMono R ∧ ∀
    (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `R} [PosMulStrictMono R], (∀` → `R}, (PosMulStrictMono R ∧ ∀`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 0 < a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `≤` → `<`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 0 ≤ a * b ^ n) → a ≤ 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∧ 0 < a ∧ 0 ≤ b
```

Change: `∨` → `∧`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 0 ≤ a + b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `*` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [PosMulStrictMono R], (∀
    (n : ℕ), 1 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {a b : ℕ}, (∀ (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: removed `{R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R]`; `R} [PosMulStrictMono R],` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommMonoidWithZero R] [inst_1 : LinearOrder R] {a b : R}
    [PosMulStrictMono R], (∀ (n : ℕ), 0 ≤ a * b ^ n) → a = 0 ∨ 0 < a ∧ 0 ≤ b
```

Change: `Semiring` → `CommMonoidWithZero`

#### Did not fire (13)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 2. `QuadraticForm.equivalent_one_zero_neg_one_weighted_sum_squared`

- **Module** — `Mathlib.LinearAlgebra.QuadraticForm.Real`
- **Source** — mathlib:4
- **Shapes** — `conj_hypothesis`, `disjunction`, `equality`, `forall_then_exists`, `implication`, `numeral`, `typeclass_binder`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 51 Lean calls, 343.2s

**Original signature (as it appears in the sheet):**

```lean
∀ {M : Type u_1} [inst : AddCommGroup M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M] (Q : QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)), w i = -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares ℝ w)
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {M : Type u_1} [inst : AddCommGroup M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M] (Q :
    QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)),
    w i = -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares ℝ
    w)
```

#### Variants produced (9/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (M : Type u_1) (inst : AddCommGroup M) (inst_1 : Module ℝ M), FiniteDimensional ℝ M ∧ ∃ (Q :
    QuadraticForm ℝ M), ∀ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)),
    w i = -1 ∨ w i = 0 ∨ w i = 1) → ¬QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares
    ℝ w)
```

Change: `∀ {M` → `∃ (M`; `u_1} [inst` → `u_1) (inst`; `M] [inst_1` → `M) (inst_1`; `M] [FiniteDimensional` → `M), FiniteDimensional`; `M]` → `M ∧ ∃`; `∃` → `∀`; …and 1 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {M : Type u_1} [inst : AddCommGroup M] [inst_1 : Module ℝ M], ¬FiniteDimensional ℝ M ∨ ∀ (Q :
    QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)),
    w i = -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares ℝ
    w)
```

Change: `M] [FiniteDimensional` → `M], ¬FiniteDimensional`; `M]` → `M ∨ ∀`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {M : Type u_1} [inst : AddCommGroupWithOne M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M] (Q
    : QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ
    M)), w i = -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q
    (QuadraticMap.weightedSumSquares ℝ w)
```

Change: `AddCommGroup` → `AddCommGroupWithOne`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : AddCommGroup α] [inst_1 : Module ℝ α] [FiniteDimensional ℝ α] (x :
    QuadraticForm ℝ α), ∃ (w : Fin (Module.finrank ℝ α) → ℝ), (∀ (i : Fin (Module.finrank ℝ α)),
    w i = -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent x (QuadraticMap.weightedSumSquares ℝ
    w)
```

Change: `{M` → `{α`; `M]` → `α]`; `M]` → `α]`; `M] (Q` → `α] (x`; `M),` → `α),`; `M)` → `α)`; …and 2 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (M : Type u_1) [inst : AddCommGroup M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M] (Q :
    QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)),
    w i = -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares ℝ
    w)
```

Change: `{M` → `(M`; `u_1}` → `u_1)`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : AddCommGroup M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M] (Q :
    QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)),
    w i ≤ -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares ℝ
    w)
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : AddCommGroup M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M] (Q :
    QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)),
    w i = -1 ∧ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares ℝ
    w)
```

Change: `∨` → `∧`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : AddCommGroup M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M] (Q :
    QuadraticForm ℝ M), ∃ (w : Fin (Module.finrank ℝ M) → ℝ), (∀ (i : Fin (Module.finrank ℝ M)),
    w i = -0 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q (QuadraticMap.weightedSumSquares ℝ
    w)
```

Change: `-1` → `-0`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ (Q : QuadraticForm ℝ ℝ), ∃ (w : Fin (Module.finrank ℝ ℝ) → ℝ), (∀ (i : Fin (Module.finrank ℝ
    ℝ)), w i = -1 ∨ w i = 0 ∨ w i = 1) ∧ QuadraticMap.Equivalent Q
    (QuadraticMap.weightedSumSquares ℝ w)
```

Change: removed `{M : Type u_1} [inst : AddCommGroup M] [inst_1 : Module ℝ M] [FiniteDimensional ℝ M]`; `M),` → `ℝ),`; `M)` → `ℝ)`; `M)),` → `ℝ)),`

#### Did not fire (19)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_weaken_hyp` | rejected | 11 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | rejected | 8 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_weaken_conc` | rejected | 2 candidate(s) proposed, all rejected by the Lean type-checker |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | rejected | 9 candidate(s) proposed, all rejected by the Lean type-checker |

---

### 3. `Nat.digits_add`

- **Module** — `Mathlib.Data.Nat.Digits`
- **Source** — mathlib:16
- **Shapes** — `arith_op`, `disjunction`, `equality`, `implication`, `inequality`, `leading_explicit_forall`, `numeral`, `two_hypotheses`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 19 Lean calls, 304.7s

**Original signature (as it appears in the sheet):**

```lean
∀ (b : ℕ), 1 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ (b : ℕ), 1 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

#### Variants produced (13/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (b : ℕ), 1 < b ∧ ∃ (x : ℕ) (y : ℕ), x < b ∧ (x ≠ 0 ∨ y ≠ 0) ∧ b.digits (x + b * y) ≠ x ::
    b.digits y
```

Change: `∀` → `∃`; `→ ∀` → `∧ ∃`; `y` → `: ℕ) (y`; `→ x` → `∧ (x`; `0 →` → `0) ∧`; `=` → `≠`

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ (b : ℕ), ¬1 < b ∨ ∀ (x y : ℕ), ¬x < b ∨ x = 0 ∧ y = 0 ∨ b.digits (x + b * y) = x :: b.digits y
```

Change: `1` → `¬1`; `→` → `∨`; `x` → `¬x`; `→` → `∨`; `≠` → `= 0 ∧ y =`; removed `y ≠ 0 →`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ (b : ℕ), 1 > b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

Change: `<` → `>`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ (k : ℕ), 1 < k → ∀ (x y : ℕ), x < k → x ≠ 0 ∨ y ≠ 0 → k.digits (x + k * y) = x :: k.digits y
```

Change: `(b` → `(k`; `b` → `k`; `b` → `k`; `b.digits` → `k.digits`; `b` → `k`; `b.digits` → `k.digits`

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ (b : ℕ), ∀ (x y : ℕ), x < b →1 < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

Change: removed `1 < b →`; added `< b →1`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ {b : ℕ}, 1 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

Change: `(b` → `{b`; `ℕ),` → `ℕ},`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ (b : ℕ), 1 < b → ∀ (x y : ℕ), x < b ∧ (x ≠ 0 ∨ y ≠ 0) → b.digits (x + b * y) = x :: b.digits y
```

Change: `→ x` → `∧ (x`; `0` → `0)`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ (b : ℕ), 1 ≤ b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

Change: `<` → `≤`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ (b : ℕ), 1 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) ≤ x :: b.digits y
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ (b : ℕ), 1 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∧ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

Change: `∨` → `∧`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ (b : ℕ), 1 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x * b * y) = x :: b.digits y
```

Change: `+` → `*`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ (b : ℕ), 0 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

Change: `1` → `0`

##### `forall_to_exists` — quantifier, inferred truth: **unknown**

```lean
∃ (b : ℕ), 1 < b → ∀ (x y : ℕ), x < b → x ≠ 0 ∨ y ≠ 0 → b.digits (x + b * y) = x :: b.digits y
```

Change: `∀` → `∃`

#### Did not fire (15)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `specialize_type` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 4. `exists_increasing_or_nonincreasing_subseq`

- **Module** — `Mathlib.Order.OrderIsoNat`
- **Source** — mathlib:19
- **Shapes** — `disjunction`, `forall_then_exists`, `implication`, `inequality`, `two_hypotheses`, `typeclass_binder`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 17 Lean calls, 304.0s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m < n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m <
    n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

#### Variants produced (11/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (r : α → α → Prop), IsTrans α r ∧ ∃ (f : ℕ → α), ∀ (g : ℕ ↪o ℕ), (∃ (m : ℕ) (n
    : ℕ), m < n ∧ ¬r (f (g m)) (f (g n))) ∧ ∃ (m : ℕ) (n : ℕ), m < n ∧ r (f (g m)) (f (g n))
```

Change: `∀ {α` → `∃ (α`; `u_1}` → `u_1)`; `Prop) [IsTrans` → `Prop), IsTrans`; `r]` → `r ∧ ∃`; `∃` → `∀`; `(∀` → `(∃`; …and 3 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} (r : α → α → Prop), ¬IsTrans α r ∨ ∀ (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ),
    ¬m < n ∨ r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), ¬m < n ∨ ¬r (f (g m)) (f (g n))
```

Change: `Prop) [IsTrans` → `Prop), ¬IsTrans`; `r]` → `r ∨ ∀`; `m` → `¬m`; `→` → `∨`; `m` → `¬m`; `→` → `∨`

##### `quantifier_swap` — quantifier, inferred truth: **unknown**

```lean
∃ (g : ℕ ↪o ℕ), ∀ {α : Type u_1} (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), (∀ (m n : ℕ), m <
    n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: added `∃ (g : ℕ ↪o ℕ),`; removed `∃ (g : ℕ ↪o ℕ),`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} (r : α → α → Prop) [IsPreorder α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ),
    m < n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `[IsTrans` → `[IsPreorder`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m >
    n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `<` → `>`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {ι : Type u_1} (h : ι → ι → Prop) [IsTrans ι h] (φ : ℕ → ι), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m <
    n → h (φ (g m)) (φ (g n))) ∨ ∀ (m n : ℕ), m < n → ¬h (φ (g m)) (φ (g n))
```

Change: `{α` → `{ι`; `(r` → `(h`; `α` → `ι`; `α` → `ι`; `α r] (f` → `ι h] (φ`; `α),` → `ι),`; …and 4 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m <
    n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m <
    n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n ∧ r (f (g m)) (f (g n)) → False
```

Change: `→ ¬r` → `∧ r`; added `→ False`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m ≤
    n → r (f (g m)) (f (g n))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `<` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) [IsTrans α r] (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m <
    n → r (f (g m)) (f (g n))) ∧ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `∨` → `∧`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ (r : ℕ → ℕ → Prop) (f : ℕ → ℕ), ∃ (g : ℕ ↪o ℕ), (∀ (m n : ℕ), m < n → r (f (g m)) (f (g n))) ∨
    ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: removed `{α : Type u_1}`; `α` → `ℕ`; `α` → `ℕ`; removed `[IsTrans α r]`; `α),` → `ℕ),`

#### Did not fire (17)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 5. `mul_eq_mul_iff_eq_and_eq_of_pos`

- **Module** — `Mathlib.Algebra.Order.GroupWithZero.Unbundled.Basic`
- **Source** — mathlib:29
- **Shapes** — `arith_op`, `conj_hypothesis`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 28 Lean calls, 111.3s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α] [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔ a = b ∧ c = d)
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔
    a = b ∧ c = d)
```

#### Variants produced (14/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : MulZeroClass α) (a : α) (b : α) (c : α) (d : α) (inst_1 : PartialOrder
    α), PosMulStrictMono α ∧ MulPosStrictMono α ∧ a ≤ b ∧ c ≤ d ∧ 0 < a ∧ 0 < d ∧ (a * c = b * d
    ∧ (a = b → c ≠ d) ∨ a * c ≠ b * d ∧ a = b ∧ c = d)
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α] {a b c d` → `α) (a`; `α} [inst_1` → `α) (b : α) (c : α) (d : α) (inst_1`; `α] [PosMulStrictMono α] [MulPosStrictMono α],` → `α), PosMulStrictMono α ∧ MulPosStrictMono α ∧`; `→` → `∧`; …and 4 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α],
    ¬PosMulStrictMono α ∨ ¬MulPosStrictMono α ∨ ¬a ≤ b ∨ ¬c ≤ d ∨ ¬0 < a ∨ ¬0 < d ∨ (a * c = b *
    d ↔ a = b ∧ c = d)
```

Change: removed `α] [PosMulStrictMono α] [MulPosStrictMono`; `a` → `¬PosMulStrictMono α ∨ ¬MulPosStrictMono α ∨ ¬a`; `→ c` → `∨ ¬c`; `→ 0` → `∨ ¬0`; `→ 0` → `∨ ¬0`; `→` → `∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : Preorder α] [PosMulStrictMono
    α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔ a = b ∧ c = d)
```

Change: `PartialOrder` → `Preorder`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroOneClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `MulZeroClass` → `MulZeroOneClass`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≥ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {γ : Type u_1} [inst : MulZeroClass γ] {x y z w : γ} [inst_1 : PartialOrder γ]
    [PosMulStrictMono γ] [MulPosStrictMono γ], x ≤ y → z ≤ w → 0 < x → 0 < w → (x * z = y * w ↔
    x = y ∧ z = w)
```

Change: `{α` → `{γ`; `α] {a b c d` → `γ] {x y z w`; `α}` → `γ}`; `α]` → `γ]`; `α]` → `γ]`; `α], a` → `γ], x`; …and 13 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], c ≤ d →a ≤ b → 0 < a → 0 < d → (a * c = b * d ↔ a
    = b ∧ c = d)
```

Change: removed `a ≤ b →`; added `→a ≤ b`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α],
    PosMulStrictMono α ∧ MulPosStrictMono α ∧ a ≤ b ∧ c ≤ d ∧ 0 < a ∧ 0 < d → (a * c = b * d ↔ a
    = b ∧ c = d)
```

Change: removed `α] [PosMulStrictMono α] [MulPosStrictMono`; added `PosMulStrictMono α ∧ MulPosStrictMono α ∧`; `→` → `∧`; `→` → `∧`; `→` → `∧`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a < b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `≤` → `<`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c ≤ b * d ↔
    a = b ∧ c = d)
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔
    a = b ∨ c = d)
```

Change: `∧` → `∨`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {a b c d : ℕ}, a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔ a = b ∧ c = d)
```

Change: removed `{α : Type u_1} [inst : MulZeroClass α]`; `α} [inst_1 : PartialOrder α] [PosMulStrictMono α] [MulPosStrictMono α],` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Semiring α] {a b c d : α} [inst_1 : PartialOrder α] [PosMulStrictMono
    α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < a → 0 < d → (a * c = b * d ↔ a = b ∧ c = d)
```

Change: `MulZeroClass` → `Semiring`

#### Did not fire (14)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `arith_op_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `const_to_zero_one` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 6. `exists_increasing_or_nonincreasing_subseq'`

- **Module** — `Mathlib.Order.OrderIsoNat`
- **Source** — mathlib:18
- **Shapes** — `arith_op`, `disjunction`, `forall_then_exists`, `implication`, `inequality`, `numeral`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 18 Lean calls, 109.5s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g (n + 1)))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

#### Variants produced (12/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (r : α → α → Prop) (f : ℕ → α), ∀ (g : ℕ ↪o ℕ), (∃ (n : ℕ), ¬r (f (g n)) (f (g
    (n + 1)))) ∧ ∃ (m : ℕ) (n : ℕ), m < n ∧ r (f (g m)) (f (g n))
```

Change: `∀ {α` → `∃ (α`; `u_1}` → `u_1)`; `∃` → `∀`; `(∀` → `(∃`; `r` → `¬r`; `∨ ∀` → `∧ ∃`; …and 2 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∨ ∀ (m n : ℕ), ¬m < n ∨ ¬r (f (g m)) (f (g n))
```

Change: `m` → `¬m`; `→` → `∨`

##### `quantifier_swap` — quantifier, inferred truth: **unknown**

```lean
∃ (g : ℕ ↪o ℕ), ∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: added `∃ (g : ℕ ↪o ℕ),`; removed `∃ (g : ℕ ↪o ℕ),`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∨ ∀ (m n : ℕ), m > n → ¬r (f (g m)) (f (g n))
```

Change: `<` → `>`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {β : Type u_1} (h : β → β → Prop) (φ : ℕ → β), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), h (φ (g n)) (φ (g
    (n + 1)))) ∨ ∀ (m n : ℕ), m < n → ¬h (φ (g m)) (φ (g n))
```

Change: `{α` → `{β`; `(r` → `(h`; `α` → `β`; `α` → `β`; `(f` → `(φ`; `α),` → `β),`; …and 4 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∨ ∀ (m n : ℕ), m < n ∧ r (f (g m)) (f (g n)) → False
```

Change: `→ ¬r` → `∧ r`; added `→ False`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∨ ∀ (m n : ℕ), m ≤ n → ¬r (f (g m)) (f (g n))
```

Change: `<` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 1)))) ∧ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `∨` → `∧`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n * 1)))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `+` → `*`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} (r : α → α → Prop) (f : ℕ → α), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g
    (n + 0)))) ∨ ∀ (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: `1))))` → `0))))`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ (r : ℕ → ℕ → Prop) (f : ℕ → ℕ), ∃ (g : ℕ ↪o ℕ), (∀ (n : ℕ), r (f (g n)) (f (g (n + 1)))) ∨ ∀
    (m n : ℕ), m < n → ¬r (f (g m)) (f (g n))
```

Change: removed `{α : Type u_1}`; `α` → `ℕ`; `α` → `ℕ`; `α),` → `ℕ),`

#### Did not fire (16)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 7. `LocallyBoundedVariationOn.exists_monotoneOn_sub_monotoneOn`

- **Module** — `Mathlib.Topology.EMetricSpace.BoundedVariation`
- **Source** — mathlib:50
- **Shapes** — `arith_op`, `conj_hypothesis`, `equality`, `implication`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 24 Lean calls, 131.3s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : LinearOrder α] {f : α → ℝ} {s : Set α}, LocallyBoundedVariationOn f s → ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧ f = p - q
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : LinearOrder α] {f : α → ℝ} {s : Set α}, LocallyBoundedVariationOn f s →
    ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧ f = p - q
```

#### Variants produced (10/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : LinearOrder α) (f : α → ℝ) (s : Set α), LocallyBoundedVariationOn f s ∧
    ∀ (p q : α → ℝ), MonotoneOn p s → MonotoneOn q s → f ≠ p - q
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α] {f : α → ℝ} {s : Set α}, LocallyBoundedVariationOn f s → ∃ (p` → `α) (f`; `(q` → `(s : Set α), LocallyBoundedVariationOn f s ∧ ∀ (p q`; `∧` → `→`; `∧` → `→`; …and 1 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : LinearOrder α] {f : α → ℝ} {s : Set α}, ¬LocallyBoundedVariationOn f s
    ∨ ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧ f = p - q
```

Change: `LocallyBoundedVariationOn` → `¬LocallyBoundedVariationOn`; `→` → `∨`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : LinearOrderedAddCommGroupWithTop α] {f : α → ℝ} {s : Set α},
    LocallyBoundedVariationOn f s → ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧
    f = p - q
```

Change: `LinearOrder` → `LinearOrderedAddCommGroupWithTop`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {κ : Type u_1} [inst : LinearOrder κ] {G : κ → ℝ} {C : Set κ}, LocallyBoundedVariationOn G C →
    ∃ (p : κ → ℝ) (q : κ → ℝ), MonotoneOn p C ∧ MonotoneOn q C ∧ G = p - q
```

Change: `{α` → `{κ`; `α] {f` → `κ] {G`; `α` → `κ`; `{s` → `{C`; `α},` → `κ},`; `f s` → `G C`; …and 5 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : LinearOrder α] {f : α → ℝ} {s : Set α}, LocallyBoundedVariationOn f s →
    ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧ f = p - q
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : LinearOrder α] {f : α → ℝ} {s : Set α}, LocallyBoundedVariationOn f s →
    ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧ f ≤ p - q
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : LinearOrder α] {f : α → ℝ} {s : Set α}, LocallyBoundedVariationOn f s →
    ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∨ MonotoneOn q s ∧ f = p - q
```

Change: `∧` → `∨`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : LinearOrder α] {f : α → ℝ} {s : Set α}, LocallyBoundedVariationOn f s →
    ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧ f = p + q
```

Change: `-` → `+`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {f : ℕ → ℝ} {s : Set ℕ}, LocallyBoundedVariationOn f s → ∃ (p : ℕ → ℝ) (q : ℕ → ℝ), MonotoneOn
    p s ∧ MonotoneOn q s ∧ f = p - q
```

Change: removed `{α : Type u_1} [inst : LinearOrder α]`; `α` → `ℕ`; `α},` → `ℕ},`; `α` → `ℕ`; `α` → `ℕ`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : CompleteLinearOrder α] {f : α → ℝ} {s : Set α},
    LocallyBoundedVariationOn f s → ∃ (p : α → ℝ) (q : α → ℝ), MonotoneOn p s ∧ MonotoneOn q s ∧
    f = p - q
```

Change: `LinearOrder` → `CompleteLinearOrder`

#### Did not fire (18)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 5 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 8. `trichotomy_of_mul_eq_mul`

- **Module** — `Mathlib.Algebra.Order.Monoid.Unbundled.Basic`
- **Source** — mathlib:39
- **Shapes** — `arith_op`, `conj_hypothesis`, `disjunction`, `equality`, `implication`, `inequality`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 24 Lean calls, 109.3s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono α] [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono α]
    [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

#### Variants produced (13/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : Mul α) (inst_1 : LinearOrder α) (a : α) (b : α) (c : α) (d : α),
    MulLeftStrictMono α ∧ MulRightStrictMono α ∧ a * b = c * d ∧ (a = c → b ≠ d) ∧ c ≤ a ∧ d ≤ b
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α] [inst_1` → `α) (inst_1`; `α] {a b c d` → `α) (a`; `α} [MulLeftStrictMono α] [MulRightStrictMono α],` → `α) (b : α) (c : α) (d : α), MulLeftStrictMono α ∧ MulRightStrictMono α ∧`; `→ a` → `∧ (a`; …and 3 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α}, ¬MulLeftStrictMono α ∨
    ¬MulRightStrictMono α ∨ ¬a * b = c * d ∨ a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: `α} [MulLeftStrictMono α] [MulRightStrictMono α], a` → `α}, ¬MulLeftStrictMono α ∨ ¬MulRightStrictMono α ∨ ¬a`; `→` → `∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : PartialOrder α] {a b c d : α} [MulLeftStrictMono α]
    [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: `LinearOrder` → `PartialOrder`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : CommMagma α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono
    α] [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: `Mul` → `CommMagma`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono α]
    [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a > c ∨ b < d
```

Change: `<` → `>`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {δ : Type u_1} [inst : Mul δ] [inst_1 : LinearOrder δ] {x y z w : δ} [MulLeftStrictMono δ]
    [MulRightStrictMono δ], x * y = z * w → x = z ∧ y = w ∨ x < z ∨ y < w
```

Change: `{α` → `{δ`; `α]` → `δ]`; `α] {a b c d` → `δ] {x y z w`; `α}` → `δ}`; `α]` → `δ]`; `α], a` → `δ], x`; …and 11 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono α]
    [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α}, MulLeftStrictMono α ∧
    MulRightStrictMono α ∧ a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: `α} [MulLeftStrictMono α] [MulRightStrictMono α],` → `α}, MulLeftStrictMono α ∧ MulRightStrictMono α ∧`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono α]
    [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a ≤ c ∨ b < d
```

Change: `<` → `≤`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono α]
    [MulRightStrictMono α], a * b ≤ c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α] {a b c d : α} [MulLeftStrictMono α]
    [MulRightStrictMono α], a * b = c * d → a = c ∨ b = d ∨ a < c ∨ b < d
```

Change: `∧` → `∨`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {a b c d : ℕ}, a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: removed `{α : Type u_1} [inst : Mul α] [inst_1 : LinearOrder α]`; `α} [MulLeftStrictMono α] [MulRightStrictMono α],` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Mul α] [inst_1 : CompleteLinearOrder α] {a b c d : α}
    [MulLeftStrictMono α] [MulRightStrictMono α], a * b = c * d → a = c ∧ b = d ∨ a < c ∨ b < d
```

Change: `LinearOrder` → `CompleteLinearOrder`

#### Did not fire (15)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `arith_op_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 9. `Ordnode.Valid'.balance'_lemma`

- **Module** — `Mathlib.Data.Ordmap.Ordset`
- **Source** — mathlib:39
- **Shapes** — `arith_op`, `conj_hypothesis`, `disjunction`, `equality`, `implication`, `inequality`, `numeral`, `two_hypotheses`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 19 Lean calls, 112.8s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' → l.size.dist l' ≤ 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 * l.size + 5 ∨ r.size ≤ 3
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≤ 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

#### Variants produced (14/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (l : Ordnode α) (l' : ℕ) (r : Ordnode α) (r' : ℕ), Ordnode.BalancedSz l' r' ∧
    (l.size.dist l' ≤ 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l') ∧ 9 * l.size + 5 < 2 *
    r.size ∧ 3 < r.size
```

Change: `∀ {α` → `∃ (α`; `u_1} {l` → `u_1) (l`; `α} {l'` → `α) (l'`; `ℕ} {r` → `ℕ) (r`; `α} {r'` → `α) (r'`; `ℕ},` → `ℕ),`; …and 5 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, ¬Ordnode.BalancedSz l' r' ∨
    (¬l.size.dist l' ≤ 1 ∨ ¬r.size = r') ∧ (¬r.size.dist r' ≤ 1 ∨ ¬l.size = l') ∨ 2 * r.size ≤ 9
    * l.size + 5 ∨ r.size ≤ 3
```

Change: `Ordnode.BalancedSz` → `¬Ordnode.BalancedSz`; `→ l.size.dist` → `∨ (¬l.size.dist`; added `∨ ¬r.size = r')`; `r.size = r' ∨ r.size.dist` → `(¬r.size.dist`; `∧ l.size` → `∨ ¬l.size`; `l' →` → `l') ∨`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≥ 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `≤` → `≥`

##### `bound_tighter` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≤ 0 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `1` → `0`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {τ : Type u_1} {y : Ordnode τ} {n : ℕ} {z : Ordnode τ} {k : ℕ}, Ordnode.BalancedSz n k →
    y.size.dist n ≤ 1 ∧ z.size = k ∨ z.size.dist k ≤ 1 ∧ y.size = n → 2 * z.size ≤ 9 * y.size +
    5 ∨ z.size ≤ 3
```

Change: `{α` → `{τ`; `{l` → `{y`; `α} {l'` → `τ} {n`; `{r` → `{z`; `α} {r'` → `τ} {k`; `l' r'` → `n k`; …and 9 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, l.size.dist l' ≤ 1 ∧ r.size
    = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' →Ordnode.BalancedSz l' r' → 2 * r.size ≤ 9 * l.size
    + 5 ∨ r.size ≤ 3
```

Change: removed `Ordnode.BalancedSz l' r' →`; added `→Ordnode.BalancedSz l' r'`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≤ 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' ∧
    (l.size.dist l' ≤ 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l') → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `→ l.size.dist` → `∧ (l.size.dist`; `l'` → `l')`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' < 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `≤` → `<`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≤ 1 ∧ r.size ≤ r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≤ 1 ∨ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `∧` → `∨`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≤ 1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 + r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `*` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} {l : Ordnode α} {l' : ℕ} {r : Ordnode α} {r' : ℕ}, Ordnode.BalancedSz l' r' →
    l.size.dist l' ≤ 0 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 *
    l.size + 5 ∨ r.size ≤ 3
```

Change: `1` → `0`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {l : Ordnode ℕ} {l' : ℕ} {r : Ordnode ℕ} {r' : ℕ}, Ordnode.BalancedSz l' r' → l.size.dist l' ≤
    1 ∧ r.size = r' ∨ r.size.dist r' ≤ 1 ∧ l.size = l' → 2 * r.size ≤ 9 * l.size + 5 ∨ r.size ≤
    3
```

Change: removed `{α : Type u_1}`; `α}` → `ℕ}`; `α}` → `ℕ}`

#### Did not fire (14)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 10. `mul_eq_mul_iff_eq_and_eq_of_pos'`

- **Module** — `Mathlib.Algebra.Order.GroupWithZero.Unbundled.Basic`
- **Source** — mathlib:30
- **Shapes** — `arith_op`, `conj_hypothesis`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 28 Lean calls, 112.6s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α] [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔ a = b ∧ c = d)
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔
    a = b ∧ c = d)
```

#### Variants produced (14/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : MulZeroClass α) (a : α) (b : α) (c : α) (d : α) (inst_1 : PartialOrder
    α), PosMulStrictMono α ∧ MulPosStrictMono α ∧ a ≤ b ∧ c ≤ d ∧ 0 < b ∧ 0 < c ∧ (a * c = b * d
    ∧ (a = b → c ≠ d) ∨ a * c ≠ b * d ∧ a = b ∧ c = d)
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α] {a b c d` → `α) (a`; `α} [inst_1` → `α) (b : α) (c : α) (d : α) (inst_1`; `α] [PosMulStrictMono α] [MulPosStrictMono α],` → `α), PosMulStrictMono α ∧ MulPosStrictMono α ∧`; `→` → `∧`; …and 4 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α],
    ¬PosMulStrictMono α ∨ ¬MulPosStrictMono α ∨ ¬a ≤ b ∨ ¬c ≤ d ∨ ¬0 < b ∨ ¬0 < c ∨ (a * c = b *
    d ↔ a = b ∧ c = d)
```

Change: removed `α] [PosMulStrictMono α] [MulPosStrictMono`; `a` → `¬PosMulStrictMono α ∨ ¬MulPosStrictMono α ∨ ¬a`; `→ c` → `∨ ¬c`; `→ 0` → `∨ ¬0`; `→ 0` → `∨ ¬0`; `→` → `∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : Preorder α] [PosMulStrictMono
    α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔ a = b ∧ c = d)
```

Change: `PartialOrder` → `Preorder`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroOneClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `MulZeroClass` → `MulZeroOneClass`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≥ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {σ : Type u_1} [inst : MulZeroClass σ] {x y z w : σ} [inst_1 : PartialOrder σ]
    [PosMulStrictMono σ] [MulPosStrictMono σ], x ≤ y → z ≤ w → 0 < y → 0 < z → (x * z = y * w ↔
    x = y ∧ z = w)
```

Change: `{α` → `{σ`; `α] {a b c d` → `σ] {x y z w`; `α}` → `σ}`; `α]` → `σ]`; `α]` → `σ]`; `α], a` → `σ], x`; …and 13 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], c ≤ d →a ≤ b → 0 < b → 0 < c → (a * c = b * d ↔ a
    = b ∧ c = d)
```

Change: removed `a ≤ b →`; added `→a ≤ b`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α],
    PosMulStrictMono α ∧ MulPosStrictMono α ∧ a ≤ b ∧ c ≤ d ∧ 0 < b ∧ 0 < c → (a * c = b * d ↔ a
    = b ∧ c = d)
```

Change: removed `α] [PosMulStrictMono α] [MulPosStrictMono`; added `PosMulStrictMono α ∧ MulPosStrictMono α ∧`; `→` → `∧`; `→` → `∧`; `→` → `∧`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a < b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔
    a = b ∧ c = d)
```

Change: `≤` → `<`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c ≤ b * d ↔
    a = b ∧ c = d)
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : MulZeroClass α] {a b c d : α} [inst_1 : PartialOrder α]
    [PosMulStrictMono α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔
    a = b ∨ c = d)
```

Change: `∧` → `∨`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {a b c d : ℕ}, a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔ a = b ∧ c = d)
```

Change: removed `{α : Type u_1} [inst : MulZeroClass α]`; `α} [inst_1 : PartialOrder α] [PosMulStrictMono α] [MulPosStrictMono α],` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Semiring α] {a b c d : α} [inst_1 : PartialOrder α] [PosMulStrictMono
    α] [MulPosStrictMono α], a ≤ b → c ≤ d → 0 < b → 0 < c → (a * c = b * d ↔ a = b ∧ c = d)
```

Change: `MulZeroClass` → `Semiring`

#### Did not fire (14)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `arith_op_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `const_to_zero_one` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 11. `ringKrullDim_succ_le_of_surjective`

- **Module** — `Mathlib.RingTheory.KrullDimension.NonZeroDivisors`
- **Source** — mathlib:2
- **Shapes** — `arith_op`, `equality`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 25 Lean calls, 121.2s

**Original signature (as it appears in the sheet):**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S), Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≤ ringKrullDim R
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

#### Variants produced (15/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (R : Type u_1) (S : Type u_2) (inst : CommRing R) (inst_1 : CommRing S) (f : R →+* S),
    Function.Surjective ⇑f ∧ ∃ r ∈ nonZeroDivisors R, f r = 0 ∧ ringKrullDim R < ringKrullDim S
    + 1
```

Change: `∀ {R` → `∃ (R`; `u_1} {S` → `u_1) (S`; `u_2} [inst` → `u_2) (inst`; `R] [inst_1` → `R) (inst_1`; `S]` → `S)`; `→ ∀ {r : R},` → `∧ ∃`; …and 3 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    ¬Function.Surjective ⇑f ∨ ∀ {r : R}, r ∉ nonZeroDivisors R ∨ ¬f r = 0 ∨ ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `Function.Surjective` → `¬Function.Surjective`; `→` → `∨`; `∈` → `∉`; `→ f` → `∨ ¬f`; `→` → `∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommSemiring R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `CommRing` → `CommSemiring`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : EuclideanDomain R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `CommRing` → `EuclideanDomain`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≥
    ringKrullDim R
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {τ : Type u_1} {α : Type u_2} [inst : CommRing τ] [inst_1 : CommRing α] (G : τ →+* α),
    Function.Surjective ⇑G → ∀ {r : τ}, r ∈ nonZeroDivisors τ → G r = 0 → ringKrullDim α + 1 ≤
    ringKrullDim τ
```

Change: `{R` → `{τ`; `{S` → `{α`; `R]` → `τ]`; `S] (f` → `α] (G`; `R` → `τ`; `S),` → `α),`; …and 6 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S), ∀ {r :
    R}, r ∈ nonZeroDivisors R →Function.Surjective ⇑f → f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: removed `Function.Surjective ⇑f →`; added `→Function.Surjective ⇑f`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (R : Type u_1) {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `{R` → `(R`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R ∧ f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `→` → `∧`

##### `definitional_unfold` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S), (∀ (b :
    S), ∃ (a : R), f a = b) → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `Function.Surjective ⇑f` → `(∀ (b : S), ∃ (a : R), f a = b)`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 <
    ringKrullDim R
```

Change: `≤` → `<`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S * 1 ≤
    ringKrullDim R
```

Change: `+` → `*`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommRing R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 1 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {S : Type u_2} [inst_1 : CommRing S] (f : ℕ →+* S), Function.Surjective ⇑f → ∀ {r : ℕ}, r ∈
    nonZeroDivisors ℕ → f r = 0 → ringKrullDim S + 1 ≤ ringKrullDim ℕ
```

Change: removed `{R : Type u_1}`; removed `[inst : CommRing R]`; `R` → `ℕ`; `R},` → `ℕ},`; `R` → `ℕ`; `R` → `ℕ`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} [inst : CommSemiring R] [inst_1 : CommRing S] (f : R →+* S),
    Function.Surjective ⇑f → ∀ {r : R}, r ∈ nonZeroDivisors R → f r = 0 → ringKrullDim S + 1 ≤
    ringKrullDim R
```

Change: `CommRing` → `CommSemiring`

#### Did not fire (13)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `eq_to_le` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 12. `nonneg_and_nonneg_or_nonpos_and_nonpos_of_mul_nonneg`

- **Module** — `Mathlib.Algebra.Order.Ring.Unbundled.Basic`
- **Source** — mathlib:42
- **Shapes** — `arith_op`, `conj_hypothesis`, `disjunction`, `implication`, `inequality`, `numeral`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 26 Lean calls, 108.7s

**Original signature (as it appears in the sheet):**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R] [PosMulStrictMono R], 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

#### Variants produced (14/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (R : Type u_1) (inst : Semiring R) (inst_1 : LinearOrder R) (a : R) (b : R), MulPosStrictMono
    R ∧ PosMulStrictMono R ∧ 0 ≤ a * b ∧ (0 ≤ a → b < 0) ∧ (a ≤ 0 → 0 < b)
```

Change: `∀ {R` → `∃ (R`; `u_1} [inst` → `u_1) (inst`; `R] [inst_1` → `R) (inst_1`; `R] {a b` → `R) (a`; `R} [MulPosStrictMono R] [PosMulStrictMono R],` → `R) (b : R), MulPosStrictMono R ∧ PosMulStrictMono R ∧`; added `∧ (0 ≤ a → b < 0) ∧ (a ≤ 0`; …and 1 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R}, ¬MulPosStrictMono R ∨
    ¬PosMulStrictMono R ∨ ¬0 ≤ a * b ∨ 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `R} [MulPosStrictMono R] [PosMulStrictMono R], 0` → `R}, ¬MulPosStrictMono R ∨ ¬PosMulStrictMono R ∨ ¬0`; `→` → `∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : MonoidWithZero R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono
    R] [PosMulStrictMono R], 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `Semiring` → `MonoidWithZero`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `Semiring` → `CommSemiring`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 0 ≥ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {δ : Type u_1} [inst : Semiring δ] [inst_1 : LinearOrder δ] {d x : δ} [MulPosStrictMono δ]
    [PosMulStrictMono δ], 0 ≤ d * x → 0 ≤ d ∧ 0 ≤ x ∨ d ≤ 0 ∧ x ≤ 0
```

Change: `{R` → `{δ`; `R]` → `δ]`; `R] {a b` → `δ] {d x`; `R}` → `δ}`; `R]` → `δ]`; `R],` → `δ],`; …and 6 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (R : Type u_1) [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `{R` → `(R`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R}, MulPosStrictMono R ∧
    PosMulStrictMono R ∧ 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `R} [MulPosStrictMono R] [PosMulStrictMono R],` → `R}, MulPosStrictMono R ∧ PosMulStrictMono R ∧`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 0 < a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `≤` → `<`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 0 ≤ a * b → 0 ≤ a ∨ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `∧` → `∨`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 0 ≤ a + b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `*` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [MulPosStrictMono R]
    [PosMulStrictMono R], 1 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {a b : ℕ}, 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: removed `{R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R]`; `R} [MulPosStrictMono R] [PosMulStrictMono R],` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommMonoidWithZero R] [inst_1 : LinearOrder R] {a b : R}
    [MulPosStrictMono R] [PosMulStrictMono R], 0 ≤ a * b → 0 ≤ a ∧ 0 ≤ b ∨ a ≤ 0 ∧ b ≤ 0
```

Change: `Semiring` → `CommMonoidWithZero`

#### Did not fire (14)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | no-op | output identical to the anchor |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 13. `Pell.existsUnique_pos_generator`

- **Module** — `Mathlib.NumberTheory.Pell`
- **Source** — mathlib:61
- **Shapes** — `conj_hypothesis`, `disjunction`, `equality`, `implication`, `inequality`, `numeral`, `two_hypotheses`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 17 Lean calls, 122.5s

**Original signature (as it appears in the sheet):**

```lean
∀ {d : ℤ}, 0 < d → ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a : Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {d : ℤ}, 0 < d → ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

#### Variants produced (10/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (d : ℤ), 0 < d ∧ ¬IsSquare d ∧ ¬∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `∀ {d` → `∃ (d`; `ℤ},` → `ℤ),`; `→` → `∧`; `→ ∃!` → `∧ ¬∃!`

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {d : ℤ}, ¬0 < d ∨ IsSquare d ∨ ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `0` → `¬0`; `→ ¬IsSquare` → `∨ IsSquare`; `→` → `∨`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {d : ℤ}, 0 > d → ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `<` → `>`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {q : ℤ}, 0 < q → ¬IsSquare q → ∃! a₁ : Pell.Solution₁ q, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ q), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `{d` → `{q`; `d` → `q`; `d` → `q`; `d,` → `q,`; `d),` → `q),`

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {d : ℤ}, ¬IsSquare d →0 < d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `0` → `¬IsSquare d →0`; removed `d → ¬IsSquare`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (d : ℤ), 0 < d → ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `{d` → `(d`; `ℤ},` → `ℤ),`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {d : ℤ}, 0 < d ∧ ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `→` → `∧`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {d : ℤ}, 0 ≤ d → ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `<` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {d : ℤ}, 0 < d → ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∨ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `∧` → `∨`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {d : ℤ}, 1 < d → ¬IsSquare d → ∃! a₁ : Pell.Solution₁ d, 1 < a₁.x ∧ 0 < a₁.y ∧ ∀ (a :
    Pell.Solution₁ d), ∃ (n : ℤ), a = a₁ ^ n ∨ a = -a₁ ^ n
```

Change: `0` → `1`

#### Did not fire (18)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `specialize_type` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 14. `two_mul_le_add_of_sq_eq_mul`

- **Module** — `Mathlib.Algebra.Order.Ring.Unbundled.Basic`
- **Source** — mathlib:98
- **Shapes** — `arith_op`, `equality`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 25 Lean calls, 123.4s

**Original signature (as it appears in the sheet):**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R] [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R}, 0 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

#### Variants produced (15/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (R : Type u_1) (inst : CommSemiring R) (inst_1 : LinearOrder R), ExistsAddOfLE R ∧
    MulPosStrictMono R ∧ PosMulStrictMono R ∧ AddLeftReflectLE R ∧ AddLeftMono R ∧ ∃ (a : R) (b
    : R) (r : R), 0 ≤ a ∧ 0 ≤ b ∧ r ^ 2 = a * b ∧ a + b < 2 * r
```

Change: `∀ {R` → `∃ (R`; `u_1} [inst` → `u_1) (inst`; `R] [inst_1` → `R) (inst_1`; `R] [ExistsAddOfLE R] [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r` → `R), ExistsAddOfLE R ∧ MulPosStrictMono R ∧ PosMulStrictMono R ∧ AddLeftReflectLE R ∧ AddLeftMono R ∧ ∃ (a`; `R},` → `R) (b : R) (r : R),`; `→` → `∧`; …and 3 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R], ¬ExistsAddOfLE R ∨
    ¬MulPosStrictMono R ∨ ¬PosMulStrictMono R ∨ ¬AddLeftReflectLE R ∨ ¬AddLeftMono R ∨ ∀ {a b r
    : R}, ¬0 ≤ a ∨ ¬0 ≤ b ∨ ¬r ^ 2 = a * b ∨ 2 * r ≤ a + b
```

Change: `R] [ExistsAddOfLE R] [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R]` → `R], ¬ExistsAddOfLE R ∨ ¬MulPosStrictMono R ∨ ¬PosMulStrictMono R ∨ ¬AddLeftReflectLE R ∨ ¬AddLeftMono R ∨ ∀`; `0` → `¬0`; `→ 0` → `∨ ¬0`; `→ r` → `∨ ¬r`; `→` → `∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `CommSemiring` → `Semiring`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : CommRing R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `CommSemiring` → `CommRing`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≥ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {γ : Type u_1} [inst : CommSemiring γ] [inst_1 : LinearOrder γ] [ExistsAddOfLE γ]
    [MulPosStrictMono γ] [PosMulStrictMono γ] [AddLeftReflectLE γ] [AddLeftMono γ] {x y z : γ},
    0 ≤ x → 0 ≤ y → z ^ 2 = x * y → 2 * z ≤ x + y
```

Change: `{R` → `{γ`; `R]` → `γ]`; `R]` → `γ]`; `R]` → `γ]`; `R]` → `γ]`; `R]` → `γ]`; …and 11 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ b →0 ≤ a → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: added `b →0 ≤`; removed `→ 0 ≤ b`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (R : Type u_1) [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `{R` → `(R`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R], ExistsAddOfLE R ∧
    MulPosStrictMono R ∧ PosMulStrictMono R ∧ AddLeftReflectLE R ∧ AddLeftMono R → ∀ {a b r :
    R}, 0 ≤ a ∧ 0 ≤ b ∧ r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `R] [ExistsAddOfLE R] [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R]` → `R], ExistsAddOfLE R ∧ MulPosStrictMono R ∧ PosMulStrictMono R ∧ AddLeftReflectLE R ∧ AddLeftMono R → ∀`; `→` → `∧`; `→` → `∧`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 < a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `≤` → `<`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ a → 0 ≤ b → r ^ 2 ≤ a * b → 2 * r ≤ a + b
```

Change: `=` → `≤`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ a → 0 ≤ b → r ^ 2 = a + b → 2 * r ≤ a + b
```

Change: `*` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    1 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {a b r : ℕ}, 0 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: removed `{R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] [ExistsAddOfLE R] [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R]`; `R},` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : CommRing R] [inst_1 : LinearOrder R] [ExistsAddOfLE R]
    [MulPosStrictMono R] [PosMulStrictMono R] [AddLeftReflectLE R] [AddLeftMono R] {a b r : R},
    0 ≤ a → 0 ≤ b → r ^ 2 = a * b → 2 * r ≤ a + b
```

Change: `CommSemiring` → `CommRing`

#### Did not fire (13)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 15. `mul_nonneg_iff_pos_imp_nonneg`

- **Module** — `Mathlib.Algebra.Order.Ring.Unbundled.Basic`
- **Source** — mathlib:74
- **Shapes** — `arith_op`, `conj_hypothesis`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 32 Lean calls, 127.0s

**Original signature (as it appears in the sheet):**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R] [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a * b ↔ (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a * b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

#### Variants produced (14/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (R : Type u_1) (inst : Semiring R) (inst_1 : LinearOrder R) (a : R) (b : R), ExistsAddOfLE R ∧
    PosMulStrictMono R ∧ MulPosStrictMono R ∧ AddLeftMono R ∧ AddLeftReflectLE R ∧ (0 ≤ a * b ∧
    ((0 < a → 0 ≤ b) → 0 < b ∧ a < 0) ∨ a * b < 0 ∧ (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a))
```

Change: `∀ {R` → `∃ (R`; `u_1} [inst` → `u_1) (inst`; `R] [inst_1` → `R) (inst_1`; `R] {a b` → `R) (a`; `R} [ExistsAddOfLE R] [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0` → `R) (b : R), ExistsAddOfLE R ∧ PosMulStrictMono R ∧ MulPosStrictMono R ∧ AddLeftMono R ∧ AddLeftReflectLE R ∧ (0`; `↔` → `∧ ((0 < a → 0 ≤ b) → 0 < b ∧ a < 0) ∨ a * b < 0 ∧`; …and 1 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R}, ¬ExistsAddOfLE R ∨
    ¬PosMulStrictMono R ∨ ¬MulPosStrictMono R ∨ ¬AddLeftMono R ∨ ¬AddLeftReflectLE R ∨ (0 ≤ a *
    b ↔ (¬0 < a ∨ 0 ≤ b) ∧ (¬0 < b ∨ 0 ≤ a))
```

Change: `R} [ExistsAddOfLE R] [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0` → `R}, ¬ExistsAddOfLE R ∨ ¬PosMulStrictMono R ∨ ¬MulPosStrictMono R ∨ ¬AddLeftMono R ∨ ¬AddLeftReflectLE R ∨ (0`; `(0` → `(¬0`; `→` → `∨`; `(0` → `(¬0`; `→` → `∨`; `a)` → `a))`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : NonAssocSemiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE
    R] [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a * b
    ↔ (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `Semiring` → `NonAssocSemiring`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : CommSemiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a * b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `Semiring` → `CommSemiring`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≥ a * b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {σ : Type u_1} [inst : Semiring σ] [inst_1 : LinearOrder σ] {x y : σ} [ExistsAddOfLE σ]
    [PosMulStrictMono σ] [MulPosStrictMono σ] [AddLeftMono σ] [AddLeftReflectLE σ], 0 ≤ x * y ↔
    (0 < x → 0 ≤ y) ∧ (0 < y → 0 ≤ x)
```

Change: `{R` → `{σ`; `R]` → `σ]`; `R] {a b` → `σ] {x y`; `R}` → `σ}`; `R]` → `σ]`; `R]` → `σ]`; …and 9 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (R : Type u_1) [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a * b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `{R` → `(R`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R}, ExistsAddOfLE R ∧
    PosMulStrictMono R ∧ MulPosStrictMono R ∧ AddLeftMono R ∧ AddLeftReflectLE R → (0 ≤ a * b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a))
```

Change: `R} [ExistsAddOfLE R] [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0` → `R}, ExistsAddOfLE R ∧ PosMulStrictMono R ∧ MulPosStrictMono R ∧ AddLeftMono R ∧ AddLeftReflectLE R → (0`; `a)` → `a))`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 < a * b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `≤` → `<`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a * b ↔
    (0 < a → 0 ≤ b) ∨ (0 < b → 0 ≤ a)
```

Change: `∧` → `∨`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a + b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `*` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R] {a b : R} [ExistsAddOfLE R]
    [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 1 ≤ a * b ↔
    (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {a b : ℕ}, 0 ≤ a * b ↔ (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: removed `{R : Type u_1} [inst : Semiring R] [inst_1 : LinearOrder R]`; `R} [ExistsAddOfLE R] [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R],` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} [inst : Semiring R] [inst_1 : CompleteLinearOrder R] {a b : R} [ExistsAddOfLE
    R] [PosMulStrictMono R] [MulPosStrictMono R] [AddLeftMono R] [AddLeftReflectLE R], 0 ≤ a * b
    ↔ (0 < a → 0 ≤ b) ∧ (0 < b → 0 ≤ a)
```

Change: `LinearOrder` → `CompleteLinearOrder`

#### Did not fire (14)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 16. `Ideal.IsPrime.mem_or_mem_of_mul_eq_zero`

- **Module** — `Mathlib.RingTheory.Ideal.Prime`
- **Source** — mathlib:5
- **Shapes** — `arith_op`, `disjunction`, `equality`, `implication`, `numeral`, `two_hypotheses`, `typeclass_binder`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 37 Lean calls, 123.5s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : Semiring α] {I : Ideal α}, I.IsPrime → ∀ {x y : α}, x * y = 0 → x ∈ I ∨ y ∈ I
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : Semiring α] {I : Ideal α}, I.IsPrime → ∀ {x y : α}, x * y = 0 → x ∈ I ∨
    y ∈ I
```

#### Variants produced (10/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : Semiring α) (I : Ideal α), I.IsPrime ∧ ∃ (x : α) (y : α), x * y = 0 ∧ x
    ∉ I ∧ y ∉ I
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α] {I` → `α) (I`; `α},` → `α),`; `→ ∀ {x y` → `∧ ∃ (x`; `α},` → `α) (y : α),`; …and 4 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : Semiring α] {I : Ideal α}, ¬I.IsPrime ∨ ∀ {x y : α}, ¬x * y = 0 ∨ x ∈ I
    ∨ y ∈ I
```

Change: `I.IsPrime →` → `¬I.IsPrime ∨`; `x` → `¬x`; `→` → `∨`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : CommSemiring α] {I : Ideal α}, I.IsPrime → ∀ {x y : α}, x * y = 0 → x ∈
    I ∨ y ∈ I
```

Change: `Semiring` → `CommSemiring`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {β : Type u_1} [inst : Semiring β] {z : Ideal β}, z.IsPrime → ∀ {x y : β}, x * y = 0 → x ∈ z ∨
    y ∈ z
```

Change: `{α` → `{β`; `α] {I` → `β] {z`; `α}, I.IsPrime` → `β}, z.IsPrime`; `α},` → `β},`; `I` → `z`; `I` → `z`

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : Semiring α] {I : Ideal α}, ∀ {x y : α}, x * y = 0 →I.IsPrime → x ∈ I ∨
    y ∈ I
```

Change: removed `I.IsPrime →`; added `→I.IsPrime`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : Semiring α] {I : Ideal α}, I.IsPrime → ∀ {x y : α}, x * y = 0 → x ∈ I ∨
    y ∈ I
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Semiring α] {I : Ideal α}, I.IsPrime → ∀ {x y : α}, x * y = 0 → x ∈ I ∧
    y ∈ I
```

Change: `∨` → `∧`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Semiring α] {I : Ideal α}, I.IsPrime → ∀ {x y : α}, x + y = 0 → x ∈ I ∨
    y ∈ I
```

Change: `*` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : Semiring α] {I : Ideal α}, I.IsPrime → ∀ {x y : α}, x * y = 1 → x ∈ I ∨
    y ∈ I
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {I : Ideal ℕ}, I.IsPrime → ∀ {x y : ℕ}, x * y = 0 → x ∈ I ∨ y ∈ I
```

Change: removed `{α : Type u_1} [inst : Semiring α]`; `α},` → `ℕ},`; `α},` → `ℕ},`

#### Did not fire (18)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 10 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | rejected | 8 candidate(s) proposed, all rejected by the Lean type-checker |

---

### 17. `DivisorChain.exists_chain_of_prime_pow`

- **Module** — `Mathlib.RingTheory.ChainOfDivisors`
- **Source** — mathlib:1
- **Shapes** — `arith_op`, `conj_hypothesis`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 30 Lean calls, 154.1s

**Original signature (as it appears in the sheet):**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r : Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

#### Variants produced (16/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (M : Type u_1) (inst : CommMonoidWithZero M), IsCancelMulZero M ∧ ∃ (p : Associates M) (n :
    ℕ), n ≠ 0 ∧ Prime p ∧ ∀ (c : Fin (n + 1) → Associates M), c 1 = p → StrictMono c → ∃ (r :
    Associates M), (r ≤ p ^ n ∧ ∀ (i : Fin (n + 1)), r ≠ c i) ∨ ¬r ≤ p ^ n ∧ ∃ (i : Fin (n +
    1)), r = c i
```

Change: `∀ {M` → `∃ (M`; `u_1} [inst` → `u_1) (inst`; `M] [IsCancelMulZero M] {p` → `M), IsCancelMulZero M ∧ ∃ (p`; `M} {n` → `M) (n`; `ℕ},` → `ℕ),`; `→` → `∧`; …and 5 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M], ¬IsCancelMulZero M ∨ ∀ {p : Associates M} {n :
    ℕ}, n = 0 ∨ ¬Prime p ∨ ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `M] [IsCancelMulZero M]` → `M], ¬IsCancelMulZero M ∨ ∀`; `≠` → `=`; `→ Prime` → `∨ ¬Prime`; `→` → `∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsLeftCancelMulZero M] {p : Associates M} {n :
    ℕ}, n ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `[IsCancelMulZero` → `[IsLeftCancelMulZero`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {M : Type u_1} [inst : CommGroupWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `CommMonoidWithZero` → `CommGroupWithZero`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≥ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : CommMonoidWithZero α] [IsCancelMulZero α] {a : Associates α} {k : ℕ}, k
    ≠ 0 → Prime a → ∃ (c : Fin (k + 1) → Associates α), c 1 = a ∧ StrictMono c ∧ ∀ {r :
    Associates α}, r ≤ a ^ k ↔ ∃ (i : Fin (k + 1)), r = c i
```

Change: `{M` → `{α`; `M]` → `α]`; `M] {p` → `α] {a`; `M} {n` → `α} {k`; `n` → `k`; `p` → `a`; …and 7 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ},
    Prime p →n ≠ 0 → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `n` → `Prime p →n`; removed `→ Prime p`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (M : Type u_1) [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `{M` → `(M`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 ∧ Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `→` → `∧`

##### `definitional_unfold` — connective, inferred truth: **true**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ (∀ ⦃a b : Fin (n + 1)⦄, a < b
    → c a < c b) ∧ ∀ {r : Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `StrictMono` → `(∀ ⦃a b : Fin (n + 1)⦄, a < b →`; added `a < c b)`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r < p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `≤` → `<`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 ≤ p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∨ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `∧` → `∨`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n
    ≠ 1 → Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r :
    Associates M}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {p : Associates ℕ} {n : ℕ}, n ≠ 0 → Prime p → ∃ (c : Fin (n + 1) → Associates ℕ), c 1 = p ∧
    StrictMono c ∧ ∀ {r : Associates ℕ}, r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: removed `{M : Type u_1} [inst : CommMonoidWithZero M] [IsCancelMulZero M]`; `M}` → `ℕ}`; `M),` → `ℕ),`; `M},` → `ℕ},`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {M : Type u_1} [inst : CommRing M] [IsCancelMulZero M] {p : Associates M} {n : ℕ}, n ≠ 0 →
    Prime p → ∃ (c : Fin (n + 1) → Associates M), c 1 = p ∧ StrictMono c ∧ ∀ {r : Associates M},
    r ≤ p ^ n ↔ ∃ (i : Fin (n + 1)), r = c i
```

Change: `CommMonoidWithZero` → `CommRing`

#### Did not fire (12)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `arith_op_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 18. `Ideal.map_eq_top_or_isMaximal_of_surjective`

- **Module** — `Mathlib.RingTheory.Ideal.Maps`
- **Source** — mathlib:72
- **Shapes** — `disjunction`, `equality`, `implication`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 65 Lean calls, 238.0s

**Original signature (as it appears in the sheet):**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2 : FunLike F R S] (f : F) [RingHomClass F R S], Function.Surjective ⇑f → ∀ {I : Ideal R}, I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [RingHomClass F R S], Function.Surjective ⇑f → ∀ {I : Ideal R},
    I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

#### Variants produced (12/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (R : Type u_1) (S : Type u_2) (F : Type u_3) (inst : Semiring R) (inst_1 : Semiring S) (inst_2
    : FunLike F R S) (f : F), RingHomClass F R S ∧ Function.Surjective ⇑f ∧ ∃ (I : Ideal R),
    I.IsMaximal ∧ Ideal.map f I ≠ ⊤ ∧ ¬(Ideal.map f I).IsMaximal
```

Change: `∀ {R` → `∃ (R`; `u_1} {S` → `u_1) (S`; `u_2} {F` → `u_2) (F`; `u_3} [inst` → `u_3) (inst`; `R] [inst_1` → `R) (inst_1`; `S] [inst_2` → `S) (inst_2`; …and 8 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F), ¬RingHomClass F R S ∨ ¬Function.Surjective ⇑f ∨ ∀ {I : Ideal R},
    ¬I.IsMaximal ∨ Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `F) [RingHomClass` → `F), ¬RingHomClass`; `S], Function.Surjective` → `S ∨ ¬Function.Surjective`; `→` → `∨`; `I.IsMaximal →` → `¬I.IsMaximal ∨`

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [AddMonoidHomClass F R S], Function.Surjective ⇑f → ∀ {I : Ideal
    R}, I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `[RingHomClass` → `[AddMonoidHomClass`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : CommSemiring R] [inst_1 : Semiring S]
    [inst_2 : FunLike F R S] (f : F) [RingHomClass F R S], Function.Surjective ⇑f → ∀ {I : Ideal
    R}, I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `Semiring` → `CommSemiring`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {ζ : Type u_1} {ι : Type u_2} {κ : Type u_3} [inst : Semiring ζ] [inst_1 : Semiring ι] [inst_2
    : FunLike κ ζ ι] (w : κ) [RingHomClass κ ζ ι], Function.Surjective ⇑w → ∀ {I : Ideal ζ},
    I.IsMaximal → Ideal.map w I = ⊤ ∨ (Ideal.map w I).IsMaximal
```

Change: `{R` → `{ζ`; `{S` → `{ι`; `{F` → `{κ`; `R]` → `ζ]`; `S]` → `ι]`; `F R S] (f` → `κ ζ ι] (w`; …and 6 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [RingHomClass F R S], ∀ {I : Ideal R}, I.IsMaximal
    →Function.Surjective ⇑f → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: removed `Function.Surjective ⇑f →`; added `→Function.Surjective ⇑f`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (R : Type u_1) {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [RingHomClass F R S], Function.Surjective ⇑f → ∀ {I : Ideal R},
    I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `{R` → `(R`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F), RingHomClass F R S ∧ Function.Surjective ⇑f → ∀ {I : Ideal R},
    I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `F) [RingHomClass` → `F), RingHomClass`; `S],` → `S ∧`

##### `definitional_unfold` — connective, inferred truth: **true**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [RingHomClass F R S], (∀ (b : S), ∃ (a : R), f a = b) → ∀ {I :
    Ideal R}, I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `Function.Surjective ⇑f` → `(∀ (b : S), ∃ (a : R), f a = b)`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [RingHomClass F R S], Function.Surjective ⇑f → ∀ {I : Ideal R},
    I.IsMaximal → Ideal.map f I ≤ ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `=` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [RingHomClass F R S], Function.Surjective ⇑f → ∀ {I : Ideal R},
    I.IsMaximal → Ideal.map f I = ⊤ ∧ (Ideal.map f I).IsMaximal
```

Change: `∨` → `∧`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {R : Type u_1} {S : Type u_2} {F : Type u_3} [inst : Semiring R] [inst_1 : Semiring S] [inst_2
    : FunLike F R S] (f : F) [NonUnitalRingHomClass F R S], Function.Surjective ⇑f → ∀ {I :
    Ideal R}, I.IsMaximal → Ideal.map f I = ⊤ ∨ (Ideal.map f I).IsMaximal
```

Change: `[RingHomClass` → `[NonUnitalRingHomClass`

#### Did not fire (16)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | rejected | 4 candidate(s) proposed, all rejected by the Lean type-checker |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `specialize_type` | rejected | 5 candidate(s) proposed, all rejected by the Lean type-checker |

---

### 19. `List.formPerm_eq_formPerm_iff`

- **Module** — `Mathlib.GroupTheory.Perm.List`
- **Source** — mathlib:38
- **Shapes** — `conj_hypothesis`, `disjunction`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 18 Lean calls, 197.2s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm = l'.formPerm ↔ l ~r l' ∨ l.length ≤ 1 ∧ l'.length ≤ 1)
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≤ 1 ∧ l'.length ≤ 1)
```

#### Variants produced (12/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : DecidableEq α) (l : List α) (l' : List α), l.Nodup ∧ l'.Nodup ∧
    (l.formPerm = l'.formPerm ∧ ¬l ~r l' ∧ (l.length ≤ 1 → 1 < l'.length) ∨ l.formPerm ≠
    l'.formPerm ∧ (l ~r l' ∨ l.length ≤ 1 ∧ l'.length ≤ 1))
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α] {l l'` → `α) (l`; `α},` → `α) (l' : List α),`; `→` → `∧`; `→` → `∧`; …and 2 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, ¬l.Nodup ∨ ¬l'.Nodup ∨ (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≤ 1 ∧ l'.length ≤ 1)
```

Change: `l.Nodup → l'.Nodup →` → `¬l.Nodup ∨ ¬l'.Nodup ∨`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≥ 1 ∧ l'.length ≤ 1)
```

Change: `≤` → `≥`

##### `bound_tighter` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≤ 0 ∧ l'.length ≤ 1)
```

Change: `1` → `0`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {ε : Type u_1} [inst : DecidableEq ε] {x y : List ε}, x.Nodup → y.Nodup → (x.formPerm =
    y.formPerm ↔ x ~r y ∨ x.length ≤ 1 ∧ y.length ≤ 1)
```

Change: `{α` → `{ε`; `α] {l l'` → `ε] {x y`; `α}, l.Nodup` → `ε}, x.Nodup`; `l'.Nodup` → `y.Nodup`; `(l.formPerm` → `(x.formPerm`; `l'.formPerm` → `y.formPerm`; …and 4 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l'.Nodup →l.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≤ 1 ∧ l'.length ≤ 1)
```

Change: removed `l.Nodup →`; added `→l.Nodup`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≤ 1 ∧ l'.length ≤ 1)
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup ∧ l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≤ 1 ∧ l'.length ≤ 1)
```

Change: `→` → `∧`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length < 1 ∧ l'.length ≤ 1)
```

Change: `≤` → `<`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∧ l.length ≤ 1 ∧ l'.length ≤ 1)
```

Change: `∨` → `∧`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : DecidableEq α] {l l' : List α}, l.Nodup → l'.Nodup → (l.formPerm =
    l'.formPerm ↔ l ~r l' ∨ l.length ≤ 0 ∧ l'.length ≤ 1)
```

Change: `1` → `0`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {l l' : List ℕ}, l.Nodup → l'.Nodup → (l.formPerm = l'.formPerm ↔ l ~r l' ∨ l.length ≤ 1 ∧
    l'.length ≤ 1)
```

Change: removed `{α : Type u_1} [inst : DecidableEq α]`; `α},` → `ℕ},`

#### Did not fire (16)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 20. `Nat.stabilises_of_monotone`

- **Module** — `Mathlib.Order.Monotone.Basic`
- **Source** — mathlib:107
- **Shapes** — `arith_op`, `equality`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 17 Lean calls, 156.2s

**Original signature (as it appears in the sheet):**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m ≤ b) → (∀ (m : ℕ), f m = f (m + 1) → f (m + 1) = f (m + 2)) → b ≤ n → f n = f b
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m ≤ b) → (∀ (m : ℕ), f m = f (m + 1) → f (m
    + 1) = f (m + 2)) → b ≤ n → f n = f b
```

#### Variants produced (12/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (f : ℕ → ℕ) (b : ℕ) (n : ℕ), Monotone f ∧ (∀ (m : ℕ), f m ≤ b) ∧ (∀ (m : ℕ), f m = f (m + 1) →
    f (m + 1) = f (m + 2)) ∧ b ≤ n ∧ f n ≠ f b
```

Change: `∀ {f` → `∃ (f`; `ℕ} {b n` → `ℕ) (b`; `ℕ},` → `ℕ) (n : ℕ),`; `→` → `∧`; `→` → `∧`; `→` → `∧`; …and 2 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, ¬Monotone f ∨ (∃ (x : ℕ), ¬f x ≤ b) ∨ (∃ (x : ℕ), f x = f (x + 1) ∧ ¬f
    (x + 1) = f (x + 2)) ∨ ¬b ≤ n ∨ f n = f b
```

Change: `Monotone` → `¬Monotone`; `→ (∀ (m` → `∨ (∃ (x : ℕ), ¬f x ≤ b) ∨ (∃ (x`; `m ≤ b) → (∀ (m : ℕ), f m` → `x`; `(m` → `(x`; `→ f (m` → `∧ ¬f (x`; `(m` → `(x`; …and 2 more

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m ≥ b) → (∀ (m : ℕ), f m = f (m + 1) → f (m
    + 1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: `≤` → `≥`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {g : ℕ → ℕ} {k i : ℕ}, Monotone g → (∀ (m : ℕ), g m ≤ k) → (∀ (m : ℕ), g m = g (m + 1) → g (m
    + 1) = g (m + 2)) → k ≤ i → g i = g k
```

Change: `{f` → `{g`; `{b n` → `{k i`; `f` → `g`; `f` → `g`; `b)` → `k)`; `f` → `g`; …and 7 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, (∀ (m : ℕ), f m ≤ b) →Monotone f → (∀ (m : ℕ), f m = f (m + 1) → f (m +
    1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: removed `Monotone f →`; added `→Monotone f`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (f : ℕ → ℕ) {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m ≤ b) → (∀ (m : ℕ), f m = f (m + 1) → f (m
    + 1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: `{f` → `(f`; `ℕ}` → `ℕ)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f ∧ (∀ (m : ℕ), f m ≤ b) ∧ (∀ (m : ℕ), f m = f (m + 1) → f (m
    + 1) = f (m + 2)) ∧ b ≤ n → f n = f b
```

Change: `→` → `∧`; `→` → `∧`; `→` → `∧`

##### `definitional_unfold` — connective, inferred truth: **true**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, (∀ ⦃a b : ℕ⦄, a ≤ b → f a ≤ f b) → (∀ (m : ℕ), f m ≤ b) → (∀ (m : ℕ), f
    m = f (m + 1) → f (m + 1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: `Monotone` → `(∀ ⦃a b : ℕ⦄, a ≤ b →`; added `a ≤ f b)`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m < b) → (∀ (m : ℕ), f m = f (m + 1) → f (m
    + 1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: `≤` → `<`

##### `eq_to_le` — relation, inferred truth: **unknown**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m ≤ b) → (∀ (m : ℕ), f m ≤ f (m + 1) → f (m
    + 1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: `=` → `≤`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m ≤ b) → (∀ (m : ℕ), f m = f (m * 1) → f (m
    + 1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: `+` → `*`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {f : ℕ → ℕ} {b n : ℕ}, Monotone f → (∀ (m : ℕ), f m ≤ b) → (∀ (m : ℕ), f m = f (m + 0) → f (m
    + 1) = f (m + 2)) → b ≤ n → f n = f b
```

Change: `1)` → `0)`

#### Did not fire (16)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `specialize_type` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 21. `Metric.exists_subseq_summable_dist_of_cauchySeq`

- **Module** — `Mathlib.Analysis.Normed.Group.Completeness`
- **Source** — mathlib:0
- **Shapes** — `arith_op`, `conj_hypothesis`, `implication`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 18 Lean calls, 165.1s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ), StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ),
    StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

#### Variants produced (10/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : PseudoMetricSpace α) (u : ℕ → α), CauchySeq u ∧ ∀ (f : ℕ → ℕ),
    StrictMono f → ¬Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α]` → `α)`; `→ ∃` → `∧ ∀`; `∧ Summable` → `→ ¬Summable`

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), ¬CauchySeq u ∨ ∃ (f : ℕ → ℕ),
    StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

Change: `CauchySeq` → `¬CauchySeq`; `→` → `∨`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ), StrictMono f ∧
    Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

Change: `PseudoMetricSpace` → `MetricSpace`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {ι : Type u_1} [inst : PseudoMetricSpace ι] (g : ℕ → ι), CauchySeq g → ∃ (f : ℕ → ℕ),
    StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (g (f (i + 1))) (g (f i))
```

Change: `{α` → `{ι`; `α] (u` → `ι] (g`; `α),` → `ι),`; `u` → `g`; `(u` → `(g`; `(u` → `(g`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ),
    StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `definitional_unfold` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ), (∀ ⦃a b
    : ℕ⦄, a < b → f a < f b) ∧ Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

Change: `StrictMono` → `(∀ ⦃a b : ℕ⦄, a < b →`; added `a < f b)`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ),
    StrictMono f ∨ Summable fun (i : ℕ) ↦ dist (u (f (i + 1))) (u (f i))
```

Change: `∧` → `∨`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ),
    StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (u (f (i * 1))) (u (f i))
```

Change: `+` → `*`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∃ (f : ℕ → ℕ),
    StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (u (f (i + 0))) (u (f i))
```

Change: `1)))` → `0)))`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ (u : ℕ → ℕ), CauchySeq u → ∃ (f : ℕ → ℕ), StrictMono f ∧ Summable fun (i : ℕ) ↦ dist (u (f (i
    + 1))) (u (f i))
```

Change: removed `{α : Type u_1} [inst : PseudoMetricSpace α]`; `α),` → `ℕ),`

#### Did not fire (18)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 22. `ZMod.completedLFunction_one_sub_even`

- **Module** — `Mathlib.NumberTheory.LSeries.ZMod`
- **Source** — mathlib:34
- **Shapes** — `arith_op`, `disjunction`, `equality`, `implication`, `numeral`, `two_hypotheses`, `typeclass_binder`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 17 Lean calls, 311.0s

**Original signature (as it appears in the sheet):**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, Function.Even Φ → ∀ (s : ℂ), s ≠ 0 ∨ ∑ j : ZMod N, Φ j = 0 → s ≠ 1 ∨ Φ 0 = 0 → ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) * ZMod.completedLFunction (ZMod.dft Φ) s
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, Function.Even Φ → ∀ (s : ℂ), s ≠ 0 ∨ ∑ j : ZMod N,
    Φ j = 0 → s ≠ 1 ∨ Φ 0 = 0 → ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

#### Variants produced (9/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (N : ℕ) (h : NeZero N) (Φ : ZMod N → ℂ), Function.Even Φ ∧ ∃ (s : ℂ), (s ≠ 0 ∨ ∑ j : ZMod N, Φ
    j = 0) ∧ (s ≠ 1 ∨ Φ 0 = 0) ∧ ZMod.completedLFunction Φ (1 - s) ≠ ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: `∀ {N` → `∃ (N`; `ℕ} [inst` → `ℕ) (h`; `N] {Φ` → `N) (Φ`; `ℂ},` → `ℂ),`; `→ ∀` → `∧ ∃`; `s` → `(s`; …and 3 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, ¬Function.Even Φ ∨ ∀ (s : ℂ), s = 0 ∧ ¬∑ j : ZMod
    N, Φ j = 0 ∨ s = 1 ∧ ¬Φ 0 = 0 ∨ ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: `Function.Even` → `¬Function.Even`; `→` → `∨`; `≠` → `=`; `∨ ∑` → `∧ ¬∑`; `→` → `∨`; `≠` → `=`; …and 2 more

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {q : ℕ} [inst : NeZero q] {G : ZMod q → ℂ}, Function.Even G → ∀ (s : ℂ), s ≠ 0 ∨ ∑ j : ZMod q,
    G j = 0 → s ≠ 1 ∨ G 0 = 0 → ZMod.completedLFunction G (1 - s) = ↑q ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft G) s
```

Change: `{N` → `{q`; `N] {Φ` → `q] {G`; `N` → `q`; `Φ` → `G`; `N, Φ` → `q, G`; `Φ` → `G`; …and 3 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, ∀ (s : ℂ), s ≠ 0 ∨ ∑ j : ZMod N, Φ j = 0
    →Function.Even Φ → s ≠ 1 ∨ Φ 0 = 0 → ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: removed `Function.Even Φ →`; added `→Function.Even Φ`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (N : ℕ) [inst : NeZero N] {Φ : ZMod N → ℂ}, Function.Even Φ → ∀ (s : ℂ), s ≠ 0 ∨ ∑ j : ZMod N,
    Φ j = 0 → s ≠ 1 ∨ Φ 0 = 0 → ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: `{N` → `(N`; `ℕ}` → `ℕ)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, Function.Even Φ → ∀ (s : ℂ), (s ≠ 0 ∨ ∑ j : ZMod
    N, Φ j = 0) ∧ (s ≠ 1 ∨ Φ 0 = 0) → ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: `s` → `(s`; `0 → s` → `0) ∧ (s`; `0` → `0)`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, Function.Even Φ → ∀ (s : ℂ), s ≠ 0 ∧ ∑ j : ZMod N,
    Φ j = 0 → s ≠ 1 ∨ Φ 0 = 0 → ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: `∨` → `∧`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, Function.Even Φ → ∀ (s : ℂ), s ≠ 0 ∨ ∑ j : ZMod N,
    Φ j = 0 → s ≠ 1 ∨ Φ 0 = 0 → ZMod.completedLFunction Φ (1 + s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: `-` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {N : ℕ} [inst : NeZero N] {Φ : ZMod N → ℂ}, Function.Even Φ → ∀ (s : ℂ), s ≠ 1 ∨ ∑ j : ZMod N,
    Φ j = 0 → s ≠ 1 ∨ Φ 0 = 0 → ZMod.completedLFunction Φ (1 - s) = ↑N ^ (s - 1) *
    ZMod.completedLFunction (ZMod.dft Φ) s
```

Change: `0` → `1`

#### Did not fire (19)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `specialize_type` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 23. `Metric.exists_subseq_bounded_of_cauchySeq`

- **Module** — `Mathlib.Topology.MetricSpace.Cauchy`
- **Source** — mathlib:9
- **Shapes** — `conj_hypothesis`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`, `unfoldable_predicate`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 19 Lean calls, 155.1s

**Original signature (as it appears in the sheet):**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n : ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b n
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b
    n
```

#### Variants produced (12/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (inst : PseudoMetricSpace α) (u : ℕ → α), CauchySeq u ∧ ∃ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 < b n) ∧ ∀ (f : ℕ → ℕ), StrictMono f → ∃ (n : ℕ), ∃ m ≥ f n, b n ≤ dist (u m) (u (f
    n))
```

Change: `∀ {α` → `∃ (α`; `u_1} [inst` → `u_1) (inst`; `α]` → `α)`; `→ ∀` → `∧ ∃`; `→ ∃` → `∧ ∀`; `∧ ∀` → `→ ∃`; …and 5 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), ¬CauchySeq u ∨ ∀ (b : ℕ → ℝ), (∃ (x :
    ℕ), ¬0 < b x) ∨ ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), ¬m ≥ f n ∨ dist (u m) (u (f n)) <
    b n
```

Change: `CauchySeq` → `¬CauchySeq`; `→` → `∨`; `(∀ (n` → `(∃ (x`; `0` → `¬0`; `n) →` → `x) ∨`; `m` → `¬m`; …and 1 more

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : MetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n : ℕ), 0
    < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b n
```

Change: `PseudoMetricSpace` → `MetricSpace`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≤ f n → dist (u m) (u (f n)) < b
    n
```

Change: `≥` → `≤`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {τ : Type u_1} [inst : PseudoMetricSpace τ] (G : ℕ → τ), CauchySeq G → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (G m) (G (f n)) < b
    n
```

Change: `{α` → `{τ`; `α] (u` → `τ] (G`; `α),` → `τ),`; `u` → `G`; `(u` → `(G`; `(u` → `(G`

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), ∀ (b : ℕ → ℝ), (∀ (n : ℕ), 0 < b n)
    →CauchySeq u → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b
    n
```

Change: removed `CauchySeq u →`; added `→CauchySeq u`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type u_1) [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b
    n
```

Change: `{α` → `(α`; `u_1}` → `u_1)`

##### `definitional_unfold` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), (∀ ⦃a b : ℕ⦄, a < b → f a < f b) ∧ ∀ (n m : ℕ), m ≥ f n → dist
    (u m) (u (f n)) < b n
```

Change: `StrictMono` → `(∀ ⦃a b : ℕ⦄, a < b →`; added `a < f b)`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 ≤ b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b
    n
```

Change: `<` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∨ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b
    n
```

Change: `∧` → `∨`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {α : Type u_1} [inst : PseudoMetricSpace α] (u : ℕ → α), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n :
    ℕ), 1 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧ ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b
    n
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ (u : ℕ → ℕ), CauchySeq u → ∀ (b : ℕ → ℝ), (∀ (n : ℕ), 0 < b n) → ∃ (f : ℕ → ℕ), StrictMono f ∧
    ∀ (n m : ℕ), m ≥ f n → dist (u m) (u (f n)) < b n
```

Change: removed `{α : Type u_1} [inst : PseudoMetricSpace α]`; `α),` → `ℕ),`

#### Did not fire (16)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 24. `minpoly.unique'`

- **Module** — `Mathlib.FieldTheory.Minpoly.Basic`
- **Source** — mathlib:15
- **Shapes** — `disjunction`, `equality`, `implication`, `inequality`, `numeral`, `two_hypotheses`, `typeclass_binder`
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 63 Lean calls, 152.3s

**Original signature (as it appears in the sheet):**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 0 → (∀ (q : Polynomial A), q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 0 → (∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

#### Variants produced (12/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (A : Type u_1) (B : Type u_2) (inst : CommRing A) (inst_1 : Ring B) (inst_2 : Algebra A B) (x
    : B) (p : Polynomial A), p.Monic ∧ (Polynomial.aeval x) p = 0 ∧ (∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) ∧ p ≠ minpoly A x
```

Change: `∀` → `∃`; `{B` → `(B`; `u_2} [inst` → `u_2) (inst`; `A] [inst_1` → `A) (inst_1`; `B] [inst_2` → `B) (inst_2`; `B]` → `B)`; …and 6 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, ¬p.Monic ∨ ¬(Polynomial.aeval x) p = 0 ∨ (∃ (x_1 : Polynomial A),
    x_1.degree < p.degree ∧ ¬x_1 = 0 ∧ (Polynomial.aeval x) x_1 = 0) ∨ p = minpoly A x
```

Change: `p.Monic → (Polynomial.aeval` → `¬p.Monic ∨ ¬(Polynomial.aeval`; `→ (∀ (q` → `∨ (∃ (x_1`; `q.degree` → `x_1.degree`; `→ q` → `∧ ¬x_1`; `∨` → `∧`; `q ≠` → `x_1 =`; …and 1 more

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : EuclideanDomain A] [inst_1 : Ring B] [inst_2 : Algebra A
    B] (x : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 0 → (∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: `CommRing` → `EuclideanDomain`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 0 → (∀ (q : Polynomial A),
    q.degree > p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: `<` → `>`

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ (ζ : Type u_1) {ι : Type u_2} [inst : CommRing ζ] [inst_1 : Ring ι] [inst_2 : Algebra ζ ι] (b
    : ι) {c : Polynomial ζ}, c.Monic → (Polynomial.aeval b) c = 0 → (∀ (q : Polynomial ζ),
    q.degree < c.degree → q = 0 ∨ (Polynomial.aeval b) q ≠ 0) → c = minpoly ζ b
```

Change: `(A` → `(ζ`; `{B` → `{ι`; `A]` → `ζ]`; `B]` → `ι]`; `A B] (x` → `ζ ι] (b`; `B) {p` → `ι) {c`; …and 7 more

##### `premise_permute` — structure, inferred truth: **true**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, (Polynomial.aeval x) p = 0 →p.Monic → (∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: removed `p.Monic →`; added `→p.Monic`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (A : Type u_1) (B : Type u_2) [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 0 → (∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: `{B` → `(B`; `u_2}` → `u_2)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, (p.Monic ∧ (Polynomial.aeval x) p = 0 ∧ ∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: `p.Monic →` → `(p.Monic ∧`; `→ (∀` → `∧ ∀`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 0 → (∀ (q : Polynomial A),
    q.degree ≤ p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: `<` → `≤`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 0 → (∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∧ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: `∨` → `∧`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ (A : Type u_1) {B : Type u_2} [inst : CommRing A] [inst_1 : Ring B] [inst_2 : Algebra A B] (x
    : B) {p : Polynomial A}, p.Monic → (Polynomial.aeval x) p = 1 → (∀ (q : Polynomial A),
    q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p = minpoly A x
```

Change: `0` → `1`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {B : Type u_2} [inst_1 : Ring B] (x : B) {p : Polynomial ℤ}, p.Monic → (Polynomial.aeval x) p
    = 0 → (∀ (q : Polynomial ℤ), q.degree < p.degree → q = 0 ∨ (Polynomial.aeval x) q ≠ 0) → p =
    minpoly ℤ x
```

Change: removed `(A : Type u_1)`; removed `[inst : CommRing A]`; removed `B] [inst_2 : Algebra A`; `A},` → `ℤ},`; `A),` → `ℤ),`; `A` → `ℤ`

#### Did not fire (16)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | no-op | output identical to the anchor |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 25 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | rejected | 18 candidate(s) proposed, all rejected by the Lean type-checker |

---
