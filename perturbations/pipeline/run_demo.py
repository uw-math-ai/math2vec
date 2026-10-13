#!/usr/bin/env python3
"""
run_demo.py — apply every registered perturbation to a curated set of theorems.

This is the Python replacement for ``hackathon-demo/demo.ipynb``. It runs all
single perturbations plus a fixed set of chained combinations against 10
curated Lean theorems and writes the results to a JSONL file.

Usage:
    python pipeline/run_demo.py                           # default output path
    python pipeline/run_demo.py --output /tmp/x.jsonl     # custom path
    python pipeline/run_demo.py --quiet                   # suppress per-theorem prints

Requires ``lake env lean`` on PATH; the first run will compile the Lean tactics
in ``Wiggle.lean`` and may take several minutes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Path setup: walk up to the Lake project root and put src/ on sys.path ────-
_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent
while PROJECT_ROOT != PROJECT_ROOT.parent and not (PROJECT_ROOT / "Wiggle.lean").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))


# ── Backend selection: must run BEFORE importing wiggle ──────────────────────-
# We sniff the argv early so the env var is in place by the time
# ``wiggle.lean_runner`` first inspects it. ``argparse`` runs a second pass
# in ``main()`` with a complete spec; this pre-pass is intentionally narrow.
def _early_set_backend() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--backend", choices=("server", "subprocess"))
    known, _ = parser.parse_known_args()
    if known.backend is not None:
        os.environ["WIGGLE_LEAN_BACKEND"] = known.backend


_early_set_backend()

from wiggle.chains import apply_chain, normalize_statement  # noqa: E402
from wiggle.registry import PERTURBATIONS  # noqa: E402


# ── Curated theorems ──────────────────────────────────────────────────────────
# These are the same 10 hand-picked Mathlib statements used by the hackathon
# demo notebook. Kept verbatim so demo outputs are directly comparable.
TOY_THEOREMS: list[dict[str, str]] = [
    {
        "id": "nat_pos_of_ne_zero",
        "binders": "(n : ℕ)",
        "body": "n ≠ 0 → n > 0",
        "type_str": "∀ (n : ℕ), n ≠ 0 → n > 0",
        "description": "A nonzero natural number is positive.",
    },
    {
        "id": "nat_gcd_iff",
        "binders": "{i j : ℕ}",
        "body": "Nat.gcd i j = 0 ↔ i = 0 ∧ j = 0",
        "type_str": "∀ {i j : ℕ}, Nat.gcd i j = 0 ↔ i = 0 ∧ j = 0",
        "description": "gcd(i,j)=0 iff both arguments are zero.",
    },
    {
        "id": "add_comm_monoid",
        "binders": "{α : Type*} [inst : AddCommMonoid α] (a b : α)",
        "body": "a + b = b + a",
        "type_str": "∀ {α : Type*} [inst : AddCommMonoid α] (a b : α), a + b = b + a",
        "description": "Addition commutes in any AddCommMonoid.",
    },
    {
        "id": "field_mul_inv_cancel",
        "binders": "{α : Type*} [inst : Field α] (a : α)",
        "body": "a ≠ 0 → a * a⁻¹ = 1",
        "type_str": "∀ {α : Type*} [inst : Field α] (a : α), a ≠ 0 → a * a⁻¹ = 1",
        "description": "In a field, a * a⁻¹ = 1 for any nonzero a.",
    },
    {
        "id": "polynomial_is_domain",
        "binders": "{R : Type*} [inst : CommRing R] [inst_1 : IsDomain R]",
        "body": "IsDomain (Polynomial R)",
        "type_str": (
            "∀ {R : Type*} [inst : CommRing R] [inst_1 : IsDomain R], "
            "IsDomain (Polynomial R)"
        ),
        "description": "Polynomials over an integral domain form an integral domain.",
    },
    {
        "id": "nat_lt_cancel_left",
        "binders": "{k : ℕ} (m n : ℕ)",
        "body": "k + m < k + n → m < n",
        "type_str": "∀ {k : ℕ} (m n : ℕ), k + m < k + n → m < n",
        "description": "Strict inequality preserved after cancelling left summand.",
    },
    {
        "id": "exp_deriv_unused_hyp",
        "binders": "(x : ℝ) (h_unused : True)",
        "body": "HasDerivAt Real.exp (Real.exp x) x",
        "type_str": "∀ (x : ℝ) (h_unused : True), HasDerivAt Real.exp (Real.exp x) x",
        "description": "Derivative of exp at x is exp(x). Has a dummy True hypothesis.",
    },
    {
        "id": "comm_ring_mul_comm",
        "binders": "{α : Type*} [inst : CommRing α] (a b : α)",
        "body": "a * b = b * a",
        "type_str": "∀ {α : Type*} [inst : CommRing α] (a b : α), a * b = b * a",
        "description": "Multiplication commutes in any commutative ring.",
    },
    {
        "id": "nat_ge_one_of_pos",
        "binders": "(n : ℕ)",
        "body": "n > 0 → n ≥ 1",
        "type_str": "∀ (n : ℕ), n > 0 → n ≥ 1",
        "description": "A positive natural number is at least 1.",
    },
    {
        "id": "linear_order_le_or_ge",
        "binders": "{α : Type*} [inst : LinearOrder α] (a b : α)",
        "body": "a ≤ b ∨ b ≤ a",
        "type_str": "∀ {α : Type*} [inst : LinearOrder α] (a b : α), a ≤ b ∨ b ≤ a",
        "description": "Any two elements of a linear order are comparable.",
    },
]


# ── Chained perturbations to run ──────────────────────────────────────────────
# Curated combinations that exercise the chain runner. New chains can be added
# here without touching any other file.
CHAINS: list[list[str]] = [
    ["negate", "negate"],
    ["drop_unused_hyp", "negate"],
    ["tc_weaken_hyp", "tc_weaken_hyp"],
    ["tc_weaken_hyp", "negate"],
    ["contrapose", "converse"],
    ["converse", "negate"],
    ["flip_bound", "negate"],
    ["bound_tighter", "negate"],
    # New chains exercising the Phase-2 perturbations
    ["inverse", "negate"],
    ["de_morgan_rewrite", "negate"],
    ["quantifier_swap", "negate"],
]


# ── Main ─────────────────────────────────────────────────────────────────────-

def _run_single(theorem: dict, perturbation, *, quiet: bool) -> dict | None:
    """Apply one perturbation to one theorem. Returns a JSONL record or None."""
    result = perturbation.fn(theorem["id"], theorem["type_str"])
    if result is None:
        if not quiet:
            print(f"    [{perturbation.name:<20}] (not applicable)", flush=True)
        return None
    variant_sig, variant_type = result
    if not quiet:
        preview = variant_type[:60] + ("…" if len(variant_type) > 60 else "")
        print(f"    [{perturbation.name:<20}] {preview}", flush=True)
    return {
        "source_id": theorem["id"],
        "original_statement": theorem["body"],
        "original_type_str": theorem["type_str"],
        "perturbations_applied": [perturbation.name],
        "perturbed_statement": normalize_statement(variant_type),
        "is_true": perturbation.propagation["true"],
        "perturbation_description": perturbation.name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "layer": perturbation.layer,
    }


def _run_chain(theorem: dict, chain: list[str], *, quiet: bool) -> dict:
    record = apply_chain(theorem, chain, verify_compile=False)
    if not quiet:
        label = " -> ".join(chain)
        if record["chain_status"] == "ok":
            stmt = record["perturbed_statement"] or ""
            preview = stmt[:60] + ("…" if len(stmt) > 60 else "")
            print(f"    [{label}] is_true={record['is_true']:<8} {preview}", flush=True)
        else:
            print(
                f"    [{label}] BROKEN at step {len(record['perturbations_applied'])}",
                flush=True,
            )
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "demo_perturbations.jsonl",
        help="Output JSONL path. Default: data/demo_perturbations.jsonl",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress per-row prints.")
    parser.add_argument(
        "--singles-only",
        action="store_true",
        help="Skip chained perturbations (faster for sanity tests).",
    )
    parser.add_argument(
        "--backend",
        choices=("server", "subprocess"),
        default=os.environ.get("WIGGLE_LEAN_BACKEND", "server"),
        help=(
            "Lean execution backend. 'server' (default) reuses one persistent "
            "lake env lean --server process across calls; 'subprocess' spawns "
            "a fresh lean per call (slower, kept for debugging)."
        ),
    )
    args = parser.parse_args(argv)
    # _early_set_backend has already exported this; re-export so subprocesses
    # (e.g. lake env) inherit the same value.
    os.environ["WIGGLE_LEAN_BACKEND"] = args.backend

    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"Project root : {PROJECT_ROOT}")
    print(f"Output file  : {args.output}")
    print(f"Backend      : {args.backend}")
    print(f"Theorems     : {len(TOY_THEOREMS)}")
    print(f"Perturbations: {len(PERTURBATIONS)} ({', '.join(p.name for p in PERTURBATIONS)})")
    if not args.singles_only:
        print(f"Chains       : {len(CHAINS)}")
    print()

    records: list[dict] = []

    # ── Single perturbations ──────────────────────────────────────────────────
    for theorem in TOY_THEOREMS:
        print(f"[{theorem['id']}]  {theorem['body'][:55]}")
        for perturbation in PERTURBATIONS:
            rec = _run_single(theorem, perturbation, quiet=args.quiet)
            if rec is not None:
                records.append(rec)
        print()

    # ── Chained perturbations ─────────────────────────────────────────────────
    if not args.singles_only:
        print("─" * 70)
        print("Chains:")
        for theorem in TOY_THEOREMS:
            print(f"\n[{theorem['id']}]  {theorem['body'][:55]}")
            for chain in CHAINS:
                rec = _run_chain(theorem, chain, quiet=args.quiet)
                if rec["chain_status"] == "ok":
                    records.append(rec)

    # ── Write ─────────────────────────────────────────────────────────────────
    with args.output.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\n{'═' * 70}")
    print(f"Wrote {len(records)} records to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
