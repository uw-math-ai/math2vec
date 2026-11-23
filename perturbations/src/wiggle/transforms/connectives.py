"""
Connective rewriting — equivalence-preserving transforms based on De Morgan
and curry/uncurry style identities.

The current set of contrastive-training positives is just ``contrapose``.
``de_morgan_rewrite`` is the first non-trivial second source: a single Lean
``simp only`` invocation across a fixed set of named identities. We treat the
whole bundle as one perturbation because the individual rewrites are usually
chained together by Lean automatically — splitting them at the Python layer
would just create artificial step boundaries.
"""

from __future__ import annotations

from wiggle.lean_runner import extract_goal

__all__ = ["de_morgan_rewrite", "curry", "uncurry", "definitional_unfold"]


def _rewrite_via(tactic: str, sig: str, type_str: str) -> tuple[str, str] | None:
    """Run a Lean ``tactic`` then ``extract_goal``; drop no-ops and failures.

    Shared by every equivalence-preserving tactic wrapper here. ``extract_goal``
    returns ``None`` when the tactic errors (e.g. ``simp only`` made no
    progress); we additionally treat an unchanged goal as a no-op so the chain
    runner sees a clean stop rather than a duplicate record.
    """
    result = extract_goal(tactic, type_str)
    if result is None:
        return None
    variant_sig, variant_type = result
    if variant_type.strip() == type_str.strip():
        return None
    return variant_sig, variant_type


def de_morgan_rewrite(sig: str, type_str: str) -> tuple[str, str] | None:
    """Apply De Morgan / connective rewrites to the statement.

    Logically equivalent to the original (truth-preserving). Lean tactic
    ``de_morgan_rewrite`` lives in ``Wiggle.lean``; see it for the lemma set.
    """
    return _rewrite_via("de_morgan_rewrite", sig, type_str)


def curry(sig: str, type_str: str) -> tuple[str, str] | None:
    """Rewrite a conjunctive hypothesis ``P ∧ Q → R`` as ``P → Q → R``.

    Equivalence-preserving. Fires only when an ``∧`` sits in hypothesis
    position (otherwise the underlying ``simp only [and_imp]`` makes no
    progress and we emit nothing). Tactic ``curry`` lives in ``Wiggle.lean``.
    """
    return _rewrite_via("curry", sig, type_str)


def uncurry(sig: str, type_str: str) -> tuple[str, str] | None:
    """Rewrite ``P → Q → R`` as ``(P ∧ Q) → R``. Equivalence-preserving.

    The common case for Mathlib statements, which are usually curried. Tactic
    ``uncurry`` lives in ``Wiggle.lean``.
    """
    return _rewrite_via("uncurry", sig, type_str)


def definitional_unfold(sig: str, type_str: str) -> tuple[str, str] | None:
    """Unfold a common Mathlib predicate to its definition.

    E.g. ``Function.Injective f`` → ``∀ a b, f a = f b → a = b``. Logically
    identical, syntactically very different — a strong positive pair. Fires
    only when one of the predicates in the ``unfold_defs`` lemma set (see
    ``Wiggle.lean``) appears in the statement.
    """
    return _rewrite_via("unfold_defs", sig, type_str)
