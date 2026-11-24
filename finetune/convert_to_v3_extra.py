#!/usr/bin/env python3
"""Convert "11-20 training run.json" into v3 concept JSONL for
train_qwen_mnrl_multiview_v3_tg.py --extra_train_jsonl (training only).

Per unique problem id:
  - one concept: nl_informal=statement, lean_signature=lean_code,
    hard_negatives.nl = every distinct hard-negative NL statement
  - one concept per distinct hard-negative pair (hn nl <-> hn lean), so the
    perturbed Lean statements are also trained against their own text.
"""
import json
import re
import sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "11-20 training run.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "11-20_extra_v3.jsonl"
MODULE = "MediumHardNegatives"


def clean_lean(code: str) -> str:
    lines = [l for l in code.splitlines() if not l.strip().startswith("import ")]
    return re.sub(r"\s*:=\s*by\s+sorry\s*$", "", "\n".join(lines).strip()).strip()


def concept(cid, nl, lean, hn_nls):
    return {
        "concept_id": cid,
        "views": {"nl_informal": nl, "lean_signature": lean},
        "hard_negatives": {"nl": hn_nls},
        "metadata": {"module_name": MODULE},
    }


with open(SRC, encoding="utf-8") as f:
    rows = json.load(f)

problems = {}
for r in rows:
    p = problems.setdefault(r["id"], {"nl": r["statement"].strip(),
                                      "lean": clean_lean(r["lean_code"]), "hn": {}})
    hn_nl = r["hard_negative"]["nl"].strip()
    p["hn"].setdefault(hn_nl, clean_lean(r["hard_negative"]["lean"]))

n = 0
with open(OUT, "w", encoding="utf-8") as f:
    for pid, p in problems.items():
        f.write(json.dumps(concept(f"medium_{pid}", p["nl"], p["lean"], list(p["hn"])),
                           ensure_ascii=False) + "\n")
        n += 1
        for k, (hn_nl, hn_lean) in enumerate(p["hn"].items()):
            f.write(json.dumps(concept(f"medium_{pid}_neg{k}", hn_nl, hn_lean, []),
                               ensure_ascii=False) + "\n")
            n += 1
print(f"{len(rows)} rows -> {len(problems)} problems, {n} concepts -> {OUT}")
