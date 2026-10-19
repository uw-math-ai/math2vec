#!/usr/bin/env python
"""Independently re-elaborate every variant in a review run.

The perturbation pipeline treats two different things as "verified":

  * text transforms call ``compile_lean`` on the candidate, so their output is
    known to elaborate standalone;
  * tactic transforms read their output back out of Lean via ``extract_goal``
    and trust it *because Lean printed it*.

That second guarantee is weaker than it looks. ``extract_goal`` prints the goal
in the context it was elaborated in, so it can emit names — auto-bound universe
parameters especially — that do not resolve when the statement is lifted out on
its own. This script closes that gap: it takes ``results.jsonl`` from
``run_benchmark_review.py`` and checks that every emitted variant elaborates as
a standalone ``example``.

Usage::

    python pipeline/verify_variants.py --run data/benchmark-review
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def check(item: tuple[int, str]) -> tuple[int, bool, str]:
    """Elaborate one variant standalone; return ``(index, ok, first_error)``."""
    idx, variant = item
    from wiggle.lean_runner import run_lean

    output = run_lean("import Mathlib\n\nexample : " + variant + " := by sorry\n")
    ok = "error:" not in output
    detail = ""
    if not ok:
        block = output.split("error:", 1)[1]
        detail = " ".join(block.split())[:180]
    return idx, ok, detail


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, default=PROJECT_ROOT / "data" / "benchmark-review")
    ap.add_argument("--num-workers", type=int, default=4)
    args = ap.parse_args()

    path = args.run / "results.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    variants = [(i, r["variant"]) for i, r in enumerate(records) if r.get("variant")]

    print(f"re-elaborating {len(variants)} variants with {args.num_workers} workers", flush=True)
    started = time.time()

    outcomes: dict[int, tuple[bool, str]] = {}
    with ProcessPoolExecutor(max_workers=args.num_workers) as pool:
        futures = [pool.submit(check, v) for v in variants]
        for n, fut in enumerate(as_completed(futures), 1):
            idx, ok, detail = fut.result()
            outcomes[idx] = (ok, detail)
            if n % 10 == 0 or n == len(variants):
                print(f"  {n}/{len(variants)} ({time.time() - started:.0f}s)", flush=True)

    per_pert: dict[str, Counter] = defaultdict(Counter)
    failures: list[dict] = []
    for idx, (ok, detail) in outcomes.items():
        rec = records[idx]
        rec["standalone_elaborates"] = ok
        rec["standalone_error"] = detail
        per_pert[rec["perturbation"]]["ok" if ok else "fail"] += 1
        if not ok:
            failures.append(rec)

    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_ok = sum(1 for ok, _ in outcomes.values() if ok)
    lines = [
        "# Standalone re-elaboration check",
        "",
        f"{n_ok}/{len(variants)} variants elaborate on their own as "
        "`example : <variant> := by sorry`.",
        "",
        "A variant that fails here was still produced by Lean, but is not a",
        "self-contained statement — it depends on names bound in the context it",
        "was extracted from. Those cannot go into a dataset as-is.",
        "",
        "| Perturbation | Emitted | Standalone-valid | Broken |",
        "|---|---|---|---|",
    ]
    for name in sorted(per_pert):
        c = per_pert[name]
        total = c["ok"] + c["fail"]
        lines.append(f"| `{name}` | {total} | {c['ok']} | **{c['fail']}** |")
    lines += ["", "## Broken variants", ""]
    if not failures:
        lines.append("_None._")
    for rec in failures:
        lines += [
            f"### `{rec['perturbation']}` on `{rec['declaration']}`",
            "",
            "```lean",
            rec["variant"],
            "```",
            "",
            f"Lean: `{rec['standalone_error']}`",
            "",
        ]

    out = args.run / "standalone-check.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n{n_ok}/{len(variants)} standalone-valid  ({time.time() - started:.0f}s)\n  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
