"""Build medium-difficulty hard negatives from medium_flc.json.

Each negative edits the conclusion of a (statement, lean_code) pair in both views.
Only rows whose Lean goal is a single atomic relation are used, so every edit
contradicts the original conclusion (assuming the original is true and its
hypotheses are satisfiable).

Methods
  relation_negation   a >= b   ->  a < b          (one edit)
  constant_change     a = c    ->  a = c'         (one edit)
  relation_and_shift  a >= c   ->  a < c - k      (two edits, easier to tell apart)

Usage: python generate_medium_hard_negatives.py [input.json] [output.json] [count]
"""
import json
import random
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "medium_flc.json"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "medium_hard_negatives.json"
COUNT = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
LABEL = "medium_hard_negatives"
TIME_BUDGET = 150  # seconds of scanning before sampling from what was found

OPEN, CLOSE = "([{⦃⟨", ")]}⦄⟩"
LEAN_REL = re.compile(r"≤|≥|≠|<|>|=")
LEAN_CLASS = {"≤": "le", "≥": "ge", "≠": "ne", "<": "lt", ">": "gt", "=": "eq"}
LEAN_BAD = re.compile(r"=>|<=|>=|!=|<\||\|>|<\$>|<;>|:=|↔|∧|∨|¬|∃|→|←|\bif\b|\blet\b|\bfun\b|λ|\|")
LEAN_NEG = {"ge": "<", "le": ">", "lt": "≥", "gt": "≤", "eq": "≠", "ne": "="}
LEAN_LIT = re.compile(r"\s*(-?\d+)\s*$")

NL_REL = re.compile(r"\\(?:geqslant|leqslant|geq|leq|ge|le|neq|ne|lt|gt)(?![A-Za-z])|≤|≥|≠|<|>|=")
NL_BAD = re.compile(r"\\iff|\\Leftrightarrow|\\implies|\\Rightarrow|\\Longrightarrow|\\exists|\\equiv|\\not|\\mid|\\begin|\\cases|if and only if|there exist|\bor\b|\biff\b", re.I)
NL_LIT = re.compile(r"\s*(-?\d+)(?=\s*(?:\$|\\\)|\\\]|[.,;]?\s*$|[.,;]\s))")
NL_NEG = {"ge": "<", "le": ">", "lt": r"\ge", "gt": r"\le", "eq": r"\neq", "ne": "="}
NL_VERB = re.compile(r"\b(?:is|are|equals?|has|have|gives?|yields?)\b", re.I)
MARKERS = ("prove that", "show that", "then")


def nl_class(tok):
    t = tok.lstrip("\\")
    if t in ("geqslant", "geq", "ge", "≥"): return "ge"
    if t in ("leqslant", "leq", "le", "≤"): return "le"
    if t in ("neq", "ne", "≠"): return "ne"
    if t in ("lt", "<"): return "lt"
    if t in ("gt", ">"): return "gt"
    return "eq"


def lean_goal_span(code):
    """Return (start, end) of the goal text inside lean_code, or None."""
    if len(re.findall(r"\b(?:theorem|lemma)\b", code)) != 1:
        return None
    m_end = re.search(r":=\s*by\s+sorry\s*$", code)
    m_start = re.search(r"\b(?:theorem|lemma)\s+\S+", code)
    if not m_end or not m_start:
        return None
    depth = 0
    for i in range(m_start.end(), m_end.start()):
        ch = code[i]
        if ch in OPEN: depth += 1
        elif ch in CLOSE: depth -= 1
        elif ch == ":" and depth == 0 and code[i + 1] != "=":
            return i + 1, m_end.start()
    return None


def analyse(row):
    """Find the single aligned conclusion relation in both views, or None."""
    code, stmt = row.get("lean_code"), row.get("statement")
    if not isinstance(code, str) or not isinstance(stmt, str) or len(stmt) > 700:
        return None
    span = lean_goal_span(code)
    if not span:
        return None
    gs, ge = span
    goal = code[gs:ge]
    if LEAN_BAD.search(goal):
        return None
    rels = list(LEAN_REL.finditer(goal))
    if len(rels) != 1:
        return None
    lr = rels[0]
    cls = LEAN_CLASS[lr.group()]

    low = stmt.lower()
    pos = max((low.rfind(mk) + len(mk) if low.rfind(mk) >= 0 else -1) for mk in MARKERS)
    if pos < 0:
        return None
    tail = stmt[pos:]
    if NL_BAD.search(tail):
        return None
    nrels = list(NL_REL.finditer(tail))
    if len(nrels) != 1 or nl_class(nrels[0].group()) != cls:
        return None
    nr = nrels[0]
    before, after = tail[:nr.start()], tail[nr.end():]
    # the relation must be the conclusion itself: not inside a subscript/argument,
    # and not followed by a verb that carries the real claim ("... = 2 is 12")
    if before.count("{") != before.count("}") or NL_VERB.search(after):
        return None

    info = dict(cls=cls,
                lean_rel=(gs + lr.start(), gs + lr.end()),
                nl_rel=(pos + nr.start(), pos + nr.end()),
                lit=None)
    ll = LEAN_LIT.match(goal, lr.end())
    nl = NL_LIT.match(tail, nr.end())
    if ll and nl and ll.group(1) == nl.group(1):
        info["lit"] = int(ll.group(1))
        info["lean_lit"] = (gs + ll.start(1), gs + ll.end(1))
        info["nl_lit"] = (pos + nl.start(1), pos + nl.end(1))
    return info


def splice(text, edits):
    for (a, b), new in sorted(edits, reverse=True):
        text = text[:a] + new + text[b:]
    return text


def nl_sym(text, span, sym):
    """Insert an NL relation, padding so a TeX command never fuses with a letter."""
    after = text[span[1]:span[1] + 1]
    return sym + " " if sym.startswith("\\") and after.isalpha() else sym


def make(row, info, method, rng):
    code, stmt, cls, c = row["lean_code"], row["statement"], info["cls"], info["lit"]
    if method == "relation_negation":
        lean = splice(code, [(info["lean_rel"], LEAN_NEG[cls])])
        nl = splice(stmt, [(info["nl_rel"], nl_sym(stmt, info["nl_rel"], NL_NEG[cls]))])
        note = f"conclusion relation negated ({cls})"
    elif method == "constant_change":
        deltas = [d for d in (-10, -5, -3, -2, -1, 1, 2, 3, 5, 10) if not (c >= 0 and c + d < 0)]
        new = c + rng.choice(deltas)
        lean = splice(code, [(info["lean_lit"], str(new))])
        nl = splice(stmt, [(info["nl_lit"], str(new))])
        note = f"constant in conclusion changed {c} -> {new}"
    else:  # relation_and_shift
        up = cls in ("le", "lt") or (cls == "eq" and rng.random() < 0.5)
        down_ks = [k for k in (1, 2, 3, 5) if c < 0 or c - k >= 0]  # keep naturals non-negative
        if not up and not down_ks:
            up = True
        k = rng.choice((1, 2, 3, 5) if up else down_ks)
        new = c + k if up else c - k
        lean_sym = {"le": ">", "lt": "≥", "ge": "<", "gt": "≤", "eq": ">" if up else "<"}[cls]
        nl_new = {"le": ">", "lt": r"\ge", "ge": "<", "gt": r"\le", "eq": ">" if up else "<"}[cls]
        lean = splice(code, [(info["lean_rel"], lean_sym), (info["lean_lit"], str(new))])
        nl = splice(stmt, [(info["nl_rel"], nl_sym(stmt, info["nl_rel"], nl_new)), (info["nl_lit"], str(new))])
        note = f"relation changed and constant shifted {c} -> {new} ({cls})"
    return dict(id=row["id"], label=LABEL, method=method, difficulty=row.get("difficulty"),
                statement=stmt, lean_code=code,
                hard_negative=dict(nl=nl, lean=lean), note=note)


def eligible(info):
    out = ["relation_negation"]
    c, cls = info["lit"], info["cls"]
    if c is not None:
        if cls == "eq":
            out += ["constant_change", "relation_and_shift"]
        elif cls in ("le", "lt") or (cls in ("ge", "gt") and (c < 0 or c >= 1)):
            out.append("relation_and_shift")
    return out


def rows(path):
    buf = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.rstrip("\n")
            if s == "  {":
                buf = ["{"]
            elif s in ("  }", "  },"):
                buf.append("}")
                yield json.loads("\n".join(buf))
                buf = []
            elif buf:
                buf.append(s)


def main():
    rng = random.Random(0)
    pool = {"relation_negation": [], "constant_change": [], "relation_and_shift": []}
    scanned, t0 = 0, time.time()
    for row in rows(SRC):
        scanned += 1
        info = analyse(row)
        if info:
            slim = {k: row.get(k) for k in ("id", "statement", "lean_code", "difficulty")}
            for m in eligible(info):
                pool[m].append((slim, info))
        if time.time() - t0 > TIME_BUDGET:
            break
    print(f"scanned {scanned} rows in {time.time() - t0:.0f}s; candidates:",
          {m: len(v) for m, v in pool.items()})

    quota = {"constant_change": COUNT // 3, "relation_and_shift": COUNT // 3}
    quota["relation_negation"] = COUNT - sum(quota.values())
    used, out = set(), []
    for m in ("relation_and_shift", "constant_change", "relation_negation"):
        cands = [x for x in pool[m] if x[0]["id"] not in used]
        rng.shuffle(cands)
        for row, info in cands[:quota[m]]:
            used.add(row["id"])
            out.append(make(row, info, m, rng))
    rng.shuffle(out)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(out)} negatives to {OUT.name}:",
          {m: sum(o['method'] == m for o in out) for m in pool})


if __name__ == "__main__":
    main()
