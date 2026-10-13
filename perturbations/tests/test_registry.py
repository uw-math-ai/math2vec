"""
test_registry.py — invariants of the canonical perturbation list.

The registry asserts most of these at import time, but we re-check here so a
failure produces a readable pytest message rather than a bare ``AssertionError``
deep in the import chain.

Run standalone with ``python tests/test_registry.py`` or via pytest.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.registry import (  # noqa: E402
    PERTURBATIONS,
    PROPAGATION_RULES,
    TRANSFORMS,
    Perturbation,
)


EXPECTED_NAMES = {
    # Logical
    "negate", "contrapose", "converse", "inverse", "drop_unused_hyp",
    # Connectives
    "de_morgan_rewrite", "curry", "uncurry", "definitional_unfold",
    # Quantifiers
    "quantifier_swap", "forall_to_exists", "exists_to_forall",
    # Typeclass
    "tc_weaken_hyp", "tc_strengthen_hyp", "tc_strengthen_conc", "tc_weaken_conc",
    "tc_sibling_swap", "specialize_type",
    # Bounds
    "flip_bound", "bound_tighter",
    # Structure
    "alpha_rename", "premise_permute", "implicit_explicit_toggle",
    # Relation
    "strictness_swap", "eq_to_le", "connective_swap", "arith_op_swap",
    "const_to_zero_one",
}


def test_expected_names_match_registry() -> None:
    assert {p.name for p in PERTURBATIONS} == EXPECTED_NAMES


def test_no_duplicate_names() -> None:
    names = [p.name for p in PERTURBATIONS]
    assert len(names) == len(set(names))


def test_transforms_and_rules_views_are_consistent() -> None:
    assert set(TRANSFORMS) == set(PROPAGATION_RULES)
    assert set(TRANSFORMS) == {p.name for p in PERTURBATIONS}


def test_every_entry_has_total_propagation() -> None:
    for p in PERTURBATIONS:
        assert set(p.propagation.keys()) == {"true", "false", "unknown"}, p.name
        assert set(p.propagation.values()) <= {"true", "false", "unknown"}, p.name


def test_every_layer_is_valid() -> None:
    valid_layers = {
        "logical", "connective", "quantifier", "typeclass", "bounds",
        "structure", "relation",
    }
    for p in PERTURBATIONS:
        assert p.layer in valid_layers, f"{p.name} has unknown layer {p.layer!r}"


def test_every_transform_is_callable() -> None:
    for p in PERTURBATIONS:
        assert callable(p.fn), p.name


def test_perturbation_is_frozen() -> None:
    """Sanity check on the @dataclass(frozen=True) declaration."""
    p = PERTURBATIONS[0]
    try:
        p.name = "modified"  # type: ignore[misc]
    except Exception as e:
        assert "frozen" in str(e).lower() or "cannot" in str(e).lower(), str(e)
    else:
        raise AssertionError("Perturbation should be frozen but allowed mutation")


def test_truth_table_for_known_perturbations() -> None:
    """Spot-check a few well-known truth-propagation entries."""
    by_name = {p.name: p for p in PERTURBATIONS}
    # negate: true -> false
    assert by_name["negate"].propagation["true"] == "false"
    # contrapose: true -> true (equivalence-preserving)
    assert by_name["contrapose"].propagation["true"] == "true"
    # de_morgan_rewrite: true -> true (equivalence-preserving)
    assert by_name["de_morgan_rewrite"].propagation["true"] == "true"
    # quantifier_swap: true -> unknown
    assert by_name["quantifier_swap"].propagation["true"] == "unknown"
    # inverse: true -> unknown (equivalent to converse, not original)
    assert by_name["inverse"].propagation["true"] == "unknown"


if __name__ == "__main__":
    # Run every test_* function in this module.
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print(f"\nAll registry tests passed ({len(PERTURBATIONS)} perturbations registered).")
