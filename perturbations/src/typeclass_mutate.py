"""
typeclass_mutate.py

Systematically changes the generalization level of a typeclass in a Lean 4
theorem statement using the Mathlib typeclass hierarchy.

Four perturbation methods (named for what they do to the *typeclass*):

  weaken_hypothesis_typeclass    – hypothesis [TC α] → [WeakerParent α]
                                   (e.g. [AddCommMonoid α] → [AddMonoid α])
                                   The variant claims the conclusion holds
                                   over a LARGER class of types — i.e. a
                                   STRONGER statement; may not be true.

  strengthen_hypothesis_typeclass – hypothesis [TC α] → [StrongerChild α]
                                   (e.g. [AddCommMonoid α] → [AddCommGroup α])
                                   Narrower class of types — i.e. a WEAKER
                                   statement; original conclusion still
                                   holds for any qualifying type.

  strengthen_conclusion_typeclass – conclusion [TC α] → [StrongerChild α]
                                   Claims a stronger structural property;
                                   may not be true.

  weaken_conclusion_typeclass    – conclusion [TC α] → [WeakerParent α]
                                   Claims a weaker property; follows from
                                   the original by definition of the hierarchy.

Hierarchy source:
  The full Mathlib `extends` hierarchy is precomputed once into
  data/class_hierarchy.jsonl by `src/instance_graph/dump_class_hierarchy.py`
  (which runs the `#wiggle_dump_class_hierarchy` command in Wiggle.lean). Both
  parents and children are derived from that single table. Classes missing from
  the dump fall back to a live Lean `getStructureInfo?` query for parents only.
  Regenerate the dump after a Mathlib/Lean toolchain bump.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from functools import lru_cache

# ---------------------------------------------------------------------------
# Project helpers
# ---------------------------------------------------------------------------

# PROJECT_DIR is the Lake project root (one level up from src/).
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_lean(code: str, timeout: int = 120) -> str:
    """Elaborate ``code`` via the shared ``wiggle.lean_runner.run_lean`` router.

    Delegating here means the persistent Lean LSP server set up in
    :mod:`wiggle.lean_server` also speeds up every typeclass-mutation
    validity check. Falls back transparently to the subprocess backend when
    the server is unavailable (controlled by ``WIGGLE_LEAN_BACKEND``).
    """
    # Local import keeps this module standalone-importable (the legacy
    # callers in scripts/ don't always set up sys.path the same way).
    import sys
    _src = os.path.dirname(os.path.abspath(__file__))
    if _src not in sys.path:
        sys.path.insert(0, _src)
    from wiggle.lean_runner import run_lean as _run_lean_via_runner

    try:
        return _run_lean_via_runner(code, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout"


# ---------------------------------------------------------------------------
# Data-driven typeclass hierarchy
#
# The hierarchy is loaded from data/class_hierarchy.jsonl, produced by
#   python src/instance_graph/dump_class_hierarchy.py
# which runs the `#wiggle_dump_class_hierarchy` command in Wiggle.lean over the
# whole Mathlib environment. Each line is
#   {"name": "<fully.qualified.Class>", "parents": ["<fully.qualified>", ...]}
#
# Everything is keyed by SHORT name (last dotted component), since that is how
# typeclasses appear in theorem statements. Both Type-valued classes (CommRing,
# AddCommMonoid, …) and Prop-valued classes (IsDomain, IsField, …) live in the
# same table — there is no longer a separate hand-maintained Prop hierarchy.
#
# Set WIGGLE_CLASS_HIERARCHY to override the path (used by tests).
# ---------------------------------------------------------------------------

_HIERARCHY_PATH = os.path.join(PROJECT_DIR, "data", "class_hierarchy.jsonl")


def _short_name(name: str) -> str:
    """Last dotted component, e.g. ``Mathlib.Algebra.Field`` → ``Field``."""
    return name.rsplit(".", 1)[-1]


@lru_cache(maxsize=1)
def _load_hierarchy() -> tuple[dict[str, frozenset[str]], dict[str, frozenset[str]]]:
    """Load ``(parents, children)`` short-name maps from the dump.

    Both dicts are keyed by short class name. Every class that appears in the
    dump — and every class named as someone's parent — is present as a key in
    ``parents`` (possibly mapping to the empty set), so ``name in parents`` is
    a reliable "is this a known class?" test. ``children`` is the reverse edge.

    A missing dump file yields two empty maps; callers then fall back to a live
    Lean structure query for parents.
    """
    path = os.environ.get("WIGGLE_CLASS_HIERARCHY", _HIERARCHY_PATH)
    parents: dict[str, set[str]] = {}
    children: dict[str, set[str]] = {}
    if not os.path.exists(path):
        return {}, {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            child = _short_name(str(row.get("name", "")))
            if not child:
                continue
            edge_parents = {_short_name(str(p)) for p in row.get("parents", []) if p}
            edge_parents.discard(child)
            parents.setdefault(child, set()).update(edge_parents)
            for parent in edge_parents:
                parents.setdefault(parent, set())  # parent is itself a known class
                children.setdefault(parent, set()).add(child)
    return (
        {k: frozenset(v) for k, v in parents.items()},
        {k: frozenset(v) for k, v in children.items()},
    )


def is_known_class(class_name: str) -> bool:
    """True iff ``class_name`` (short or fully qualified) appears in the dump."""
    parents, _ = _load_hierarchy()
    return _short_name(class_name) in parents


# ---------------------------------------------------------------------------
# Getting parents via Lean (most reliable for arbitrary classes)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=256)
def get_class_parents_lean(class_name: str) -> list[str]:
    """
    Query Lean for the direct parent structures of `class_name`.
    Uses Lean.StructureInfo.parentInfo from Lean's core API.
    Returns [] if not a structure/class or Lean times out.
    """
    lean_code = (
        "import Mathlib\n"
        "import Lean\n\n"
        "#eval show Lean.CoreM Unit from do\n"
        "  let env ← Lean.getEnv\n"
        f"  match Lean.getStructureInfo? env `{class_name} with\n"
        '  | none => IO.println "[]"\n'
        "  | some info =>\n"
        "    let parents := info.parentInfo.map (·.structName.toString)\n"
        "    IO.println (toString parents)\n"
    )
    output = _run_lean(lean_code)
    # Lean prints something like: #[Semiring, AddCommGroup, AddGroupWithOne]
    m = re.search(r'#?\[([^\]]*)\]', output)
    if not m:
        return []
    raw = m.group(1).strip()
    if not raw:
        return []
    items = [x.strip() for x in raw.split(',') if x.strip()]
    # Strip Lean qualified prefixes: keep only the last segment
    return [name.rsplit('.', 1)[-1] for name in items]


# ---------------------------------------------------------------------------
# Public hierarchy API
# ---------------------------------------------------------------------------

def get_parents(class_name: str, use_lean: bool = True) -> list[str]:
    """
    Return direct parent classes of `class_name` (1 level up = more general).

    Reads the precomputed hierarchy (data/class_hierarchy.jsonl). For classes
    missing from the dump — e.g. a newer Mathlib than the dump was built
    against — falls back to a live Lean structure query when ``use_lean``.
    """
    parents, _ = _load_hierarchy()
    short = _short_name(class_name)
    if short in parents:
        return sorted(parents[short])
    if use_lean:
        return get_class_parents_lean(class_name)
    return []


def get_children(class_name: str) -> list[str]:
    """
    Return direct subclasses of `class_name` (1 level down = more specific).

    Children come from the reverse of the precomputed hierarchy. There is no
    live fallback: Lean offers no cheap "who extends me" reverse lookup, so a
    class absent from the dump simply has no known children.
    """
    _, children = _load_hierarchy()
    return sorted(children.get(_short_name(class_name), frozenset()))


def get_ancestors(class_name: str, depth: int = 2) -> list[str]:
    """BFS up to `depth` levels up the hierarchy."""
    visited: set[str] = set()
    frontier = [class_name]
    result: list[str] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for name in frontier:
            for parent in get_parents(name):
                if parent not in visited and parent != class_name:
                    visited.add(parent)
                    result.append(parent)
                    next_frontier.append(parent)
        frontier = next_frontier
    return result


def get_descendants(class_name: str, depth: int = 2) -> list[str]:
    """BFS up to `depth` levels down the hierarchy."""
    visited: set[str] = set()
    frontier = [class_name]
    result: list[str] = []
    for _ in range(depth):
        next_frontier: list[str] = []
        for name in frontier:
            for child in get_children(name):
                if child not in visited and child != class_name:
                    visited.add(child)
                    result.append(child)
                    next_frontier.append(child)
        frontier = next_frontier
    return result


# ---------------------------------------------------------------------------
# Parsing and substituting typeclass brackets in a Lean type string
# ---------------------------------------------------------------------------

# Matches [inst? : ?TCName args] or [TCName args]
# Group 1: optional "varname :" prefix (including colon)
# Group 2: typeclass name (Capitalized identifier)
# Group 3: remainder (arguments and closing bracket content)
_TC_BRACKET_RE = re.compile(
    r'\['
    r'([A-Za-z_][A-Za-z0-9_₀-₉]*\s*:\s*)?'   # optional "inst : "
    r'([A-Z][A-Za-z0-9_.]*)'                    # TC name
    r'([^\[\]]*)\]'                              # args + closing bracket
)


def _find_tc_brackets(
    text: str,
) -> list[tuple[str, str, str, str, int, int]]:
    """
    Find all typeclass brackets in `text`.

    Returns list of (full_match, prefix, tc_name, args, start, end).
    """
    results = []
    for m in _TC_BRACKET_RE.finditer(text):
        prefix = m.group(1) or ""
        tc_name = m.group(2)
        args = m.group(3)
        results.append((m.group(0), prefix, tc_name, args, m.start(), m.end()))
    return results


def _substitute_tc(type_str: str, old_tc: str, new_tc: str) -> str:
    """
    Replace the first occurrence of typeclass `old_tc` with `new_tc`
    inside a `[...]` bracket, keeping all arguments unchanged.
    """
    brackets = _find_tc_brackets(type_str)
    for full, prefix, tc_name, args, start, end in brackets:
        if tc_name == old_tc:
            new_bracket = f"[{prefix}{new_tc}{args}]"
            return type_str[:start] + new_bracket + type_str[end:]
    return type_str


def _split_hyps_conclusion(type_str: str) -> tuple[str, str]:
    """
    Split a Lean type string into (hypotheses_part, conclusion_part).

    Handles two forms:
      ∀ {x : T} [TC x] (a : T), <conclusion>   – split on last top-level ','
      ∀ {x : T} [TC x] → <conclusion>           – split on last top-level '→'

    Returns ("", type_str) when no separator is found.
    """
    depth = 0
    last_sep: int = -1
    sep_len: int = 1
    i = 0
    while i < len(type_str):
        c = type_str[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            # Unicode arrow → (U+2192, 3 bytes in UTF-8 but 1 char in Python str)
            if type_str[i] == "→":
                last_sep = i
                sep_len = 1
            elif c == ",":
                last_sep = i
                sep_len = 1
        i += 1
    if last_sep == -1:
        return "", type_str
    return type_str[: last_sep + sep_len], type_str[last_sep + sep_len :].strip()


def _compile_lean(type_str: str) -> bool:
    """Return True iff `example : <type_str> := by sorry` compiles in Lean."""
    code = f"import Mathlib\n\nexample : {type_str} := by sorry\n"
    output = _run_lean(code)
    # Lean 4 errors appear as both "error:" and "error(<kind>):" — match either.
    return not re.search(r"\berror[:(]", output) and "timeout" not in output


def _find_prop_tc_in_text(text: str) -> list[tuple[str, int, int]]:
    """
    Find bare typeclass applications in `text`, e.g. ``IsDomain (Polynomial R)``.
    Matches `TCName <args>` where TCName is any class in the loaded hierarchy
    (this includes Prop-valued classes such as IsDomain / IsField, which appear
    unbracketed in conclusions).
    Returns list of (tc_name, start, end_of_name).
    """
    results = []
    for m in re.finditer(r'\b([A-Z][A-Za-z0-9_]*)\b', text):
        name = m.group(1)
        if is_known_class(name):
            results.append((name, m.start(), m.end()))
    return results


def _substitute_prop_tc_in_conclusion(
    type_str: str, old_tc: str, new_tc: str, conclusion_offset: int
) -> str:
    """
    Replace first occurrence of bare Prop-TC `old_tc` in the CONCLUSION part
    of `type_str` (starting at byte offset `conclusion_offset`).
    """
    suffix = type_str[conclusion_offset:]
    m = re.search(r'\b' + re.escape(old_tc) + r'\b', suffix)
    if not m:
        return type_str
    abs_start = conclusion_offset + m.start()
    abs_end = conclusion_offset + m.end()
    return type_str[:abs_start] + new_tc + type_str[abs_end:]


# ---------------------------------------------------------------------------
# The four perturbation methods
# ---------------------------------------------------------------------------

def weaken_hypothesis_typeclass(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass [TC α] in the hypotheses and replace TC with a weaker
    ancestor class (moving UP the hierarchy). The variant is a STRONGER
    statement (claims the conclusion holds over more types) and may not be
    true. Returns (sig, new_type_str) for the first substitution that
    compiles, or None.
    """
    hyp_part, _ = _split_hyps_conclusion(type_str)
    brackets = _find_tc_brackets(hyp_part or type_str)
    for _, _, tc_name, _, _, _ in brackets:
        for ancestor in get_ancestors(tc_name, depth):
            new_type = _substitute_tc(type_str, tc_name, ancestor)
            if new_type == type_str:
                continue
            if _compile_lean(new_type):
                return sig, new_type
    return None


def strengthen_hypothesis_typeclass(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass [TC α] in the hypotheses and replace TC with a stronger
    descendant class (moving DOWN the hierarchy). The variant is a WEAKER
    statement (applies to fewer types) but remains true: any type satisfying
    the stronger class also satisfies the original. Returns (sig, new_type_str)
    for the first substitution that compiles, or None.
    """
    hyp_part, _ = _split_hyps_conclusion(type_str)
    brackets = _find_tc_brackets(hyp_part or type_str)
    for _, _, tc_name, _, _, _ in brackets:
        for descendant in get_descendants(tc_name, depth):
            new_type = _substitute_tc(type_str, tc_name, descendant)
            if new_type == type_str:
                continue
            if _compile_lean(new_type):
                return sig, new_type
    return None


def strengthen_conclusion_typeclass(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass in the conclusion and replace it with a stronger
    descendant (moving DOWN = more specific). The variant claims a stronger
    structural property and may not be true.

    Handles two conclusion forms:
      • [inst : TC α]  – structural typeclass in a binder
      • TC α           – bare Prop-valued typeclass application (e.g. IsDomain R)

    Returns (sig, new_type_str) for the first substitution that compiles,
    or None.
    """
    hyp_part, conclusion = _split_hyps_conclusion(type_str)
    conc_offset = len(hyp_part) if hyp_part else 0
    if not conclusion:
        conclusion = type_str
        conc_offset = 0

    # Pass 1: bracketed [TC ...] in the conclusion
    for _, _, tc_name, _, start, end in _find_tc_brackets(conclusion):
        for descendant in get_descendants(tc_name, depth):
            abs_start = conc_offset + start
            abs_end = conc_offset + end
            bracket = type_str[abs_start:abs_end]
            new_bracket = bracket.replace(tc_name, descendant, 1)
            new_type = type_str[:abs_start] + new_bracket + type_str[abs_end:]
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    # Pass 2: bare Prop-valued typeclass applications in the conclusion
    for tc_name, _, _ in _find_prop_tc_in_text(conclusion):
        for descendant in get_descendants(tc_name, depth):
            new_type = _substitute_prop_tc_in_conclusion(
                type_str, tc_name, descendant, conc_offset
            )
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    return None


def weaken_conclusion_typeclass(
    sig: str,
    type_str: str,
    depth: int = 2,
) -> tuple[str, str] | None:
    """
    Find a typeclass in the conclusion and replace it with a weaker
    ancestor (moving UP = more general). The variant claims a weaker
    property and follows from the original by the hierarchy.

    Handles two conclusion forms:
      • [inst : TC α]  – structural typeclass in a binder
      • TC α           – bare Prop-valued typeclass application (e.g. IsDomain R)

    Returns (sig, new_type_str) for the first substitution that compiles,
    or None.
    """
    hyp_part, conclusion = _split_hyps_conclusion(type_str)
    conc_offset = len(hyp_part) if hyp_part else 0
    if not conclusion:
        conclusion = type_str
        conc_offset = 0

    # Pass 1: bracketed [TC ...] in the conclusion
    for _, _, tc_name, _, start, end in _find_tc_brackets(conclusion):
        for ancestor in get_ancestors(tc_name, depth):
            abs_start = conc_offset + start
            abs_end = conc_offset + end
            bracket = type_str[abs_start:abs_end]
            new_bracket = bracket.replace(tc_name, ancestor, 1)
            new_type = type_str[:abs_start] + new_bracket + type_str[abs_end:]
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    # Pass 2: bare Prop-valued typeclass applications in the conclusion
    for tc_name, _, _ in _find_prop_tc_in_text(conclusion):
        for ancestor in get_ancestors(tc_name, depth):
            new_type = _substitute_prop_tc_in_conclusion(
                type_str, tc_name, ancestor, conc_offset
            )
            if new_type != type_str and _compile_lean(new_type):
                return sig, new_type

    return None


# ---------------------------------------------------------------------------
# Type specialization and sibling-class swap
# ---------------------------------------------------------------------------

# Concrete Mathlib types tried, in order, when instantiating a type variable.
# The Lean compile check decides which one actually satisfies the constraints.
_CONCRETE_TYPES = ["ℕ", "ℤ", "ℚ", "ℝ", "ℂ"]
_VAR_EXTRA = r"'′₀-₉ₐ-ₜ"


def _subst_var(text: str, var: str, repl: str) -> str:
    """Boundary-aware replacement of identifier ``var`` (so ``α`` ≠ ``α₀``)."""
    pat = rf"(?<![\w{_VAR_EXTRA}]){re.escape(var)}(?![\w{_VAR_EXTRA}])"
    return re.sub(pat, repl, text)


def _split_forall(type_str: str) -> tuple[str, str] | None:
    """Split ``∀ <binders>, <body>``; None if not a leading-∀ statement."""
    s = type_str.strip()
    if not s.startswith("∀"):
        return None
    after = s[len("∀"):]
    depth = 0
    for i, c in enumerate(after):
        if c in "({[⦃":
            depth += 1
        elif c in ")}]⦄":
            depth = max(0, depth - 1)
        elif c == "," and depth == 0:
            return after[:i].strip(), after[i + 1:].strip()
    return None


def _binder_groups(binders: str) -> list[tuple[str, str, str]]:
    """Tokenize a binder block into ``(open_char, inner, full_text)`` groups."""
    closes = {"(": ")", "{": "}", "[": "]", "⦃": "⦄"}
    groups: list[tuple[str, str, str]] = []
    i, n = 0, len(binders)
    while i < n:
        c = binders[i]
        if c in closes:
            close = closes[c]
            depth, j = 0, i
            while j < n:
                if binders[j] == c:
                    depth += 1
                elif binders[j] == close:
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            groups.append((c, binders[i + 1:j], binders[i:j + 1]))
            i = j + 1
        else:
            i += 1
    return groups


def specialize_type(sig: str, type_str: str) -> tuple[str, str] | None:
    """Instantiate the first type variable with a concrete type (ℕ/ℤ/ℚ/ℝ/ℂ).

    Drops the ``{α : Type*}`` binder and any instance binders ``[… α]`` that
    constrain it, substitutes ``α`` everywhere with the concrete type, and keeps
    the first version that compiles. A true universal statement stays true under
    instantiation at a valid type, so this is a true→true near-positive that is
    orthogonal to the typeclass-hierarchy mutations.
    """
    parsed = _split_forall(type_str)
    if parsed is None:
        return None
    binders, body = parsed
    groups = _binder_groups(binders)

    var: str | None = None
    var_group_full = ""
    for _oc, inner, full in groups:
        colon = inner.find(":")
        if colon == -1:
            continue
        names = inner[:colon].split()
        bind_type = inner[colon + 1:].strip()
        if len(names) == 1 and (bind_type.startswith("Type") or bind_type.startswith("Sort")):
            var, var_group_full = names[0], full
            break
    if var is None:
        return None

    kept: list[str] = []
    for oc, inner, full in groups:
        if full == var_group_full:
            continue
        if oc == "[" and _subst_var(inner, var, "\x00") != inner:
            continue  # instance constraint on the specialized variable
        kept.append(full)

    for concrete in _CONCRETE_TYPES:
        new_binders = _subst_var(" ".join(kept), var, concrete).strip()
        new_body = _subst_var(body, var, concrete)
        new_type = f"∀ {new_binders}, {new_body}" if new_binders else new_body
        if new_type.strip() == type_str.strip():
            continue
        if _compile_lean(new_type):
            return sig, new_type
    return None


def sibling_typeclass(sig: str, type_str: str, max_tries: int = 8) -> tuple[str, str] | None:
    """Replace a typeclass with an incomparable *sibling* (shares a parent).

    E.g. a class sitting under ``Monoid`` swapped for another class under
    ``Monoid``. Neither stronger nor weaker than the original, so truth is
    unknown — a harder negative than the up/down hierarchy moves. Returns the
    first sibling substitution that compiles.
    """
    for _full, _prefix, tc_name, _args, _start, _end in _find_tc_brackets(type_str):
        siblings: list[str] = []
        seen: set[str] = {tc_name}
        for parent in get_parents(tc_name):
            for child in get_children(parent):
                if child not in seen:
                    seen.add(child)
                    siblings.append(child)
        for sib in siblings[:max_tries]:
            new_type = _substitute_tc(type_str, tc_name, sib)
            if new_type == type_str:
                continue
            if _compile_lean(new_type):
                return sig, new_type
    return None


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

_DEMO_CASES = [
    (
        "add_comm",
        "∀ {α : Type u_1} [inst : AddCommMonoid α] (a b : α), a + b = b + a",
    ),
    (
        "mul_inv_cancel",
        "∀ {α : Type u_1} [inst : Field α] (a : α), a ≠ 0 → a * a⁻¹ = 1",
    ),
    # Conclusion contains a bare Prop-TC: IsDomain
    (
        "Polynomial.isDomain",
        "∀ {R : Type u_1} [inst : CommRing R] [inst_1 : IsDomain R], IsDomain (Polynomial R)",
    ),
]


def _demo() -> None:
    for name, type_str in _DEMO_CASES:
        print(f"\n{'='*60}")
        print(f"Original [{name}]:\n  {type_str}")

        result = weaken_hypothesis_typeclass(name, type_str)
        print(f"\nweaken_hypothesis_typeclass:")
        print(f"  {result[1] if result else '(none found)'}")

        result = strengthen_hypothesis_typeclass(name, type_str)
        print(f"\nstrengthen_hypothesis_typeclass:")
        print(f"  {result[1] if result else '(none found)'}")

        result = strengthen_conclusion_typeclass(name, type_str)
        print(f"\nstrengthen_conclusion_typeclass:")
        print(f"  {result[1] if result else '(none found)'}")

        result = weaken_conclusion_typeclass(name, type_str)
        print(f"\nweaken_conclusion_typeclass:")
        print(f"  {result[1] if result else '(none found)'}")


if __name__ == "__main__":
    _demo()
