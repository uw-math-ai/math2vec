#!/usr/bin/env python
"""One-time repair of a Mathlib run directory written before ids were unique.

Old runs keyed anchors by the dataset's ``index`` field, which repeats
(20,000 theorems shared 814 ids). This rewrites every id from the declaration
name (``prepare_mathlib_full_anchors.anchor_id``) in ``anchors.jsonl``,
``results.jsonl`` and ``certified.jsonl``.

It also drops anchors that were skipped as non-elaborating but use universe
names. Those failed only because the closed check did not declare universes;
removing them lets ``run_benchmark_review.py --resume`` check them again.

Writes ``<run>/.rekeyed_v2`` and does nothing on later calls, so it is safe to
run at the start of every Slurm submission.

Usage::

    python pipeline/rekey_mathlib_run.py --run data/mathlib-20k
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any

MARKER = ".rekeyed_v2"
HERE = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _read(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # truncated last line from a kill mid-write
    return rows


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def rekey(run: Path) -> dict[str, int]:
    anchor_id = _load("prepare_mathlib_full_anchors").anchor_id
    universe_names = _load("run_benchmark_review").universe_names
    stats = {"anchors": 0, "duplicates": 0, "retry_universe": 0,
             "results": 0, "certified": 0}

    retry: set[str] = set()
    anchors_path = run / "anchors.jsonl"
    if anchors_path.exists():
        kept, seen = [], set()
        for a in _read(anchors_path):
            a["id"] = anchor_id(a["declaration"])
            if a["id"] in seen:
                stats["duplicates"] += 1
                continue
            seen.add(a["id"])
            if a.get("skipped") and universe_names(a.get("type_str", "")):
                retry.add(a["id"])
                stats["retry_universe"] += 1
                continue
            kept.append(a)
        _write(anchors_path, kept)
        stats["anchors"] = len(kept)

    for name in ("results.jsonl", "certified.jsonl"):
        path = run / name
        if not path.exists():
            continue
        rows = []
        for r in _read(path):
            r["source_id"] = anchor_id(r["declaration"])
            if r["source_id"] not in retry:
                rows.append(r)
        _write(path, rows)
        stats[name.split(".")[0]] = len(rows)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    args = ap.parse_args()

    marker = args.run / MARKER
    if marker.exists():
        print(f"{args.run}: ids already unique ({MARKER})", flush=True)
        return 0
    if not args.run.exists():
        args.run.mkdir(parents=True)
        marker.write_text("new run\n", encoding="utf-8")
        return 0
    stats = rekey(args.run)
    marker.write_text(json.dumps(stats) + "\n", encoding="utf-8")
    print(f"{args.run}: re-keyed {json.dumps(stats)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
