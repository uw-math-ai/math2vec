"""
Perturbation transforms, grouped by layer.

Each transform is a callable ``(sig: str, type_str: str) -> tuple[str, str] | None``.
``None`` means "the transform does not apply to this statement"; the chain
runner treats that as a clean stop.

Modules:

  - ``logical``     – tactic-driven: negate, contrapose, converse, inverse,
                      drop_unused_hyp.
  - ``connectives`` – tactic-driven: de_morgan_rewrite.
  - ``quantifiers`` – Python text substitution + Lean validity oracle:
                      quantifier_swap.
  - ``typeclass``   – Python wrappers around ``src/typeclass_mutate.py``:
                      tc_weaken_hyp, tc_strengthen_hyp, tc_strengthen_conc,
                      tc_weaken_conc.
  - ``bounds``      – Python wrappers around ``src/bounds.py``: flip_bound,
                      bound_tighter.

Importing this package eagerly imports every submodule so the registry sees
every transform.
"""

from wiggle.transforms import bounds, connectives, logical, quantifiers, typeclass

__all__ = ["bounds", "connectives", "logical", "quantifiers", "typeclass"]
