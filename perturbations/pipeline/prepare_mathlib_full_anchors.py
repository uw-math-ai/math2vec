#!/usr/bin/env python
"""Write one perturbation anchor per Mathlib theorem in the math2vec corpus.

The corpus is ``FrenzyMath/mathlib_informal_v4.19.0``, the informal/Lean
pairs the project trains on. Each theorem or lemma with a Lean ``type``
becomes one JSONL record in the shape ``run_benchmark_review.py
--anchors-file`` already accepts. No Lean call: statements that do not
elaborate against plain Mathlib are dropped later by ``--skip-noncompiling``.

Usage::

    python pipeline/prepare_mathlib_full_anchors.py --out data/mathlib-full/mathlib_anchors.jsonl
    python pipeline/prepare_mathlib_full_anchors.py --jsonl data.jsonl --limit 100 --out /tmp/a.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

HF_REPO = "FrenzyMath/mathlib_informal_v4.19.0"
HF_FILE = "data.jsonl"
_KINDS = {"theorem", "lemma"}


def _join_name(value: Any) -> str:
    if isinstance(value, list):
        return ".".join(str(part) for part in value)
    return "" if value is None else str(value)


def anchor_from_record(rec: dict[str, Any], fallback_index: int) -> dict[str, Any] | None:
    """One review anchor, or None when the row is not a usable theorem or lemma."""
    kind = rec.get("kind")
    if kind is not None and kind not in _KINDS:
        return None
    type_str = " ".join((rec.get("type") or "").split())
    if not type_str or "sorry" in type_str:
        return None
    declaration = _join_name(rec.get("name"))
    if not declaration or "✝" in declaration or declaration.startswith("_"):
        return None
    index = rec.get("index", fallback_index)
    module = _join_name(rec.get("module_name")) or "Mathlib"
    return {
        "id": f"mathlib_{index}",
        "declaration": declaration,
        "module": module,
        "raw_signature": type_str,
        "type_str": type_str,
        "body": type_str,
        "is_definition": False,
        "csv_rows": [],
        "pair_ids": [f"mathlib:{index}"],
    }


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


def write_anchors(records: Iterator[dict[str, Any]], out: Path, limit: int | None) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open("w", encoding="utf-8") as fh:
        for i, rec in enumerate(records):
            anchor = anchor_from_record(rec, i)
            if anchor is None:
                continue
            fh.write(json.dumps(anchor, ensure_ascii=False) + "\n")
            n += 1
            if limit is not None and n >= limit:
                break
    return n


def dataset_jsonl() -> Path:
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(HF_REPO, HF_FILE, repo_type="dataset", local_files_only=True))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jsonl", type=Path,
                    help="local data.jsonl (default: the cached Hugging Face copy)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--limit", type=int, help="stop after this many anchors")
    args = ap.parse_args()

    path = args.jsonl if args.jsonl is not None else dataset_jsonl()
    n = write_anchors(iter_jsonl(path), args.out, args.limit)
    print(f"{n} anchors -> {args.out}", flush=True)
    return 0 if n else 1


if __name__ == "__main__":
    raise SystemExit(main())
