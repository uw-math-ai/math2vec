"""
Lean-free tests for the tactic-backed connective transforms: curry, uncurry,
and definitional_unfold. Each is a thin wrapper over ``extract_goal`` with a
specific Wiggle.lean tactic name; we mock ``extract_goal`` and check both the
tactic dispatch and the shared no-op detection.
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.transforms import connectives  # noqa: E402


def test_curry_dispatches_correct_tactic() -> None:
    fake = ("theorem t.extracted_1 : P → Q → R", "P → Q → R")
    with mock.patch.object(connectives, "extract_goal", return_value=fake) as eg:
        out = connectives.curry("sig", "(P ∧ Q) → R")
    eg.assert_called_once_with("curry", "(P ∧ Q) → R")
    assert out == fake


def test_uncurry_dispatches_correct_tactic() -> None:
    fake = ("theorem t.extracted_1 : (P ∧ Q) → R", "(P ∧ Q) → R")
    with mock.patch.object(connectives, "extract_goal", return_value=fake) as eg:
        out = connectives.uncurry("sig", "P → Q → R")
    eg.assert_called_once_with("uncurry", "P → Q → R")
    assert out == fake


def test_definitional_unfold_dispatches_correct_tactic() -> None:
    fake = ("theorem t.extracted_1 : ∀ a b, f a = f b → a = b", "∀ a b, f a = f b → a = b")
    with mock.patch.object(connectives, "extract_goal", return_value=fake) as eg:
        out = connectives.definitional_unfold("sig", "Function.Injective f")
    eg.assert_called_once_with("unfold_defs", "Function.Injective f")
    assert out == fake


def test_returns_none_on_lean_failure() -> None:
    with mock.patch.object(connectives, "extract_goal", return_value=None):
        assert connectives.curry("sig", "P → Q") is None
        assert connectives.uncurry("sig", "P → Q") is None
        assert connectives.definitional_unfold("sig", "P") is None


def test_returns_none_on_noop_unchanged_goal() -> None:
    same = "P → Q → R"
    fake = ("theorem t.extracted_1 : P → Q → R", " P → Q → R ")  # whitespace-only diff
    with mock.patch.object(connectives, "extract_goal", return_value=fake):
        assert connectives.curry("sig", same) is None


if __name__ == "__main__":
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("\nAll connective-extra tests passed.")
