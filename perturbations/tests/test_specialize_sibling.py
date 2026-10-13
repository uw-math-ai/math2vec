"""
Lean-free tests for specialize_type and sibling_typeclass in typeclass_mutate.

The Lean compile oracle (``_compile_lean``) and the hierarchy lookups
(``get_parents`` / ``get_children``) are mocked so the substitution logic is
tested deterministically.
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import typeclass_mutate as tm  # noqa: E402


# ── specialize_type ──────────────────────────────────────────────────────────────

def test_specialize_type_drops_typevar_and_instances() -> None:
    with mock.patch.object(tm, "_compile_lean", return_value=True):
        out = tm.specialize_type(
            "sig", "∀ {α : Type u_1} [inst : AddCommMonoid α] (a b : α), a + b = b + a"
        )
    assert out == ("sig", "∀ (a b : ℕ), a + b = b + a")


def test_specialize_type_none_without_type_variable() -> None:
    with mock.patch.object(tm, "_compile_lean", return_value=True):
        assert tm.specialize_type("sig", "∀ (a b : ℕ), a + b = b + a") is None


def test_specialize_type_none_when_nothing_compiles() -> None:
    with mock.patch.object(tm, "_compile_lean", return_value=False):
        assert tm.specialize_type("sig", "∀ {α : Type*} (a : α), a = a") is None


def test_specialize_type_tries_concrete_types_in_order() -> None:
    # ℕ rejected, ℤ accepted → variant should use ℤ.
    calls = []

    def fake_compile(type_str):
        calls.append(type_str)
        return "ℤ" in type_str

    with mock.patch.object(tm, "_compile_lean", side_effect=fake_compile):
        out = tm.specialize_type("sig", "∀ {α : Type*} (a : α), a = a")
    assert out == ("sig", "∀ (a : ℤ), a = a")
    assert any("ℕ" in c for c in calls)  # it did try ℕ first


# ── sibling_typeclass ─────────────────────────────────────────────────────────────

def test_sibling_typeclass_swaps_to_shared_parent_child() -> None:
    def parents(name):
        return {"Monoid": ["MulOneClass"]}.get(name, [])

    def children(name):
        return {"MulOneClass": ["Monoid", "Foo"]}.get(name, [])

    with mock.patch.object(tm, "get_parents", side_effect=parents), \
         mock.patch.object(tm, "get_children", side_effect=children), \
         mock.patch.object(tm, "_compile_lean", return_value=True):
        out = tm.sibling_typeclass(
            "sig", "∀ {α : Type u_1} [inst : Monoid α] (a : α), a * a = a"
        )
    assert out == ("sig", "∀ {α : Type u_1} [inst : Foo α] (a : α), a * a = a")


def test_sibling_typeclass_none_when_no_siblings() -> None:
    with mock.patch.object(tm, "get_parents", return_value=["MulOneClass"]), \
         mock.patch.object(tm, "get_children", return_value=["Monoid"]), \
         mock.patch.object(tm, "_compile_lean", return_value=True):
        # Only child of the parent is the class itself → no sibling.
        out = tm.sibling_typeclass("sig", "∀ {α : Type*} [inst : Monoid α] (a : α), a = a")
    assert out is None


if __name__ == "__main__":
    import inspect
    for name, fn in inspect.getmembers(sys.modules[__name__], inspect.isfunction):
        if name.startswith("test_"):
            fn()
            print(f"  ✓ {name}")
    print("\nAll specialize/sibling tests passed.")
