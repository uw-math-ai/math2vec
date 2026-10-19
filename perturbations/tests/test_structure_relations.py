"""
Lean-free tests for the structure / relation / quantifier-flip transforms.

Every transform validates its candidate with ``compile_lean``; we patch that
per-module to a constant so the parsing/edit logic is exercised without Lean.
"""

import re
import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wiggle.transforms import quantifiers, relations, structure  # noqa: E402


def _ok(module):
    return mock.patch.object(module, "compile_lean", return_value=True)


def _bad(module):
    return mock.patch.object(module, "compile_lean", return_value=False)


# ── structure.alpha_rename ──────────────────────────────────────────────────────

# Replacement names are rotated by a hash of the statement so that renamed
# output does not always reach for the same letters, which means these tests
# assert the *properties* of the rename rather than one exact string.
_BINDER_RE = re.compile(r"[({]\s*([^:(){}\[\]]+?)\s*:")


def _bound_names(type_str: str) -> list[str]:
    head = type_str.split(",")[0]
    return [tok for group in _BINDER_RE.findall(head) for tok in group.split()]


def test_alpha_rename_renames_every_bound_var_consistently() -> None:
    with _ok(structure):
        out = structure.alpha_rename("sig", "∀ {α : Type u_1} (a b : α), a + b = b + a")
    assert out is not None
    _, renamed = out

    ty, x, y = _bound_names(renamed)
    assert ty in structure._TYPE_NAMES and ty != "α"
    assert {x, y} <= set(structure._ELEM_NAMES) and x != y
    # Every occurrence must move together, or the statement stops being the
    # same proposition.
    assert renamed == f"∀ {{{ty} : Type u_1}} ({x} {y} : {ty}), {x} + {y} = {y} + {x}"


def test_alpha_rename_none_when_not_forall() -> None:
    with _ok(structure):
        assert structure.alpha_rename("sig", "P → Q") is None


def test_alpha_rename_none_when_oracle_rejects() -> None:
    with _bad(structure):
        assert structure.alpha_rename("sig", "∀ (a : ℕ), a = a") is None


def test_alpha_rename_does_not_touch_subscripted_neighbor() -> None:
    # Renaming `a` must not corrupt a distinct bound var `a₀`.
    with _ok(structure):
        out = structure.alpha_rename("sig", "∀ (a a₀ : ℕ), a = a₀")
    assert out is not None
    m, n = _bound_names(out[1])
    assert m != n
    assert out[1] == f"∀ ({m} {n} : ℕ), {m} = {n}"


def test_alpha_rename_picks_names_matching_the_binder_kind() -> None:
    # Types get Greek letters, discrete quantities get `m n k`, sets get
    # `s t u`, hypotheses get `h`-names — the point of the perturbation is that
    # the result still reads like Mathlib rather than like generator output.
    with _ok(structure):
        out = structure.alpha_rename(
            "sig", "∀ {α : Type u_1} (n : ℕ) (s : Set α) (h : n ∈ ∅), s = ∅")
    assert out is not None
    ty, num, st, hyp = _bound_names(out[1])
    assert ty in structure._TYPE_NAMES
    assert num in structure._NUM_NAMES
    assert st in structure._SET_NAMES
    assert hyp in structure._PROP_NAMES


def test_alpha_rename_leaves_instance_binders_alone() -> None:
    # `inst` is the Mathlib convention; renaming it is pure surface noise.
    with _ok(structure):
        out = structure.alpha_rename(
            "sig", "∀ {R : Type u_1} [inst : Semiring R] (a b : R), a * b = b * a")
    assert out is not None
    assert "[inst : Semiring " in out[1]
    assert "R" not in _bound_names(out[1])


def test_alpha_rename_never_renames_onto_an_existing_identifier() -> None:
    # Renaming onto a name already in the statement would capture it.
    with _ok(structure):
        out = structure.alpha_rename("sig", "∀ (a b : ℤ), a < b")
    assert out is not None
    fresh = _bound_names(out[1])
    assert len(set(fresh)) == 2
    assert not {"a", "b"} & set(fresh)


def test_alpha_rename_substitutes_simultaneously() -> None:
    # A sequential pass could rename `a`→`c` and then that same `c`→`d`,
    # collapsing two distinct variables into one.
    with _ok(structure):
        out = structure.alpha_rename("sig", "∀ (a c : ℕ), a ≠ c")
    assert out is not None
    first, second = _bound_names(out[1])
    assert first != second
    assert out[1] == f"∀ ({first} {second} : ℕ), {first} ≠ {second}"


def test_alpha_rename_is_deterministic() -> None:
    stmt = "∀ {α : Type u_1} (a b : α), a + b = b + a"
    with _ok(structure):
        assert structure.alpha_rename("sig", stmt) == structure.alpha_rename("sig", stmt)


def test_alpha_rename_varies_names_across_statements() -> None:
    # A fixed pool order would make every renamed statement start with `α`,
    # which is just a subtler version of the `wv0` fingerprint.
    stmts = [f"∀ {{α : Type u_1}} (a b : α), a + b = b + a + {i}" for i in range(30)]
    with _ok(structure):
        leading = {structure.alpha_rename("sig", s)[1].split()[1][1:] for s in stmts}
    assert len(leading) > 1


def test_alpha_rename_none_when_only_instance_binders() -> None:
    with _ok(structure):
        assert structure.alpha_rename(
            "sig", "∀ [inst : Semiring ℕ], (0 : ℕ) = 0") is None


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
