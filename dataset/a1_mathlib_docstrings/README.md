# A1 — Mathlib theorem/docstring pairs

`a1_kept_concepts_v4.19.0.jsonl` — 18,747 Lean declarations from Mathlib paired
with their human-written Mathlib docstrings.

| | |
|---|---|
| Rows | 18,747 (one JSON object per line) |
| Unique `concept_id` | 18,747 (no duplicates) |
| Modules | 3,099, all under `Mathlib.*` |
| Declaration kinds | 14,794 `theorem`, 3,953 `lemma` |
| Source | Mathlib **v4.19.0**, commit `c44e0c8ee63ca166450922a373c7409c5d26b00b` |
| Size | 15 MB |
| sha256 | `da823e1476c4b1b6dee9ba1efeaa320768ab5605f2b61796001828dc917345d3` |

```bash
sha256sum a1_kept_concepts_v4.19.0.jsonl
```

## Schema

Matches the trainer's concept schema, so it can be passed directly to
`finetune/train_qwen_mnrl_multiview_v3_tg.py`.

```json
{
  "concept_id": "DualNumber.commute_eps_left",
  "views": {
    "nl_informal": "`ε` commutes with every element of the algebra.",
    "lean_signature": "theorem DualNumber.commute_eps_left [Semiring R] (x : DualNumber R) : Commute ε x"
  },
  "hard_negatives": { "nl": [], "lean": [] },
  "metadata": {
    "kind": "theorem",
    "module_name": "Mathlib.Algebra.DualNumber",
    "source": "A1_mathlib_docstring",
    "mathlib_tag": "v4.19.0",
    "mathlib_commit": "c44e0c8ee63ca166450922a373c7409c5d26b00b",
    "github_url": "https://github.com/leanprover-community/mathlib4/blob/v4.19.0/Mathlib/Algebra/DualNumber.lean#L87",
    "is_private": false,
    "doc_slip_flag": false,
    "filter_label": "KEEP"
  }
}
```

Every record carries exactly two views (one NL, one Lean). `hard_negatives` is
present but empty for all records.

## Relationship to `MathlibViews.jsonl`

The main training set (`MathlibViews.jsonl`, 133,621 rows / 126,059 unique
concepts) is **not in this repo** — it lives on Hugging Face at
`uw-math-ai/Math2Vec-embedding-dataset`. A1 overlaps it heavily:

| | Count | Share |
|---|---|---|
| A1 concepts already in `MathlibViews.jsonl` | 14,501 | 77.4% |
| A1 concepts new to it | 4,246 | 22.6% |

For the 14,501 overlapping concepts, **A1's docstring is not a restatement of
the NL already present**: 0 are byte-identical, median text similarity is 0.129,
and the near-duplicate share is 0.1%. The two sources write in different
registers — the base data in verbose LaTeX prose, A1 in terse Mathlib prose
using Lean notation:

> **Base:** *Let $E$ be a vector space over an ordered scalar field
> $\mathbb{K}$, and let $s \subseteq E$ be a convex set...*
>
> **A1:** *If `x ∈ closure s` and `y ∈ interior s`, then the segment `(x, y]` is
> included in `interior s`.*

Measure this yourself with `finetune/a1_docstrings/overlap_text.py`.

## What it is good for

Fine-tuning measurably improves retrieval from **docstring-style** queries
(+0.0769 Recall@1, 4.3 sigma) at a small cost on base-register queries
(−0.0087). A model trained only on `MathlibViews.jsonl` is 27.6 Recall@1 points
worse when asked in Mathlib's own register; A1 closes 31% of that gap.

Full results: [`experiments/a1_mathlib_docstrings/README.md`](../../experiments/a1_mathlib_docstrings/README.md).

## Known caveats

- Some docstrings **name** a theorem rather than state it, e.g.
  `MeasureTheory.condExp_mul_of_stronglyMeasurable_left` → *"Pull-out property
  of the conditional expectation."* These are weak training signal. The
  `filter_label` and `doc_slip_flag` fields suggest earlier filtering, but the
  surviving set has not been audited for this.
- `hard_negatives` is empty throughout; none have been mined.
- Only `nl_informal` and `lean_signature` views are present — no `lean_type` or
  `nl_informal_2`.

## Usage

`finetune/a1_docstrings/setup_login.sh` stages this file into a training
workspace and verifies its checksum. To use it directly:

```bash
python finetune/train_qwen_mnrl_multiview_v3_tg.py \
  --local_jsonl data/MathlibViews.jsonl \
  --extra_train_jsonl dataset/a1_mathlib_docstrings/a1_kept_concepts_v4.19.0.jsonl \
  ...
```

`--extra_train_jsonl` adds the file to **training only**, after the train/dev
split, dropping any record that would leak into dev.
