#!/usr/bin/env python
"""Turn scraped blueprint declarations into perturbation anchors.

Reads ``dataset/blueprints.json`` (written by ``dataset/LeanBlueprintParser.py``:
one entry per blueprint project, each with the Lean source of its
declarations) and writes one JSONL anchor per ``theorem`` / ``lemma`` in the
format ``run_benchmark_review.py --anchors-file`` expects.

Each declaration's source text is reduced to a standalone type: doc comments,
attributes and modifiers are stripped, the proof after ``:=`` is dropped, and
``theorem name (binders) : T`` becomes ``∀ (binders), T``. No Lean is involved,
so many anchors still reference project-only definitions or section
``variable``s; ``run_benchmark_review.py --skip-noncompiling`` filters those
against plain Mathlib.

Usage::

    python pipeline/prepare_blueprint_anchors.py
    python pipeline/prepare_blueprint_anchors.py --input ../dataset/blueprints.json \\
        --out data/anchors/blueprints.jsonl
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
DEFAULT_INPUT = PROJECT_ROOT.parent / "dataset" / "blueprints.json"
DEFAULT_OUT = PROJECT_ROOT / "data" / "anchors" / "blueprints.jsonl"

_MODIFIERS = ("private", "protected", "noncomputable", "nonrec", "unsafe", "partial")
_OPEN = "([{⦃"
_CLOSE = ")]}⦄"
_NAME_RE = re.compile(r"([^\s(\[{⦃]+)\s*(.*)", re.DOTALL)


def _skip_block_comment(s: str, i: int) -> int:
    """``s[i:]`` starts with ``/-``; return the index just past the matching ``-/``."""
    depth, j = 0, i
    while j < len(s) - 1:
        if s.startswith("/-", j):
            depth += 1
            j += 2
        elif s.startswith("-/", j):
            depth -= 1
            j += 2
            if depth == 0:
                return j
        else:
            j += 1
    return len(s)


def strip_comments(s: str) -> str:
    """Remove ``/- … -/`` (nested) and ``-- …`` comments, outside string literals."""
    out: list[str] = []
    i, in_str = 0, False
    while i < len(s):
        c = s[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < len(s):
                out.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
        elif c == '"':
            in_str = True
            out.append(c)
            i += 1
        elif s.startswith("/-", i):
            i = _skip_block_comment(s, i)
            out.append(" ")
        elif s.startswith("--", i):
            while i < len(s) and s[i] != "\n":
                i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _skip_balanced(s: str, i: int) -> int:
    """``s[i]`` is an opening bracket; return the index just past its match."""
    depth, j, in_str = 0, i, False
    while j < len(s):
        c = s[j]
        if in_str:
            if c == "\\":
                j += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in _OPEN:
            depth += 1
        elif c in _CLOSE:
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    return len(s)


def _find_top_level(s: str, pred) -> int:
    """Index of the first depth-0 position where ``pred(s, i)`` holds, or -1."""
    depth, i, in_str = 0, 0, False
    while i < len(s):
        c = s[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c in _OPEN:
            depth += 1
        elif c in _CLOSE:
            depth = max(0, depth - 1)
        elif depth == 0 and pred(s, i):
            return i
        i += 1
    return -1


def _is_assign(s: str, i: int) -> bool:
    return s.startswith(":=", i)


def _is_type_colon(s: str, i: int) -> bool:
    return s[i] == ":" and not s.startswith(":=", i) and not s.startswith("::", i) and (
        i == 0 or s[i - 1] != ":"
    )


def to_type_str(source: str) -> tuple[str, str, str, str] | None:
    """Return ``(keyword, name, signature, type_str)`` for a theorem/lemma, else ``None``."""
    s = strip_comments(source).strip()
    while s.startswith("@["):
        s = s[_skip_balanced(s, 1):].strip()
    words = s.split(None, 1)
    while words and words[0] in _MODIFIERS:
        s = words[1] if len(words) > 1 else ""
        words = s.split(None, 1)
    if len(words) < 2 or words[0] not in ("theorem", "lemma"):
        return None
    keyword = words[0]
    m = _NAME_RE.match(words[1])
    if m is None:
        return None
    name, rest = m.group(1), " ".join(m.group(2).split())

    end = _find_top_level(rest, _is_assign)
    if end == -1:
        return None  # pattern-matching equations or a truncated scrape
    sig = rest[:end].strip()
    colon = _find_top_level(sig, _is_type_colon)
    if colon == -1:
        return None
    binders, body = sig[:colon].strip(), sig[colon + 1:].strip()
    if not body:
        return None
    return keyword, name, sig, f"∀ {binders}, {body}" if binders else body


def _project(blueprint_url: str) -> str:
    """``https://host/repo/blueprint/…`` → ``host/repo``."""
    parts = blueprint_url.split("/")
    return "/".join(parts[2:4]) if len(parts) > 3 else blueprint_url


def build_anchors(blueprints: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    anchors: list[dict[str, Any]] = []
    seen: set[str] = set()
    stats: Counter = Counter()
    for bp in blueprints:
        project = _project(bp["blueprint_url"])
        for th in bp["theorems"]:
            stats["declarations"] += 1
            parsed = to_type_str(th.get("highlighted") or "")
            if parsed is None:
                stats["not_a_theorem_or_unparsed"] += 1
                continue
            keyword, name, sig, type_str = parsed
            if type_str in seen:
                stats["duplicate"] += 1
                continue
            seen.add(type_str)
            anchors.append(
                {
                    "id": f"bp_{len(anchors):05d}",
                    "declaration": th.get("lean_decl") or name,
                    "module": project,
                    "pair_ids": [th["id"]] if th.get("id") else [],
                    "csv_rows": [],
                    "is_definition": False,
                    "raw_signature": f"{keyword} {name} {sig}",
                    "type_str": type_str,
                    "body": type_str,
                    "latex": th.get("LaTeX", ""),
                    "lean_url": th.get("lean_url", ""),
                }
            )
            stats["anchors"] += 1
    return anchors, stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    blueprints = json.loads(args.input.read_text(encoding="utf-8"))
    anchors, stats = build_anchors(blueprints)
    if not anchors:
        print("No theorem/lemma declarations could be parsed.", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for a in anchors:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")

    print(
        f"{stats['declarations']} declarations → {stats['anchors']} anchors "
        f"({stats['not_a_theorem_or_unparsed']} not theorem/lemma or unparsed, "
        f"{stats['duplicate']} duplicates) → {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
