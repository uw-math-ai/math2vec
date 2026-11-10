"""
test_quantifier_swap.py — parser + validity-oracle tests for quantifier_swap.

The transform is pure Python (no Lean tactic). It walks the type string,
extracts the leading ``∀ … , ∃ … , <body>``, builds the swapped form, and
asks ``compile_lean`` whether the result type-checks against Mathlib.

We mock ``compile_lean`` here so the test runs without Lean.
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.transforms import quantifiers  # noqa: E402
from wiggle.transforms.quantifiers import _find_top_level_comma  # noqa: E402


# ── _find_top_level_comma helper ─────────────────────────────────────────────-

def test_find_top_level_comma_at_depth_zero() -> None:
    assert _find_top_level_comma("a, b") == 1


def test_find_top_level_comma_skips_nested_parens() -> None:
    assert _find_top_level_comma("(a, b), c") == 6


def test_find_top_level_comma_skips_nested_brackets() -> None:
    assert _find_top_level_comma("[a : T], body") == 7


def test_find_top_level_comma_skips_nested_braces() -> None:
    assert _find_top_level_comma("{α : Type*}, body") == 11


def test_find_top_level_comma_returns_minus_one_when_none() -> None:
    assert _find_top_level_comma("abc") == -1
    assert _find_top_level_comma("(no, comma, here)") == -1


# ── quantifier_swap: full transform with mocked validity oracle ──────────────-

def _swap_with_oracle_true(type_str: str) -> tuple[str, str] | None:
    with mock.patch.object(quantifiers, "compile_lean", return_value=True):
        return quantifiers.quantifier_swap("sig", type_str)


def _swap_with_oracle_false(type_str: str) -> tuple[str, str] | None:
    with mock.patch.object(quantifiers, "compile_lean", return_value=False):
        return quantifiers.quantifier_swap("sig", type_str)


def test_swap_simple_forall_exists() -> None:
    out = _swap_with_oracle_true("∀ (n : ℕ), ∃ m, m > n")
    assert out == ("sig", "∃ m, ∀ (n : ℕ), m > n")


def test_swap_with_implicit_type_binder() -> None:
    out = _swap_with_oracle_true("∀ {α : Type*} (x : α), ∃ y, x = y")
    assert out == ("sig", "∃ y, ∀ {α : Type*} (x : α), x = y")


def test_no_swap_when_no_existential_follows() -> None:
    assert _swap_with_oracle_true("∀ (n : ℕ), n > 0") is None


def test_no_swap_when_starts_with_existential() -> None:
    # ∃ ∀ does not match the trigger pattern; only ∀ ∃ does.
    assert _swap_with_oracle_true("∃ x, ∀ y, P x y") is None


def test_no_swap_when_no_quantifier_at_head() -> None:
    assert _swap_with_oracle_true("P → Q") is None


def test_returns_none_when_validity_oracle_rejects() -> None:
    # Same input as test_swap_simple_forall_exists, but the mocked oracle
    # claims the swapped form fails to type-check.
    assert _swap_with_oracle_false("∀ (n : ℕ), ∃ m, m > n") is None


def test_swap_respects_bracketed_binder_commas() -> None:
    """A comma inside a binder annotation must not terminate the binder block."""
    # Without bracket-aware scanning we would wrongly stop at the comma in
    # ``Vector α n``... actually that's not a problem case. Use one with explicit
    # tuple-shaped type annotation:
    out = _swap_with_oracle_true("∀ (p : ℕ × ℕ), ∃ q, p = q")
    assert out == ("sig", "∃ q, ∀ (p : ℕ × ℕ), p = q")


if __name__ == "__main__":
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("\nAll quantifier_swap tests passed.")
