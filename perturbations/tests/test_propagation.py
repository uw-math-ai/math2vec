"""
test_propagation.py — symbolic truth propagation through perturbation paths.

These tests don't touch Lean: ``is_true`` and ``compose_truth`` work purely on
the registry's propagation tables.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.propagation import compose_truth, is_true  # noqa: E402


# ── is_true: walks a path, anchor defaults to "true" ─────────────────────────-

def test_empty_path_returns_anchor() -> None:
    assert is_true([]) == "true"
    assert is_true([], anchor_truth="false") == "false"
    assert is_true([], anchor_truth="unknown") == "unknown"


def test_single_negate_flips_truth() -> None:
    assert is_true(["negate"]) == "false"
    assert is_true(["negate"], anchor_truth="false") == "true"


def test_double_negate_recovers() -> None:
    # The propagation table is the source of truth; is_true walks it:
    #   true --negate--> false --negate--> true
    assert is_true(["negate", "negate"]) == "true"


def test_contrapose_is_equivalence_preserving() -> None:
    assert is_true(["contrapose"]) == "true"
    assert is_true(["contrapose", "contrapose"]) == "true"


def test_de_morgan_preserves_truth() -> None:
    assert is_true(["de_morgan_rewrite"]) == "true"
    assert is_true(["de_morgan_rewrite", "de_morgan_rewrite"]) == "true"


def test_inverse_yields_unknown() -> None:
    assert is_true(["inverse"]) == "unknown"


def test_quantifier_swap_yields_unknown() -> None:
    assert is_true(["quantifier_swap"]) == "unknown"


def test_unknown_perturbation_propagates_unknown() -> None:
    # Defensive: a typo'd name should degrade to "unknown" rather than crash.
    assert is_true(["this_is_not_a_real_perturbation"]) == "unknown"


def test_mixed_chain() -> None:
    # true --tc_weaken_hyp(unknown)--> unknown --negate(unknown→unknown)--> unknown
    assert is_true(["tc_weaken_hyp", "negate"]) == "unknown"


# ── compose_truth: pairwise combination of independent labels ───────────────-

def test_compose_truth_basic() -> None:
    assert compose_truth("true", "true") == "true"
    assert compose_truth("true", "unknown") == "unknown"
    assert compose_truth("unknown", "true") == "unknown"
    assert compose_truth("true", "false") == "false"


def test_compose_truth_double_false_yields_unknown() -> None:
    # The chain rule: two `false` steps may cancel (e.g. negate∘negate).
    assert compose_truth("false", "false") == "unknown"


def test_compose_truth_false_dominates_unknown() -> None:
    assert compose_truth("unknown", "false") == "false"
    assert compose_truth("false", "unknown") == "false"


def test_compose_truth_unknown_dominates_true() -> None:
    assert compose_truth("unknown", "unknown") == "unknown"


if __name__ == "__main__":
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("\nAll propagation tests passed.")


# ── apply_chain: labels come from the per-step rules, same as is_true ─────────

def _chain_truth(names: list[str]) -> str:
    from unittest import mock

    from wiggle import chains

    def fake(_sig: str, type_str: str) -> tuple[str, str]:
        return "sig", f"¬({type_str})"

    with mock.patch.dict(chains.TRANSFORMS, {n: fake for n in names}):
        record = chains.apply_chain(
            {"id": "t", "body": "P", "type_str": "P"}, names
        )
    assert record["chain_status"] == "ok"
    return record["is_true"]


def test_apply_chain_double_negate_is_true() -> None:
    assert _chain_truth(["negate", "negate"]) == "true"


def test_apply_chain_false_then_equivalence_stays_false() -> None:
    assert _chain_truth(["negate", "contrapose"]) == "false"


def test_apply_chain_agrees_with_is_true() -> None:
    for path in (["negate"], ["negate", "negate", "negate"], ["converse", "negate"]):
        assert _chain_truth(path) == is_true(path)
