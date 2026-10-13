"""
Chain runner — apply a sequence of perturbations to a single theorem.

``apply_chain`` is the per-anchor primitive used by both the demo runner and
the corpus pipeline. It feeds the output of step *i* into step *i+1*, stops
cleanly when a step returns ``None`` or when the output equals the input
(no-op), and produces a single JSONL-shaped record describing the result.

The chain runner also handles two practical wrinkles:

  1. Some transforms (``negate``, ``contrapose``, …) emit a Lean-extracted
     theorem string like ``theorem foo.extracted_1_1 {x : N} : body := …``,
     which must be parsed back into ``(binders, body, type_str)`` before the
     next transform sees it. ``parse_extracted_lean`` does that.

  2. The "current statement" used to drive the next transform should be a
     clean ``∀-type`` string, not a Lean theorem header.
     ``normalize_statement`` strips that down.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from wiggle.lean_runner import compile_lean
from wiggle.propagation import compose_truth
from wiggle.registry import ANCHOR_TRUTH, PERTURBATIONS, TRANSFORMS, TruthValue

__all__ = ["apply_chain", "parse_extracted_lean", "normalize_statement"]


# ── Helpers ──────────────────────────────────────────────────────────────────-

_PERTURBATION_DESCRIPTIONS: dict[str, str] = {p.name: p.description for p in PERTURBATIONS}
_PROPAGATION: dict[str, dict[TruthValue, TruthValue]] = {
    p.name: p.propagation for p in PERTURBATIONS
}


def normalize_statement(stmt: str) -> str:
    """Strip a leading "theorem <name>" header if present, leaving the type.

    Inputs we see in practice:

      * ``theorem wiggle_demo.extracted_1_1 {i j : N} : body := sorry``
      * ``∀ {α : Type*} [inst : AddCommMonoid α] (a b : α), a + b = b + a``

    We only normalise the first case.
    """
    s = stmt.strip()
    m = re.match(r"^theorem\s+\S+\s*(.*?)(?:\s*:=.*)?$", s, re.DOTALL)
    if m is None:
        return s
    rest = m.group(1).strip()
    # Walk for the first top-level ':' (not '::').
    depth = 0
    i = 0
    while i < len(rest):
        c = rest[i]
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth = max(0, depth - 1)
        elif c == ":" and depth == 0:
            if i + 1 < len(rest) and rest[i + 1] == ":":
                i += 2
                continue
            binders = rest[:i].strip()
            body = rest[i + 1 :].strip()
            return f"∀ {binders}, {body}" if binders else body
        i += 1
    return rest


def parse_extracted_lean(extracted: str) -> dict[str, str] | None:
    """Decompose a Lean-extracted theorem string into ``binders / body / type_str``.

    Returns ``None`` if the string doesn't have the expected
    ``theorem … := …`` shape; the caller should then fall back to treating
    the string as a plain type with no binders.
    """
    m = re.match(r"^(theorem\s+\S+.*?)\s*:=", extracted, re.DOTALL)
    if m is None:
        return None
    before_assign = m.group(1)
    m2 = re.match(r"^theorem\s+\S+\s*(.*)", before_assign, re.DOTALL)
    if m2 is None:
        return None
    sig_part = m2.group(1).strip()

    depth = 0
    i = 0
    colon_pos = -1
    while i < len(sig_part):
        c = sig_part[i]
        if c in "({[":
            depth += 1
        elif c in ")}]":
            depth = max(0, depth - 1)
        elif c == ":" and depth == 0:
            if i + 1 < len(sig_part) and sig_part[i + 1] == ":":
                i += 2
                continue
            colon_pos = i
            break
        i += 1

    if colon_pos == -1:
        binders, body = "", sig_part
    else:
        binders = sig_part[:colon_pos].strip()
        body = sig_part[colon_pos + 1 :].strip()

    type_str = f"∀ {binders}, {body}" if binders else body
    return {"binders": binders, "body": body, "type_str": type_str}


# ── Public API ───────────────────────────────────────────────────────────────-

ChainStatus = str
"""One of: ``"ok"``, ``"chain_broken"``, ``"compile_failed"``, ``"noop"``."""


def apply_chain(
    theorem: dict[str, Any],
    perturbation_names: list[str],
    *,
    anchor_truth: TruthValue = ANCHOR_TRUTH,
    verify_compile: bool = False,
) -> dict[str, Any]:
    """Apply ``perturbation_names`` in order to ``theorem``.

    Args:
        theorem: dict with at least ``id``, ``body``, ``type_str``; the chain
            runner passes ``id`` through unchanged and uses ``type_str`` as the
            input to each transform.
        perturbation_names: list of registry names. Unknown names raise
            ``ValueError`` at the start of the chain (fail fast).
        anchor_truth: starting truth label. Default ``"true"`` (Mathlib).
        verify_compile: if ``True``, run ``compile_lean`` after each step.
            Off by default because typeclass / bounds wrappers already
            validate; turn on for tactic chains driven by unfamiliar tactics.

    Returns:
        A JSONL-shaped record:

            {
                "source_id":                 …,
                "original_statement":        …,
                "original_type_str":         …,
                "perturbations_applied":     [...],
                "perturbed_statement":       ... | None,
                "is_true":                   "true"|"false"|"unknown"|"chain_broken",
                "perturbation_description":  "step1 -> step2 -> ...",
                "timestamp":                 iso-utc,
                "chain_status":              "ok"|"chain_broken"|"compile_failed"|"noop",
            }
    """
    for name in perturbation_names:
        if name not in TRANSFORMS:
            raise ValueError(f"Unknown perturbation: {name!r}")

    current = dict(theorem)
    is_true_acc: TruthValue = anchor_truth

    def _record(
        applied_so_far: list[str],
        stmt: str | None,
        truth: TruthValue | str,
        status: ChainStatus,
    ) -> dict[str, Any]:
        return {
            "source_id": theorem["id"],
            "original_statement": theorem["body"],
            "original_type_str": theorem["type_str"],
            "perturbations_applied": applied_so_far,
            "perturbed_statement": stmt,
            "is_true": truth,
            "perturbation_description": " -> ".join(applied_so_far) if applied_so_far else "",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "chain_status": status,
        }

    for step_i, name in enumerate(perturbation_names):
        fn = TRANSFORMS[name]
        result = fn(current.get("id", ""), current["type_str"])

        if result is None:
            return _record(
                perturbation_names[: step_i + 1],
                stmt=None,
                truth="chain_broken",
                status="chain_broken",
            )

        _, variant_type = result

        if variant_type.strip() == current["type_str"].strip():
            return _record(
                perturbation_names[: step_i + 1],
                stmt=None,
                truth="chain_broken",
                status="noop",
            )

        if verify_compile and not compile_lean("", variant_type):
            return _record(
                perturbation_names[: step_i + 1],
                stmt=None,
                truth="chain_broken",
                status="compile_failed",
            )

        # Update current to reflect the perturbed statement. Tactic transforms
        # produce a Lean-extracted theorem header; typeclass / bounds / quantifier
        # transforms produce a clean ∀-type. Parse-or-fall-back.
        parsed = parse_extracted_lean(variant_type)
        if parsed:
            current = {**theorem, **parsed}
        else:
            clean = normalize_statement(variant_type)
            current = {**theorem, "body": clean, "type_str": clean, "binders": ""}

        rules = _PROPAGATION[name]
        step_out: TruthValue = rules[is_true_acc] if is_true_acc in rules else "unknown"
        is_true_acc = compose_truth(is_true_acc, step_out)

    return _record(
        perturbation_names,
        stmt=normalize_statement(current["body"]),
        truth=is_true_acc,
        status="ok",
    )
