#!/usr/bin/env python3
"""How different is an MathLibDocstrings from the NL the base data already has?

CPU only, ~1-2 min. Run this BEFORE committing GPU hours.

For every MathLibDocstrings concept_id that already exists in the base data, compare MathLibDocstrings'
nl_informal against every NL view the base record already holds. If they are
near-identical, the ~14.5k "merged" concepts add restatements rather than new
information, and the experiment is more likely to come back flat.

    python overlap_text.py \
        --base data/MathlibViews.jsonl \
        --docstrings   data/MathLibDocstrings_v4.19.0.jsonl
"""
import argparse
import difflib
import json
import random
import re
import unicodedata

NL_FIELDS = ("nl_informal", "nl_informal_2", "nl_statement", "informal_statement")


def norm(s):
    """Aggressive normalisation: if two texts match here, they are the same
    sentence modulo formatting."""
    s = unicodedata.normalize("NFKC", s or "").lower()
    s = s.replace("`", " ").replace("$", " ")
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .")


def nl_views(rec):
    v = rec.get("views", {}) or {}
    out = []
    for f in NL_FIELDS:
        t = v.get(f)
        if isinstance(t, str) and t.strip():
            out.append(t)
    extra = v.get("nl_views")
    if isinstance(extra, list):
        out += [t for t in extra if isinstance(t, str) and t.strip()]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="data/MathlibViews.jsonl")
    ap.add_argument("--docstrings", default="data/MathLibDocstrings_v4.19.0.jsonl")
    ap.add_argument("--sample", type=int, default=3000,
                    help="how many overlapping concepts to run fuzzy similarity on")
    ap.add_argument("--examples", type=int, default=6)
    args = ap.parse_args()

    base = {}
    with open(args.base) as f:
        for line in f:
            r = json.loads(line)
            base.setdefault(r["concept_id"], []).extend(nl_views(r))

    rows = []
    with open(args.docstrings) as f:
        for line in f:
            r = json.loads(line)
            cid = r["concept_id"]
            if cid in base:
                doc_nl = (r.get("views", {}) or {}).get("nl_informal") or ""
                rows.append((cid, doc_nl, base[cid]))

    print(f"base concepts with NL   : {len(base):,}")
    print(f"MathLibDocstrings concepts overlapping : {len(rows):,}")
    if not rows:
        print("no overlap -- nothing to compare")
        return

    exact = normed = 0
    no_base_nl = 0
    for _, doc_nl, bviews in rows:
        if not bviews:
            no_base_nl += 1
            continue
        if any(doc_nl == b for b in bviews):
            exact += 1
        if any(norm(doc_nl) == norm(b) for b in bviews):
            normed += 1

    n = len(rows)
    print(f"\n--- exact / near-exact duplication among the {n:,} overlapping ---")
    print(f"byte-identical to an existing base view : {exact:,} ({100*exact/n:.1f}%)")
    print(f"identical after normalisation           : {normed:,} ({100*normed/n:.1f}%)")
    if no_base_nl:
        print(f"base record had NO NL view at all       : {no_base_nl:,} "
              f"({100*no_base_nl/n:.1f}%)  <- MathLibDocstrings is the only NL for these")

    sample = rows if len(rows) <= args.sample else random.Random(42).sample(rows, args.sample)
    buckets = {"identical (>=0.99)": 0, "near-dup 0.90-0.99": 0, "similar 0.70-0.90": 0,
               "different 0.40-0.70": 0, "unrelated (<0.40)": 0}
    sims = []
    for _, doc_nl, bviews in sample:
        if not bviews:
            continue
        best = max(difflib.SequenceMatcher(None, norm(doc_nl), norm(b)).ratio() for b in bviews)
        sims.append(best)
        if best >= 0.99:   buckets["identical (>=0.99)"] += 1
        elif best >= 0.90: buckets["near-dup 0.90-0.99"] += 1
        elif best >= 0.70: buckets["similar 0.70-0.90"] += 1
        elif best >= 0.40: buckets["different 0.40-0.70"] += 1
        else:              buckets["unrelated (<0.40)"] += 1

    if sims:
        m = len(sims)
        print(f"\n--- best-match text similarity, sample of {m:,} ---")
        for k, v in buckets.items():
            bar = "#" * int(40 * v / m)
            print(f"  {k:<22} {v:>6,} ({100*v/m:>5.1f}%) {bar}")
        sims.sort()
        print(f"  median similarity: {sims[m//2]:.3f}   mean: {sum(sims)/m:.3f}")

        dup = buckets["identical (>=0.99)"] + buckets["near-dup 0.90-0.99"]
        print(f"\n  near-duplicate share: {100*dup/m:.1f}%")
        if dup / m > 0.5:
            print("  => WARNING: most MathLibDocstrings restate the base NL. The ~14.5k merged\n"
                  "     concepts add little; the experiment leans on the ~4.2k new ones.")
        elif dup / m > 0.2:
            print("  => MIXED: a sizeable minority are restatements.")
        else:
            print("  => GOOD: MathLibDocstrings are genuinely different text from the base NL.")

    print(f"\n--- {args.examples} random side-by-side examples ---")
    for cid, doc_nl, bviews in random.Random(1).sample(sample, min(args.examples, len(sample))):
        best_b, best_r = "", 0.0
        for b in bviews:
            r = difflib.SequenceMatcher(None, norm(doc_nl), norm(b)).ratio()
            if r >= best_r:
                best_r, best_b = r, b
        print(f"\n[{cid}]  similarity={best_r:.3f}")
        print(f"  BASE: {best_b[:240]}")
        print(f"  MathLibDocstrings  : {doc_nl[:240]}")


if __name__ == "__main__":
    main()
