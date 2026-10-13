#!/usr/bin/env python
"""Apply every registered perturbation to benchmark-CSV anchors, for manual review.

Reads the expert-review benchmark CSV, pulls the Lean side out of each
formal/informal pair, normalises the declaration signature into a standalone
type, then applies each perturbation in the registry once (depth 1) and writes
both a machine-readable JSONL and a human-readable Markdown report.

The point of this runner (as opposed to ``run_demo.py``) is *auditability*: for
every perturbation that fails to produce a variant it records **why** — the
shape didn't match, Lean rejected the candidate, the tactic didn't fire, or the
result was identical to the input. Those four cases look the same from
``apply_chain``'s point of view but mean very different things when deciding
which perturbations are worth keeping.

Usage::

    python pipeline/run_benchmark_review.py --source Mathlib --num-workers 4
    python pipeline/run_benchmark_review.py --rows 14,18,24 --no-lean
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

DEFAULT_CSV = PROJECT_ROOT / "Math Statement Benchmark - Expert Review - Formal-Informal.csv"


# ── CSV extraction ────────────────────────────────────────────────────────────
# The sheet stores one formal/informal *pair* per row, but which half is which
# varies: columns 3-8 are one side and 9-14 the other, and the "Type" cell at
# index 3 / 9 says whether that side is "Formal" (Lean) or "Informal" (LaTeX).
# Both halves reuse the header name "LaTeX / Lean", so DictReader silently keeps
# only the second one — hence the positional access here.

_COL_TYPE_A, _COL_DECL_A, _COL_MOD_A, _COL_STMT_A = 3, 4, 5, 8
_COL_TYPE_B, _COL_DECL_B, _COL_MOD_B, _COL_STMT_B = 9, 10, 11, 14
_COL_PAIR_ID = 24


def formal_side(row: list[str]) -> tuple[str, str, str] | None:
    """Return ``(declaration, module, lean_signature)`` for a CSV row."""
    if row[_COL_TYPE_A].strip() == "Formal":
        return row[_COL_DECL_A], row[_COL_MOD_A], row[_COL_STMT_A]
    if row[_COL_TYPE_B].strip() == "Formal":
        return row[_COL_DECL_B], row[_COL_MOD_B], row[_COL_STMT_B]
    return None


# ── Signature → type normalisation ────────────────────────────────────────────
# The CSV holds `#check`-style declaration signatures:
#     Foo.bar.{u_1} {α : Type u_1} [Ring α] (h : P) : Q
# The transforms want a standalone type:
#     ∀ {α : Type _} [Ring α] (h : P), Q

_DECL_HEAD_RE = re.compile(r"^(«[^»]*»|[^\s{(\[]+?)(\.\{[^}]*\})?(?=\s|$)")
_AUTOPARAM_RE = re.compile(r"\s*:=\s*by\s+\w+")
_MAX_UNIV_RE = re.compile(r"Type\s*\(max[^)]*\)")


def _split_top_level_colon(s: str) -> tuple[str, str] | None:
    """Split at the first ``:`` that is not nested and not part of ``::``."""
    depth = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c in "([{⟨":
            depth += 1
        elif c in ")]}⟩":
            depth -= 1
        elif c == ":" and depth == 0:
            if s[i : i + 2] == "::":
                i += 2
                continue
            return s[:i], s[i + 1 :]
        i += 1
    return None


def signature_to_type_str(sig: str) -> str | None:
    """Turn a declaration signature into a standalone Lean type, or None.

    Universe parameters are replaced with ``_`` rather than declared, because
    the compile oracle emits a bare ``example : <type> := by sorry`` with no
    room for a ``universe`` command.
    """
    s = " ".join(sig.split())
    if not s:
        return None

    universes: list[str] = []
    head = _DECL_HEAD_RE.match(s)
    if head:
        if head.group(2):
            universes = [u.strip() for u in head.group(2)[2:-1].split(",") if u.strip()]
        s = s[head.end() :].strip()

    parts = _split_top_level_colon(s)
    if parts is None:
        return None
    binders, body = parts[0].strip(), parts[1].strip()
    if not body:
        return None

    out = f"∀ {binders}, {body}" if binders else body
    out = _AUTOPARAM_RE.sub("", out)  # drop `:= by volume_tac` default args
    out = _MAX_UNIV_RE.sub("Type _", out)
    for u in universes:
        out = re.sub(rf"(?<![\w.]){re.escape(u)}(?![\w.])", "_", out)
    return out


# Conclusions that are types/data rather than propositions. These are
# definitions, not theorems; their signatures are still valid Lean types so the
# perturbations will happily chew on them, but the resulting "statement pair"
# is not a mathematical claim. We flag rather than drop.
_NON_PROP_CONCLUSION_RE = re.compile(
    r"^(Prop|Type\b|Sort\b|ℕ∞|ℕ|ℤ|ℚ|ℝ|ℂ|Matrix\b|Lean\.ParserDescr\b|MeasurableSpace\b|Finset\b|Set\b)"
)


def looks_like_definition(type_str: str) -> bool:
    """Heuristic: does this signature conclude in data/a type rather than a Prop?"""
    parts = type_str.rsplit(", ", 1)
    conclusion = parts[-1].strip()
    return bool(_NON_PROP_CONCLUSION_RE.match(conclusion))


# ── Lean-call instrumentation ─────────────────────────────────────────────────
# Each transform module imported ``compile_lean`` / ``extract_goal`` by name, so
# patching the module attribute is what actually intercepts the call. Recording
# candidates lets us tell "shape didn't match" from "Lean said no".


class LeanProbe:
    """Records every oracle call a transform makes during one invocation."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.calls = []

    @property
    def n_calls(self) -> int:
        return len(self.calls)

    @property
    def candidates(self) -> list[str]:
        return [c["candidate"] for c in self.calls if c["candidate"] is not None]

    @property
    def any_accepted(self) -> bool:
        return any(c["ok"] for c in self.calls)


def install_probes(probe: LeanProbe, *, use_lean: bool = True) -> None:
    """Wrap the oracle entry points of every transform module with ``probe``.

    With ``use_lean=False`` the oracles are stubbed instead of wrapped: every
    candidate is accepted without asking Lean, and the tactic-driven transforms
    return ``None``. That turns the whole run into a pure-Python smoke test.
    """
    import typeclass_mutate
    from wiggle import lean_runner
    from wiggle.transforms import connectives, logical, quantifiers, relations, structure

    real_compile = lean_runner.compile_lean
    real_extract = lean_runner.extract_goal
    real_tc_compile = typeclass_mutate._compile_lean

    def probed_compile(sig: str, type_str: str) -> bool:
        ok = real_compile(sig, type_str) if use_lean else True
        probe.calls.append({"kind": "compile", "candidate": type_str, "ok": ok})
        return ok

    def probed_tc_compile(type_str: str) -> bool:
        ok = real_tc_compile(type_str) if use_lean else True
        probe.calls.append({"kind": "compile", "candidate": type_str, "ok": ok})
        return ok

    def probed_extract(tactic: str, type_str: str):
        result = real_extract(tactic, type_str) if use_lean else None
        probe.calls.append(
            {
                "kind": "tactic",
                "tactic": tactic,
                "candidate": result[1] if result else None,
                "ok": result is not None,
            }
        )
        return result

    for mod in (quantifiers, relations, structure):
        mod.compile_lean = probed_compile  # type: ignore[attr-defined]
    for mod in (logical, connectives):
        mod.extract_goal = probed_extract  # type: ignore[attr-defined]
    typeclass_mutate._compile_lean = probed_tc_compile  # type: ignore[attr-defined]


# ── Outcome classification ────────────────────────────────────────────────────

STATUS_APPLIED = "applied"
STATUS_NOT_APPLICABLE = "not_applicable"
STATUS_LEAN_REJECTED = "lean_rejected"
STATUS_TACTIC_FAILED = "tactic_failed"
STATUS_NOOP = "noop"
STATUS_NEEDS_LEAN = "needs_lean"
STATUS_ERROR = "error"


def _classify_failure(probe: LeanProbe, original: str, use_lean: bool) -> tuple[str, str]:
    """Explain why a transform returned None. Returns ``(status, detail)``."""
    if probe.n_calls == 0:
        return STATUS_NOT_APPLICABLE, "shape did not match; no Lean call made"

    tactic_calls = [c for c in probe.calls if c["kind"] == "tactic"]
    if tactic_calls:
        if not use_lean:
            return STATUS_NEEDS_LEAN, "tactic-driven; cannot run in text-only mode"
        return (
            STATUS_TACTIC_FAILED,
            f"tactic {tactic_calls[0].get('tactic')!r} ran but extract_goal produced nothing",
        )

    cands = probe.candidates
    if cands and all(c.strip() == original.strip() for c in cands):
        return STATUS_NOOP, "candidate identical to the anchor"
    if cands:
        return (
            STATUS_LEAN_REJECTED,
            f"{len(cands)} candidate(s) proposed, all rejected by the Lean type-checker",
        )
    return STATUS_NOT_APPLICABLE, "no candidate produced"


# ── Diffing, for the human report ─────────────────────────────────────────────

_TOKEN_RE = re.compile(r"\s+")


def wrap_lean(stmt: str, width: int = 96) -> str:
    """Soft-wrap a one-line Lean type at spaces so it is readable in the report.

    Lean is whitespace-insensitive, so breaking at spaces is safe; continuation
    lines are indented to make the wrap visually distinct from a real newline.
    """
    words = stmt.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}" if cur else w
        if len(candidate) > width and cur:
            lines.append(cur)
            cur = "    " + w
        else:
            cur = candidate
    if cur:
        lines.append(cur)
    return "\n".join(lines)


def token_diff(before: str, after: str, max_edits: int = 6) -> str:
    """Summarise the change as a short list of token-level replacements."""
    a = _TOKEN_RE.split(before.strip())
    b = _TOKEN_RE.split(after.strip())
    edits: list[str] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            continue
        old = " ".join(a[i1:i2])
        new = " ".join(b[j1:j2])
        if tag == "replace":
            edits.append(f"`{old}` → `{new}`")
        elif tag == "delete":
            edits.append(f"removed `{old}`")
        elif tag == "insert":
            edits.append(f"added `{new}`")
    if not edits:
        return "_(whitespace only)_"
    if len(edits) > max_edits:
        return "; ".join(edits[:max_edits]) + f"; …and {len(edits) - max_edits} more"
    return "; ".join(edits)


# ── Per-anchor worker ─────────────────────────────────────────────────────────


def process_anchor(anchor: dict[str, Any], use_lean: bool) -> dict[str, Any]:
    """Apply every registered perturbation once to a single anchor."""
    from wiggle.chains import normalize_statement
    from wiggle.lean_runner import compile_lean
    from wiggle.registry import ANCHOR_TRUTH, PERTURBATIONS

    probe = LeanProbe()
    install_probes(probe, use_lean=use_lean)

    type_str = anchor["type_str"]
    started = time.time()

    anchor_compiles: bool | None = None
    if use_lean:
        anchor_compiles = compile_lean("", type_str)

    results: list[dict[str, Any]] = []
    for pert in PERTURBATIONS:
        probe.reset()
        t0 = time.time()
        status = STATUS_APPLIED
        detail = ""
        variant: str | None = None

        try:
            outcome = pert.fn(anchor["id"], type_str)
        except Exception as exc:  # a broken transform shouldn't sink the run
            outcome = None
            status, detail = STATUS_ERROR, f"{type(exc).__name__}: {exc}"

        if status != STATUS_ERROR:
            if outcome is None:
                status, detail = _classify_failure(probe, type_str, use_lean)
            else:
                _, raw_variant = outcome
                variant = normalize_statement(raw_variant)
                if variant.strip() == type_str.strip():
                    status, detail, variant = STATUS_NOOP, "output identical to the anchor", None
                elif pert.layer == "bounds" and use_lean:
                    # bounds transforms skip the oracle; validate here so the
                    # report doesn't claim an unchecked variant is well-formed.
                    if not compile_lean("", variant):
                        status = STATUS_LEAN_REJECTED
                        detail = "regex edit produced a statement Lean rejects"
                        variant = None

        results.append(
            {
                "perturbation": pert.name,
                "layer": pert.layer,
                "status": status,
                "detail": detail,
                "variant": variant,
                "expected_truth": pert.propagation[ANCHOR_TRUTH] if variant else None,
                "lean_calls": probe.n_calls,
                "seconds": round(time.time() - t0, 2),
            }
        )

    return {
        **anchor,
        "anchor_compiles": anchor_compiles,
        "results": results,
        "total_seconds": round(time.time() - started, 1),
        "total_lean_calls": sum(r["lean_calls"] for r in results) + (1 if use_lean else 0),
    }


# ── Report rendering ──────────────────────────────────────────────────────────

_STATUS_ICON = {
    STATUS_APPLIED: "OK",
    STATUS_NOT_APPLICABLE: "n/a",
    STATUS_LEAN_REJECTED: "rejected",
    STATUS_TACTIC_FAILED: "tactic failed",
    STATUS_NOOP: "no-op",
    STATUS_NEEDS_LEAN: "needs Lean",
    STATUS_ERROR: "ERROR",
}


def render_report(anchors: list[dict[str, Any]], use_lean: bool) -> str:
    from wiggle.registry import PERTURBATIONS

    lines: list[str] = []
    add = lines.append

    add("# Perturbation review — benchmark anchors")
    add("")
    add(f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}  ")
    add(f"{len(anchors)} anchors × {len(PERTURBATIONS)} perturbations, depth 1  ")
    add(f"Lean verification: **{'on' if use_lean else 'off (text-only)'}**")
    add("")
    add("Every variant marked `OK` was accepted by the Lean type-checker, either")
    add("because Lean itself generated it (`extract_goal`) or because")
    add("`example : <variant> := by sorry` elaborated. Truth labels are inferred")
    add("from the propagation table, **not** proven.")
    add("")

    # ── Summary: hit rate per perturbation ────────────────────────────────────
    add("## Summary — hit rate per perturbation")
    add("")
    add("| Perturbation | Layer | Applied | n/a | Rejected | Tactic failed | No-op | Lean calls |")
    add("|---|---|---|---|---|---|---|---|")
    for pert in PERTURBATIONS:
        rows = [r for a in anchors for r in a["results"] if r["perturbation"] == pert.name]
        counts = {k: sum(1 for r in rows if r["status"] == k) for k in _STATUS_ICON}
        calls = sum(r["lean_calls"] for r in rows)
        add(
            f"| `{pert.name}` | {pert.layer} | **{counts[STATUS_APPLIED]}/{len(rows)}** | "
            f"{counts[STATUS_NOT_APPLICABLE]} | {counts[STATUS_LEAN_REJECTED]} | "
            f"{counts[STATUS_TACTIC_FAILED]} | {counts[STATUS_NOOP]} | {calls} |"
        )
    add("")

    total_variants = sum(
        1 for a in anchors for r in a["results"] if r["status"] == STATUS_APPLIED
    )
    add(f"**{total_variants} variants produced** from {len(anchors)} anchors.")
    add("")
    add("---")
    add("")

    # ── Per-anchor detail ─────────────────────────────────────────────────────
    add("## Anchors")
    add("")
    for idx, a in enumerate(anchors, 1):
        add(f"### {idx}. `{a['declaration']}`")
        add("")
        add(f"- **Module** — `{a['module']}`")
        if a["csv_rows"]:
            add(f"- **CSV rows** — {', '.join(a['pair_ids'])} (sheet row"
                f"{'s' if len(a['csv_rows']) > 1 else ''} "
                f"{', '.join(str(r + 2) for r in a['csv_rows'])})")
        else:
            add(f"- **Source** — {', '.join(a['pair_ids'])}")
        if a.get("shapes"):
            add(f"- **Shapes** — {', '.join('`' + s + '`' for s in a['shapes'])}")
        if a["is_definition"]:
            add("- **Kind** — definition (conclusion is data/a type, not a proposition)")
        else:
            add("- **Kind** — theorem")
        if a["anchor_compiles"] is not None:
            add(f"- **Anchor elaborates** — {'yes' if a['anchor_compiles'] else 'NO'}")
        add(f"- **Cost** — {a['total_lean_calls']} Lean calls, {a['total_seconds']}s")
        add("")
        add("**Original signature (as it appears in the sheet):**")
        add("")
        add("```lean")
        add(a["raw_signature"])
        add("```")
        add("")
        add("**Normalised anchor type (what the perturbations receive):**")
        add("")
        add("```lean")
        add(wrap_lean(a["type_str"]))
        add("```")
        add("")

        applied = [r for r in a["results"] if r["status"] == STATUS_APPLIED]
        skipped = [r for r in a["results"] if r["status"] != STATUS_APPLIED]

        add(f"#### Variants produced ({len(applied)}/{len(a['results'])})")
        add("")
        if not applied:
            add("_None._")
            add("")
        for r in applied:
            add(f"##### `{r['perturbation']}` — {r['layer']}, inferred truth: **{r['expected_truth']}**")
            add("")
            add("```lean")
            add(wrap_lean(r["variant"]))
            add("```")
            add("")
            add(f"Change: {token_diff(a['type_str'], r['variant'])}")
            add("")

        add(f"#### Did not fire ({len(skipped)})")
        add("")
        add("| Perturbation | Outcome | Why |")
        add("|---|---|---|")
        for r in skipped:
            add(f"| `{r['perturbation']}` | {_STATUS_ICON[r['status']]} | {r['detail']} |")
        add("")
        add("---")
        add("")

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────


def load_anchors(
    csv_path: Path, source: str | None, rows_filter: set[int] | None, limit: int | None
) -> list[dict[str, Any]]:
    """Read the CSV and return deduplicated anchors in sheet order."""
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))[1:]

    by_signature: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(rows):
        if rows_filter is not None and i not in rows_filter:
            continue
        side = formal_side(row)
        if side is None:
            continue
        declaration, module, raw_signature = side
        if source and not module.startswith(source):
            continue
        type_str = signature_to_type_str(raw_signature)
        if type_str is None:
            continue

        key = " ".join(raw_signature.split())
        if key in by_signature:
            by_signature[key]["csv_rows"].append(i)
            by_signature[key]["pair_ids"].append(row[_COL_PAIR_ID])
            continue
        by_signature[key] = {
            "id": f"bench_{len(by_signature):03d}",
            "declaration": declaration,
            "module": module,
            "raw_signature": raw_signature,
            "type_str": type_str,
            "body": type_str,
            "is_definition": looks_like_definition(type_str),
            "csv_rows": [i],
            "pair_ids": [row[_COL_PAIR_ID]],
        }

    anchors = list(by_signature.values())
    return anchors[:limit] if limit else anchors


def load_anchors_file(path: Path) -> list[dict[str, Any]]:
    """Read anchors from a JSONL file produced by ``sample_mathlib_anchors.py``.

    An alternative to the benchmark CSV for runs that need anchor shapes the
    CSV does not contain. The record layout is the same either way, so nothing
    downstream has to care which source was used.
    """
    anchors = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            anchors.append(json.loads(line))
    return anchors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--anchors-file", type=Path,
                    help="JSONL of anchors to use instead of the benchmark CSV "
                         "(see pipeline/sample_mathlib_anchors.py).")
    ap.add_argument(
        "--source",
        default="Mathlib",
        help="Only use anchors whose module starts with this (default Mathlib; "
        "pass '' for all sources).",
    )
    ap.add_argument("--rows", help="Comma-separated 0-based CSV data-row indices.")
    ap.add_argument("--limit", type=int, help="Cap the number of unique anchors.")
    ap.add_argument("--out", type=Path, default=PROJECT_ROOT / "data" / "benchmark-review")
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument(
        "--no-lean",
        action="store_true",
        help="Skip every Lean call. Only the regex-only transforms can produce "
        "anything; useful as a fast smoke test of the CSV plumbing.",
    )
    args = ap.parse_args()

    if args.anchors_file:
        anchors = load_anchors_file(args.anchors_file)
        if args.limit:
            anchors = anchors[: args.limit]
    else:
        rows_filter = (
            {int(x) for x in args.rows.split(",") if x.strip()} if args.rows else None
        )
        anchors = load_anchors(args.csv, args.source or None, rows_filter, args.limit)
    if not anchors:
        print("No anchors matched.", file=sys.stderr)
        return 1

    use_lean = not args.no_lean
    total_rows = sum(len(a["csv_rows"]) for a in anchors)
    print(
        f"{len(anchors)} unique anchors (from {total_rows} CSV rows), "
        f"Lean {'on' if use_lean else 'off'}, {args.num_workers} worker(s)",
        flush=True,
    )
    for a in anchors:
        tag = " [definition]" if a["is_definition"] else ""
        print(f"  {a['id']}  {a['declaration']}{tag}", flush=True)
    print(flush=True)

    started = time.time()
    processed: list[dict[str, Any]] = []
    workers = max(1, min(args.num_workers, len(anchors)))

    if workers == 1:
        for a in anchors:
            processed.append(process_anchor(a, use_lean))
            print(
                f"  done {processed[-1]['id']} "
                f"({processed[-1]['total_seconds']}s, "
                f"{processed[-1]['total_lean_calls']} lean calls)",
                flush=True,
            )
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(process_anchor, a, use_lean): a for a in anchors}
            for fut in as_completed(futures):
                res = fut.result()
                processed.append(res)
                n_ok = sum(1 for r in res["results"] if r["status"] == STATUS_APPLIED)
                print(
                    f"  [{len(processed)}/{len(anchors)}] {res['id']} "
                    f"{res['declaration']}: {n_ok} variants, "
                    f"{res['total_seconds']}s, {res['total_lean_calls']} lean calls",
                    flush=True,
                )

    order = {a["id"]: i for i, a in enumerate(anchors)}
    processed.sort(key=lambda a: order[a["id"]])

    args.out.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.out / "results.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as fh:
        for a in processed:
            for r in a["results"]:
                fh.write(
                    json.dumps(
                        {
                            "source_id": a["id"],
                            "declaration": a["declaration"],
                            "module": a["module"],
                            "pair_ids": a["pair_ids"],
                            "is_definition": a["is_definition"],
                            "original_type_str": a["type_str"],
                            **r,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    report_path = args.out / "review.md"
    report_path.write_text(render_report(processed, use_lean), encoding="utf-8")

    n_variants = sum(
        1 for a in processed for r in a["results"] if r["status"] == STATUS_APPLIED
    )
    print(
        f"\n{n_variants} variants from {len(processed)} anchors "
        f"in {time.time() - started:.0f}s\n  {report_path}\n  {jsonl_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
