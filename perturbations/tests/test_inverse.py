"""
test_inverse.py — unit test the `inverse` Python wrapper.

The Lean macro itself is exercised by ``pipeline/run_demo.py``; here we only
test the wrapper layer by mocking ``extract_goal``. This way the test runs in
milliseconds and doesn't require ``lake env lean``.
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.transforms import logical  # noqa: E402


FAKE_GOAL = (
    "theorem wiggle_demo.extracted_1_1 : ¬(n ≠ 0) → ¬(n > 0)",
    "¬(n ≠ 0) → ¬(n > 0)",
)


def test_inverse_calls_extract_goal_with_correct_tactic_name() -> None:
    with mock.patch.object(logical, "extract_goal", return_value=FAKE_GOAL) as eg:
        out = logical.inverse("sig", "∀ (n : ℕ), n ≠ 0 → n > 0")
    eg.assert_called_once_with("inverse", "∀ (n : ℕ), n ≠ 0 → n > 0")
    assert out == FAKE_GOAL


def test_inverse_returns_none_when_extract_goal_fails() -> None:
    with mock.patch.object(logical, "extract_goal", return_value=None):
        assert logical.inverse("sig", "anything") is None


if __name__ == "__main__":
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("\nAll inverse-wrapper tests passed.")
