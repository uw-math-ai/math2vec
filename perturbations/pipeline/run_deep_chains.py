#!/usr/bin/env python
"""Perturb one statement over and over, and keep the whole tree.

``run_benchmark_review.py`` answers "what does each perturbation do to a fresh
anchor?" — one level, many anchors. This runner answers the opposite question:
**what does the space around a single theorem look like once you perturb it,
then perturb the perturbations?**

It grows a tree breadth-first. The root is the anchor; expanding a node means
trying perturbations against *that node's* statement and keeping whatever
survives. Every surviving node is re-elaborated standalone before it is
recorded, which matters far more here than at depth 1: a tactic-produced
statement that only elaborates in its original context would otherwise become
the parent of a whole broken subtree.

Nodes are keyed by a hash of their statement, so a variant reachable by two
different paths is stored once, and re-running with the same ``--out`` resumes
instead of redoing work.

Output is ``nodes.jsonl``, which ``analyze_geometry.py`` reads directly::

    python pipeline/run_deep_chains.py --anchor bench_000 --depth 3
    python pipeline/analyze_geometry.py --run data/deep-chains
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "pipeline"))


def node_id(statement: str) -> str:
    """Content-addressed id, so the same statement is always the same node."""
    normalised = " ".join(statement.split())
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:12]


def expand(job: dict[str, Any]) -> dict[str, Any]:
    """Try every requested perturbation against one node's statement.

    Runs in a worker process. Returns the parent's id alongside the children so
    the parent process can stitch the tree back together without sharing state.
    """
    from wiggle.chains import normalize_statement
    from wiggle.lean_runner import compile_lean
    from wiggle.registry import PROPAGATION_RULES, TRANSFORMS

    parent_stmt = job["statement"]
    started = time.time()
    children: list[dict[str, Any]] = []
    tried = 0

    for name in job["perturbations"]:
        tried += 1
        try:
            outcome = TRANSFORMS[name](job["source_id"], parent_stmt)
        except Exception:
            # A transform that throws on an unusual statement shape should cost
            # us one branch, not the run.
            continue
        if outcome is None:
            continue

        statement = normalize_statement(outcome[1])
        if " ".join(statement.split()) == " ".join(parent_stmt.split()):
            continue
        if not compile_lean("", statement):
            continue

        rules = PROPAGATION_RULES[name]
        children.append(
            {
                "node_id": node_id(statement),
                "parent_id": job["node_id"],
                "path": job["path"] + [name],
                "depth": job["depth"] + 1,
                "statement": statement,
                "is_true": rules.get(job["is_true"], "unknown"),
            }
        )

    return {
        "node_id": job["node_id"],
        "children": children,
        "tried": tried,
        "seconds": round(time.time() - started, 1),
    }


def main() -> int:
    from run_benchmark_review import DEFAULT_CSV, load_anchors

    from wiggle.registry import PERTURBATIONS

    all_names = [p.name for p in PERTURBATIONS]

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--anchor", action="append",
                    help="Anchor id (e.g. bench_000). Repeatable. "
                         "Default: the first Mathlib anchor.")
    ap.add_argument("--depth", type=int, default=3,
                    help="Maximum tree depth (default 3).")
    ap.add_argument("--max-nodes", type=int, default=80,
                    help="Stop after this many nodes have been expanded, "
                         "per anchor. The tree branches fast; this is the "
                         "wallclock control (default 80).")
    ap.add_argument("--branch-sample", type=int, default=0,
                    help="At depth >= 1, try only this many randomly chosen "
                         "perturbations per node instead of all "
                         f"{len(all_names)}. 0 means try all (default).")
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path,
                    default=PROJECT_ROOT / "data" / "deep-chains")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    nodes_path = args.out / "nodes.jsonl"

    anchors = load_anchors(args.csv, "Mathlib", None, None)
    by_id = {a["id"]: a for a in anchors}
    wanted = args.anchor or [anchors[0]["id"]]
    missing = [w for w in wanted if w not in by_id]
    if missing:
        print(f"unknown anchor(s): {missing}\navailable: {list(by_id)}",
              file=sys.stderr)
        return 1

    # ── Resume ────────────────────────────────────────────────────────────────
    # Everything already on disk is both a node we must not duplicate and, if
    # it was never used as a parent, a node still waiting to be expanded.
    known: dict[str, dict[str, Any]] = {}
    expanded: set[str] = set()
    if nodes_path.exists():
        for line in nodes_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            known[rec["node_id"]] = rec
            if rec.get("parent_id"):
                expanded.add(rec["parent_id"])
        print(f"resuming: {len(known)} nodes already on disk", flush=True)

    out = open(nodes_path, "a", encoding="utf-8")

    def emit(rec: dict[str, Any]) -> None:
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()

    total_new = 0
    for anchor_id in wanted:
        anchor = by_id[anchor_id]
        root_stmt = anchor["type_str"]
        root = {
            "node_id": node_id(root_stmt),
            "parent_id": None,
            "source_id": anchor_id,
            "declaration": anchor["declaration"],
            "module": anchor["module"],
            "original_type_str": root_stmt,
            "path": [],
            "depth": 0,
            "statement": root_stmt,
            "is_true": "true",
            "status": "ok",
        }
        if root["node_id"] not in known:
            known[root["node_id"]] = root
            emit(root)

        print(f"\n=== {anchor_id}  {anchor['declaration']} ===", flush=True)
        print(f"depth<={args.depth}, max {args.max_nodes} expansions, "
              f"{args.num_workers} workers", flush=True)

        # Frontier is rebuilt from what is on disk for this anchor, so a resumed
        # run picks up exactly the nodes that were never used as a parent.
        frontier = [
            r for r in known.values()
            if r.get("source_id") == anchor_id
            and r["node_id"] not in expanded
            and r["depth"] < args.depth
        ]
        frontier.sort(key=lambda r: r["depth"])

        budget = args.max_nodes
        started = time.time()

        while frontier and budget > 0:
            level = frontier[0]["depth"]
            batch = [r for r in frontier if r["depth"] == level][:budget]
            frontier = [r for r in frontier if r not in batch]
            budget -= len(batch)

            jobs = []
            for r in batch:
                names = all_names
                if args.branch_sample and r["depth"] >= 1:
                    names = rng.sample(all_names,
                                       min(args.branch_sample, len(all_names)))
                jobs.append({
                    "node_id": r["node_id"],
                    "source_id": anchor_id,
                    "statement": r["statement"],
                    "path": r["path"],
                    "depth": r["depth"],
                    "is_true": r["is_true"],
                    "perturbations": names,
                })

            print(f"\n-- depth {level}: expanding {len(jobs)} node(s), "
                  f"{budget} expansions left in budget", flush=True)

            def absorb(res: dict[str, Any], done: int) -> None:
                nonlocal total_new
                expanded.add(res["node_id"])
                fresh = 0
                for child in res["children"]:
                    if child["node_id"] in known:
                        continue
                    rec = {
                        **child,
                        "source_id": anchor_id,
                        "declaration": anchor["declaration"],
                        "module": anchor["module"],
                        "original_type_str": root_stmt,
                        "status": "ok",
                    }
                    known[rec["node_id"]] = rec
                    emit(rec)
                    fresh += 1
                    total_new += 1
                    if rec["depth"] < args.depth:
                        frontier.append(rec)
                print(f"  [{done}/{len(jobs)}] +{fresh} new "
                      f"({len(res['children'])} survived of {res['tried']}, "
                      f"{res['seconds']}s)", flush=True)

            workers = max(1, min(args.num_workers, len(jobs)))
            if workers == 1:
                # Also the only path that works where the sandbox forbids the
                # semaphores ProcessPoolExecutor needs.
                for done, j in enumerate(jobs, 1):
                    absorb(expand(j), done)
            else:
                with ProcessPoolExecutor(max_workers=workers) as pool:
                    futures = {pool.submit(expand, j): j for j in jobs}
                    for done, fut in enumerate(as_completed(futures), 1):
                        absorb(fut.result(), done)

            elapsed = time.time() - started
            n_anchor = sum(1 for r in known.values()
                           if r.get("source_id") == anchor_id)
            print(f"-- {n_anchor} nodes for {anchor_id}, {elapsed:.0f}s elapsed",
                  flush=True)

    out.close()
    print(f"\n{total_new} new nodes, {len(known)} total\n  {nodes_path}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
