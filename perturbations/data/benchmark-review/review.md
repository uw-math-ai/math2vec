# Perturbation review — benchmark anchors

Generated 2026-07-27T00:40:02+00:00  
10 anchors × 28 perturbations, depth 1  
Lean verification: **on**

Every variant marked `OK` was accepted by the Lean type-checker, either
because Lean itself generated it (`extract_goal`) or because
`example : <variant> := by sorry` elaborated. Truth labels are inferred
from the propagation table, **not** proven.

## Summary — hit rate per perturbation

| Perturbation | Layer | Applied | n/a | Rejected | Tactic failed | No-op | Lean calls |
|---|---|---|---|---|---|---|---|
| `negate` | logical | **3/10** | 0 | 0 | 7 | 0 | 10 |
| `contrapose` | logical | **0/10** | 0 | 0 | 10 | 0 | 10 |
| `converse` | logical | **0/10** | 0 | 0 | 10 | 0 | 10 |
| `inverse` | logical | **0/10** | 0 | 0 | 10 | 0 | 10 |
| `drop_unused_hyp` | logical | **3/10** | 0 | 0 | 7 | 0 | 10 |
| `de_morgan_rewrite` | connective | **3/10** | 0 | 0 | 7 | 0 | 10 |
| `quantifier_swap` | quantifier | **0/10** | 10 | 0 | 0 | 0 | 0 |
| `tc_weaken_hyp` | typeclass | **2/10** | 3 | 5 | 0 | 0 | 23 |
| `tc_strengthen_hyp` | typeclass | **5/10** | 4 | 1 | 0 | 0 | 8 |
| `tc_strengthen_conc` | typeclass | **1/10** | 9 | 0 | 0 | 0 | 2 |
| `tc_weaken_conc` | typeclass | **0/10** | 10 | 0 | 0 | 0 | 0 |
| `flip_bound` | bounds | **2/10** | 8 | 0 | 0 | 0 | 0 |
| `bound_tighter` | bounds | **0/10** | 10 | 0 | 0 | 0 | 0 |
| `alpha_rename` | structure | **1/10** | 0 | 9 | 0 | 0 | 10 |
| `premise_permute` | structure | **0/10** | 10 | 0 | 0 | 0 | 0 |
| `implicit_explicit_toggle` | structure | **10/10** | 0 | 0 | 0 | 0 | 10 |
| `curry` | connective | **0/10** | 0 | 0 | 10 | 0 | 10 |
| `uncurry` | connective | **2/10** | 0 | 0 | 8 | 0 | 10 |
| `definitional_unfold` | connective | **0/10** | 0 | 0 | 10 | 0 | 10 |
| `strictness_swap` | relation | **2/10** | 8 | 0 | 0 | 0 | 2 |
| `eq_to_le` | relation | **0/10** | 10 | 0 | 0 | 0 | 0 |
| `connective_swap` | relation | **1/10** | 9 | 0 | 0 | 0 | 1 |
| `arith_op_swap` | relation | **1/10** | 9 | 0 | 0 | 0 | 1 |
| `const_to_zero_one` | relation | **2/10** | 8 | 0 | 0 | 0 | 2 |
| `forall_to_exists` | quantifier | **0/10** | 10 | 0 | 0 | 0 | 0 |
| `exists_to_forall` | quantifier | **0/10** | 10 | 0 | 0 | 0 | 0 |
| `specialize_type` | typeclass | **9/10** | 0 | 1 | 0 | 0 | 14 |
| `tc_sibling_swap` | typeclass | **2/10** | 5 | 3 | 0 | 0 | 17 |

**49 variants produced** from 10 anchors.

---

## Anchors

### 1. `MeasureTheory.tendstoInMeasure_iff_tendsto_Lp_finite`

- **Module** — `Mathlib.MeasureTheory.Function.UniformIntegrable`
- **CSV rows** — draft1-fi-015, draft1-fi-038 (sheet rows 16, 39)
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 32 Lean calls, 322.1s

**Original signature (as it appears in the sheet):**

```lean
MeasureTheory.tendstoInMeasure_iff_tendsto_Lp_finite.{u_1, u_2} {α : Type u_1} {β : Type u_2} {m : MeasurableSpace α}
  {μ : MeasureTheory.Measure α} [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
  [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≤ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ), MeasureTheory.MemLp (f n) p μ)
  (hg : MeasureTheory.MemLp g p μ) :
  MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≤ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

#### Variants produced (12/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (β : Type u_2) (m : MeasurableSpace α) (μ : MeasureTheory.Measure α) (inst :
    NormedAddCommGroup β) (p : ENNReal) (f : ℕ → α → β) (g : α → β),
    MeasureTheory.IsFiniteMeasure μ ∧ 1 ≤ p ∧ p ≠ ⊤ ∧ (∀ (n : ℕ), MeasureTheory.MemLp (f n) p μ)
    ∧ MeasureTheory.MemLp g p μ ∧ ((MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧
    MeasureTheory.UnifIntegrable f p μ) ∧ ¬Filter.Tendsto (fun (n : ℕ) ↦ MeasureTheory.eLpNorm
    (f n - g) p μ) Filter.atTop (nhds 0) ∨ (MeasureTheory.TendstoInMeasure μ f Filter.atTop g →
    ¬MeasureTheory.UnifIntegrable f p μ) ∧ Filter.Tendsto (fun (n : ℕ) ↦ MeasureTheory.eLpNorm
    (f n - g) p μ) Filter.atTop (nhds 0))
```

Change: `∀ {α` → `∃ (α`; `_} {β` → `u_1) (β`; `_} {m` → `u_2) (m`; `α} {μ` → `α) (μ`; `α} [NormedAddCommGroup β] {p` → `α) (inst`; `ENNReal} {f` → `NormedAddCommGroup β) (p : ENNReal) (f`; …and 9 more

##### `drop_unused_hyp` — logical, inferred truth: **true**

```lean
∀ {α : Type u_1} {β : Type u_2} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α} [inst :
    NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ], 1 ≤ p → p ≠ ⊤ → (∀ (n : ℕ), MeasureTheory.MemLp (f n) p
    μ) → MeasureTheory.MemLp g p μ → (MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧
    MeasureTheory.UnifIntegrable f p μ ↔ Filter.Tendsto (fun (n : ℕ) ↦ MeasureTheory.eLpNorm (f
    n - g) p μ) Filter.atTop (nhds 0))
```

Change: `_}` → `u_1}`; `_}` → `u_2}`; `[NormedAddCommGroup` → `[inst : NormedAddCommGroup`; `μ] (hp :` → `μ],`; `p) (hp' :` → `p →`; `⊤) (hf : ∀` → `⊤ → (∀`; …and 4 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} {β : Type u_2} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α} [inst :
    NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β},
    ¬MeasureTheory.IsFiniteMeasure μ ∨ ¬1 ≤ p ∨ p = ⊤ ∨ (∃ (x : ℕ), ¬MeasureTheory.MemLp (f x) p
    μ) ∨ ¬MeasureTheory.MemLp g p μ ∨ (MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧
    MeasureTheory.UnifIntegrable f p μ ↔ Filter.Tendsto (fun (n : ℕ) ↦ MeasureTheory.eLpNorm (f
    n - g) p μ) Filter.atTop (nhds 0))
```

Change: `_}` → `u_1}`; `_}` → `u_2}`; `[NormedAddCommGroup` → `[inst : NormedAddCommGroup`; `β} [MeasureTheory.IsFiniteMeasure μ] (hp : 1` → `β}, ¬MeasureTheory.IsFiniteMeasure μ ∨ ¬1`; removed `p) (hp' :`; `≠ ⊤) (hf : ∀ (n` → `∨ p = ⊤ ∨ (∃ (x`; …and 6 more

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≥ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

Change: `≤` → `≥`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type _) {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≤ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

Change: `{α` → `(α`; `_}` → `_)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} {β : Type u_2} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α} [inst :
    NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β},
    MeasureTheory.IsFiniteMeasure μ ∧ 1 ≤ p ∧ p ≠ ⊤ ∧ (∀ (n : ℕ), MeasureTheory.MemLp (f n) p μ)
    ∧ MeasureTheory.MemLp g p μ → (MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧
    MeasureTheory.UnifIntegrable f p μ ↔ Filter.Tendsto (fun (n : ℕ) ↦ MeasureTheory.eLpNorm (f
    n - g) p μ) Filter.atTop (nhds 0))
```

Change: `_}` → `u_1}`; `_}` → `u_2}`; `[NormedAddCommGroup` → `[inst : NormedAddCommGroup`; `β} [MeasureTheory.IsFiniteMeasure μ] (hp :` → `β}, MeasureTheory.IsFiniteMeasure μ ∧`; `p) (hp' :` → `p ∧`; `⊤) (hf : ∀` → `⊤ ∧ (∀`; …and 4 more

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 1 < p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

Change: `≤` → `<`

##### `connective_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≤ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∨ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

Change: `∧` → `∨`

##### `arith_op_swap` — relation, inferred truth: **unknown**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≤ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n + g) p μ) Filter.atTop (nhds 0)
```

Change: `-` → `+`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 0 ≤ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

Change: `1` → `0`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {β : Type _} {m : MeasurableSpace ℕ} {μ : MeasureTheory.Measure ℕ} [NormedAddCommGroup β] {p :
    ENNReal} {f : ℕ → ℕ → β} {g : ℕ → β} [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≤ p) (hp' : p
    ≠ ⊤) (hf : ∀ (n : ℕ), MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

Change: removed `{α : Type _}`; `α}` → `ℕ}`; `α}` → `ℕ}`; `α` → `ℕ`; `α` → `ℕ`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NonUnitalNormedRing β] {p : ENNReal} {f : ℕ → α → β} {g : α → β}
    [MeasureTheory.IsFiniteMeasure μ] (hp : 1 ≤ p) (hp' : p ≠ ⊤) (hf : ∀ (n : ℕ),
    MeasureTheory.MemLp (f n) p μ) (hg : MeasureTheory.MemLp g p μ),
    MeasureTheory.TendstoInMeasure μ f Filter.atTop g ∧ MeasureTheory.UnifIntegrable f p μ ↔
    Filter.Tendsto (fun n => MeasureTheory.eLpNorm (f n - g) p μ) Filter.atTop (nhds 0)
```

Change: `[NormedAddCommGroup` → `[NonUnitalNormedRing`

#### Did not fire (16)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 8 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 2. `MeasureTheory.UniformIntegrable.memLp_of_tendstoInMeasure`

- **Module** — `Mathlib.MeasureTheory.Function.UniformIntegrable`
- **CSV rows** — draft1-fi-019, draft1-fi-020 (sheet rows 20, 21)
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 28 Lean calls, 320.9s

**Original signature (as it appears in the sheet):**

```lean
MeasureTheory.UniformIntegrable.memLp_of_tendstoInMeasure.{u_1, u_2, u_4} {α : Type u_1} {β : Type u_2}
  {m : MeasurableSpace α} {μ : MeasureTheory.Measure α} [NormedAddCommGroup β] {p : ENNReal} {κ : Type u_4}
  {u : Filter κ} [u.NeBot] [u.IsCountablyGenerated] {f : κ → α → β} {g : α → β}
  (hUI : MeasureTheory.UniformIntegrable f p μ) (htends : MeasureTheory.TendstoInMeasure μ f u g) :
  MeasureTheory.MemLp g p μ
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {κ : Type _} {u : Filter κ} [u.NeBot]
    [u.IsCountablyGenerated] {f : κ → α → β} {g : α → β} (hUI : MeasureTheory.UniformIntegrable
    f p μ) (htends : MeasureTheory.TendstoInMeasure μ f u g), MeasureTheory.MemLp g p μ
```

#### Variants produced (7/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (α : Type u_1) (β : Type u_2) (m : MeasurableSpace α) (μ : MeasureTheory.Measure α) (inst :
    NormedAddCommGroup β) (p : ENNReal) (κ : Type u_3) (u : Filter κ), u.NeBot ∧
    u.IsCountablyGenerated ∧ ∃ (f : κ → α → β) (g : α → β), MeasureTheory.UniformIntegrable f p
    μ ∧ MeasureTheory.TendstoInMeasure μ f u g ∧ ¬MeasureTheory.MemLp g p μ
```

Change: `∀ {α` → `∃ (α`; `_} {β` → `u_1) (β`; `_} {m` → `u_2) (m`; `α} {μ` → `α) (μ`; `α} [NormedAddCommGroup β] {p` → `α) (inst`; `ENNReal} {κ` → `NormedAddCommGroup β) (p : ENNReal) (κ`; …and 6 more

##### `drop_unused_hyp` — logical, inferred truth: **true**

```lean
∀ {α : Type u_1} {β : Type u_2} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α} [inst :
    NormedAddCommGroup β] {p : ENNReal} {κ : Type u_3} {u : Filter κ} [u.NeBot]
    [u.IsCountablyGenerated] {f : κ → α → β} {g : α → β}, MeasureTheory.UniformIntegrable f p μ
    → MeasureTheory.TendstoInMeasure μ f u g → MeasureTheory.MemLp g p μ
```

Change: `_}` → `u_1}`; `_}` → `u_2}`; `[NormedAddCommGroup` → `[inst : NormedAddCommGroup`; `_}` → `u_3}`; `β} (hUI :` → `β},`; `μ) (htends :` → `μ →`; …and 1 more

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} {β : Type u_2} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α} [inst :
    NormedAddCommGroup β] {p : ENNReal} {κ : Type u_3} {u : Filter κ}, ¬u.NeBot ∨
    ¬u.IsCountablyGenerated ∨ ∀ {f : κ → α → β} {g : α → β}, ¬MeasureTheory.UniformIntegrable f
    p μ ∨ ¬MeasureTheory.TendstoInMeasure μ f u g ∨ MeasureTheory.MemLp g p μ
```

Change: `_}` → `u_1}`; `_}` → `u_2}`; `[NormedAddCommGroup` → `[inst : NormedAddCommGroup`; `_}` → `u_3}`; `κ} [u.NeBot] [u.IsCountablyGenerated]` → `κ}, ¬u.NeBot ∨ ¬u.IsCountablyGenerated ∨ ∀`; `β} (hUI : MeasureTheory.UniformIntegrable` → `β}, ¬MeasureTheory.UniformIntegrable`; …and 2 more

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type _) {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NormedAddCommGroup β] {p : ENNReal} {κ : Type _} {u : Filter κ} [u.NeBot]
    [u.IsCountablyGenerated] {f : κ → α → β} {g : α → β} (hUI : MeasureTheory.UniformIntegrable
    f p μ) (htends : MeasureTheory.TendstoInMeasure μ f u g), MeasureTheory.MemLp g p μ
```

Change: `{α` → `(α`; `_}` → `_)`

##### `uncurry` — connective, inferred truth: **true**

```lean
∀ {α : Type u_1} {β : Type u_2} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α} [inst :
    NormedAddCommGroup β] {p : ENNReal} {κ : Type u_3} {u : Filter κ}, u.NeBot ∧
    u.IsCountablyGenerated → ∀ {f : κ → α → β} {g : α → β}, MeasureTheory.UniformIntegrable f p
    μ ∧ MeasureTheory.TendstoInMeasure μ f u g → MeasureTheory.MemLp g p μ
```

Change: `_}` → `u_1}`; `_}` → `u_2}`; `[NormedAddCommGroup` → `[inst : NormedAddCommGroup`; `_}` → `u_3}`; `κ} [u.NeBot] [u.IsCountablyGenerated]` → `κ}, u.NeBot ∧ u.IsCountablyGenerated → ∀`; `β} (hUI :` → `β},`; …and 2 more

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {β : Type _} {m : MeasurableSpace ℕ} {μ : MeasureTheory.Measure ℕ} [NormedAddCommGroup β] {p :
    ENNReal} {κ : Type _} {u : Filter κ} [u.NeBot] [u.IsCountablyGenerated] {f : κ → ℕ → β} {g :
    ℕ → β} (hUI : MeasureTheory.UniformIntegrable f p μ) (htends :
    MeasureTheory.TendstoInMeasure μ f u g), MeasureTheory.MemLp g p μ
```

Change: removed `{α : Type _}`; `α}` → `ℕ}`; `α}` → `ℕ}`; `α` → `ℕ`; `α` → `ℕ`

##### `tc_sibling_swap` — typeclass, inferred truth: **unknown**

```lean
∀ {α : Type _} {β : Type _} {m : MeasurableSpace α} {μ : MeasureTheory.Measure α}
    [NonUnitalNormedRing β] {p : ENNReal} {κ : Type _} {u : Filter κ} [u.NeBot]
    [u.IsCountablyGenerated] {f : κ → α → β} {g : α → β} (hUI : MeasureTheory.UniformIntegrable
    f p μ) (htends : MeasureTheory.TendstoInMeasure μ f u g), MeasureTheory.MemLp g p μ
```

Change: `[NormedAddCommGroup` → `[NonUnitalNormedRing`

#### Did not fire (21)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 8 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |

---

### 3. `Matrix.gram`

- **Module** — `Mathlib.Analysis.InnerProductSpace.GramMatrix`
- **CSV rows** — draft1-fi-025, draft1-fi-035 (sheet rows 26, 36)
- **Kind** — definition (conclusion is data/a type, not a proposition)
- **Anchor elaborates** — yes
- **Cost** — 16 Lean calls, 265.1s

**Original signature (as it appears in the sheet):**

```lean
Matrix.gram.{u_1, u_2, u_5} {E : Type u_1} {n : Type u_2} (𝕜 : Type u_5) [Inner 𝕜 E] (v : n → E) : Matrix n n 𝕜
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {E : Type _} {n : Type _} (𝕜 : Type _) [Inner 𝕜 E] (v : n → E), Matrix n n 𝕜
```

#### Variants produced (2/28)

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (E : Type _) {n : Type _} (𝕜 : Type _) [Inner 𝕜 E] (v : n → E), Matrix n n 𝕜
```

Change: `{E` → `(E`; `_}` → `_)`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {n : Type _} (𝕜 : Type _) (v : n → ℕ), Matrix n n 𝕜
```

Change: removed `{E : Type _}`; removed `[Inner 𝕜 E]`; `E),` → `ℕ),`

#### Did not fire (26)

| Perturbation | Outcome | Why |
|---|---|---|
| `negate` | tactic failed | tactic 'negate_state' ran but extract_goal produced nothing |
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | tactic failed | tactic 'drop_unused_hyp' ran but extract_goal produced nothing |
| `de_morgan_rewrite` | tactic failed | tactic 'de_morgan_rewrite' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | rejected | 3 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 4. `MeasureTheory.IsStoppingTime`

- **Module** — `Mathlib.Probability.Process.Stopping`
- **CSV rows** — draft1-fi-039 (sheet row 40)
- **Kind** — definition (conclusion is data/a type, not a proposition)
- **Anchor elaborates** — yes
- **Cost** — 17 Lean calls, 265.2s

**Original signature (as it appears in the sheet):**

```lean
MeasureTheory.IsStoppingTime.{u_1, u_3} {Ω : Type u_1} {ι : Type u_3} {m : MeasurableSpace Ω} [Preorder ι]
  (f : MeasureTheory.Filtration ι m) (τ : Ω → WithTop ι) : Prop
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {Ω : Type _} {ι : Type _} {m : MeasurableSpace Ω} [Preorder ι] (f : MeasureTheory.Filtration ι
    m) (τ : Ω → WithTop ι), Prop
```

#### Variants produced (3/28)

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {Ω : Type _} {ι : Type _} {m : MeasurableSpace Ω} [PartialOrder ι] (f :
    MeasureTheory.Filtration ι m) (τ : Ω → WithTop ι), Prop
```

Change: `[Preorder` → `[PartialOrder`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (Ω : Type _) {ι : Type _} {m : MeasurableSpace Ω} [Preorder ι] (f : MeasureTheory.Filtration ι
    m) (τ : Ω → WithTop ι), Prop
```

Change: `{Ω` → `(Ω`; `_}` → `_)`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {ι : Type _} {m : MeasurableSpace ℕ} [Preorder ι] (f : MeasureTheory.Filtration ι m) (τ : ℕ →
    WithTop ι), Prop
```

Change: removed `{Ω : Type _}`; `Ω}` → `ℕ}`; `Ω` → `ℕ`

#### Did not fire (25)

| Perturbation | Outcome | Why |
|---|---|---|
| `negate` | tactic failed | tactic 'negate_state' ran but extract_goal produced nothing |
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | tactic failed | tactic 'drop_unused_hyp' ran but extract_goal produced nothing |
| `de_morgan_rewrite` | tactic failed | tactic 'de_morgan_rewrite' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 2 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |

---

### 5. `ProbabilityTheory.IsMarkovKernel`

- **Module** — `Mathlib.Probability.Kernel.Defs`
- **CSV rows** — draft1-fi-042 (sheet row 43)
- **Kind** — definition (conclusion is data/a type, not a proposition)
- **Anchor elaborates** — yes
- **Cost** — 13 Lean calls, 119.7s

**Original signature (as it appears in the sheet):**

```lean
ProbabilityTheory.IsMarkovKernel.{u_1, u_2} {α : Type u_1} {β : Type u_2} {mα : MeasurableSpace α}
  {mβ : MeasurableSpace β} (κ : ProbabilityTheory.Kernel α β) : Prop
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {α : Type _} {β : Type _} {mα : MeasurableSpace α} {mβ : MeasurableSpace β} (κ :
    ProbabilityTheory.Kernel α β), Prop
```

#### Variants produced (3/28)

##### `alpha_rename` — structure, inferred truth: **true**

```lean
∀ {wv0 : Type _} {wv1 : Type _} {wv2 : MeasurableSpace wv0} {wv3 : MeasurableSpace wv1} (wv4 :
    ProbabilityTheory.Kernel wv0 wv1), Prop
```

Change: `{α` → `{wv0`; `{β` → `{wv1`; `{mα` → `{wv2`; `α} {mβ` → `wv0} {wv3`; `β} (κ` → `wv1} (wv4`; `α β),` → `wv0 wv1),`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (α : Type _) {β : Type _} {mα : MeasurableSpace α} {mβ : MeasurableSpace β} (κ :
    ProbabilityTheory.Kernel α β), Prop
```

Change: `{α` → `(α`; `_}` → `_)`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {β : Type _} {mα : MeasurableSpace ℕ} {mβ : MeasurableSpace β} (κ : ProbabilityTheory.Kernel ℕ
    β), Prop
```

Change: removed `{α : Type _}`; `α}` → `ℕ}`; `α` → `ℕ`

#### Did not fire (25)

| Perturbation | Outcome | Why |
|---|---|---|
| `negate` | tactic failed | tactic 'negate_state' ran but extract_goal produced nothing |
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | tactic failed | tactic 'drop_unused_hyp' ran but extract_goal produced nothing |
| `de_morgan_rewrite` | tactic failed | tactic 'de_morgan_rewrite' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 6. `Metric.coveringNumber_subset_le`

- **Module** — `Mathlib.Topology.MetricSpace.CoveringNumbers`
- **CSV rows** — draft1-fi-050 (sheet row 51)
- **Kind** — theorem
- **Anchor elaborates** — yes
- **Cost** — 17 Lean calls, 131.4s

**Original signature (as it appears in the sheet):**

```lean
Metric.coveringNumber_subset_le.{u_1} {X : Type u_1} [PseudoEMetricSpace X] {A B : Set X} {ε : NNReal} (h : A ⊆ B) :
  Metric.coveringNumber ε A ≤ Metric.coveringNumber (ε / 2) B
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {X : Type _} [PseudoEMetricSpace X] {A B : Set X} {ε : NNReal} (h : A ⊆ B),
    Metric.coveringNumber ε A ≤ Metric.coveringNumber (ε / 2) B
```

#### Variants produced (9/28)

##### `negate` — logical, inferred truth: **false**

```lean
∃ (X : Type u_1) (inst : PseudoEMetricSpace X) (A : Set X) (B : Set X) (ε : NNReal), A ⊆ B ∧
    Metric.coveringNumber (ε / 2) B < Metric.coveringNumber ε A
```

Change: `∀ {X` → `∃ (X`; `_} [PseudoEMetricSpace X] {A B` → `u_1) (inst : PseudoEMetricSpace X) (A`; `X} {ε` → `X) (B`; `NNReal} (h` → `Set X) (ε`; added `NNReal),`; `B), Metric.coveringNumber ε A ≤` → `B ∧`; …and 1 more

##### `drop_unused_hyp` — logical, inferred truth: **true**

```lean
∀ {X : Type u_1} [inst : PseudoEMetricSpace X] {A B : Set X} {ε : NNReal}, A ⊆ B →
    Metric.coveringNumber ε A ≤ Metric.coveringNumber (ε / 2) B
```

Change: `_} [PseudoEMetricSpace` → `u_1} [inst : PseudoEMetricSpace`; `NNReal} (h :` → `NNReal},`; `B),` → `B →`

##### `de_morgan_rewrite` — connective, inferred truth: **true**

```lean
∀ {X : Type u_1} [inst : PseudoEMetricSpace X] {A B : Set X} {ε : NNReal}, ¬A ⊆ B ∨
    Metric.coveringNumber ε A ≤ Metric.coveringNumber (ε / 2) B
```

Change: `_} [PseudoEMetricSpace` → `u_1} [inst : PseudoEMetricSpace`; `NNReal} (h : A` → `NNReal}, ¬A`; `B),` → `B ∨`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {X : Type _} [EMetricSpace X] {A B : Set X} {ε : NNReal} (h : A ⊆ B), Metric.coveringNumber ε
    A ≤ Metric.coveringNumber (ε / 2) B
```

Change: `[PseudoEMetricSpace` → `[EMetricSpace`

##### `flip_bound` — bounds, inferred truth: **unknown**

```lean
∀ {X : Type _} [PseudoEMetricSpace X] {A B : Set X} {ε : NNReal} (h : A ⊆ B),
    Metric.coveringNumber ε A ≥ Metric.coveringNumber (ε / 2) B
```

Change: `≤` → `≥`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (X : Type _) [PseudoEMetricSpace X] {A B : Set X} {ε : NNReal} (h : A ⊆ B),
    Metric.coveringNumber ε A ≤ Metric.coveringNumber (ε / 2) B
```

Change: `{X` → `(X`; `_}` → `_)`

##### `strictness_swap` — relation, inferred truth: **unknown**

```lean
∀ {X : Type _} [PseudoEMetricSpace X] {A B : Set X} {ε : NNReal} (h : A ⊆ B),
    Metric.coveringNumber ε A < Metric.coveringNumber (ε / 2) B
```

Change: `≤` → `<`

##### `const_to_zero_one` — relation, inferred truth: **unknown**

```lean
∀ {X : Type _} [PseudoEMetricSpace X] {A B : Set X} {ε : NNReal} (h : A ⊆ B),
    Metric.coveringNumber ε A ≤ Metric.coveringNumber (ε / 0) B
```

Change: `2)` → `0)`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {A B : Set ℕ} {ε : NNReal} (h : A ⊆ B), Metric.coveringNumber ε A ≤ Metric.coveringNumber (ε /
    2) B
```

Change: removed `{X : Type _} [PseudoEMetricSpace X]`; `X}` → `ℕ}`

#### Did not fire (19)

| Perturbation | Outcome | Why |
|---|---|---|
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 7. `MeasureTheory.IsProjectiveMeasureFamily`

- **Module** — `Mathlib.MeasureTheory.Constructions.Projective`
- **CSV rows** — draft1-fi-052 (sheet row 53)
- **Kind** — definition (conclusion is data/a type, not a proposition)
- **Anchor elaborates** — yes
- **Cost** — 17 Lean calls, 119.4s

**Original signature (as it appears in the sheet):**

```lean
MeasureTheory.IsProjectiveMeasureFamily.{u_1, u_2} {ι : Type u_1} {α : ι → Type u_2} [(i : ι) → MeasurableSpace (α i)]
  (P : (J : Finset ι) → MeasureTheory.Measure ((j : ↥J) → α ↑j)) : Prop
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {ι : Type _} {α : ι → Type _} [(i : ι) → MeasurableSpace (α i)] (P : (J : Finset ι) →
    MeasureTheory.Measure ((j : ↥J) → α ↑j)), Prop
```

#### Variants produced (1/28)

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (ι : Type _) {α : ι → Type _} [(i : ι) → MeasurableSpace (α i)] (P : (J : Finset ι) →
    MeasureTheory.Measure ((j : ↥J) → α ↑j)), Prop
```

Change: `{ι` → `(ι`; `_}` → `_)`

#### Did not fire (27)

| Perturbation | Outcome | Why |
|---|---|---|
| `negate` | tactic failed | tactic 'negate_state' ran but extract_goal produced nothing |
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | tactic failed | tactic 'drop_unused_hyp' ran but extract_goal produced nothing |
| `de_morgan_rewrite` | tactic failed | tactic 'de_morgan_rewrite' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_hyp` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `specialize_type` | rejected | 5 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---

### 8. `MeasureTheory.Filtration`

- **Module** — `Mathlib.Probability.Process.Filtration`
- **CSV rows** — draft1-fi-073, draft1-fi-086 (sheet rows 74, 87)
- **Kind** — definition (conclusion is data/a type, not a proposition)
- **Anchor elaborates** — yes
- **Cost** — 16 Lean calls, 111.8s

**Original signature (as it appears in the sheet):**

```lean
MeasureTheory.Filtration.{u_1, u_2} {Ω : Type u_1} (ι : Type u_2) [Preorder ι] (m : MeasurableSpace Ω) :
  Type (max u_1 u_2)
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {Ω : Type _} (ι : Type _) [Preorder ι] (m : MeasurableSpace Ω), Type _
```

#### Variants produced (4/28)

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {Ω : Type _} (ι : Type _) [LE ι] (m : MeasurableSpace Ω), Type _
```

Change: `[Preorder` → `[LE`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {Ω : Type _} (ι : Type _) [PartialOrder ι] (m : MeasurableSpace Ω), Type _
```

Change: `[Preorder` → `[PartialOrder`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (Ω : Type _) (ι : Type _) [Preorder ι] (m : MeasurableSpace Ω), Type _
```

Change: `{Ω` → `(Ω`; `_}` → `_)`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ (ι : Type _) [Preorder ι] (m : MeasurableSpace ℕ), Type _
```

Change: removed `{Ω : Type _}`; `Ω),` → `ℕ),`

#### Did not fire (24)

| Perturbation | Outcome | Why |
|---|---|---|
| `negate` | tactic failed | tactic 'negate_state' ran but extract_goal produced nothing |
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | tactic failed | tactic 'drop_unused_hyp' ran but extract_goal produced nothing |
| `de_morgan_rewrite` | tactic failed | tactic 'de_morgan_rewrite' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |

---

### 9. `MeasureTheory.IsStoppingTime.measurableSpace`

- **Module** — `Mathlib.Probability.Process.Stopping`
- **CSV rows** — draft1-fi-082, draft1-fi-088 (sheet rows 83, 89)
- **Kind** — definition (conclusion is data/a type, not a proposition)
- **Anchor elaborates** — yes
- **Cost** — 19 Lean calls, 101.0s

**Original signature (as it appears in the sheet):**

```lean
MeasureTheory.IsStoppingTime.measurableSpace.{u_1, u_3} {Ω : Type u_1} {ι : Type u_3} {m : MeasurableSpace Ω}
  [Preorder ι] {f : MeasureTheory.Filtration ι m} {τ : Ω → WithTop ι} (hτ : MeasureTheory.IsStoppingTime f τ) :
  MeasurableSpace Ω
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {Ω : Type _} {ι : Type _} {m : MeasurableSpace Ω} [Preorder ι] {f : MeasureTheory.Filtration ι
    m} {τ : Ω → WithTop ι} (hτ : MeasureTheory.IsStoppingTime f τ), MeasurableSpace Ω
```

#### Variants produced (4/28)

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {Ω : Type _} {ι : Type _} {m : MeasurableSpace Ω} [PartialOrder ι] {f :
    MeasureTheory.Filtration ι m} {τ : Ω → WithTop ι} (hτ : MeasureTheory.IsStoppingTime f τ),
    MeasurableSpace Ω
```

Change: `[Preorder` → `[PartialOrder`

##### `tc_strengthen_conc` — typeclass, inferred truth: **unknown**

```lean
∀ {Ω : Type _} {ι : Type _} {m : MeasurableSpace Ω} [Preorder ι] {f : MeasureTheory.Filtration ι
    m} {τ : Ω → WithTop ι} (hτ : MeasureTheory.IsStoppingTime f τ), UpgradedStandardBorel Ω
```

Change: `MeasurableSpace` → `UpgradedStandardBorel`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (Ω : Type _) {ι : Type _} {m : MeasurableSpace Ω} [Preorder ι] {f : MeasureTheory.Filtration ι
    m} {τ : Ω → WithTop ι} (hτ : MeasureTheory.IsStoppingTime f τ), MeasurableSpace Ω
```

Change: `{Ω` → `(Ω`; `_}` → `_)`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ {ι : Type _} {m : MeasurableSpace ℕ} [Preorder ι] {f : MeasureTheory.Filtration ι m} {τ : ℕ →
    WithTop ι} (hτ : MeasureTheory.IsStoppingTime f τ), MeasurableSpace ℕ
```

Change: removed `{Ω : Type _}`; `Ω}` → `ℕ}`; `Ω` → `ℕ`; `Ω` → `ℕ`

#### Did not fire (24)

| Perturbation | Outcome | Why |
|---|---|---|
| `negate` | tactic failed | tactic 'negate_state' ran but extract_goal produced nothing |
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | tactic failed | tactic 'drop_unused_hyp' ran but extract_goal produced nothing |
| `de_morgan_rewrite` | tactic failed | tactic 'de_morgan_rewrite' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_weaken_hyp` | rejected | 2 candidate(s) proposed, all rejected by the Lean type-checker |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |

---

### 10. `Metric.coveringNumber`

- **Module** — `Mathlib.Topology.MetricSpace.CoveringNumbers`
- **CSV rows** — draft1-fi-092, draft1-fi-093 (sheet rows 93, 94)
- **Kind** — definition (conclusion is data/a type, not a proposition)
- **Anchor elaborates** — yes
- **Cost** — 15 Lean calls, 95.2s

**Original signature (as it appears in the sheet):**

```lean
Metric.coveringNumber.{u_1} {X : Type u_1} [PseudoEMetricSpace X] (ε : NNReal) (A : Set X) : ℕ∞
```

**Normalised anchor type (what the perturbations receive):**

```lean
∀ {X : Type _} [PseudoEMetricSpace X] (ε : NNReal) (A : Set X), ℕ∞
```

#### Variants produced (4/28)

##### `tc_weaken_hyp` — typeclass, inferred truth: **unknown**

```lean
∀ {X : Type _} [EDist X] (ε : NNReal) (A : Set X), ℕ∞
```

Change: `[PseudoEMetricSpace` → `[EDist`

##### `tc_strengthen_hyp` — typeclass, inferred truth: **true**

```lean
∀ {X : Type _} [EMetricSpace X] (ε : NNReal) (A : Set X), ℕ∞
```

Change: `[PseudoEMetricSpace` → `[EMetricSpace`

##### `implicit_explicit_toggle` — structure, inferred truth: **true**

```lean
∀ (X : Type _) [PseudoEMetricSpace X] (ε : NNReal) (A : Set X), ℕ∞
```

Change: `{X` → `(X`; `_}` → `_)`

##### `specialize_type` — typeclass, inferred truth: **true**

```lean
∀ (ε : NNReal) (A : Set ℕ), ℕ∞
```

Change: removed `{X : Type _} [PseudoEMetricSpace X]`; `X),` → `ℕ),`

#### Did not fire (24)

| Perturbation | Outcome | Why |
|---|---|---|
| `negate` | tactic failed | tactic 'negate_state' ran but extract_goal produced nothing |
| `contrapose` | tactic failed | tactic 'contrapositive' ran but extract_goal produced nothing |
| `converse` | tactic failed | tactic 'converse' ran but extract_goal produced nothing |
| `inverse` | tactic failed | tactic 'inverse' ran but extract_goal produced nothing |
| `drop_unused_hyp` | tactic failed | tactic 'drop_unused_hyp' ran but extract_goal produced nothing |
| `de_morgan_rewrite` | tactic failed | tactic 'de_morgan_rewrite' ran but extract_goal produced nothing |
| `quantifier_swap` | n/a | shape did not match; no Lean call made |
| `tc_strengthen_conc` | n/a | shape did not match; no Lean call made |
| `tc_weaken_conc` | n/a | shape did not match; no Lean call made |
| `flip_bound` | n/a | shape did not match; no Lean call made |
| `bound_tighter` | n/a | shape did not match; no Lean call made |
| `alpha_rename` | rejected | 1 candidate(s) proposed, all rejected by the Lean type-checker |
| `premise_permute` | n/a | shape did not match; no Lean call made |
| `curry` | tactic failed | tactic 'curry' ran but extract_goal produced nothing |
| `uncurry` | tactic failed | tactic 'uncurry' ran but extract_goal produced nothing |
| `definitional_unfold` | tactic failed | tactic 'unfold_defs' ran but extract_goal produced nothing |
| `strictness_swap` | n/a | shape did not match; no Lean call made |
| `eq_to_le` | n/a | shape did not match; no Lean call made |
| `connective_swap` | n/a | shape did not match; no Lean call made |
| `arith_op_swap` | n/a | shape did not match; no Lean call made |
| `const_to_zero_one` | n/a | shape did not match; no Lean call made |
| `forall_to_exists` | n/a | shape did not match; no Lean call made |
| `exists_to_forall` | n/a | shape did not match; no Lean call made |
| `tc_sibling_swap` | n/a | shape did not match; no Lean call made |

---
