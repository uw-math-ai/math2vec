"""
Bound-mutation perturbations.

Thin wrappers around ``src/bounds.py`` so the public registry can refer to
them with the canonical ``flip_bound`` / ``bound_tighter`` names.

These are pure regex substitution on the type string; they do not invoke Lean.
The chain runner will subsequently call ``compile_lean`` on the result as part
of its normal flow.
"""

from __future__ import annotations

from bounds import flip_bound as _flip_bound_impl
from bounds import perturb_bound as _bound_tighter_impl

__all__ = ["flip_bound", "bound_tighter"]


def flip_bound(sig: str, type_str: str) -> tuple[str, str] | None:
    """Flip the first inequality direction (``<`` ↔ ``>``, ``≤`` ↔ ``≥``)."""
    return _flip_bound_impl(sig, type_str)


def bound_tighter(sig: str, type_str: str) -> tuple[str, str] | None:
    """Tighten the first numeric bound by ±1 in the tighter direction."""
    return _bound_tighter_impl(sig, type_str)
