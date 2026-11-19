"""Turn certified perturbations into contrastive training data.

Reads ``<run>/certified.jsonl`` (from certify_labels.py) and writes one record
per anchor that has at least one Lean-certified equivalent variant and at
least one hard negative::

    {"source_id": ..., "module": ..., "anchor": "<Lean statement>",
     "positives": [{"text": ..., "perturbation": ...}, ...],
     "negatives": [{"text": ..., "perturbation": ..., "class": ...}, ...]}

Positives are variants whose ``label_class`` is ``equivalent``; every other
class (entailed, graded, contradictory) is a hard negative: a statement that
looks almost the same and says something different. ``unverified`` variants
are left out, as is any text that turns up on both sides.

Anchors are split into train and dev by ``module`` (the blueprint project, or
the Mathlib module), so near-duplicate statements from one project never end
up on both sides. Outputs, in ``--out`` (default ``<run>/training``):

* ``train.jsonl``, ``dev.jsonl`` -- the records above
* ``dev_certified.jsonl`` -- the certified rows of the dev anchors, for
  ``mteb_perturbation_eval.py`` before and after fine-tuning
* ``stats.json``

Usage::

    python pipeline/export_training_data.py --run data/blueprint-review
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _norm(text: str) -> str:
    return " ".join(text.split())


def build_records(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Counter]:
    by_anchor: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("status") == "applied" and r.get("variant") and r.get("label_class"):
            by_anchor[r["source_id"]].append(r)

    stats: Counter = Counter()
    records = []
    for sid, variants in by_anchor.items():
        anchor = variants[0]["original_type_str"]
        pos: dict[str, str] = {}
        neg: dict[str, tuple[str, str]] = {}
        for r in variants:
            text, cls = _norm(r["variant"]), r["label_class"]
            if text == _norm(anchor) or cls == "unverified":
                continue
            if cls == "equivalent":
                pos.setdefault(text, r["perturbation"])
            else:
                neg.setdefault(text, (r["perturbation"], cls))
        ambiguous = pos.keys() & neg.keys()
        stats["ambiguous_variants"] += len(ambiguous)
        for text in ambiguous:
            del pos[text], neg[text]
        if not pos:
            stats["skipped_no_positive"] += 1
            continue
        if not neg:
            stats["skipped_no_negative"] += 1
            continue
        records.append({
            "source_id": sid,
            "module": variants[0].get("module") or "UNKNOWN",
            "anchor": anchor,
            "positives": [{"text": t, "perturbation": p} for t, p in pos.items()],
            "negatives": [{"text": t, "perturbation": p, "class": c}
                          for t, (p, c) in neg.items()],
        })
    return records, stats


def split_by_module(records: list[dict[str, Any]], dev_frac: float,
                    seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    modules = sorted({r["module"] for r in records})
    random.Random(seed).shuffle(modules)
    n_dev = max(1, round(len(modules) * dev_frac)) if len(modules) > 1 else 0
    dev_modules = set(modules[:n_dev])
    train = [r for r in records if r["module"] not in dev_modules]
    dev = [r for r in records if r["module"] in dev_modules]
    return train, dev


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True,
                    help="directory holding certified.jsonl from certify_labels.py")
    ap.add_argument("--out", type=Path, help="output directory (default <run>/training)")
    ap.add_argument("--dev-frac", type=float, default=0.15,
                    help="fraction of modules (projects) held out for dev")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    certified = args.run / "certified.jsonl"
    if not certified.exists():
        ap.error(f"{certified} not found; run pipeline/certify_labels.py first")
    rows = [json.loads(line) for line in certified.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    records, stats = build_records(rows)
    train, dev = split_by_module(records, args.dev_frac, args.seed)

    out = args.out or args.run / "training"
    out.mkdir(parents=True, exist_ok=True)
    write_jsonl(out / "train.jsonl", train)
    write_jsonl(out / "dev.jsonl", dev)
    dev_ids = {r["source_id"] for r in dev}
    write_jsonl(out / "dev_certified.jsonl", [r for r in rows if r["source_id"] in dev_ids])

    def summary(recs: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "anchors": len(recs),
            "modules": len({r["module"] for r in recs}),
            "positives": sum(len(r["positives"]) for r in recs),
            "negatives": sum(len(r["negatives"]) for r in recs),
            "negatives_by_class": dict(Counter(n["class"] for r in recs for n in r["negatives"])),
        }

    report = {"train": summary(train), "dev": summary(dev), **stats}
    (out / "stats.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    print(f"wrote {out}/train.jsonl, dev.jsonl, dev_certified.jsonl")
    return 0 if train and dev else 1


if __name__ == "__main__":
    raise SystemExit(main())
