"""
Typeclass-mutation perturbations.

Thin wrappers around ``src/typeclass_mutate.py``. The wrapper layer adds:

  * a uniform ``(sig, type_str) -> tuple[str, str] | None`` signature,
  * a no-op filter so the chain runner can stop cleanly when the typeclass
    substitution yielded the original statement back.

The actual hierarchy traversal and Lean type-check live in
``typeclass_mutate``; this module is just naming and adapters.

Names describe what happens to the TYPECLASS at that position; see
``Wiggle.lean`` / ``typeclass_mutate.py`` for the rationale.
"""

from __future__ import annotations

from typeclass_mutate import (
    sibling_typeclass,
    specialize_type as _specialize_type_impl,
    strengthen_conclusion_typeclass,
    strengthen_hypothesis_typeclass,
    weaken_conclusion_typeclass,
    weaken_hypothesis_typeclass,
)

__all__ = [
    "tc_weaken_hyp",
    "tc_strengthen_hyp",
    "tc_strengthen_conc",
    "tc_weaken_conc",
    "tc_sibling_swap",
    "specialize_type",
]


def _wrap(fn, sig: str, type_str: str) -> tuple[str, str] | None:
    result = fn(sig, type_str)
    if result is None:
        return None
    variant_sig, variant_type = result
    if (
        variant_sig.strip() == sig.strip()
        and variant_type.strip() == type_str.strip()
    ):
        return None
    return variant_sig, variant_type


def tc_weaken_hyp(sig: str, type_str: str) -> tuple[str, str] | None:
    """Replace a hypothesis typeclass with a WEAKER parent class."""
    return _wrap(weaken_hypothesis_typeclass, sig, type_str)


def tc_strengthen_hyp(sig: str, type_str: str) -> tuple[str, str] | None:
    """Replace a hypothesis typeclass with a STRONGER child class."""
    return _wrap(strengthen_hypothesis_typeclass, sig, type_str)


def tc_strengthen_conc(sig: str, type_str: str) -> tuple[str, str] | None:
    """Replace a conclusion typeclass with a STRONGER child class."""
    return _wrap(strengthen_conclusion_typeclass, sig, type_str)


def tc_weaken_conc(sig: str, type_str: str) -> tuple[str, str] | None:
    """Replace a conclusion typeclass with a WEAKER parent class."""
    return _wrap(weaken_conclusion_typeclass, sig, type_str)


def tc_sibling_swap(sig: str, type_str: str) -> tuple[str, str] | None:
    """Replace a typeclass with an incomparable SIBLING (shares a parent)."""
    return _wrap(sibling_typeclass, sig, type_str)


def specialize_type(sig: str, type_str: str) -> tuple[str, str] | None:
    """Instantiate the first type variable with a concrete type (ℕ/ℤ/ℚ/ℝ/ℂ)."""
    return _wrap(_specialize_type_impl, sig, type_str)
