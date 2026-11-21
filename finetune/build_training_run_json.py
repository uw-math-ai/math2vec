#!/usr/bin/env python3
"""Build "11-20 training run.json": 2000 medium-difficulty rows (hard-negative
triplets) to mix into training. Pools medium_hard_negatives.json (v1) and
medium_hard_negatives_v2.json, samples 2000 rows (seed 42)."""
import json
import random

SRC = ["medium_hard_negatives.json", "medium_hard_negatives_v2.json"]
OUT = "11-20 training run.json"
N = 2000

rows = []
for f in SRC:
    with open(f, encoding="utf-8") as fh:
        for r in json.load(fh):
            hn = r.get("hard_negative") or {}
            if r.get("statement") and r.get("lean_code") and hn.get("nl") and hn.get("lean"):
                r["source"] = f
                rows.append(r)

random.Random(42).shuffle(rows)
rows = rows[:N]
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, ensure_ascii=False, indent=1)
print(f"wrote {len(rows)} rows ({len({r['id'] for r in rows})} unique ids) -> {OUT}")
