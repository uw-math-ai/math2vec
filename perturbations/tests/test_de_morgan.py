"""
test_de_morgan.py — unit test the `de_morgan_rewrite` Python wrapper.

The most interesting behaviour to test in isolation is the **no-op
detection**: ``simp only [...]`` is allowed to leave the goal unchanged, in
which case we don't want to emit a dataset record.
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.transforms import connectives  # noqa: E402


def test_de_morgan_calls_extract_goal_with_correct_tactic_name() -> None:
    fake = ("theorem ... extracted_1_1 : ¬a ∨ b", "¬a ∨ b")
    with mock.patch.object(connectives, "extract_goal", return_value=fake) as eg:
        out = connectives.de_morgan_rewrite("sig", "a → b")
    eg.assert_called_once_with("de_morgan_rewrite", "a → b")
    assert out == fake


def test_de_morgan_returns_none_on_lean_failure() -> None:
    with mock.patch.object(connectives, "extract_goal", return_value=None):
        assert connectives.de_morgan_rewrite("sig", "a → b") is None


def test_de_morgan_returns_none_when_output_equals_input_type() -> None:
    """If simp made no progress, ``extract_goal`` may echo the input back.

    The wrapper must detect this so the chain runner sees a stop, not a
    duplicate record.
    """
    same_type = "P ∧ Q"
    fake_noop = ("theorem ... extracted_1_1 : P ∧ Q", same_type)
    with mock.patch.object(connectives, "extract_goal", return_value=fake_noop):
        assert connectives.de_morgan_rewrite("sig", same_type) is None


def test_de_morgan_returns_none_when_whitespace_only_change() -> None:
    """Whitespace-only differences are also no-ops."""
    fake = ("theorem ... extracted_1_1 : P ∧ Q", " P ∧ Q ")
    with mock.patch.object(connectives, "extract_goal", return_value=fake):
        assert connectives.de_morgan_rewrite("sig", "P ∧ Q") is None


if __name__ == "__main__":
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("\nAll de_morgan-wrapper tests passed.")
