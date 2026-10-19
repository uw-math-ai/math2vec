"""
Truth-value propagation through a perturbation path.

We never re-prove anything in Lean to determine truth — instead, every
perturbation declares (in the registry) how it maps anchor truth to variant
truth. ``is_true`` composes those rules across an arbitrary path; the chain
runner applies the same per-step rules. ``compose_truth`` is a separate
heuristic for merging two independently-derived labels.

Truth lattice (string-encoded for JSONL friendliness):

    "true"     – provable
    "false"    – disproved (negation of a known-true theorem, etc.)
    "unknown"  – under-specified by this propagation alone
"""

from __future__ import annotations

from typing import Iterable

from wiggle.registry import ANCHOR_TRUTH, PROPAGATION_RULES, TruthValue

__all__ = ["is_true", "compose_truth"]


# ── Single-step propagation ──────────────────────────────────────────────────-
def _step(perturbation: str, current: TruthValue) -> TruthValue:
    """Apply one perturbation to a current truth value."""
    rules = PROPAGATION_RULES.get(perturbation)
    if rules is None:
        # Unknown perturbation name — degrade gracefully rather than crash.
        # The chain runner is responsible for validation; this is the safety
        # net that keeps `is_true` total.
        return "unknown"
    return rules[current]


# ── Public API ───────────────────────────────────────────────────────────────-
def is_true(perturbation_path: Iterable[str], anchor_truth: TruthValue = ANCHOR_TRUTH) -> TruthValue:
    """Propagate truth symbolically through ``perturbation_path``.

    ``anchor_truth`` defaults to ``"true"`` because all anchors come from
    Mathlib. Override only if running on a corpus whose anchors have a
    different truth label.
    """
    current: TruthValue = anchor_truth
    for perturbation in perturbation_path:
        current = _step(perturbation, current)
    return current


def compose_truth(so_far: TruthValue, new_val: TruthValue) -> TruthValue:
    """Combine two independently-derived truth labels.

    Not for chains: a propagation rule's output already *is* the new label,
    so folding it into the previous label again double-counts (``negate``
    twice would come out ``false``). Chains go through ``is_true`` / the
    per-step rules directly.

    Composition rules:

      * ``true ∘ true == true``
      * ``false ∘ false == unknown``   ─ two false-labelled steps may cancel
        (e.g. ``negate ∘ negate`` recovers something close to the original).
      * Otherwise ``false`` dominates, then ``unknown`` dominates ``true``.
    """
    if so_far == "false" and new_val == "false":
        return "unknown"
    if so_far == "false" or new_val == "false":
        return "false"
    if so_far == "unknown" or new_val == "unknown":
        return "unknown"
    return "true"
