# archive/

Code and data that are **no longer part of the live pipeline** but kept for
reference / possible future use. Nothing here is imported by `src/`, `pipeline/`,
`scripts/`, or `tests/`.

## `instance_graph/` — Mathlib instance-graph builders

An earlier approach to deriving typeclass relationships by dumping Mathlib's
registered *instances* and turning them into implication edges. Superseded for
the hierarchy by `src/instance_graph/dump_class_hierarchy.py`, which dumps the
`extends` hierarchy directly into `data/class_hierarchy.jsonl` (what
`typeclass_mutate.py` now reads).

- `dump_mathlib_instances.py` — runs the `#wiggle_dump_instances` command in
  `Wiggle.lean` → `mathlib_instances.jsonl` (every registered instance).
- `build_instance_implications.py` — instances → `instance_implications.jsonl`
  (edges like `CommRing R → IsDomain (Polynomial R)`).
- `typeclass_implication_table.py` — Lean `#synth`-verified implication table
  built from the `mathlib-initiative/mathlib-types` dataset (never fully run).

These may still be useful as a source of **instance-level edges for richer
dataset labels**. The `#wiggle_dump_instances` elaborator they depend on is
still present in `Wiggle.lean`.

## `data/`

`mathlib_instances.jsonl` and `instance_implications.jsonl`, the outputs of the
scripts above. Gitignored (large, regenerable) — present locally only.
