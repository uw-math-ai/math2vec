# MEGenerator datasets

Lean-only data from the MEGenerator fine-tuning experiments (Qwen3-Embedding-8B,
`finetune/` multi-view recipe). Every statement here comes from Mathlib; none of
it is model-written text.

| File | Rows | What it is |
|---|---:|---|
| `formal_nobinders_train.jsonl` | 19,942 | Formal iff training set used by the `formal_nobinders` run, in the multi-view trainer's format. Each row pairs the two sides of a Mathlib iff as `lean_signature` / `lean_type`, with binders left out of the views (they are kept in `metadata.lean_binders`). NL views are empty. Sources: 12,750 kernel-verified wide20k pairs (`megen-formal:`), 4,205 from `iff_scrape/chained_iffs.jsonl` (`labchained:`), 2,987 from `iff_scrape/direct_iffs.jsonl` (`labdirect:`). Evaluation modules, trainer dev modules and duplicates are removed. |
| `implies_pairs.jsonl` | 20,129 | One-way implications `A → B` from Mathlib theorems, each kernel-verified (`formal.kernel_verified`, `formal.proof_term`). Used for the implication retrieval task. Summary by field in `implies_report.json`. |
| `equiv_vs_imp.jsonl` | 738 | Equivalent-vs-implied benchmark: for each premise, Mathlib statements that are equivalent to it and statements it only implies. A model passes an item when it ranks the equivalents above the implied ones. `equivalent_held_out` lists the equivalents whose iff pair was held out of training; the 142 premises with a non-empty list form the held-out subset. |
| `equiv_vs_imp_checked.jsonl` | 532 | The same benchmark with ambiguous implied statements removed (an implied statement that is arguably also equivalent under the binders). Removals are listed in `implied_dropped`; 113 premises are in the held-out subset. The filtering used an LLM judgment, but every statement is still verbatim Mathlib. |

Training runs exclude modules chosen by `is_eval_module(module, 0.2, seed=0)`,
so results on held-out premises are the ones to compare.
