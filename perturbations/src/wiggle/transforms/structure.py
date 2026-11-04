"""
Structural perturbations — equivalence-preserving rewrites of the *shape* of a
statement that leave its meaning untouched. These are "positive" pairs for
contrastive embedder training: same proposition, different surface syntax.

Both are pure Python text edits validated by ``compile_lean`` (the same
validity-oracle pattern as ``quantifier_swap`` / ``typeclass_mutate``):

  * ``premise_permute``         — reorder two hypotheses (arrow antecedents).
  * ``implicit_explicit_toggle``— flip the first ``{x : T}`` binder to ``(x : T)``
                                  (or vice versa).
"""

from __future__ import annotations

from wiggle.lean_runner import compile_lean

__all__ = ["premise_permute", "implicit_explicit_toggle"]


# ── shared bracket-aware scanners ──────────────────────────────────────────────
def _find_top_level(s: str, targets: str, start: int = 0) -> int:
    """Index of the first char in ``targets`` at bracket depth 0, else -1."""
    depth = 0
    i = start
    while i < len(s):
        c = s[i]
        if c in "({[⦃":
            depth += 1
        elif c in ")}]⦄":
            depth = max(0, depth - 1)
        elif depth == 0 and c in targets:
            return i
        i += 1
    return -1


def _split_top_level_arrows(s: str) -> list[str]:
    """Split ``s`` on top-level ``→`` into [antecedent, ..., conclusion]."""
    parts: list[str] = []
    depth = 0
    start = 0
    for i, c in enumerate(s):
        if c in "({[⦃":
            depth += 1
        elif c in ")}]⦄":
            depth = max(0, depth - 1)
        elif depth == 0 and c == "→":
            parts.append(s[start:i])
            start = i + 1
    parts.append(s[start:])
    return parts


def _leading_binders(type_str: str) -> tuple[str, str] | None:
    """Split ``∀ <binders>, <body>`` into ``(binders, body)``; None if not ∀-form."""
    s = type_str.lstrip()
    if not s.startswith("∀"):
        return None
    after = s[len("∀"):]
    comma = _find_top_level(after, ",")
    if comma == -1:
        return None
    return after[:comma].strip(), after[comma + 1:].strip()


# ── perturbations ───────────────────────────────────────────────────────────────
def premise_permute(sig: str, type_str: str) -> tuple[str, str] | None:
    """Swap the first two hypotheses written as arrow antecedents.

    ``P → Q → R`` becomes ``Q → P → R``. Logically equivalent. Operates on the
    body's top-level arrow chain; needs at least two antecedents plus a
    conclusion. Returns ``None`` if there are fewer than two antecedents or the
    swap fails to type-check (e.g. a dependency between the hypotheses).
    """
    parsed = _leading_binders(type_str)
    prefix = ""
    body = type_str
    if parsed is not None:
        binders, body = parsed
        prefix = f"∀ {binders}, "

    segments = _split_top_level_arrows(body)
    if len(segments) < 3:  # need H1 → H2 → ... → C
        return None
    segments[0], segments[1] = segments[1], segments[0]
    new_body = "→".join(segments)
    out = f"{prefix}{new_body}"

    if out.strip() == type_str.strip():
        return None
    if not compile_lean(sig, out):
        return None
    return sig, out


def implicit_explicit_toggle(sig: str, type_str: str) -> tuple[str, str] | None:
    """Flip the first ``{x : T}`` binder to ``(x : T)``, or the first ``(x : T)``
    to ``{x : T}`` if no implicit binder is present.

    The proposition is unchanged (only binder visibility differs), so this is
    truth-preserving. Instance binders ``[..]`` are left alone. Returns ``None``
    if there is no eligible binder or the result fails to type-check.
    """
    parsed = _leading_binders(type_str)
    if parsed is None:
        return None
    binders, body = parsed

    def _swap_first(open_c: str, close_c: str, to_open: str, to_close: str) -> str | None:
        idx = binders.find(open_c)
        if idx == -1:
            return None
        depth = 0
        j = idx
        while j < len(binders):
            if binders[j] == open_c:
                depth += 1
            elif binders[j] == close_c:
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= len(binders):
            return None
        return binders[:idx] + to_open + binders[idx + 1:j] + to_close + binders[j + 1:]

    new_binders = _swap_first("{", "}", "(", ")")
    if new_binders is None:
        new_binders = _swap_first("(", ")", "{", "}")
    if new_binders is None:
        return None

    out = f"∀ {new_binders}, {body}"
    if out.strip() == type_str.strip():
        return None
    if not compile_lean(sig, out):
        return None
    return sig, out
