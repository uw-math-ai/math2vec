#!/usr/bin/env python3
"""
bench_backends.py — wallclock comparison of the two Lean execution backends.

Runs the same 5 ``run_lean`` calls against each backend. The persistent-server
backend pays Mathlib's import cost once during startup; every subsequent call
is sub-second. The subprocess backend pays the full cost every call.

Reference run on a 2024 M-series Mac with warm caches::

    backend     | first | warm avg | total
    server      | ~45s  | ~0.2s   | ~46s
    subprocess  | ~16s  | ~15s    | ~76s

Usage:
    python scripts/bench_backends.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

SNIPPETS = [
    "import Mathlib\n\nexample : True := by trivial\n",
    "import Mathlib\n\nexample : 1 + 1 = 2 := by decide\n",
    "import Mathlib\n\nexample : (∀ n : Nat, n + 0 = n) := fun n => Nat.add_zero n\n",
    "import Mathlib\n\nexample : ∀ (a b : Nat), a + b = b + a := Nat.add_comm\n",
    "import Mathlib\n\nexample : (1 : Int) ≠ 0 := by decide\n",
]


def _bench(backend: str) -> tuple[float, list[float]]:
    os.environ["WIGGLE_LEAN_BACKEND"] = backend
    # Force re-import so the runner sees the new env var.
    for mod in list(sys.modules):
        if mod.startswith("wiggle"):
            del sys.modules[mod]
    from wiggle.lean_runner import run_lean

    durations: list[float] = []
    total = time.perf_counter()
    for code in SNIPPETS:
        t0 = time.perf_counter()
        out = run_lean(code, timeout=180)
        durations.append(time.perf_counter() - t0)
        if "error:" in out:
            print(f"  WARN: snippet returned error: {out[:100]}")
    total = time.perf_counter() - total
    return total, durations


def main() -> int:
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Snippets    : {len(SNIPPETS)}")
    print()

    for backend in ("server", "subprocess"):
        print(f"── backend = {backend} ──")
        wallclock, per_call = _bench(backend)
        print(f"  total       : {wallclock:6.2f}s")
        print(f"  per-call    : {[f'{x:.2f}s' for x in per_call]}")
        if len(per_call) > 1:
            warm = per_call[1:]
            print(f"  warm avg    : {sum(warm)/len(warm):6.2f}s (after first call)")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
