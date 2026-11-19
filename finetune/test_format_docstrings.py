"""
Offline unit tests for format_docstrings.py and the scoring in validate_docstrings.py.
No model or network needed.

    python -m pytest finetune/test_format_docstrings.py -q
"""
from __future__ import annotations

import json
import sys
import types
from argparse import Namespace

import numpy as np
import pytest

from format_docstrings import (
    attach_docstring,
    build_record,
    check_record,
    docstring_text,
    escape_comment_delims,
    format_docstring,
    strip_docstrings,
)
from validate_docstrings import gold_ranks, metrics_from_ranks, run_model, sample_records

LEAN = (
    "import Mathlib\nimport Aesop\n\nset_option maxHeartbeats 400000\n\n"
    "open BigOperators Real Nat\n\n"
    "theorem mathd_algebra_10 (x : ℝ) (h : 2 * x + 3 = 7) : x = 2 := by sorry"
)
OK_COMPILE = {"messages": [{"severity": "warning", "data": "declaration uses 'sorry'"}]}


def row(i, stmt, lean=LEAN, compile_result=OK_COMPILE):
    return {"id": f"r{i}", "statement": stmt, "lean_code": lean, "compile_result": compile_result,
            "difficulty": 2, "domain": ["Algebra"], "source": "test"}


# ---- format_docstring -------------------------------------------------------
def test_short_statement_is_one_line():
    assert format_docstring("Solve  $2x+3=7$ for $x$.  ") == "/-- Solve $2x+3=7$ for $x$. -/"


def test_long_statement_puts_close_on_own_line():
    doc = format_docstring("word " * 40)
    assert doc.startswith("/-- word") and doc.endswith("\n-/")


def test_multiline_keeps_paragraphs_and_normalises_crlf():
    doc = format_docstring("First line.\r\n\r\n\r\n\r\nSecond   line.  ")
    assert doc == "/-- First line.\n\nSecond line.\n-/"


def test_comment_delimiters_are_escaped():
    doc = format_docstring("Compute $1/-2$ and $a-/b$ and /-/ here.")
    inner = docstring_text(doc)
    assert "/-" not in inner and "-/" not in inner


def test_idempotent_on_existing_docstring():
    once = format_docstring("Show that $x = 2$.")
    assert format_docstring(once) == once


def test_empty_returns_none():
    assert format_docstring("  \n ") is None


def test_wrap_breaks_long_lines_without_changing_words():
    text = "Let $f(x) = x^2$ " * 15
    doc = format_docstring(text, wrap=60)
    assert all(len(ln) <= 64 for ln in docstring_text(doc).split("\n"))
    assert docstring_text(doc).split() == text.split()


def test_escape_handles_overlapping():
    assert "/-" not in escape_comment_delims("/-/-/") and "-/" not in escape_comment_delims("/-/-/")


# ---- attach / strip ---------------------------------------------------------
def test_attach_goes_after_header_before_theorem():
    doc = "/-- Show that $x = 2$. -/"
    out = attach_docstring(LEAN, doc)
    assert "open BigOperators Real Nat\n\n/-- Show that $x = 2$. -/\ntheorem mathd_algebra_10" in out
    assert strip_docstrings(out) == strip_docstrings(LEAN)


def test_attach_replaces_existing_docstring():
    lean = LEAN.replace("theorem", "/-- old doc -/\ntheorem")
    out = attach_docstring(lean, "/-- new -/")
    assert "old doc" not in out and out.count("/--") == 1


def test_attach_before_attributes():
    lean = "import Mathlib\n\n@[simp] theorem foo : 1 = 1 := by sorry"
    assert attach_docstring(lean, "/-- d -/").endswith("/-- d -/\n@[simp] theorem foo : 1 = 1 := by sorry")


def test_attach_no_declaration():
    assert attach_docstring("import Mathlib\n-- nothing here", "/-- d -/") is None


# ---- build_record / check_record --------------------------------------------
def test_build_record_passes_checks():
    rec, reason = build_record(row(0, "If $2x + 3 = 7$, show that $x = 2$."))
    assert reason is None and check_record(rec) == []


def test_check_record_catches_broken_record():
    rec, _ = build_record(row(0, "If $2x + 3 = 7$, show that $x = 2$."))
    rec["lean_with_docstring"] = rec["lean_with_docstring"].replace("theorem", "-- moved\ntheorem")
    assert "docstring_not_above_declaration" in check_record(rec)


# ---- sampling ---------------------------------------------------------------
def test_sampling_dedupes_and_filters(tmp_path):
    rows = [row(i, f"Statement number {i}.", lean=LEAN.replace("10", str(i))) for i in range(8)]
    rows.append(row(99, "Statement number 1.", lean=LEAN.replace("10", "999")))  # dup statement
    rows.append(row(98, "Bad.", compile_result={"messages": [{"severity": "error"}]}))
    p = tmp_path / "s.jsonl"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    args = Namespace(local=str(p), n=100, seed=1, max_scan=1000, keep_uncompiled=False, wrap=0)
    recs, stats = sample_records(args)
    assert len(recs) == 8 and stats["drop_duplicate"] == 1 and stats["drop_compile_error"] == 1


# ---- scoring ----------------------------------------------------------------
def test_gold_ranks_and_metrics():
    q = np.eye(4, dtype=np.float32)
    d = np.eye(4, dtype=np.float32)
    d[[2, 3]] = d[[3, 2]]  # queries 2 and 3 now rank their gold 2nd
    ranks, _ = gold_ranks(q, d)
    assert ranks.tolist() == [0, 0, 1, 1]
    m = metrics_from_ranks(ranks, ks=(1, 5), mrr_k=10)
    assert m["recall@1"] == 0.5 and m["recall@5"] == 1.0 and m["mrr@10"] == pytest.approx(0.75)


def test_run_model_end_to_end_with_fake_encoder(monkeypatch):
    """Bag-of-characters fake encoder: checks wiring, not model quality."""
    class FakeST:
        def __init__(self, *a, **k):
            self.max_seq_length = 0

        def encode(self, texts, **k):
            v = np.array([[t.count(c) for c in "0123456789xyz"] for t in texts], dtype=np.float32) + 1e-3
            return v / np.linalg.norm(v, axis=1, keepdims=True)

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeST))
    recs = [build_record(row(i, f"Show {i}{i}{i} = {i}.", lean=LEAN.replace("x = 2", f"x = {i}{i}{i}")))[0]
            for i in range(1, 6)]
    args = Namespace(model_name="fake", device=None, max_seq_len=128, wrap_query=True,
                     instruction="i", batch_size=4)
    results, per_query = run_model(recs, args)
    assert len(per_query) == 5 and set(results) >= {"formatted", "raw_statement"}
    assert 0.0 <= results["formatted"]["recall@10"] <= 1.0
