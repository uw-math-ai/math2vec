#!/usr/bin/env python3
"""
validate_docstrings.py  --  check formatted FineLeanCorpus docstrings and the
embedding model's retrieval results on a sample (default 100).

Steps
  1. Sample N compiled, de-duplicated rows from m-a-p/FineLeanCorpus
     (streaming + seeded shuffle buffer, so the full corpus is not downloaded).
  2. Format each statement as a Lean docstring (format_docstrings.py) and run
     the structural checks on every record.
  3. Embed docstring text as queries and the docstring-free Lean code as the
     corpus, then score docstring -> Lean retrieval (Recall@1/5/10, MRR@10).
     The raw (unformatted) statements are scored against the same corpus, so
     you can see whether formatting changed the model's results.
  4. Write samples.jsonl, retrieval.jsonl (per-query rank + top-5) and
     report.json to --out_dir. Exit code 1 if any check fails.

Pass/fail
  * every sampled record passes the structural checks
  * formatted Recall@10 >= --min_recall_at_10   (sanity floor; random is k/N = 0.10)
  * formatted Recall@1 is not more than --max_r1_drop below raw Recall@1

Usage (from the conda env, inside finetune/)
    python validate_docstrings.py                                   # 100 rows, Qwen3-Embedding-0.6B
    python validate_docstrings.py --model_name checkpoints/mnrl_qwen4b --device cuda
    python validate_docstrings.py --local sample.jsonl --skip_model # format checks only, offline
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from format_docstrings import build_record, check_record, docstring_text, strip_docstrings
from prepare_fineleancorpus import COLUMNS, compiled_ok, norm_ws

DEFAULT_INSTRUCTION = "Retrieve the corresponding Lean theorem statement for the given informal math description."


# --------------------------------------------------------------------------- #
# Sampling
# --------------------------------------------------------------------------- #
def iter_source_rows(args) -> Iterable[dict]:
    if args.local and args.local.endswith(".jsonl"):
        rows = []
        with open(args.local, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        random.Random(args.seed).shuffle(rows)
        yield from rows
        return
    from datasets import load_dataset  # lazy: not needed for --local .jsonl

    if args.local:
        ds = load_dataset("parquet", data_files=args.local, split="train").shuffle(seed=args.seed)
    else:
        ds = load_dataset(args.dataset, split="train", streaming=True)
        ds = ds.shuffle(seed=args.seed, buffer_size=args.shuffle_buffer)
    try:
        ds = ds.select_columns(COLUMNS)
    except Exception:
        pass
    yield from ds


def sample_records(args) -> tuple[list[dict], dict]:
    """Take the first N usable rows from the shuffled stream. Rows that repeat
    a statement or a Lean formalization already sampled are skipped so each
    query has exactly one correct document."""
    recs, seen_stmt, seen_lean = [], set(), set()
    stats = {"scanned": 0, "drop_compile_error": 0, "drop_duplicate": 0, "drop_unformattable": 0}
    for i, row in enumerate(iter_source_rows(args)):
        if len(recs) >= args.n:
            break
        stats["scanned"] += 1
        if stats["scanned"] > args.max_scan:
            break
        if not args.keep_uncompiled and not compiled_ok(row.get("compile_result")):
            stats["drop_compile_error"] += 1
            continue
        rec, _ = build_record(row, wrap=args.wrap, row_index=i)
        if rec is None:
            stats["drop_unformattable"] += 1
            continue
        ks, kl = norm_ws(rec["statement"]).lower(), norm_ws(strip_docstrings(rec["lean_code"]))
        if ks in seen_stmt or kl in seen_lean:
            stats["drop_duplicate"] += 1
            continue
        seen_stmt.add(ks)
        seen_lean.add(kl)
        recs.append(rec)
    return recs, stats


# --------------------------------------------------------------------------- #
# Retrieval scoring
# --------------------------------------------------------------------------- #
def gold_ranks(q_emb: np.ndarray, d_emb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Query i's gold doc is doc i. Returns (0-based rank of gold, top-k idx)."""
    sims = q_emb @ d_emb.T
    gold = np.diag(sims)
    ranks = (sims > gold[:, None]).sum(axis=1)
    order = np.argsort(-sims, axis=1)
    return ranks, order


def metrics_from_ranks(ranks: np.ndarray, ks=(1, 5, 10), mrr_k: int = 10) -> dict:
    m = {f"recall@{k}": float(np.mean(ranks < k)) for k in ks}
    rr = np.where(ranks < mrr_k, 1.0 / (ranks + 1), 0.0)
    m[f"mrr@{mrr_k}"] = float(rr.mean())
    m["mean_rank"] = float(ranks.mean() + 1)
    return m


def encode(model, texts: list[str], batch_size: int) -> np.ndarray:
    emb = model.encode(
        texts,
        batch_size=batch_size,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(emb, dtype=np.float32)


def run_model(recs: list[dict], args) -> tuple[dict, list[dict]]:
    from sentence_transformers import SentenceTransformer

    kw = {"device": args.device} if args.device else {}
    model = SentenceTransformer(args.model_name, **kw)
    model.max_seq_length = args.max_seq_len

    def wrap(t: str) -> str:
        return f"Instruct: {args.instruction}\nQuery: {t}" if args.wrap_query else t

    docs = [strip_docstrings(r["lean_code"]) for r in recs]
    q_fmt = [wrap(docstring_text(r["docstring"])) for r in recs]
    q_raw = [wrap(r["statement"]) for r in recs]

    t0 = time.time()
    d_emb = encode(model, docs, args.batch_size)
    fmt_emb = encode(model, q_fmt, args.batch_size)
    raw_emb = encode(model, q_raw, args.batch_size)
    enc_s = time.time() - t0

    fmt_ranks, fmt_order = gold_ranks(fmt_emb, d_emb)
    raw_ranks, _ = gold_ranks(raw_emb, d_emb)
    per_query = [
        {
            "id": r["id"],
            "gold_rank": int(fmt_ranks[i]) + 1,
            "raw_gold_rank": int(raw_ranks[i]) + 1,
            "top5_ids": [recs[j]["id"] for j in fmt_order[i, :5]],
            "docstring": r["docstring"],
        }
        for i, r in enumerate(recs)
    ]
    results = {
        "formatted": metrics_from_ranks(fmt_ranks),
        "raw_statement": metrics_from_ranks(raw_ranks),
        "queries_changed_rank": int((fmt_ranks != raw_ranks).sum()),
        "encode_seconds": round(enc_s, 1),
        "random_baseline_recall@10": min(1.0, 10 / len(recs)),
    }
    return results, per_query


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    for s in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dataset", default="m-a-p/FineLeanCorpus")
    ap.add_argument("--local", help="local .jsonl or .parquet instead of streaming the HF hub")
    ap.add_argument("--n", type=int, default=100, help="number of docstrings to validate")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--shuffle_buffer", type=int, default=10_000)
    ap.add_argument("--max_scan", type=int, default=50_000, help="give up after scanning this many rows")
    ap.add_argument("--keep_uncompiled", action="store_true")
    ap.add_argument("--wrap", type=int, default=0, help="hard-wrap docstrings at N columns (0 = off)")
    ap.add_argument("--model_name", default="Qwen/Qwen3-Embedding-0.6B", help="HF id or local checkpoint dir")
    ap.add_argument("--device", default=None, help="e.g. cpu, cuda, cuda:0 (default: auto)")
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--max_seq_len", type=int, default=512)
    ap.add_argument("--no_wrap_query", dest="wrap_query", action="store_false",
                    help="don't prepend the Instruct:/Query: prefix (on by default, as in training)")
    ap.add_argument("--instruction", default=DEFAULT_INSTRUCTION)
    ap.add_argument("--min_recall_at_10", type=float, default=0.5)
    ap.add_argument("--max_r1_drop", type=float, default=0.05)
    ap.add_argument("--skip_model", action="store_true", help="only run the formatting checks")
    ap.add_argument("--out_dir", default="results/docstring_validation")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    recs, sample_stats = sample_records(args)
    print(f"Sampled {len(recs)} docstrings  {json.dumps(sample_stats)}")
    with (out / "samples.jsonl").open("w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    failures: list[str] = []
    if len(recs) < args.n:
        failures.append(f"only {len(recs)} usable rows found (wanted {args.n})")

    bad = {r["id"]: p for r in recs if (p := check_record(r))}
    fmt_report = {"checked": len(recs), "passed": len(recs) - len(bad), "failed": bad}
    print(f"Format checks: {fmt_report['passed']}/{len(recs)} passed")
    for rid, probs in list(bad.items())[:10]:
        print(f"  {rid}: {', '.join(probs)}")
    if bad:
        failures.append(f"{len(bad)} records failed format checks")

    report = {"config": vars(args), "sampling": sample_stats, "format_checks": fmt_report}

    if not args.skip_model and len(recs) >= 2:
        print(f"Encoding with {args.model_name} ...")
        model_results, per_query = run_model(recs, args)
        report["retrieval"] = model_results
        with (out / "retrieval.jsonl").open("w", encoding="utf-8") as f:
            for q in per_query:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")

        f_m, r_m = model_results["formatted"], model_results["raw_statement"]
        print(f"\n{'metric':<12}{'formatted':>12}{'raw':>12}")
        for k in ("recall@1", "recall@5", "recall@10", "mrr@10", "mean_rank"):
            print(f"{k:<12}{f_m[k]:>12.3f}{r_m[k]:>12.3f}")
        print(f"random recall@10 baseline: {model_results['random_baseline_recall@10']:.2f}  "
              f"| queries whose rank changed: {model_results['queries_changed_rank']}")

        if f_m["recall@10"] < args.min_recall_at_10:
            failures.append(f"recall@10 {f_m['recall@10']:.3f} < {args.min_recall_at_10}")
        if r_m["recall@1"] - f_m["recall@1"] > args.max_r1_drop:
            failures.append(
                f"formatting dropped recall@1 by {r_m['recall@1'] - f_m['recall@1']:.3f} (> {args.max_r1_drop})"
            )

    report["passed"] = not failures
    report["failures"] = failures
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{'PASS' if not failures else 'FAIL'}" + "".join(f"\n  - {x}" for x in failures))
    print(f"Wrote {out / 'report.json'}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
