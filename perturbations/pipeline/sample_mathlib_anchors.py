#!/usr/bin/env python
"""Pick Mathlib anchors that will actually exercise the whole registry.

The 10 Mathlib anchors in the benchmark CSV leave **12 of 28 perturbations
with zero variants** — every quantifier perturbation, every implication-shaped
logical perturbation, `curry`, `definitional_unfold`, `eq_to_le`,
`bound_tighter`, `premise_permute`, `tc_weaken_conc`. Anything we say about
those is currently unmeasured, and sampling more anchors at random would not
fix it: a random Mathlib theorem is unlikely to have the shape any particular
transform needs.

So this samples for *coverage* rather than volume. Each candidate is tagged
with the syntactic shapes it exhibits, and anchors are then chosen greedily to
cover the shapes that are currently starved. Twenty well-chosen anchors buy
more measurement than two hundred random ones, which matters when each anchor
costs about five minutes of Lean.

The shape predicates below mirror the pre-Lean conditions inside each
transform. They are heuristics *for sampling only* — the transform itself
remains the source of truth, and a shape we predict wrongly costs nothing
worse than one wasted slot.

Usage::

    python pipeline/sample_mathlib_anchors.py --limit 20 --verify
    python pipeline/run_benchmark_review.py --anchors-file data/anchors/mathlib-20.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

HF_REPO = "FrenzyMath/mathlib_informal_v4.19.0"
HF_FILE = "data.jsonl"

_MAX_UNIV_RE = re.compile(r"Type\s*\(max[^)]*\)")
_UNFOLDABLE = (
    "Function.Injective", "Function.Surjective", "Function.Bijective",
    "Function.LeftInverse", "Function.RightInverse",
    "Monotone", "Antitone", "StrictMono", "StrictAnti",
)


def find_top_level_comma(s: str, start: int = 0) -> int:
    """First comma not nested in brackets, or -1. Mirrors the transforms."""
    depth = 0
    for i in range(start, len(s)):
        c = s[i]
        if c in "({[⟨":
            depth += 1
        elif c in ")}]⟩":
            depth = max(0, depth - 1)
        elif c == "," and depth == 0:
            return i
    return -1


def find_top_level_arrow(s: str) -> int:
    """Index of the first ``→`` not nested inside brackets, or -1."""
    depth = 0
    for i, c in enumerate(s):
        if c in "({[⟨":
            depth += 1
        elif c in ")}]⟩":
            depth = max(0, depth - 1)
        elif c == "→" and depth == 0:
            return i
    return -1


def split_binders(type_str: str) -> tuple[str, str]:
    """``(leading binder block, body)`` for a leading ∀/∃, else ``("", whole)``."""
    m = re.match(r"^\s*[∀∃]\s+", type_str)
    if m is None:
        return "", type_str
    comma = find_top_level_comma(type_str, start=m.end())
    if comma == -1:
        return "", type_str
    return type_str[m.end():comma].strip(), type_str[comma + 1:].strip()


def shapes_of(type_str: str) -> set[str]:
    """Which perturbation-relevant shapes does this statement have?"""
    found: set[str] = set()
    binders, body = split_binders(type_str)

    # quantifier layer
    if type_str.lstrip().startswith("∀") and binders:
        if not any(ch in binders for ch in "{[⦃"):
            found.add("leading_explicit_forall")     # forall_to_exists
        if body.lstrip().startswith("∃"):
            found.add("forall_then_exists")          # quantifier_swap
    if type_str.lstrip().startswith("∃"):
        found.add("leading_exists")                  # exists_to_forall

    # implication shape drives contrapose / converse / inverse / uncurry
    if "→" in body:
        found.add("implication")
        if body.count("→") >= 2:
            found.add("two_hypotheses")              # premise_permute, uncurry
    # `curry` rewrites `(P ∧ Q) → R` via `and_imp`, so the conjunction has to
    # sit in *hypothesis* position. A conjunction in the conclusion —
    # `a = 0 ∨ 0 < a ∧ 0 ≤ b` — looks the same to a naive `"∧" in body` test
    # but gives `simp made no progress`.
    arrow = find_top_level_arrow(body)
    if arrow != -1 and "∧" in body[:arrow]:
        found.add("conj_hypothesis")                 # curry

    # connective / relation layer
    if "∨" in body:
        found.add("disjunction")                     # connective_swap
    if re.search(r"(?<![≠<>])=(?!=)", body) and "↔" not in body:
        found.add("equality")                        # eq_to_le
    if any(op in body for op in ("≤", "≥", " < ", " > ")):
        found.add("inequality")                      # flip_bound, strictness_swap
    if re.search(r"(?<![\w'])\d+(?![\w'])", body):
        found.add("numeral")                         # bound_tighter, const_to_zero_one
    if re.search(r"\s[+\-*]\s", body):
        found.add("arith_op")                        # arith_op_swap

    # typeclass layer
    if re.search(r"\[[^\]]*\]", type_str):
        found.add("typeclass_binder")                # tc_*
    if any(p in type_str for p in _UNFOLDABLE):
        found.add("unfoldable_predicate")            # definitional_unfold

    return found


# Shapes the benchmark anchors already cover well, and therefore worth less.
STARVED_SHAPES = {
    "forall_then_exists", "leading_explicit_forall", "leading_exists",
    "implication", "two_hypotheses", "conj_hypothesis",
    "unfoldable_predicate", "equality", "numeral", "disjunction",
}


# The dataset's own ``type`` field is pretty-printed with notation disabled —
# `≤` comes out as `LE.le`, `∨` as `Or`, `+` as `HAdd.hAdd`. That is unusable
# here for two reasons: the regex-driven transforms look for the notation, and
# feeding prefix-form statements into the lexical comparison would compare them
# against benchmark anchors written in ordinary Mathlib syntax.
#
# The ``signature`` field *is* ordinary syntax, but it is section-relative:
# variables introduced by `variable` are used without being bound, so it does
# not elaborate on its own.
#
# So we use the dataset only to pick promising *names*, and then ask Lean for
# the real thing. These are the prefix spellings, used for that first cheap
# pass only.
_PREFIX_HINTS = {
    "disjunction": ("Or ",),
    "conj_hypothesis": ("And ",),
    "inequality": ("LE.le", "LT.lt", "GE.ge", "GT.gt"),
    "equality": ("Eq ",),
    "arith_op": ("HAdd.hAdd", "HSub.hSub", "HMul.hMul"),
    "leading_exists": ("Exists",),
    "unfoldable_predicate": _UNFOLDABLE,
}


def prefix_shape_hints(type_str: str) -> set[str]:
    """Approximate shapes from the dataset's prefix-notation type field."""
    found = set()
    for shape, needles in _PREFIX_HINTS.items():
        if any(n in type_str for n in needles):
            found.add(shape)
    if "→" in type_str:
        found.add("implication")
        if type_str.count("→") >= 2:
            found.add("two_hypotheses")
    if type_str.count("∀") >= 2:
        found.add("leading_explicit_forall")
    if re.search(r"\[[^\]]*\]", type_str):
        found.add("typeclass_binder")
    return found


def load_candidates(path: Path, min_len: int, max_len: int) -> list[dict[str, Any]]:
    """Read the dataset and keep theorems of a workable size and shape."""
    out: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            rec = json.loads(line)
            if rec.get("kind") != "theorem":
                continue
            type_str = " ".join((rec.get("type") or "").split())
            if not (min_len <= len(type_str) <= max_len):
                continue
            if "sorry" in type_str:
                continue
            name = rec["name"]
            module = rec["module_name"]
            declaration = ".".join(name) if isinstance(name, list) else name
            if "✝" in declaration or declaration.startswith("_"):
                continue
            out.append({
                "declaration": declaration,
                "module": ".".join(module) if isinstance(module, list) else module,
                "raw_signature": "",
                "type_str": type_str,
                "shapes": prefix_shape_hints(type_str),
                "index": rec.get("index"),
            })
    return out


# ── Asking Lean for the real signature ────────────────────────────────────────
# `#check @Foo.bar` prints the fully-elaborated type with every binder explicit
# and ordinary notation restored — exactly the form the benchmark CSV holds and
# the transforms expect. Hundreds of them go in one file, so the whole batch
# costs a single Mathlib import instead of one per theorem.

# Lean prints `@Foo.bar : …` when the declaration has implicit binders and
# plain `Foo.bar : …` when every binder is already explicit, so the `@` is
# optional. The type itself may wrap over several lines.
_CHECK_RE = re.compile(r"\s*@?(\S+)\s*:\s*(.*)", re.DOTALL)


def resolve_signatures(declarations: list[str], batch: int = 200
                       ) -> dict[str, str]:
    """Return ``{declaration: type_str}`` as Lean itself prints it."""
    from wiggle.lean_runner import run_lean

    resolved: dict[str, str] = {}
    for start in range(0, len(declarations), batch):
        chunk = declarations[start:start + batch]
        code = ("import Mathlib\n\nset_option pp.funBinderTypes true\n\n"
                + "".join(f"#check @{d}\n" for d in chunk))
        print(f"  #check batch {start // batch + 1} "
              f"({len(chunk)} declarations)…", flush=True)
        output = run_lean(code, timeout=900)

        # Each #check is its own `info:` diagnostic, so splitting on that keeps
        # multi-line wrapped types together with their own declaration. A
        # trailing `warning:` (the style linter objects to `set_option pp.*`)
        # lands inside the last block and has to be cut off.
        for block in output.split("info:")[1:]:
            for marker in ("\nwarning:", "\nerror:"):
                block = block.split(marker)[0]
            m = _CHECK_RE.match(block)
            if m is None:
                continue
            name, type_str = m.group(1), " ".join(m.group(2).split())
            if name in resolved or not type_str:
                continue
            resolved[name] = _MAX_UNIV_RE.sub("Type _", type_str)
    return resolved


def greedy_cover(candidates: list[dict[str, Any]], limit: int,
                 rng_seed: int) -> list[dict[str, Any]]:
    """Pick anchors that spread evenly across the starved shapes.

    Plain greedy set cover does badly here. A statement carrying four common
    shapes always outscores one carrying a single rare shape, so the common
    shapes fill every slot and the rare ones — the whole reason for sampling —
    end up with nothing. Instead, each round explicitly targets the *least
    covered* shape that still has candidates, and only then picks the best
    statement offering it. That guarantees breadth first and lets the value
    function break ties. Shorter statements win ties, being cheaper in Lean.
    """
    import random

    rng = random.Random(rng_seed)
    pool = candidates[:]
    rng.shuffle(pool)

    by_shape: dict[str, list[dict[str, Any]]] = {s: [] for s in STARVED_SHAPES}
    for c in pool:
        for s in c["shapes"] & STARVED_SHAPES:
            by_shape[s].append(c)

    covered: Counter[str] = Counter()
    chosen: list[dict[str, Any]] = []
    taken: set[int] = set()

    def value(c: dict[str, Any]) -> tuple[float, int]:
        score = sum((3.0 if s in STARVED_SHAPES else 1.0) / (1 + covered[s])
                    for s in c["shapes"])
        return (score, -len(c["type_str"]))

    live = {s for s in STARVED_SHAPES if by_shape[s]}
    while len(chosen) < limit and live:
        target = min(live, key=lambda s: (covered[s], s))
        options = [c for c in by_shape[target] if id(c) not in taken]
        if not options:
            live.discard(target)
            continue
        best = max(options, key=value)
        taken.add(id(best))
        chosen.append(best)
        covered.update(best["shapes"])

    # Any slots left over (a small pool, or few starved shapes) get the plain
    # greedy treatment over everything still available.
    remaining = [c for c in pool if id(c) not in taken]
    while len(chosen) < limit and remaining:
        best = max(remaining, key=value)
        remaining.remove(best)
        chosen.append(best)
        covered.update(best["shapes"])

    return chosen


def verify(anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only anchors that elaborate standalone, one Lean call each.

    Worth the few minutes it costs: an anchor that does not elaborate would
    otherwise burn a full five-minute perturbation slot producing nothing.
    """
    from wiggle.lean_runner import compile_lean

    kept = []
    for i, a in enumerate(anchors, 1):
        ok = compile_lean("", a["type_str"])
        print(f"  [{i}/{len(anchors)}] {'ok  ' if ok else 'FAIL'} "
              f"{a['declaration'][:70]}", flush=True)
        if ok:
            kept.append(a)
    return kept


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=20,
                    help="How many anchors to keep (default 20).")
    ap.add_argument("--min-len", type=int, default=60)
    ap.add_argument("--max-len", type=int, default=320,
                    help="Cap on statement length in characters. Long "
                         "statements are slow in Lean and tend to be "
                         "category-theory diagram chases (default 320).")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verify", action="store_true",
                    help="Elaborate each chosen anchor before writing it out.")
    ap.add_argument("--oversample", type=int, default=8,
                    help="Shortlist this multiple of --limit before asking "
                         "Lean, so that rejects still leave a full set "
                         "(default 8).")
    ap.add_argument("--dataset", type=Path,
                    help="Local path to data.jsonl (default: download from HF).")
    ap.add_argument("--out", type=Path,
                    default=PROJECT_ROOT / "data" / "anchors")
    args = ap.parse_args()

    path = args.dataset
    if path is None:
        from huggingface_hub import hf_hub_download
        print(f"fetching {HF_REPO}…", flush=True)
        path = Path(hf_hub_download(repo_id=HF_REPO, filename=HF_FILE,
                                    repo_type="dataset"))

    print(f"reading {path}", flush=True)
    candidates = load_candidates(path, args.min_len, args.max_len)
    print(f"{len(candidates)} candidate theorems in range", flush=True)

    # Pass 1 — shortlist on the cheap prefix-notation hints.
    shortlist = greedy_cover(candidates, args.limit * args.oversample, args.seed)
    print(f"\nshortlisted {len(shortlist)}; asking Lean for real signatures",
          flush=True)

    # Pass 2 — replace the guessed type with Lean's own, re-derive shapes from
    # the real notation, and only then make the final selection.
    resolved = resolve_signatures([c["declaration"] for c in shortlist])
    print(f"  resolved {len(resolved)}/{len(shortlist)}", flush=True)

    real: list[dict[str, Any]] = []
    for c in shortlist:
        type_str = resolved.get(c["declaration"])
        if not type_str or len(type_str) > args.max_len:
            continue
        shapes = shapes_of(type_str)
        if not shapes:
            continue
        real.append({**c, "type_str": type_str,
                     "raw_signature": type_str, "shapes": shapes})
    print(f"  {len(real)} usable after re-derivation", flush=True)

    chosen = greedy_cover(real, args.limit * (2 if args.verify else 1), args.seed)

    if args.verify:
        print(f"\nverifying {len(chosen)} candidates…", flush=True)
        chosen = verify(chosen)
    chosen = chosen[:args.limit]

    coverage: Counter[str] = Counter()
    for c in chosen:
        coverage.update(c["shapes"])
    print("\nshape coverage:")
    for shape, n in coverage.most_common():
        star = " *" if shape in STARVED_SHAPES else ""
        print(f"  {shape:26s} {n}{star}")
    missing = STARVED_SHAPES - set(coverage)
    if missing:
        print(f"  still uncovered: {sorted(missing)}")

    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / f"mathlib-{len(chosen)}.jsonl"
    with open(out_path, "w", encoding="utf-8") as fh:
        for i, c in enumerate(chosen):
            fh.write(json.dumps({
                "id": f"mathlib_{i:03d}",
                "declaration": c["declaration"],
                "module": c["module"],
                "raw_signature": c["raw_signature"],
                "type_str": c["type_str"],
                "body": c["type_str"],
                "is_definition": False,
                "shapes": sorted(c["shapes"]),
                "csv_rows": [],
                "pair_ids": [f"mathlib:{c['index']}"],
            }, ensure_ascii=False) + "\n")

    print(f"\n{len(chosen)} anchors\n  {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
