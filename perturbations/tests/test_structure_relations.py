"""
Lean-free tests for the structure / relation / quantifier-flip transforms.

Every transform validates its candidate with ``compile_lean``; we patch that
per-module to a constant so the parsing/edit logic is exercised without Lean.
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.transforms import quantifiers, relations, structure  # noqa: E402


def _ok(module):
    return mock.patch.object(module, "compile_lean", return_value=True)


def _bad(module):
    return mock.patch.object(module, "compile_lean", return_value=False)


# ── structure.premise_permute ───────────────────────────────────────────────────

def test_premise_permute_swaps_first_two_antecedents() -> None:
    with _ok(structure):
        out = structure.premise_permute("sig", "∀ (a : ℕ), P a → Q a → R a")
    assert out is not None
    body = out[1].split(",", 1)[1]
    assert body.index("Q a") < body.index("P a")
    assert out[1].rstrip().endswith("R a")


def test_premise_permute_none_with_single_hypothesis() -> None:
    with _ok(structure):
        assert structure.premise_permute("sig", "∀ (a : ℕ), P a → R a") is None


# ── structure.implicit_explicit_toggle ──────────────────────────────────────────

def test_toggle_implicit_to_explicit() -> None:
    with _ok(structure):
        out = structure.implicit_explicit_toggle("sig", "∀ {α : Type*} (a : α), a = a")
    assert out == ("sig", "∀ (α : Type*) (a : α), a = a")


def test_toggle_explicit_to_implicit_when_no_implicit() -> None:
    with _ok(structure):
        out = structure.implicit_explicit_toggle("sig", "∀ (a : ℕ), a = a")
    assert out == ("sig", "∀ {a : ℕ}, a = a")


# ── relations ────────────────────────────────────────────────────────────────────

def test_strictness_swap() -> None:
    with _ok(relations):
        assert relations.strictness_swap("s", "∀ (a b : ℕ), a < b") == ("s", "∀ (a b : ℕ), a ≤ b")


def test_eq_to_le() -> None:
    with _ok(relations):
        assert relations.eq_to_le("s", "∀ (a b : ℕ), a = b") == ("s", "∀ (a b : ℕ), a ≤ b")


def test_connective_swap() -> None:
    with _ok(relations):
        assert relations.connective_swap("s", "P ∧ Q") == ("s", "P ∨ Q")


def test_arith_op_swap_ignores_type_star() -> None:
    # The `*` in `Type*` has no surrounding spaces, so the binary `+` is swapped.
    with _ok(relations):
        out = relations.arith_op_swap("s", "∀ {α : Type*} (a b : α), a + b = b + a")
    assert out == ("s", "∀ {α : Type*} (a b : α), a * b = b + a")


def test_const_to_zero_one() -> None:
    with _ok(relations):
        assert relations.const_to_zero_one("s", "∀ (a : ℕ), a = 5") == ("s", "∀ (a : ℕ), a = 0")
        assert relations.const_to_zero_one("s", "∀ (a : ℕ), a = 0") == ("s", "∀ (a : ℕ), a = 1")


def test_relations_return_none_when_no_target() -> None:
    with _ok(relations):
        assert relations.strictness_swap("s", "P ∧ Q") is None
        assert relations.const_to_zero_one("s", "∀ (a : ℕ), a = a") is None


def test_relations_return_none_when_oracle_rejects() -> None:
    with _bad(relations):
        assert relations.connective_swap("s", "P ∧ Q") is None


# ── quantifier-kind flips ────────────────────────────────────────────────────────

def test_forall_to_exists() -> None:
    with _ok(quantifiers):
        assert quantifiers.forall_to_exists("s", "∀ (n : ℕ), n ≥ 0") == ("s", "∃ (n : ℕ), n ≥ 0")


def test_forall_to_exists_skips_implicit_binders() -> None:
    # ∃ cannot bind {α : Type*}, so this must be skipped.
    with _ok(quantifiers):
        assert quantifiers.forall_to_exists("s", "∀ {α : Type*} (x : α), x = x") is None


def test_exists_to_forall() -> None:
    with _ok(quantifiers):
        assert quantifiers.exists_to_forall("s", "∃ n, n ≥ 0") == ("s", "∀ n, n ≥ 0")


if __name__ == "__main__":
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("\nAll structure/relation/quantifier-flip tests passed.")
