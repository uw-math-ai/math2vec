"""v2 of the medium hard negatives: every negative applies TWO edit methods.

Both edits push the conclusion further from the original, so the negative stays
false and is easier to tell apart than a one-token flip.

Pairs
  relation_change + constant_shift    a >= 6      ->  a < 3        (RHS is an integer)
  relation_change + offset_insertion  a >= b + c  ->  a < b + c - 2 (RHS is an expression)

Usage: python generate_medium_hard_negatives_v2.py [input.json] [output.json] [count]
"""
import json
import random
import re
import sys
import time
from pathlib import Path

from generate_medium_hard_negatives import analyse, lean_goal_span, nl_sym, rows, splice

HERE = Path(__file__).parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "medium_flc.json"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "medium_hard_negatives_v2.json"
COUNT = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
V1 = HERE / "medium_hard_negatives.json"
LABEL = "medium_hard_negatives"

LEAN_SYM = {"le": ">", "lt": "≥", "ge": "<", "gt": "≤"}
NL_SYM = {"le": ">", "lt": r"\ge", "ge": "<", "gt": r"\le"}
LEAN_RHS_BAD = re.compile(r"∑|∏|∫|⨆|⨅|∀|,|%|\bfun\b|\bif\b")
NL_RHS_BAD = re.compile(r"\\(?:sum|prod|int|lim|max|min|sup|inf|text|quad|qquad|cdots|ldots|dots|pm|mp|\\)|&|,|;|[A-Za-z]{4,}")
NL_CLOSE = re.compile(r"\\\)|\\\]|\$")


def plan_shift(cls, c, rng):
    """Pick (up, new_constant) so the new claim contradicts the original."""
    if cls in ("le", "lt"):
        up = True
    elif cls in ("ge", "gt"):
        up = False
    else:
        up = rng.random() < 0.5
    down = c - max(2, (abs(c) + 1) // 2)
    if c >= 0 and down < 0:
        down = 0
    if not up and down == c:
        if cls != "eq":
            return None
        up = True
    return up, (c + max(2, abs(c)) if up else down)


def norm(expr):
    """Reduce an NL or Lean expression to letters, digits and +/- for comparison."""
    expr = re.sub(r"\\[dt]?frac|\\cdot|\\times|\\left|\\right|\\sqrt|\bReal\.|\bsqrt\b|√", "", expr)
    return re.sub(r"[^A-Za-z0-9+-]", "", expr)


def plan_offset(row, info):
    """Locate where an offset term can be appended to the RHS in both views."""
    code, stmt = row["lean_code"], row["statement"]
    gs, ge = lean_goal_span(code)
    rhs = code[info["lean_rel"][1]:ge]
    if LEAN_RHS_BAD.search(rhs) or not rhs.strip() or re.fullmatch(r"\s*\(?-?\d+\)?\s*", rhs):
        return None
    lean_at = info["lean_rel"][1] + len(rhs.rstrip())
    m = NL_CLOSE.search(stmt, info["nl_rel"][1])
    if not m:
        return None
    nl_rhs = stmt[info["nl_rel"][1]:m.start()]
    core = nl_rhs.rstrip().rstrip(".").rstrip()
    if (not core.strip() or NL_RHS_BAD.search(core)
            or core.count("{") != core.count("}")
            or core.count("(") != core.count(")")
            or core.count("\\left") != core.count("\\right")):
        return None
    if norm(core) != norm(rhs):  # both views must state the same right-hand side
        return None
    return lean_at, info["nl_rel"][1] + len(core)


def make(row, info, kind, rng):
    code, stmt, cls = row["lean_code"], row["statement"], info["cls"]
    if kind == "shift":
        c = info["lit"]
        up, new = plan_shift(cls, c, rng)
        lean_sym = LEAN_SYM.get(cls, ">" if up else "<")
        nl_new = NL_SYM.get(cls, ">" if up else "<")
        lean = splice(code, [(info["lean_rel"], lean_sym), (info["lean_lit"], str(new))])
        nl = splice(stmt, [(info["nl_rel"], nl_sym(stmt, info["nl_rel"], nl_new)), (info["nl_lit"], str(new))])
        methods = ["relation_change", "constant_shift"]
        note = f"relation changed ({cls}) and constant shifted {c} -> {new}"
    else:
        lean_at, nl_at = info["offset"]
        k = rng.choice((1, 2, 3, 5, 10))
        term = f" + {k}" if cls in ("le", "lt") else f" - {k}"
        lean = splice(code, [(info["lean_rel"], LEAN_SYM[cls]), ((lean_at, lean_at), term)])
        nl = splice(stmt, [(info["nl_rel"], nl_sym(stmt, info["nl_rel"], NL_SYM[cls])), ((nl_at, nl_at), term)])
        methods = ["relation_change", "offset_insertion"]
        note = f"relation changed ({cls}) and offset{term} added to the right-hand side"
    return dict(id=row["id"], label=LABEL, version=2, methods=methods, difficulty=row.get("difficulty"),
                statement=stmt, lean_code=code, hard_negative=dict(nl=nl, lean=lean), note=note)


def main():
    rng = random.Random(0)
    v1_ids = {r["id"] for r in json.loads(V1.read_text(encoding="utf-8"))} if V1.exists() else set()
    pool = {"shift": [], "offset": []}
    scanned, t0 = 0, time.time()
    for row in rows(SRC):
        scanned += 1
        info = analyse(row)
        if not info or info["cls"] == "ne":
            continue
        slim = {k: row.get(k) for k in ("id", "statement", "lean_code", "difficulty")}
        if info["lit"] is not None:
            if plan_shift(info["cls"], info["lit"], random.Random(0)):
                pool["shift"].append((slim, info))
        elif info["cls"] != "eq":
            info["offset"] = plan_offset(slim, info)
            if info["offset"]:
                pool["offset"].append((slim, info))
    print(f"scanned {scanned} rows in {time.time() - t0:.0f}s; candidates:", {k: len(v) for k, v in pool.items()})

    out = []
    for kind, quota in (("shift", COUNT // 2), ("offset", COUNT - COUNT // 2)):
        cands = pool[kind]
        rng.shuffle(cands)
        cands.sort(key=lambda x: x[0]["id"] not in v1_ids)  # reuse v1 anchors first
        out += [make(row, info, kind, rng) for row, info in cands[:quota]]
    rng.shuffle(out)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(out)} negatives to {OUT.name};",
          {k: sum(o['methods'][1].startswith('constant' if k == 'shift' else 'offset') for o in out) for k in pool},
          "| anchors shared with v1:", sum(o["id"] in v1_ids for o in out))


if __name__ == "__main__":
    main()
