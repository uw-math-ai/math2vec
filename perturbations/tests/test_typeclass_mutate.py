"""
test_typeclass_mutate.py

Quick test of the four typeclass perturbation methods on a simple theorem.
"""

import sys
from pathlib import Path

# Put the project's src/ on the path so we can import the wiggle library.
PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from typeclass_mutate import (
    weaken_hypothesis_typeclass,
    strengthen_hypothesis_typeclass,
    strengthen_conclusion_typeclass,
    weaken_conclusion_typeclass,
)

# ── Test theorem ──────────────────────────────────────────────────────────────
#
# Mathlib: add_comm
#   ∀ {α : Type u_1} [inst : AddCommMonoid α] (a b : α), a + b = b + a
#
# The typeclass [AddCommMonoid α] sits in the middle of the hierarchy:
#
#   AddMonoid          ← weaker (parent)
#     └─ AddCommMonoid ← our starting point
#           └─ AddCommGroup  ← stronger (child)

SIG      = "add_comm"
TYPE_STR = "∀ {α : Type u_1} [inst : AddCommMonoid α] (a b : α), a + b = b + a"

SEP = "─" * 70

print(SEP)
print("ORIGINAL THEOREM")
print(f"  sig  : {SIG}")
print(f"  type : {TYPE_STR}")
print()

# ── Method 1: weaken hypothesis typeclass ─────────────────────────────────────
print(SEP)
print("METHOD 1 — weaken_hypothesis_typeclass")
print("  Strategy : replace [AddCommMonoid α] with a WEAKER parent class")
print("  Effect   : variant claims the conclusion for a LARGER class of types")
print()

result = weaken_hypothesis_typeclass(SIG, TYPE_STR)
if result:
    _, new_type = result
    print(f"  BEFORE : {TYPE_STR}")
    print(f"  AFTER  : {new_type}")
else:
    print("  (no valid substitution found)")
print()

# ── Method 2: strengthen hypothesis typeclass ────────────────────────────────
print(SEP)
print("METHOD 2 — strengthen_hypothesis_typeclass")
print("  Strategy : replace [AddCommMonoid α] with a STRONGER child class")
print("  Effect   : variant restricts to a narrower class of types")
print()

result = strengthen_hypothesis_typeclass(SIG, TYPE_STR)
if result:
    _, new_type = result
    print(f"  BEFORE : {TYPE_STR}")
    print(f"  AFTER  : {new_type}")
else:
    print("  (no valid substitution found)")
print()

# ── Methods 3 & 4: conclusion methods need a TC in the conclusion ─────────────
#
# The conclusion "a + b = b + a" is a plain equality — no typeclass there.
# We switch to a theorem whose conclusion IS a typeclass predicate:
#
#   Polynomial.isDomain
#   ∀ {R : Type u_1} [inst : CommRing R] [inst_1 : IsDomain R],
#       IsDomain (Polynomial R)
#
# Hierarchy used for the conclusion:
#
#   Nontrivial / IsCancelMulZero   ← weaker (parents of IsDomain)
#     └─ IsDomain                  ← conclusion predicate
#           └─ EuclideanDomain      ← stronger (child of IsDomain)
#                 └─ IsField        ← even stronger

SIG2      = "Polynomial.isDomain"
TYPE_STR2 = (
    "∀ {R : Type u_1} [inst : CommRing R] [inst_1 : IsDomain R], "
    "IsDomain (Polynomial R)"
)

print(SEP)
print("THEOREM FOR CONCLUSION TESTS")
print(f"  sig  : {SIG2}")
print(f"  type : {TYPE_STR2}")
print()

# ── Method 3: strengthen conclusion typeclass ────────────────────────────────
print(SEP)
print("METHOD 3 — strengthen_conclusion_typeclass")
print("  Strategy : replace IsDomain in conclusion with a STRONGER predicate")
print("  Effect   : theorem becomes stronger (claims more about the output)")
print()

result = strengthen_conclusion_typeclass(SIG2, TYPE_STR2)
if result:
    _, new_type = result
    print(f"  BEFORE : {TYPE_STR2}")
    print(f"  AFTER  : {new_type}")
else:
    print("  (no valid substitution found)")
print()

# ── Method 4: weaken conclusion typeclass ────────────────────────────────────
print(SEP)
print("METHOD 4 — weaken_conclusion_typeclass")
print("  Strategy : replace IsDomain in conclusion with a WEAKER predicate")
print("  Effect   : theorem becomes weaker (claims less about the output)")
print()

result = weaken_conclusion_typeclass(SIG2, TYPE_STR2)
if result:
    _, new_type = result
    print(f"  BEFORE : {TYPE_STR2}")
    print(f"  AFTER  : {new_type}")
else:
    print("  (no valid substitution found)")
print()

print(SEP)
print("All tests complete.")
