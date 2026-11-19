#!/usr/bin/env python3
"""
prepare_fineleancorpus.py  --  reformat m-a-p/FineLeanCorpus for math2vec training.

Source columns used (verified against the dataset viewer):
    id, statement, lean_code, compile_result, difficulty, domain, source
(eval_reasons, difficulty_rationale, domain_summary are dropped to save memory.)

IMPORTANT data facts that shape the tasks
  * There is NO separate LaTeX column. `statement` = English prose with inline
    LaTeX. LaTeX-only views are DERIVED by extracting math spans (heuristic, lossy).
  * Every lean_code ends in `sorry` -> no proofs. We therefore do NOT build
    proof-generation tasks; lean->lean tasks are statement-level only.

Tasks emitted (each as prompt/completion JSONL records):
    en2lean            English(+inline LaTeX) statement  -> Lean 4
    lean2en            Lean 4                            -> English statement
    latex2lean         LaTeX-only view                   -> Lean 4
    lean2latex         Lean 4                            -> LaTeX-only view
    lean2lean_complete header + binders                  -> conclusion (+ `:= by sorry`)
    lean2lean_infill   Lean with a <MASK>ed span         -> the masked span
    lean2lean_variant  one formalization                 -> another formalization of the
                                                            same statement (noisy; see README note)

Usage
    pip install datasets
    python prepare_fineleancorpus.py --out_dir data/fineleancorpus_m2v
    python prepare_fineleancorpus.py --local sample.jsonl --out_dir /tmp/out   # offline test
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

COLUMNS = ["id", "statement", "lean_code", "compile_result", "difficulty", "domain", "source"]

ALL_TASKS = [
    "en2lean", "lean2en",
    "latex2lean", "lean2latex",
    "lean2lean_complete", "lean2lean_infill", "lean2lean_variant",
]

# --------------------------------------------------------------------------- #
# Prompt templates (plain text, no new special tokens required)
# --------------------------------------------------------------------------- #
TEMPLATES = {
    "en2lean": "Translate the following mathematical statement into Lean 4 (Mathlib).\n\n{x}\n\nLean 4:\n",
    "lean2en": "Translate the following Lean 4 statement into natural-language mathematics.\n\n{x}\n\nStatement:\n",
    "latex2lean": "Translate the following LaTeX mathematics into a Lean 4 (Mathlib) statement.\n\n{x}\n\nLean 4:\n",
    "lean2latex": "Express the mathematical content of the following Lean 4 statement in LaTeX.\n\n{x}\n\nLaTeX:\n",
    "lean2lean_complete": "Complete the Lean 4 theorem statement.\n\n{x}",
    "lean2lean_infill": "Fill in the <MASK> in the Lean 4 code.\n\n{x}\n\nMasked text:\n",
    "lean2lean_variant": "Rewrite the following Lean 4 statement as an alternative formalization of the same problem.\n\n{x}\n\nAlternative Lean 4:\n",
}

# --------------------------------------------------------------------------- #
# Cleaning / normalisation helpers
# --------------------------------------------------------------------------- #
def clean_text(s: str) -> str:
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def norm_ws(s: str) -> str:
    return " ".join(s.split())


def compiled_ok(cr) -> bool:
    """True if the Lean compile result has no severity=='error' messages.
    (The expected 'declaration uses sorry' warning is fine.)"""
    if cr is None:
        return False
    if isinstance(cr, str):
        try:
            cr = json.loads(cr)
        except Exception:
            return False
    if isinstance(cr, list):
        msgs = cr
    else:
        msgs = (cr or {}).get("messages") or []
    return not any((m or {}).get("severity") == "error" for m in msgs)


def to_text_list(value: Any) -> list[str]:
    """Normalize a scalar/list field into a list of non-empty strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    return [s] if s else []


def parse_int_set(csv: str) -> set[int]:
    vals = set()
    for chunk in csv.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        vals.add(int(chunk))
    return vals


def parse_where_filters(raw_filters: list[str]) -> dict[str, set[str]]:
    """Parse repeatable --where column=value filters (exact, case-insensitive)."""
    out: dict[str, set[str]] = defaultdict(set)
    for raw in raw_filters:
        if "=" not in raw:
            raise ValueError(f"Invalid --where value '{raw}'. Use column=value.")
        col, val = raw.split("=", 1)
        col = col.strip()
        val = val.strip().lower()
        if not col or not val:
            raise ValueError(f"Invalid --where value '{raw}'. Use column=value.")
        if col not in COLUMNS:
            raise ValueError(f"Unknown column '{col}' in --where. Allowed: {', '.join(COLUMNS)}")
        out[col].add(val)
    return dict(out)


def row_matches_filters(
    row: dict,
    *,
    args,
    srcs: set[str],
    dom_substrings: list[str],
    difficulty_values: set[int],
    where_filters: dict[str, set[str]],
) -> tuple[bool, str | None]:
    """Return (keep, reason). reason is a stats key when dropped."""
    if not args.keep_uncompiled and not compiled_ok(row.get("compile_result")):
        return False, "drop_compile_error"

    difficulty_raw = row.get("difficulty")
    try:
        difficulty = int(difficulty_raw)
    except Exception:
        difficulty = None

    if difficulty is None:
        return False, "drop_missing_difficulty"
    if difficulty_values and difficulty not in difficulty_values:
        return False, "drop_difficulty_values"
    if not (args.min_difficulty <= difficulty <= args.max_difficulty):
        return False, "drop_difficulty"

    source = str(row.get("source") or "").strip()
    if srcs and source not in srcs:
        return False, "drop_source"

    domain_text = " ".join(to_text_list(row.get("domain"))).lower()
    if dom_substrings and not any(d in domain_text for d in dom_substrings):
        return False, "drop_domain"

    for col, allowed in where_filters.items():
        values = [v.lower() for v in to_text_list(row.get(col))]
        if not values or not any(v in allowed for v in values):
            return False, f"drop_where_{col}"

    return True, None


def split_bucket(norm_stmt: str, n: int = 1000) -> float:
    h = hashlib.md5(norm_stmt.encode("utf-8")).hexdigest()
    return (int(h, 16) % n) / n


# --------------------------------------------------------------------------- #
# LaTeX-only view (heuristic): keep only the math spans from the statement
# --------------------------------------------------------------------------- #
MATH_RE = re.compile(
    r"\$\$(.+?)\$\$"          # $$ ... $$
    r"|\\\[(.+?)\\\]"         # \[ ... \]
    r"|\\\((.+?)\\\)"         # \( ... \)
    r"|(?<!\\)\$(.+?)(?<!\\)\$",  # $ ... $
    re.S,
)


def latex_view(statement: str, min_chars: int) -> str | None:
    spans = []
    for m in MATH_RE.finditer(statement):
        body = next((g for g in m.groups() if g is not None), "").strip()
        # skip lone-symbol spans like \(R\) / $x$ -- they're prose-anchoring noise
        if len(body) > 2 and len(re.sub(r"\\[A-Za-z]+|[^A-Za-z0-9]", "", body)) > 1:
            spans.append(body)
    if not spans or sum(len(s) for s in spans) < min_chars:
        return None
    return "\n".join(spans)


# --------------------------------------------------------------------------- #
# Lean parsing helpers (lightweight, paren-depth based; skips on any doubt)
# --------------------------------------------------------------------------- #
DECL_RE = re.compile(
    r"^(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable)\s+)*"
    r"(theorem|lemma|def|example|abbrev)\b",
    re.M,
)
PROOF_TAIL_RE = re.compile(r"\s*:=\s*(?:by\s+)?sorry\s*$")
OPEN_B, CLOSE_B = "([{⟨", ")]}⟩"


def split_header(lean: str):
    """-> (header, body, n_decls). header = imports/opens/etc before first decl."""
    decls = list(DECL_RE.finditer(lean))
    if not decls:
        return None, None, 0
    i = decls[0].start()
    return lean[:i].rstrip(), lean[i:], len(decls)


def split_signature(body: str):
    """Split `theorem name binders : conclusion := by sorry`
    -> (prefix_through_colon, conclusion_with_tail) using the first depth-0 ':'."""
    m = DECL_RE.match(body)
    if not m:
        return None
    # skip the declaration name
    n = re.match(r"\s+[^\s(\[{⟨:]+", body[m.end():])
    pos = m.end() + (n.end() if n else 0)
    depth = 0
    for k in range(pos, len(body)):
        c = body[k]
        if c in OPEN_B:
            depth += 1
        elif c in CLOSE_B:
            depth -= 1
        elif c == ":" and depth == 0:
            nxt = body[k + 1] if k + 1 < len(body) else ""
            prv = body[k - 1] if k > 0 else ""
            if nxt in "=:" or prv == ":":
                continue
            prefix, rest = body[: k + 1], body[k + 1:].lstrip()
            if not PROOF_TAIL_RE.search(rest) or len(rest) < 3:
                return None
            return prefix, rest
    return None


def make_infill(lean: str, rng: random.Random):
    """Mask a contiguous span of whitespace-delimited tokens in the signature
    (never the header, never the declaration keyword/name)."""
    header, body, _ = split_header(lean)
    if body is None:
        return None
    m = DECL_RE.match(body)
    n = re.match(r"\s+\S+", body[m.end():])
    region_start = m.end() + (n.end() if n else 0)
    tail = PROOF_TAIL_RE.search(body)
    region_end = tail.start() if tail else len(body)
    region = body[region_start:region_end]
    toks = list(re.finditer(r"\S+", region))
    if len(toks) < 6:
        return None
    k = rng.randint(2, max(2, min(12, int(len(toks) * 0.3))))
    s = rng.randint(0, len(toks) - k)
    a, b = toks[s].start(), toks[s + k - 1].end()
    masked_text = region[a:b]
    new_region = region[:a] + "<MASK>" + region[b:]
    new_body = body[:region_start] + new_region + body[region_end:]
    prompt_code = (header + "\n\n" if header else "") + new_body
    return prompt_code, masked_text


# --------------------------------------------------------------------------- #
# IO
# --------------------------------------------------------------------------- #
def iter_rows(args):
    if args.local and args.local.endswith(".jsonl"):
        with open(args.local, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)
        return
    from datasets import load_dataset  # lazy import

    if args.local:
        ds = load_dataset("parquet", data_files=args.local, split="train")
    else:
        ds = load_dataset(args.dataset, split="train", streaming=args.streaming)
    try:
        ds = ds.select_columns(COLUMNS)
    except Exception:
        pass
    yield from ds


def get_split(norm_stmt: str, val: float, test: float) -> str:
    b = split_bucket(norm_stmt)
    if b < test:
        return "test"
    if b < test + val:
        return "validation"
    return "train"


def rec(task, pair_id, x, y, row, split):
    return {
        "id": f"{pair_id}:{task}",
        "pair_id": pair_id,
        "task": task,
        "prompt": TEMPLATES[task].format(x=x),
        "completion": y,
        "source": row.get("source"),
        "difficulty": row.get("difficulty"),
        "split": split,
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="m-a-p/FineLeanCorpus")
    ap.add_argument("--local", help="local .jsonl or .parquet instead of the HF hub")
    ap.add_argument("--streaming", action="store_true")
    ap.add_argument("--out_dir", default="data/fineleancorpus_m2v")
    ap.add_argument("--tasks", default=",".join(ALL_TASKS), help="comma-separated subset of: " + ", ".join(ALL_TASKS))
    ap.add_argument("--val_frac", type=float, default=0.01)
    ap.add_argument("--test_frac", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--min_difficulty", type=int, default=0)
    ap.add_argument("--max_difficulty", type=int, default=10)
    ap.add_argument("--difficulty_values", default="", help="exact difficulty whitelist, comma-separated (e.g. 5 or 4,5)")
    ap.add_argument("--sources", default="", help="comma-separated source whitelist (e.g. AoPs,Omni-Math)")
    ap.add_argument("--domains", default="", help="comma-separated substrings; keep rows whose domain matches any")
    ap.add_argument("--where", action="append", default=[], help="repeatable exact-match filter: column=value (e.g. --where difficulty=5 --where source=AoPS)")
    ap.add_argument("--max_chars", type=int, default=6000, help="drop rows where statement or lean exceeds this")
    ap.add_argument("--min_latex_chars", type=int, default=8)
    ap.add_argument("--max_variant_pairs", type=int, default=2, help="alt-formalization pairs per statement group")
    ap.add_argument("--limit", type=int, default=0, help="debug: stop after N input rows")
    ap.add_argument("--keep_uncompiled", action="store_true", help="don't filter on compile_result errors")
    args = ap.parse_args()

    tasks = [t.strip() for t in args.tasks.split(",") if t.strip()]
    bad = set(tasks) - set(ALL_TASKS)
    if bad:
        sys.exit(f"unknown tasks: {bad}")
    srcs = {s.strip() for s in args.sources.split(",") if s.strip()}
    doms = [d.strip().lower() for d in args.domains.split(",") if d.strip()]
    try:
        difficulty_values = parse_int_set(args.difficulty_values)
    except ValueError as e:
        sys.exit(f"invalid --difficulty_values: {e}")
    try:
        where_filters = parse_where_filters(args.where)
    except ValueError as e:
        sys.exit(str(e))

    # ---- pass 1: filter, clean, dedupe --------------------------------------
    stats = Counter()
    rows, seen = [], set()
    for i, r in enumerate(iter_rows(args)):
        if args.limit and i >= args.limit:
            break
        stats["input_rows"] += 1
        keep, reason = row_matches_filters(
            r,
            args=args,
            srcs=srcs,
            dom_substrings=doms,
            difficulty_values=difficulty_values,
            where_filters=where_filters,
        )
        if not keep:
            stats[reason] += 1
            continue
        stmt, lean = clean_text(r.get("statement") or ""), clean_text(r.get("lean_code") or "")
        if not stmt or not lean or len(stmt) > args.max_chars or len(lean) > args.max_chars:
            stats["drop_empty_or_long"] += 1
            continue
        key = (norm_ws(stmt), norm_ws(lean))
        if key in seen:
            stats["drop_exact_duplicate"] += 1
            continue
        seen.add(key)
        row_id = str(r.get("id") or f"row-{i}")
        rows.append({
            "id": row_id,
            "statement": stmt,
            "lean": lean,
            "norm_stmt": key[0].lower(),
            "difficulty": r.get("difficulty"),
            "source": r.get("source"),
        })
    stats["kept_rows"] = len(rows)

    # ---- pass 2: build task records -----------------------------------------
    out = {"train": [], "validation": [], "test": []}
    groups = defaultdict(list)  # norm_stmt -> [row, ...] for variant pairs

    for row in rows:
        split = get_split(row["norm_stmt"], args.val_frac, args.test_frac)  # grouped by statement -> no leakage
        row["split"] = split
        groups[row["norm_stmt"]].append(row)
        pid, stmt, lean = row["id"], row["statement"], row["lean"]
        emit = lambda task, x, y: (out[split].append(rec(task, pid, x, y, row, split)), stats.update([task]))

        if "en2lean" in tasks:
            emit("en2lean", stmt, lean)
        if "lean2en" in tasks:
            emit("lean2en", lean, stmt)

        if "latex2lean" in tasks or "lean2latex" in tasks:
            lv = latex_view(stmt, args.min_latex_chars)
            if lv is None:
                stats["skip_no_latex_spans"] += 1
            else:
                if "latex2lean" in tasks:
                    emit("latex2lean", lv, lean)
                if "lean2latex" in tasks:
                    emit("lean2latex", lean, lv)

        if "lean2lean_complete" in tasks:
            header, body, n_decl = split_header(lean)
            sig = split_signature(body) if (body and n_decl == 1) else None
            if sig is None:
                stats["skip_complete_unparsed"] += 1
            else:
                prefix, rest = sig
                emit("lean2lean_complete", (header + "\n\n" if header else "") + prefix, " " + rest)

        if "lean2lean_infill" in tasks:
            rng = random.Random(f"{args.seed}-{pid}")
            res = make_infill(lean, rng)
            if res is None:
                stats["skip_infill"] += 1
            else:
                emit("lean2lean_infill", res[0], res[1])

    if "lean2lean_variant" in tasks:
        for ns, grp in groups.items():
            # distinct formalizations only (whitespace-normalised)
            uniq = {norm_ws(g["lean"]): g for g in grp}
            vs = list(uniq.values())
            if len(vs) < 2:
                continue
            rng = random.Random(f"{args.seed}-{ns}")
            pairs = [(a, b) for a in vs for b in vs if a is not b]
            rng.shuffle(pairs)
            for a, b in pairs[: args.max_variant_pairs]:
                split = a["split"]
                out[split].append(rec("lean2lean_variant", f"{a['id']}~{b['id']}", a["lean"], b["lean"], a, split))
                stats["lean2lean_variant"] += 1

    # ---- write ---------------------------------------------------------------
    od = Path(args.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    for split, recs in out.items():
        rng.shuffle(recs)
        with open(od / f"{split}.jsonl", "w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        stats[f"n_{split}"] = len(recs)
    (od / "stats.json").write_text(json.dumps(dict(stats), indent=2))
    print(json.dumps(dict(stats), indent=2))
    print(f"\nWrote {od}/train.jsonl, validation.jsonl, test.jsonl, stats.json")


if __name__ == "__main__":
    main()
