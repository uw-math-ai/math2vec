"""Check each variant's label by asking Lean automation to prove how it relates to its anchor.

A perturbation's semantic class (``wiggle.registry.SEMANTIC_CLASSES``) says
what the rewrite *should* do; a buggy tactic or an unlucky statement can make
it do something else. This step tries, for every applied variant V of an
anchor A, a fixed battery of cheap automation (``exact``, a propositional
normal form, ``simpa``, ``simp_all``, ``grind``, ``aesop``, ``tauto``) under a
heartbeat limit on

    A → V        V follows from the anchor (V is true)
    V → A        V is at least as strong as the anchor
    A → ¬V       V contradicts the anchor (V is false)
    V            V is easy on its own
    A            the anchor is easy on its own (once per anchor)

and reads the label off what succeeded:

    A → ¬V                      contradictory
    A → V and V → A             equivalent
    A → V only                  entailed
    V → A only                  stronger
    nothing                     unverified

Automation failing proves nothing, so ``unverified`` means "no certificate",
not "not equivalent". If automation proves A by itself, ``V → A`` holds
vacuously, so such anchors never certify ``equivalent`` or ``stronger``.

Every row of ``results.jsonl`` is written to ``certified.jsonl`` with a
``certificate`` (which goals were proved) and a ``label_class``:

* a variant whose structural class is ``equivalent`` keeps that label only if
  both directions are proved, becomes ``contradictory`` if that is proved, and
  is otherwise ``unverified`` and dropped by the eval, since
  an unproven positive is the one label we cannot afford to get wrong;
* any other variant takes its certified class if it has one (a "negative"
  that Lean proves equivalent becomes a positive, ``stronger`` reads as
  ``graded``) and otherwise keeps its structural class: it is a different
  statement as far as anyone can tell, which is what a hard negative is.

``certify_summary.md`` cross-tabulates perturbation against certified class;
a structurally equivalent perturbation with certified-contradictory variants
is a bug in that perturbation.

Usage::

    python pipeline/certify_labels.py --run data/blueprint-review --num-workers 32
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wiggle.registry import SEMANTIC_CLASSES  # noqa: E402

# Pushes negations inward, turns implications into disjunctions, sorts ∧/∨
# (simp orders commutative lemmas) and pushes ∀ in as far as it goes, so statements that differ only by
# propositional rewriting -- contrapose, De Morgan, (un)currying, premise order,
# negate -- reach the same normal form.
LOGIC_NF = ("not_and_or, not_or, not_forall, not_exists, not_not, not_le, not_lt, "
            "ne_eq, imp_iff_not_or, and_imp, or_assoc, and_assoc, or_comm, "
            "or_left_comm, and_comm, and_left_comm, forall_or_left, forall_or_right")

AUTOMATION = f"""first
    | exact @h
    | (intros; apply h <;> assumption)
    | (simp only [{LOGIC_NF}] at h ⊢; exact @h)
    | (simpa using h)
    | (intros; simp_all)
    | grind
    | aesop
    | tauto"""

GOALS = ("forward", "backward", "contradiction", "variant_alone")
CERTIFIED_CLASSES = ("equivalent", "entailed", "stronger", "contradictory", "unverified")


def _proves(statement: str, intro: str, heartbeats: int, timeout: int) -> bool:
    from wiggle.lean_runner import run_lean

    code = (
        "import Mathlib\n\n"
        f"set_option maxHeartbeats {heartbeats} in\n"
        f"example : {statement} := by\n"
        f"  {intro}\n"
        f"  {AUTOMATION}\n"
    )
    output = run_lean(code, timeout=timeout)
    return "error" not in output and "sorry" not in output


_UNIVERSE_RE = re.compile(r"\bu_\d+\b")


def _ground_universes(anchor: str, variant: str) -> str:
    """Set universes that only the anchor mentions to 0.

    In ``example : A → V`` a universe name is a fixed parameter, so an anchor
    about ``α : Type u_1`` cannot be applied at ``ℕ : Type`` and a specialised
    variant would never follow from it.
    """
    only_anchor = set(_UNIVERSE_RE.findall(anchor)) - set(_UNIVERSE_RE.findall(variant))
    if not only_anchor:
        return anchor
    return _UNIVERSE_RE.sub(lambda m: "0" if m.group(0) in only_anchor else m.group(0), anchor)


def certificate(anchor: str, variant: str, anchor_easy: bool,
                heartbeats: int, timeout: int) -> dict[str, bool]:
    a, v = f"({_ground_universes(anchor, variant)})", f"({variant})"
    cert = {
        "contradiction": _proves(f"{a} → ¬{v}", "intro h", heartbeats, timeout),
        "forward": False,
        "backward": False,
        "variant_alone": False,
        "anchor_alone": anchor_easy,
    }
    if not cert["contradiction"]:
        cert["forward"] = _proves(f"{a} → {v}", "intro h", heartbeats, timeout)
        cert["backward"] = (not anchor_easy) and _proves(f"{v} → {a}", "intro h", heartbeats, timeout)
        cert["variant_alone"] = _proves(v, "have h := True.intro", heartbeats, timeout)
    return cert


def certified_class(cert: dict[str, bool]) -> str:
    if cert["contradiction"]:
        return "contradictory"
    if cert["forward"] and cert["backward"]:
        return "equivalent"
    if cert["forward"] or cert["variant_alone"]:
        return "entailed"
    if cert["backward"]:
        return "stronger"
    return "unverified"


def label_class(structural: str, certified: str) -> str:
    if structural == "equivalent":
        # Only a proof settles it: one direction proved says nothing about the other.
        return certified if certified in ("equivalent", "contradictory") else "unverified"
    if certified == "unverified":
        return structural
    return "graded" if certified == "stronger" else certified


def certify_anchor(rows: list[dict[str, Any]], heartbeats: int, timeout: int) -> list[dict[str, Any]]:
    anchor = rows[0]["original_type_str"]
    applied = [r for r in rows if r.get("status") == "applied" and r.get("variant")]
    anchor_easy = bool(applied) and _proves(anchor, "have h := True.intro", heartbeats, timeout)
    out = []
    for r in rows:
        r = dict(r)
        if r.get("status") == "applied" and r.get("variant"):
            started = time.time()
            cert = certificate(anchor, r["variant"], anchor_easy, heartbeats, timeout)
            structural = SEMANTIC_CLASSES.get(r["perturbation"], "graded")
            r["structural_class"] = structural
            r["certificate"] = cert
            r["certified_class"] = certified_class(cert)
            r["label_class"] = label_class(structural, r["certified_class"])
            r["certify_seconds"] = round(time.time() - started, 2)
        out.append(r)
    return out


def write_summary(rows: list[dict[str, Any]], path: Path) -> None:
    table: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        if "certified_class" in r:
            table[r["perturbation"]][r["certified_class"]] += 1
    lines = [
        "# Certified labels",
        "",
        "Rows: perturbation (structural class). Columns: what Lean automation proved",
        "about each applied variant against its anchor.",
        "",
        "| perturbation | structural | " + " | ".join(CERTIFIED_CLASSES) + " | n |",
        "|---|---|" + "---:|" * (len(CERTIFIED_CLASSES) + 1),
    ]
    for pert in sorted(table, key=lambda p: (SEMANTIC_CLASSES.get(p, "graded"), p)):
        c = table[pert]
        lines.append(
            f"| {pert} | {SEMANTIC_CLASSES.get(pert, 'graded')} | "
            + " | ".join(str(c[k]) for k in CERTIFIED_CLASSES)
            + f" | {sum(c.values())} |"
        )
    labels = Counter(r["label_class"] for r in rows if "label_class" in r)
    lines += ["", "Final labels used by the eval: "
              + ", ".join(f"{k} {v}" for k, v in sorted(labels.items())), ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True,
                    help="directory holding results.jsonl from run_benchmark_review.py")
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--heartbeats", type=int, default=100000,
                    help="maxHeartbeats per proof attempt (Lean's default is 200000)")
    ap.add_argument("--timeout", type=int, default=60, help="wall-clock seconds per Lean call")
    ap.add_argument("--limit", type=int, help="only the first N anchors")
    ap.add_argument("--resume", action="store_true",
                    help="keep anchors already in certified.jsonl")
    ap.add_argument("--deadline-epoch", type=float,
                    help="start no new anchors after this Unix time")
    args = ap.parse_args()

    by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in (args.run / "results.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            by_anchor[r["source_id"]].append(r)
    anchor_ids = list(by_anchor)[: args.limit] if args.limit else list(by_anchor)

    out_path = args.run / "certified.jsonl"
    done: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if args.resume and out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            done[r["source_id"]].append(r)
    else:
        out_path.write_text("", encoding="utf-8")
    todo = [a for a in anchor_ids if a not in done]
    print(f"{len(anchor_ids)} anchors, {len(done)} already certified, "
          f"{len(todo)} to go, {args.num_workers} worker(s)", flush=True)

    started = time.time()
    pool = ProcessPoolExecutor(max_workers=max(1, args.num_workers))
    with out_path.open("a", encoding="utf-8") as fh:
        pending = {pool.submit(certify_anchor, by_anchor[a], args.heartbeats, args.timeout): a
                   for a in todo}
        while pending:
            timeout = None if args.deadline_epoch is None else max(0.0, args.deadline_epoch - time.time())
            finished, _ = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
            for fut in finished:
                aid = pending.pop(fut)
                rows = fut.result()
                done[aid] = rows
                for r in rows:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                fh.flush()
                n = sum(1 for r in rows if "certified_class" in r)
                print(f"  [{len(done)}/{len(anchor_ids)}] {aid}: {n} variants, "
                      f"{time.time() - started:.0f}s", flush=True)
            if args.deadline_epoch is not None and time.time() >= args.deadline_epoch and pending:
                print(f"deadline reached: {len(pending)} anchors left for --resume", flush=True)
                for proc in list(getattr(pool, "_processes", {}).values()):
                    proc.terminate()
                break
    pool.shutdown(wait=False, cancel_futures=True)

    all_rows = [r for a in anchor_ids for r in done.get(a, [])]
    write_summary(all_rows, args.run / "certify_summary.md")
    print(f"wrote {out_path} and {args.run / 'certify_summary.md'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
