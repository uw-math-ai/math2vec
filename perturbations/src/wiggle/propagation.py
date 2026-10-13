"""
Truth-value propagation through a perturbation path.

We never re-prove anything in Lean to determine truth — instead, every
perturbation declares (in the registry) how it maps anchor truth to variant
truth. ``is_true`` composes those rules across an arbitrary path; ``compose_truth``
exposes the same logic on raw truth values for the chain runner.

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
    """Combine two truth labels at chain-application time.

    Used by ``apply_chain`` when accumulating the running truth across steps.
    Distinct from ``is_true``: ``compose_truth`` operates on already-evaluated
    truth values (e.g. when a step's propagation rule yielded ``"false"`` and
    you want to fold it into the running total), whereas ``is_true`` walks
    perturbation NAMES.

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
