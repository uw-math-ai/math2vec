"""
Perturbation registry — single source of truth.

Every perturbation has a unique ``name`` and exactly one ``Perturbation``
entry. The implementation callable, the truth-propagation rules, the human
description, and the layer tag all travel together. Other modules consume
this list via ``TRANSFORMS`` and ``PROPAGATION_RULES`` (dict views over the
list) — they should never define their own copies.

Adding a new perturbation requires exactly two things:

  1. A function in ``wiggle.transforms.<layer>`` with the standard signature
     ``(sig: str, type_str: str) -> tuple[str, str] | None``.
  2. One ``Perturbation(...)`` entry below.

The module-level assertion guarantees ``TRANSFORMS`` and ``PROPAGATION_RULES``
have identical key sets and that every entry has a complete propagation
table.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from wiggle.transforms import (
    bounds,
    connectives,
    logical,
    quantifiers,
    relations,
    structure,
    typeclass,
)

__all__ = [
    "Perturbation",
    "PERTURBATIONS",
    "TRANSFORMS",
    "PROPAGATION_RULES",
    "ANCHOR_TRUTH",
    "TruthValue",
    "SemanticClass",
    "SEMANTIC_CLASSES",
    "SEMANTIC_DISTANCE",
    "semantic_class",
]


# ── Types ─────────────────────────────────────────────────────────────────────

TruthValue = Literal["true", "false", "unknown"]
"""Three-valued truth annotation. Stored as a string for JSONL friendliness."""

ANCHOR_TRUTH: TruthValue = "true"
"""All anchors come from Mathlib (proven theorems) so they start as ``true``."""

TransformFn = Callable[[str, str], "tuple[str, str] | None"]
"""Signature every transform must implement."""


@dataclass(frozen=True)
class Perturbation:
    """One perturbation, with everything anyone needs to use it."""

    name: str
    """Stable identifier — used in JSONL records and as the dict key."""

    fn: TransformFn
    """Transform callable; returns ``None`` to mean "does not apply"."""

    propagation: dict[TruthValue, TruthValue]
    """How ``is_true`` evolves: ``{anchor_truth: variant_truth}``."""

    description: str
    """One-line human description."""

    layer: Literal[
        "logical", "connective", "quantifier", "typeclass", "bounds",
        "structure", "relation",
    ]
    """Family of the perturbation, for grouping in reports."""


# ── The canonical list ────────────────────────────────────────────────────────
# Order is meaningful: it determines the order of demo output. Group by layer.

PERTURBATIONS: list[Perturbation] = [
    # ── Layer 1: logical structure (Lean tactics) ────────────────────────────
    Perturbation(
        name="negate",
        fn=logical.negate,
        propagation={"true": "false", "false": "true", "unknown": "unknown"},
        description="Negate the full statement (¬P). Always False from a True anchor.",
        layer="logical",
    ),
    Perturbation(
        name="contrapose",
        fn=logical.contrapose,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description="Contrapositive (¬Q → ¬P). Logically equivalent, True.",
        layer="logical",
    ),
    Perturbation(
        name="converse",
        fn=logical.converse,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Converse (Q → P). Truth unknown.",
        layer="logical",
    ),
    Perturbation(
        name="inverse",
        fn=logical.inverse,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Inverse (¬P → ¬Q). Equivalent to converse, not to original.",
        layer="logical",
    ),
    Perturbation(
        name="drop_unused_hyp",
        fn=logical.drop_unused_hyp,
        propagation={"true": "true", "false": "unknown", "unknown": "unknown"},
        description="Strip Prop-valued hypotheses not used by the goal. True.",
        layer="logical",
    ),
    # ── Layer 2: connective rewriting (Lean tactics) ─────────────────────────
    Perturbation(
        name="de_morgan_rewrite",
        fn=connectives.de_morgan_rewrite,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description=(
            "Equivalence-preserving connective rewriting via simp only "
            "[not_and_or, not_or, not_forall, not_exists, imp_iff_not_or, "
            "and_imp, not_not]."
        ),
        layer="connective",
    ),
    # ── Layer 3: quantifier scope (Python + Lean type-check) ─────────────────
    Perturbation(
        name="quantifier_swap",
        fn=quantifiers.quantifier_swap,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description=(
            "Swap ∀x ∃y → ∃y ∀x at the head of the statement. Strictly stronger "
            "claim; usually false."
        ),
        layer="quantifier",
    ),
    # ── Layer 4: typeclass mutations (Python + Lean type-check) ──────────────
    Perturbation(
        name="tc_weaken_hyp",
        fn=typeclass.tc_weaken_hyp,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description="Weaken typeclass in hypothesis (parent class). Unknown.",
        layer="typeclass",
    ),
    Perturbation(
        name="tc_strengthen_hyp",
        fn=typeclass.tc_strengthen_hyp,
        propagation={"true": "true", "false": "unknown", "unknown": "unknown"},
        description="Strengthen typeclass in hypothesis (child class). True.",
        layer="typeclass",
    ),
    Perturbation(
        name="tc_strengthen_conc",
        fn=typeclass.tc_strengthen_conc,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description="Strengthen typeclass in conclusion (child class). Unknown.",
        layer="typeclass",
    ),
    Perturbation(
        name="tc_weaken_conc",
        fn=typeclass.tc_weaken_conc,
        propagation={"true": "true", "false": "unknown", "unknown": "unknown"},
        description="Weaken typeclass in conclusion (parent class). True.",
        layer="typeclass",
    ),
    # ── Layer 5: bound mutations (regex) ─────────────────────────────────────
    Perturbation(
        name="flip_bound",
        fn=bounds.flip_bound,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Flip inequality direction (< ↔ >, ≤ ↔ ≥). Truth unknown.",
        layer="bounds",
    ),
    Perturbation(
        name="bound_tighter",
        fn=bounds.bound_tighter,
        propagation={"true": "unknown", "false": "false", "unknown": "unknown"},
        description="Tighten numeric bound by ±1 in the tighter direction. Unknown.",
        layer="bounds",
    ),
    # ── Layer 6: structural rewrites (equivalence-preserving positives) ───────
    Perturbation(
        name="alpha_rename",
        fn=structure.alpha_rename,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description="Rename bound variables to other idiomatic names. Equivalent.",
        layer="structure",
    ),
    Perturbation(
        name="premise_permute",
        fn=structure.premise_permute,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description="Swap the first two hypotheses (P → Q → R ↦ Q → P → R). Equivalent.",
        layer="structure",
    ),
    Perturbation(
        name="implicit_explicit_toggle",
        fn=structure.implicit_explicit_toggle,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description="Flip the first {x : T} binder to (x : T) or vice versa. Equivalent.",
        layer="structure",
    ),
    Perturbation(
        name="curry",
        fn=connectives.curry,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description="Rewrite (P ∧ Q) → R as P → Q → R via and_imp. Equivalent.",
        layer="connective",
    ),
    Perturbation(
        name="uncurry",
        fn=connectives.uncurry,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description="Rewrite P → Q → R as (P ∧ Q) → R via ← and_imp. Equivalent.",
        layer="connective",
    ),
    Perturbation(
        name="definitional_unfold",
        fn=connectives.definitional_unfold,
        propagation={"true": "true", "false": "false", "unknown": "unknown"},
        description=(
            "Unfold a common predicate to its definition (e.g. Function.Injective "
            "f → ∀ a b, f a = f b → a = b). Equivalent."
        ),
        layer="connective",
    ),
    # ── Layer 7: relation / operator mutations (graded hard negatives) ────────
    Perturbation(
        name="strictness_swap",
        fn=relations.strictness_swap,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Swap strict ↔ non-strict on the first inequality (< ↔ ≤). Unknown.",
        layer="relation",
    ),
    Perturbation(
        name="eq_to_le",
        fn=relations.eq_to_le,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Weaken the first equality a = b to a ≤ b. Unknown.",
        layer="relation",
    ),
    Perturbation(
        name="connective_swap",
        fn=relations.connective_swap,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Swap the first ∧ ↔ ∨. Unknown.",
        layer="relation",
    ),
    Perturbation(
        name="arith_op_swap",
        fn=relations.arith_op_swap,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Swap the first arithmetic operator (+ / - / *). Unknown.",
        layer="relation",
    ),
    Perturbation(
        name="const_to_zero_one",
        fn=relations.const_to_zero_one,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Mutate the first numeric literal (0 → 1, else → 0). Unknown.",
        layer="relation",
    ),
    # ── Layer 3 (extended): quantifier-kind flips ─────────────────────────────
    Perturbation(
        name="forall_to_exists",
        fn=quantifiers.forall_to_exists,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Weaken leading ∀ (x …) to ∃ (x …). Unknown.",
        layer="quantifier",
    ),
    Perturbation(
        name="exists_to_forall",
        fn=quantifiers.exists_to_forall,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Strengthen leading ∃ x to ∀ x. Unknown.",
        layer="quantifier",
    ),
    # ── Layer 4 (extended): type specialization + sibling swap ────────────────
    Perturbation(
        name="specialize_type",
        fn=typeclass.specialize_type,
        propagation={"true": "true", "false": "unknown", "unknown": "unknown"},
        description="Instantiate the first type variable with a concrete type (ℤ/ℝ/…). True.",
        layer="typeclass",
    ),
    Perturbation(
        name="tc_sibling_swap",
        fn=typeclass.tc_sibling_swap,
        propagation={"true": "unknown", "false": "unknown", "unknown": "unknown"},
        description="Replace a typeclass with an incomparable sibling. Unknown.",
        layer="typeclass",
    ),
]


# ── Dict views, derived from the canonical list ───────────────────────────────

TRANSFORMS: dict[str, TransformFn] = {p.name: p.fn for p in PERTURBATIONS}

PROPAGATION_RULES: dict[str, dict[TruthValue, TruthValue]] = {
    p.name: p.propagation for p in PERTURBATIONS
}


# ── Semantic class, read off the propagation table ────────────────────────────
# How logically far a variant is from its anchor. This is *derived*, not a
# second hand-maintained list: the propagation table already draws every
# distinction we need.
#
#   identity map          → the variant is interchangeable with the anchor
#                           under every anchor truth value, i.e. equivalent.
#   true↔false swap       → the variant contradicts the anchor.
#   true↦true, false↦?    → truth survives but falsity does not, so the
#                           variant is implied by the anchor without being
#                           equivalent to it (a strictly weaker or more
#                           special claim).
#   anything else         → the anchor's truth tells us nothing.

SemanticClass = Literal["equivalent", "entailed", "graded", "contradictory"]

_IDENTITY = {"true": "true", "false": "false", "unknown": "unknown"}
_SWAP = {"true": "false", "false": "true", "unknown": "unknown"}


def semantic_class(name: str) -> SemanticClass:
    """Classify how far a perturbation moves a statement logically."""
    rules = PROPAGATION_RULES.get(name)
    if rules is None:
        return "graded"
    if rules == _IDENTITY:
        return "equivalent"
    if rules == _SWAP:
        return "contradictory"
    if rules["true"] == "true":
        return "entailed"
    return "graded"


SEMANTIC_CLASSES: dict[str, SemanticClass] = {
    p.name: semantic_class(p.name) for p in PERTURBATIONS
}

SEMANTIC_DISTANCE: dict[SemanticClass, float] = {
    "equivalent": 0.0,
    "entailed": 0.34,
    "graded": 0.67,
    "contradictory": 1.0,
}
"""Ordinal logical distance, for plotting surface change against meaning change.

The spacing is nominal — these are ranks, not measured quantities. What the
axis has to support is the comparison "did the meaning move more or less than
the surface form did", and for that only the order matters.
"""


# ── Internal consistency (catches typos at import time) ───────────────────────

assert len({p.name for p in PERTURBATIONS}) == len(
    PERTURBATIONS
), "Duplicate perturbation names in PERTURBATIONS"

_TRUTH_KEYS = {"true", "false", "unknown"}
for _p in PERTURBATIONS:
    assert set(_p.propagation.keys()) == _TRUTH_KEYS, (
        f"Perturbation {_p.name!r} propagation must have keys "
        f"{_TRUTH_KEYS}; got {set(_p.propagation)}"
    )
    assert set(_p.propagation.values()) <= _TRUTH_KEYS, (
        f"Perturbation {_p.name!r} propagation has non-truth values: "
        f"{set(_p.propagation.values()) - _TRUTH_KEYS}"
    )

del _p
