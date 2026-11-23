"""
Relation / operator mutations — small surgical edits to a single relation,
connective, operator, or literal in the statement, validated by ``compile_lean``.

These are the "graded" family: the variant looks almost identical to the anchor
but means something different, so most are truth-``unknown`` and serve as fine
hard negatives. Because a single edit usually breaks type-checking, hit rates
are low by design — the compile oracle keeps only the well-formed ones.

All edits target **space-padded** binary operators (`` a + b ``, `` a ≤ b ``),
which is how Lean pretty-prints them. This avoids mangling tokens like
``Type*`` or ``u_1`` that contain an operator/digit without surrounding spaces.

  * ``strictness_swap``   — `` < `` ↔ `` ≤ ``, `` > `` ↔ `` ≥ `` (keep direction)
  * ``eq_to_le``          — `` = `` → `` ≤ ``
  * ``connective_swap``   — `` ∧ `` ↔ `` ∨ ``
  * ``arith_op_swap``     — `` + ``/`` - ``/`` * `` swapped for another
  * ``const_to_zero_one`` — first numeric literal → 0 (or 1 if it was 0)
"""

from __future__ import annotations

import re

from wiggle.lean_runner import compile_lean

__all__ = [
    "strictness_swap",
    "eq_to_le",
    "connective_swap",
    "arith_op_swap",
    "const_to_zero_one",
]


def _swap_first_op(type_str: str, mapping: dict[str, str]) -> str | None:
    """Replace the first occurrence (lowest index) of any key in ``mapping``."""
    best_idx = -1
    best_key = ""
    for key in mapping:
        idx = type_str.find(key)
        if idx != -1 and (best_idx == -1 or idx < best_idx):
            best_idx, best_key = idx, key
    if best_idx == -1:
        return None
    end = best_idx + len(best_key)
    return type_str[:best_idx] + mapping[best_key] + type_str[end:]


def _validated(sig: str, type_str: str, candidate: str | None) -> tuple[str, str] | None:
    if candidate is None or candidate.strip() == type_str.strip():
        return None
    if not compile_lean(sig, candidate):
        return None
    return sig, candidate


def strictness_swap(sig: str, type_str: str) -> tuple[str, str] | None:
    """Swap strict ↔ non-strict on the first inequality, preserving direction."""
    cand = _swap_first_op(type_str, {" < ": " ≤ ", " ≤ ": " < ", " > ": " ≥ ", " ≥ ": " > "})
    return _validated(sig, type_str, cand)


def eq_to_le(sig: str, type_str: str) -> tuple[str, str] | None:
    """Weaken the first equality ``a = b`` to ``a ≤ b``."""
    cand = _swap_first_op(type_str, {" = ": " ≤ "})
    return _validated(sig, type_str, cand)


def connective_swap(sig: str, type_str: str) -> tuple[str, str] | None:
    """Swap the first ``∧`` ↔ ``∨``."""
    cand = _swap_first_op(type_str, {" ∧ ": " ∨ ", " ∨ ": " ∧ "})
    return _validated(sig, type_str, cand)


def arith_op_swap(sig: str, type_str: str) -> tuple[str, str] | None:
    """Swap the first arithmetic operator (`` + ``→`` * ``, `` * ``→`` + ``, `` - ``→`` + ``)."""
    cand = _swap_first_op(type_str, {" + ": " * ", " * ": " + ", " - ": " + "})
    return _validated(sig, type_str, cand)


_LITERAL_RE = re.compile(r"(?<![\w])\d+(?![\w])")


def const_to_zero_one(sig: str, type_str: str) -> tuple[str, str] | None:
    """Mutate the first standalone numeric literal: ``0`` → ``1``, anything else → ``0``."""
    m = _LITERAL_RE.search(type_str)
    if m is None:
        return None
    new_val = "1" if m.group(0) == "0" else "0"
    cand = type_str[: m.start()] + new_val + type_str[m.end():]
    return _validated(sig, type_str, cand)
