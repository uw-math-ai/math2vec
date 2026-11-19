# Certified labels

Rows: perturbation (structural class). Columns: what Lean automation proved
about each applied variant against its anchor.

| perturbation | structural | equivalent | entailed | stronger | contradictory | unverified | n |
|---|---|---:|---:|---:|---:|---:|---:|
| negate | contradictory | 0 | 0 | 0 | 273 | 51 | 324 |
| specialize_type | entailed | 0 | 12 | 0 | 0 | 1 | 13 |
| tc_strengthen_hyp | entailed | 0 | 5 | 0 | 0 | 3 | 8 |
| tc_weaken_conc | entailed | 0 | 0 | 0 | 0 | 2 | 2 |
| contrapose | equivalent | 166 | 19 | 0 | 0 | 56 | 241 |
| curry | equivalent | 6 | 0 | 0 | 0 | 0 | 6 |
| de_morgan_rewrite | equivalent | 172 | 19 | 0 | 0 | 56 | 247 |
| definitional_unfold | equivalent | 6 | 1 | 0 | 0 | 0 | 7 |
| implicit_explicit_toggle | equivalent | 243 | 37 | 0 | 0 | 3 | 283 |
| premise_permute | equivalent | 110 | 9 | 0 | 0 | 2 | 121 |
| uncurry | equivalent | 116 | 15 | 0 | 0 | 43 | 174 |
| arith_op_swap | graded | 0 | 2 | 12 | 0 | 196 | 210 |
| bound_tighter | graded | 2 | 12 | 3 | 0 | 117 | 134 |
| connective_swap | graded | 1 | 11 | 6 | 0 | 28 | 46 |
| const_to_zero_one | graded | 10 | 35 | 13 | 5 | 212 | 275 |
| converse | graded | 2 | 4 | 12 | 7 | 216 | 241 |
| drop_hypothesis | graded | 6 | 10 | 193 | 6 | 26 | 241 |
| eq_to_le | graded | 8 | 55 | 6 | 0 | 21 | 90 |
| exists_to_forall | graded | 0 | 0 | 1 | 0 | 5 | 6 |
| flip_bound | graded | 0 | 31 | 3 | 1 | 178 | 213 |
| forall_to_exists | graded | 5 | 134 | 0 | 0 | 39 | 178 |
| inverse | graded | 0 | 7 | 0 | 7 | 227 | 241 |
| quantifier_swap | graded | 0 | 0 | 0 | 0 | 1 | 1 |
| strictness_swap | graded | 10 | 24 | 25 | 5 | 150 | 214 |
| tc_sibling_swap | graded | 0 | 1 | 1 | 0 | 3 | 5 |
| tc_strengthen_conc | graded | 0 | 0 | 0 | 0 | 1 | 1 |
| tc_weaken_hyp | graded | 0 | 1 | 2 | 0 | 2 | 5 |

Final labels used by the eval: contradictory 355, entailed 350, equivalent 863, graded 1699, unverified 260
