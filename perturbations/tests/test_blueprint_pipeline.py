"""
Tests for the blueprint run: anchor extraction, the strict anchor filter and
resume in ``run_benchmark_review.py``, and the MTEB reranking data builder.
No Lean and no embedding model needed.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest import mock

_PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _PIPELINE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


prep = _load("prepare_blueprint_anchors")


class TestToTypeStr:
    def test_binders_become_forall(self) -> None:
        src = (
            "/-- Doc with := inside. -/\n@[simp]\ntheorem foo (x y : ℝ) (hx : 1 < x) :\n"
            "    Summable (fun n : ℕ => (n : ℝ) ^ (-x)) := by\n  sorry"
        )
        assert prep.to_type_str(src)[1:] == (
            "foo",
            "(x y : ℝ) (hx : 1 < x) : Summable (fun n : ℕ => (n : ℝ) ^ (-x))",
            "∀ (x y : ℝ) (hx : 1 < x), Summable (fun n : ℕ => (n : ℝ) ^ (-x))",
        )

    def test_no_binders_keeps_body(self) -> None:
        assert prep.to_type_str("lemma bar : 1 + 1 = 2 := rfl")[3] == "1 + 1 = 2"

    def test_modifiers_and_comments_stripped(self) -> None:
        src = "private theorem baz {n : ℕ} -- note: x\n : n = n := rfl"
        assert prep.to_type_str(src)[3] == "∀ {n : ℕ}, n = n"

    def test_colon_inside_binder_is_not_the_type_colon(self) -> None:
        src = "theorem q (f : ℕ → ℕ) (h : ∀ x : ℕ, f x = x) : f 0 = 0 := by simp [h]"
        assert prep.to_type_str(src)[3] == "∀ (f : ℕ → ℕ) (h : ∀ x : ℕ, f x = x), f 0 = 0"

    def test_named_argument_is_not_the_proof(self) -> None:
        src = "theorem r : foo (x := 1) = 1 := rfl"
        assert prep.to_type_str(src)[3] == "foo (x := 1) = 1"

    def test_definitions_are_rejected(self) -> None:
        assert prep.to_type_str("def f (n : ℕ) : ℕ := n") is None
        assert prep.to_type_str("instance : Inhabited ℕ := ⟨0⟩") is None


def test_build_anchors_dedupes_identical_statements() -> None:
    blueprints = [
        {"blueprint_url": "https://a.github.io/proj/blueprint/", "theorems": [
            {"id": "t1", "lean_decl": "A.x", "highlighted": "theorem x : 1 = 1 := rfl"},
            {"id": "t2", "lean_decl": "A.d", "highlighted": "def d : ℕ := 0"},
        ]},
        {"blueprint_url": "https://b.github.io/mirror/blueprint/", "theorems": [
            {"id": "t3", "lean_decl": "B.x", "highlighted": "theorem x : 1 = 1 := by rfl"},
        ]},
    ]
    anchors, stats = prep.build_anchors(blueprints)
    assert [a["declaration"] for a in anchors] == ["A.x"]
    assert anchors[0]["type_str"] == "1 = 1"
    assert anchors[0]["raw_signature"] == "theorem x : 1 = 1"
    assert stats["duplicate"] == 1


class TestStrictAnchorFilter:
    def test_check_disables_auto_implicit(self) -> None:
        review = _load("run_benchmark_review")
        with mock.patch("wiggle.lean_runner.run_lean", return_value="") as run:
            assert review.anchor_elaborates_closed("x = x") is True
        assert "set_option autoImplicit false in" in run.call_args[0][0]

    def test_noncompiling_anchor_skips_every_perturbation(self) -> None:
        review = _load("run_benchmark_review")
        anchor = {"id": "bp_1", "declaration": "d", "type_str": "projDef x = 1"}
        with mock.patch(
            "wiggle.lean_runner.run_lean",
            return_value="<stdin>:3:10: error: unknown identifier 'projDef'",
        ) as run:
            out = review.process_anchor(anchor, use_lean=True, skip_noncompiling=True)
        assert run.call_count == 1
        assert out["skipped"] is True and out["anchor_compiles"] is False
        assert out["results"] == []


def test_review_resume_only_processes_new_anchors(tmp_path: Path) -> None:
    anchors = tmp_path / "anchors.jsonl"
    anchors.write_text("".join(
        json.dumps({"id": f"bp_{i}", "declaration": f"d{i}", "module": "m",
                    "pair_ids": [], "csv_rows": [], "is_definition": False,
                    "raw_signature": f"theorem d{i} : P{i}", "type_str": f"P{i} ∧ Q{i}"}) + "\n"
        for i in range(3)
    ))
    out = tmp_path / "out"

    def run(limit: int, *extra: str) -> str:
        return subprocess.run(
            [sys.executable, str(_PIPELINE / "run_benchmark_review.py"),
             "--anchors-file", str(anchors), "--limit", str(limit), "--no-lean",
             "--num-workers", "1", "--out", str(out), *extra],
            check=True, capture_output=True, text=True,
        ).stdout

    run(2)
    first = (out / "anchors.jsonl").read_text().splitlines()
    assert len(first) == 2

    stdout = run(3, "--resume")
    assert "resuming: 2 anchors already done" in stdout
    assert stdout.count("[3/3]") == 1 and "[1/3]" not in stdout
    lines = (out / "anchors.jsonl").read_text().splitlines()
    assert lines[:2] == first and len(lines) == 3
    ids = {json.loads(l)["source_id"] for l in (out / "results.jsonl").read_text().splitlines()}
    assert ids == {"bp_0", "bp_1", "bp_2"}


def test_rerank_data_positives_are_equivalent_variants_only() -> None:
    mteb_eval = _load("mteb_perturbation_eval")

    def row(sid: str, pert: str, variant: str, status: str = "applied") -> dict:
        return {"source_id": sid, "original_type_str": f"anchor {sid}",
                "perturbation": pert, "variant": variant, "status": status}

    rows = [
        row("a", "alpha_rename", "v_eq"),          # equivalent → positive
        row("a", "negate", "v_neg"),               # contradictory → negative
        row("a", "eq_to_le", "v_graded"),          # graded → negative
        row("a", "flip_bound", "v_x", "lean_rejected"),
        row("a", "curry", "v_amb"),                # same text as a graded one:
        row("a", "connective_swap", "v_amb"),      #   ambiguous, dropped
        row("a", "premise_permute", "anchor a"),   # identical to anchor, dropped
        row("b", "negate", "only_neg"),            # no positive → no query
        row("c", "curry", "only_pos"),             # no negative → no query
    ]
    data = mteb_eval.build_rerank_data(rows)
    assert list(data["queries"]) == ["a"]
    assert data["relevant_docs"]["a"] == {
        "a::alpha_rename": 1, "a::negate": 0, "a::eq_to_le": 0,
    }
    assert sorted(data["top_ranked"]["a"]) == sorted(data["relevant_docs"]["a"])
    s = data["stats"]
    assert (s["ambiguous_variants"], s["skipped_no_positive"], s["skipped_no_negative"]) == (1, 1, 1)
