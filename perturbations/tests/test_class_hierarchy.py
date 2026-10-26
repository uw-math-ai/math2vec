"""
test_class_hierarchy.py — the data-driven typeclass hierarchy loader.

These tests are Lean-free. They point ``typeclass_mutate`` at a synthetic
``class_hierarchy.jsonl`` via the ``WIGGLE_CLASS_HIERARCHY`` env override and
verify parent/child/ancestor/descendant lookups, short-name handling, and the
``is_known_class`` membership test. The ``@lru_cache`` on ``_load_hierarchy``
is cleared in the fixture so each test sees its own file.

A final test runs against the real, checked-in ``data/class_hierarchy.jsonl``
to guard against the dump going missing or the schema drifting.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import typeclass_mutate as tm  # noqa: E402


# A tiny hand-built hierarchy:
#
#     Monoid
#       └─ CommMonoid
#            └─ CommGroup        (CommGroup also extends Group)
#       └─ Group
#            └─ CommGroup
#
#     IsCancelMulZero, Nontrivial
#       └─ IsDomain              (a Prop-valued class, same table)
#
# Names are written fully-qualified on purpose to exercise short-name folding.
_SYNTHETIC = [
    {"name": "Monoid", "parents": []},
    {"name": "Mathlib.Algebra.CommMonoid", "parents": ["Monoid"]},
    {"name": "Group", "parents": ["Monoid"]},
    {"name": "CommGroup", "parents": ["Mathlib.Algebra.CommMonoid", "Group"]},
    {"name": "IsDomain", "parents": ["IsCancelMulZero", "Nontrivial"]},
]


@pytest.fixture
def synthetic_hierarchy(tmp_path, monkeypatch):
    """Write the synthetic table to a temp file and point the loader at it."""
    path = tmp_path / "class_hierarchy.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for row in _SYNTHETIC:
            f.write(json.dumps(row) + "\n")
    monkeypatch.setenv("WIGGLE_CLASS_HIERARCHY", str(path))
    tm._load_hierarchy.cache_clear()
    yield path
    tm._load_hierarchy.cache_clear()


# ── short-name helper ─────────────────────────────────────────────────────────

def test_short_name_strips_namespace() -> None:
    assert tm._short_name("Mathlib.Algebra.Field") == "Field"
    assert tm._short_name("Field") == "Field"
    assert tm._short_name("A.B.C.D") == "D"


# ── parents / children ─────────────────────────────────────────────────────────

def test_parents_use_short_names(synthetic_hierarchy) -> None:
    # CommGroup's parents were given fully-qualified; we read them back short.
    assert tm.get_parents("CommGroup", use_lean=False) == ["CommMonoid", "Group"]


def test_children_are_reverse_edges(synthetic_hierarchy) -> None:
    assert tm.get_children("Monoid") == ["CommMonoid", "Group"]
    assert tm.get_children("Group") == ["CommGroup"]


def test_leaf_has_no_children(synthetic_hierarchy) -> None:
    assert tm.get_children("CommGroup") == []


def test_root_has_no_parents(synthetic_hierarchy) -> None:
    assert tm.get_parents("Monoid", use_lean=False) == []


def test_qualified_lookup_matches_short(synthetic_hierarchy) -> None:
    # Looking up by a fully-qualified name folds to the short key.
    assert tm.get_parents("Mathlib.Algebra.CommMonoid", use_lean=False) == ["Monoid"]


# ── ancestors / descendants (BFS) ──────────────────────────────────────────────

def test_ancestors_walk_multiple_levels(synthetic_hierarchy) -> None:
    anc = tm.get_ancestors("CommGroup", depth=2)
    assert set(anc) == {"CommMonoid", "Group", "Monoid"}


def test_descendants_walk_multiple_levels(synthetic_hierarchy) -> None:
    desc = tm.get_descendants("Monoid", depth=2)
    assert set(desc) == {"CommMonoid", "Group", "CommGroup"}


def test_ancestors_respect_depth_limit(synthetic_hierarchy) -> None:
    # Depth 1 from CommGroup reaches only direct parents, not Monoid.
    assert set(tm.get_ancestors("CommGroup", depth=1)) == {"CommMonoid", "Group"}


# ── membership ─────────────────────────────────────────────────────────────────

def test_is_known_class(synthetic_hierarchy) -> None:
    assert tm.is_known_class("CommGroup")
    assert tm.is_known_class("Mathlib.Algebra.CommGroup")  # qualified
    assert tm.is_known_class("Monoid")
    # A parent named only inside an edge is still a known class.
    assert tm.is_known_class("IsCancelMulZero")
    assert not tm.is_known_class("Polynomial")
    assert not tm.is_known_class("NotAClass")


def test_prop_class_shares_the_same_table(synthetic_hierarchy) -> None:
    # IsDomain is Prop-valued but lives in the unified hierarchy.
    assert tm.get_parents("IsDomain", use_lean=False) == ["IsCancelMulZero", "Nontrivial"]
    assert tm.is_known_class("IsDomain")


# ── robustness ─────────────────────────────────────────────────────────────────

def test_missing_file_yields_empty_maps(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WIGGLE_CLASS_HIERARCHY", str(tmp_path / "does_not_exist.jsonl"))
    tm._load_hierarchy.cache_clear()
    try:
        parents, children = tm._load_hierarchy()
        assert parents == {}
        assert children == {}
        # get_children never hits Lean, so it's safe to assert here.
        assert tm.get_children("Field") == []
        assert not tm.is_known_class("Field")
    finally:
        tm._load_hierarchy.cache_clear()


def test_corrupt_lines_are_skipped(tmp_path, monkeypatch) -> None:
    path = tmp_path / "class_hierarchy.jsonl"
    path.write_text(
        '{"name": "Group", "parents": ["Monoid"]}\n'
        "this is not json\n"
        "\n"
        '{"name": "Monoid", "parents": []}\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("WIGGLE_CLASS_HIERARCHY", str(path))
    tm._load_hierarchy.cache_clear()
    try:
        assert tm.get_parents("Group", use_lean=False) == ["Monoid"]
        assert tm.get_children("Monoid") == ["Group"]
    finally:
        tm._load_hierarchy.cache_clear()


# ── the real, checked-in dump ───────────────────────────────────────────────────

def test_real_dump_present_and_sane() -> None:
    """The committed data/class_hierarchy.jsonl exists and has real edges."""
    tm._load_hierarchy.cache_clear()
    try:
        parents, children = tm._load_hierarchy()
        # The dump should cover far more than the old ~60 hardcoded classes.
        assert len(parents) > 500
        # Well-known algebra edges that must survive any Mathlib version.
        assert "CommRing" in tm.get_parents("Field", use_lean=False)
        assert "Field" in tm.get_children("CommRing")
        assert tm.is_known_class("AddCommMonoid")
    finally:
        tm._load_hierarchy.cache_clear()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
