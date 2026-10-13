# Standalone re-elaboration check

49/49 variants elaborate on their own as `example : <variant> := by sorry`.

A variant that fails here was still produced by Lean, but is not a
self-contained statement — it depends on names bound in the context it
was extracted from. Those cannot go into a dataset as-is.

| Perturbation | Emitted | Standalone-valid | Broken |
|---|---|---|---|
| `alpha_rename` | 1 | 1 | **0** |
| `arith_op_swap` | 1 | 1 | **0** |
| `connective_swap` | 1 | 1 | **0** |
| `const_to_zero_one` | 2 | 2 | **0** |
| `de_morgan_rewrite` | 3 | 3 | **0** |
| `drop_unused_hyp` | 3 | 3 | **0** |
| `flip_bound` | 2 | 2 | **0** |
| `implicit_explicit_toggle` | 10 | 10 | **0** |
| `negate` | 3 | 3 | **0** |
| `specialize_type` | 9 | 9 | **0** |
| `strictness_swap` | 2 | 2 | **0** |
| `tc_sibling_swap` | 2 | 2 | **0** |
| `tc_strengthen_conc` | 1 | 1 | **0** |
| `tc_strengthen_hyp` | 5 | 5 | **0** |
| `tc_weaken_hyp` | 2 | 2 | **0** |
| `uncurry` | 2 | 2 | **0** |

## Broken variants

_None._