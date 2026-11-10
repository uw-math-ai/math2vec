"""
Logical-structure perturbations.

Each function runs a Lean tactic defined in ``Wiggle.lean`` then uses
``extract_goal`` to read the rewritten statement back out.
"""

from __future__ import annotations

from wiggle.lean_runner import extract_goal

__all__ = [
    "negate",
    "contrapose",
    "converse",
    "inverse",
    "drop_hypothesis",
]


def negate(sig: str, type_str: str) -> tuple[str, str] | None:
    """Replace P with ¬P, push negations inwards (Aristotle-style)."""
    del sig
    return extract_goal("negate_state", type_str)


def contrapose(sig: str, type_str: str) -> tuple[str, str] | None:
    """Rewrite P → Q as ¬Q → ¬P (logically equivalent)."""
    del sig
    return extract_goal("contrapositive", type_str)


def converse(sig: str, type_str: str) -> tuple[str, str] | None:
    """Rewrite P → Q as Q → P (truth unknown)."""
    del sig
    return extract_goal("converse", type_str)


def inverse(sig: str, type_str: str) -> tuple[str, str] | None:
    """Rewrite P → Q as ¬P → ¬Q.

    Logically equivalent to the converse, never to the original. Completes
    the classical {original, contrapositive, converse, inverse} foursome.
    """
    del sig
    return extract_goal("inverse", type_str)


def drop_hypothesis(sig: str, type_str: str) -> tuple[str, str] | None:
    """Drop the last Prop hypothesis nothing else depends on.

    The result claims more than the anchor (same conclusion, fewer
    assumptions), so it implies the anchor but is often false.
    """
    del sig
    return extract_goal("drop_hypothesis", type_str)
