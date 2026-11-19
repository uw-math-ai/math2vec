#!/usr/bin/env python3
"""
format_docstrings.py  --  turn FineLeanCorpus statements into Lean 4 docstrings.

For every row of m-a-p/FineLeanCorpus this produces:

    docstring            `/-- <cleaned English + inline LaTeX statement> -/`
    lean_with_docstring  the row's lean_code with that docstring placed directly
                         above the first declaration (after imports / opens /
                         set_option), replacing any docstring already there
    lean_code            the original Lean, unchanged

Formatting rules (see format_docstring):
  * CRLF -> LF, trailing whitespace stripped, 3+ blank lines -> 1 blank line
  * runs of spaces/tabs inside a line collapsed to one space
  * an existing `/-- ... -/` or `/-! ... -/` wrapper is removed first (idempotent)
  * `/-` and `-/` inside the text are broken up (`/ -`, `- /`): Lean block
    comments nest and end at `-/`, so either would corrupt the docstring
  * short text -> one line `/-- text -/`; long or multi-line text -> the closing
    `-/` goes on its own line, as in Mathlib
  * optional hard wrap (--wrap N). Off by default so the text the embedder sees
    is the statement itself, not a re-flowed copy.

Reuses the loader, compile filter and Lean header splitter from
prepare_fineleancorpus.py so both scripts agree on what a "row" is.

Usage
    python format_docstrings.py --limit 1000 --out data/fineleancorpus_docstrings.jsonl
    python format_docstrings.py --local sample.jsonl --out /tmp/docstrings.jsonl  # offline
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from collections import Counter
from pathlib import Path
from typing import Optional

from prepare_fineleancorpus import (
    DECL_RE,
    clean_text,
    compiled_ok,
    iter_rows,
    split_header,
)

DOC_OPEN = "/--"
DOC_CLOSE = "-/"
DEFAULT_ONE_LINE_WIDTH = 100

_WRAPPER_RE = re.compile(r"^\s*/-[-!]\s*(.*?)\s*-/\s*$", re.S)
# a docstring sitting at the very end of the header, right before the declaration
_TRAILING_DOC_RE = re.compile(r"/--(?:(?!-/).)*-/\s*$", re.S)
_ANY_DOC_RE = re.compile(r"/--(?:(?!-/).)*-/[ \t]*\n?", re.S)
_INLINE_WS_RE = re.compile(r"[ \t\f\v]+")


# --------------------------------------------------------------------------- #
# Text -> docstring
# --------------------------------------------------------------------------- #
def normalize_statement(text: str) -> str:
    """Whitespace/line-ending normalisation shared by the formatter and the
    round-trip check. Does not touch the mathematical content."""
    m = _WRAPPER_RE.match(text or "")
    if m:
        text = m.group(1)
    text = clean_text(text)
    lines = [_INLINE_WS_RE.sub(" ", ln).strip() for ln in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def escape_comment_delims(text: str) -> str:
    """Break up `/-` and `-/` so they cannot open/close a Lean block comment."""
    # loop: "/-/" contains both, and one pass can create a new match
    prev = None
    while prev != text:
        prev = text
        text = text.replace("-/", "- /").replace("/-", "/ -")
    return text


def format_docstring(
    statement: str,
    *,
    wrap: int = 0,
    one_line_width: int = DEFAULT_ONE_LINE_WIDTH,
) -> Optional[str]:
    """Return a Lean doc comment for `statement`, or None if it is empty."""
    body = escape_comment_delims(normalize_statement(statement))
    if not body:
        return None
    if wrap and wrap > 0:
        paras = body.split("\n\n")
        body = "\n\n".join(
            "\n".join(
                textwrap.fill(ln, width=wrap, break_long_words=False, break_on_hyphens=False)
                for ln in p.split("\n")
            )
            for p in paras
        )
    one_line = f"{DOC_OPEN} {body} {DOC_CLOSE}"
    if "\n" not in body and len(one_line) <= one_line_width:
        return one_line
    return f"{DOC_OPEN} {body}\n{DOC_CLOSE}"


def docstring_text(doc: str) -> str:
    """Inverse of format_docstring: the text inside `/-- ... -/`."""
    m = _WRAPPER_RE.match(doc or "")
    return (m.group(1) if m else (doc or "")).strip()


# --------------------------------------------------------------------------- #
# Docstring <-> Lean code
# --------------------------------------------------------------------------- #
def attach_docstring(lean: str, doc: str) -> Optional[str]:
    """Place `doc` directly above the first declaration in `lean`.
    Any docstring already directly above it is replaced. Returns None if no
    declaration is found."""
    header, body, _ = split_header(lean)
    if body is None:
        return None
    header = _TRAILING_DOC_RE.sub("", header).rstrip()
    return (header + "\n\n" if header else "") + doc + "\n" + body


def strip_docstrings(lean: str) -> str:
    """Remove every `/-- ... -/` doc comment (used to build doc-free Lean)."""
    out = _ANY_DOC_RE.sub("", lean or "")
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def check_record(rec: dict) -> list[str]:
    """Structural checks for one formatted record. Empty list == OK."""
    problems = []
    doc, lean_doc = rec.get("docstring") or "", rec.get("lean_with_docstring") or ""
    if not doc.startswith(DOC_OPEN + " ") or not doc.endswith(DOC_CLOSE):
        problems.append("docstring_not_wrapped")
    inner = docstring_text(doc)
    if "/-" in inner or "-/" in inner:
        problems.append("unescaped_comment_delimiter")
    expected = escape_comment_delims(normalize_statement(rec.get("statement") or ""))
    if " ".join(inner.split()) != " ".join(expected.split()):
        problems.append("roundtrip_mismatch")
    if lean_doc.count(DOC_OPEN) != 1:
        problems.append("lean_docstring_count_not_1")
    i = lean_doc.find(doc)
    if i < 0:
        problems.append("docstring_missing_from_lean")
    else:
        after = lean_doc[i + len(doc):].lstrip("\n")
        if not DECL_RE.match(after):
            problems.append("docstring_not_above_declaration")
    if strip_docstrings(lean_doc) != strip_docstrings(rec.get("lean_code") or ""):
        problems.append("lean_code_changed")
    return problems


def build_record(row: dict, *, wrap: int = 0, row_index: int = 0) -> tuple[Optional[dict], Optional[str]]:
    """-> (record, drop_reason)."""
    stmt = clean_text(row.get("statement") or "")
    lean = clean_text(row.get("lean_code") or "")
    if not stmt or not lean:
        return None, "drop_empty"
    doc = format_docstring(stmt, wrap=wrap)
    if doc is None:
        return None, "drop_empty"
    lean_doc = attach_docstring(lean, doc)
    if lean_doc is None:
        return None, "drop_no_declaration"
    return {
        "id": str(row.get("id") or f"row-{row_index}"),
        "statement": stmt,
        "docstring": doc,
        "lean_code": lean,
        "lean_with_docstring": lean_doc,
        "source": row.get("source"),
        "difficulty": row.get("difficulty"),
        "domain": row.get("domain"),
    }, None


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="m-a-p/FineLeanCorpus")
    ap.add_argument("--local", help="local .jsonl or .parquet instead of the HF hub")
    ap.add_argument("--streaming", action="store_true")
    ap.add_argument("--out", default="data/fineleancorpus_docstrings.jsonl")
    ap.add_argument("--wrap", type=int, default=0, help="hard-wrap docstring text at N columns (0 = off)")
    ap.add_argument("--limit", type=int, default=0, help="stop after N input rows")
    ap.add_argument("--keep_uncompiled", action="store_true", help="don't filter on compile_result errors")
    args = ap.parse_args()

    stats = Counter()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for i, row in enumerate(iter_rows(args)):
            if args.limit and i >= args.limit:
                break
            stats["input_rows"] += 1
            if not args.keep_uncompiled and not compiled_ok(row.get("compile_result")):
                stats["drop_compile_error"] += 1
                continue
            rec, reason = build_record(row, wrap=args.wrap, row_index=i)
            if rec is None:
                stats[reason] += 1
                continue
            for p in check_record(rec):
                stats[f"check_{p}"] += 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            stats["written"] += 1
    print(json.dumps(dict(stats), indent=2))
    print(f"\nWrote {out}")
    if any(k.startswith("check_") for k in stats):
        sys.exit("Some records failed structural checks (see check_* counts above).")


if __name__ == "__main__":
    main()
