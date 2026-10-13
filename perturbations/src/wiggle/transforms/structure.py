"""
Structural perturbations — equivalence-preserving rewrites of the *shape* of a
statement that leave its meaning untouched. These are strong "positive" pairs
for contrastive embedder training: same proposition, different surface syntax.

All three are pure Python text edits validated by ``compile_lean`` (the same
validity-oracle pattern as ``quantifier_swap`` / ``typeclass_mutate``):

  * ``alpha_rename``            — rename bound variables to other idiomatic names.
  * ``premise_permute``         — reorder two hypotheses (arrow antecedents).
  * ``implicit_explicit_toggle``— flip the first ``{x : T}`` binder to ``(x : T)``
                                  (or vice versa).
"""

from __future__ import annotations

import re
import zlib

from wiggle.lean_runner import compile_lean

__all__ = ["alpha_rename", "premise_permute", "implicit_explicit_toggle"]


# Characters that may appear *inside* a Lean identifier. Used to build
# boundary-aware substitutions so renaming `a` never touches `a₀`, `Nat`, etc.
# `\w` (unicode) already covers ASCII + Greek letters + digits + underscore;
# we add primes and subscript ranges that `\w` misses.
_IDENT_EXTRA = r"'′-‷₀-₉ₐ-ₜᵢ-ᵪ"
_BEFORE = rf"(?<![\w{_IDENT_EXTRA}])"
_AFTER = rf"(?![\w{_IDENT_EXTRA}])"


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


# ── binder parsing ─────────────────────────────────────────────────────────────
_BINDER_GROUP_RE = re.compile(r"[({\[⦃]")


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


def _binder_groups(binders: str) -> list[tuple[str, list[str], str]]:
    """Split a binder block into ``(bracket, names, type_text)`` per group.

    For ``{α : Type*} (a b : α) [inst : Ring α]`` →
    ``[("{", ["α"], "Type*"), ("(", ["a", "b"], "α"), ("[", ["inst"], "Ring α")]``.
    Keeping the bracket and the declared type is what lets ``alpha_rename``
    pick a replacement of the right *kind* rather than one canonical name for
    everything.
    """
    groups: list[tuple[str, list[str], str]] = []
    i = 0
    n = len(binders)
    while i < n:
        c = binders[i]
        if c in "({[⦃":
            close = {"(": ")", "{": "}", "[": "]", "⦃": "⦄"}[c]
            depth = 0
            j = i
            while j < n:
                if binders[j] == c:
                    depth += 1
                elif binders[j] == close:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = binders[i + 1:j]
            colon = _find_top_level(inner, ":")
            head = inner[:colon] if colon != -1 else inner
            type_text = inner[colon + 1:].strip() if colon != -1 else ""
            names = [
                tok for tok in head.split()
                if tok != "_" and re.fullmatch(rf"[\w{_IDENT_EXTRA}]+", tok)
            ]
            if names:
                groups.append((c, names, type_text))
            i = j + 1
        else:
            i += 1
    return groups


# ── Mathlib-idiomatic replacement names ────────────────────────────────────────
# Renaming to `wv0`, `wv1`, … is out of distribution for Mathlib, so a model
# learns "`wv` marks a perturbed statement" instead of "renaming preserves
# meaning". Replacements are drawn per *kind* so the result still reads like
# something Mathlib would have written. Note this does not (and cannot) make
# the variant lexically closer to its anchor: identifiers are high-IDF tokens,
# so renaming them moves the statement a long way whatever the new names are.
# Each pool is stylistically homogeneous on purpose: variables declared in one
# group are filled from a consecutive run, so a pool that mixed conventions
# would emit things like `(u A : Set α)` that Mathlib would never write.
_TYPE_NAMES = ("α", "β", "γ", "δ", "ε", "ζ", "ι", "κ", "σ", "τ")
_PROP_NAMES = ("h", "h₁", "h₂", "h₃", "h₄", "h₅", "h₆", "h₇")
_NUM_NAMES = ("m", "n", "k", "i", "j", "p", "q")
_REAL_NAMES = ("x", "y", "z", "w", "a", "b", "c")
_FUN_NAMES = ("f", "g", "h", "φ", "ψ", "F", "G")
_SET_NAMES = ("s", "t", "u", "v", "A", "B", "C")
_ELEM_NAMES = ("a", "b", "c", "d", "x", "y", "z", "w")

_RELATION_CHARS = "=≤<≥>∈∉∣≠∼≈≅⊆⊂∧∨¬↔"
# Mathlib reserves `m n k` for discrete quantities and `x y z` for continuous
# ones, so the two need different pools.
_DISCRETE_TYPES = ("ℕ", "ℤ", "Nat", "Int", "Fin")
_CONTINUOUS_TYPES = ("ℚ", "ℝ", "ℂ", "NNReal", "ENNReal")


def _name_pool(type_text: str) -> tuple[str, ...]:
    """Pick the family of replacement names appropriate to a binder's type."""
    t = type_text.strip()
    if t.startswith("Type") or t.startswith("Sort"):
        return _TYPE_NAMES
    # A hypothesis binder's "type" is the proposition itself (`h : 0 < a`), so
    # a relation symbol anywhere in it is the tell — check before `→`, which
    # would otherwise misread `a ≤ b → c` as a function.
    if t == "Prop" or any(ch in t for ch in _RELATION_CHARS):
        return _PROP_NAMES
    if "→" in t:
        return _FUN_NAMES
    if t.startswith("Set ") or t.startswith("Finset "):
        return _SET_NAMES
    if any(t == nt or t.startswith(nt + " ") for nt in _DISCRETE_TYPES):
        return _NUM_NAMES
    if any(t == nt or t.startswith(nt + " ") for nt in _CONTINUOUS_TYPES):
        return _REAL_NAMES
    return _ELEM_NAMES


def _all_identifiers(s: str) -> set[str]:
    return set(re.findall(rf"[\w{_IDENT_EXTRA}]+", s))


def _fresh_names(
    pool: tuple[str, ...], count: int, taken: set[str], offset: int = 0
) -> list[str]:
    """``count`` unused names from ``pool``, consecutive if that is possible.

    Variables declared together should read as a set — Mathlib writes
    ``(s t : Set α)``, never ``(u A : Set α)`` — so prefer an unbroken run of
    the pool before falling back to whatever is still free.

    ``offset`` rotates the starting point. Always taking the pool's first free
    name would make every renamed statement reach for ``α`` and ``c``, which is
    just a subtler version of the ``wv0`` fingerprint we are trying to remove.
    """
    rotated = pool[offset % len(pool):] + pool[:offset % len(pool)]
    for start in range(len(rotated) - count + 1):
        window = rotated[start:start + count]
        if all(c not in taken for c in window):
            return list(window)
    return [c for c in rotated if c not in taken][:count]


# ── perturbations ───────────────────────────────────────────────────────────────
def alpha_rename(sig: str, type_str: str) -> tuple[str, str] | None:
    """Rename bound variables to different, Mathlib-idiomatic names.

    Equivalence-preserving — a definitionally identical statement with a
    different set of identifiers. Each variable is replaced by one of the same
    *kind* (types get Greek letters, hypotheses get ``h``-names, naturals get
    ``m``/``n``/``k``, …) so the variant still reads like ordinary Mathlib.

    Instance binders are left alone: ``inst`` is the convention, so renaming it
    adds surface noise without making the pair any more informative.

    Returns ``None`` when there are no renameable binders, when no fresh name is
    available, or when the result is a no-op / fails to type-check.
    """
    parsed = _leading_binders(type_str)
    if parsed is None:
        return None
    binders, _ = parsed

    # Every identifier already present is off limits as a target. That is
    # stricter than necessary but it makes capture impossible: we can never
    # rename onto a free variable, a constant, or another binder's name.
    taken = _all_identifiers(type_str) | _all_identifiers(sig)

    # Derived from the statement so the rename is reproducible, but different
    # from one theorem to the next.
    offset = zlib.crc32(type_str.encode("utf-8"))

    mapping: dict[str, str] = {}
    for bracket, names, type_text in _binder_groups(binders):
        if bracket == "[":
            continue
        pool = _name_pool(type_text)
        todo = [n for n in names if n not in mapping]
        if not todo:
            continue
        for fresh in _fresh_names(pool, len(todo), taken, offset):
            mapping[todo.pop(0)] = fresh
            taken.add(fresh)

    if not mapping:
        return None

    # One simultaneous pass. Sequential substitution would let an earlier
    # rename be re-renamed by a later rule (`a`→`b` then `b`→`c`), which is
    # exactly the capture this perturbation must not introduce.
    pattern = re.compile(
        _BEFORE
        + "("
        + "|".join(re.escape(n) for n in sorted(mapping, key=len, reverse=True))
        + ")"
        + _AFTER
    )
    out = pattern.sub(lambda m: mapping[m.group(1)], type_str)

    if out.strip() == type_str.strip():
        return None
    if not compile_lean(sig, out):
        return None
    return sig, out


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
