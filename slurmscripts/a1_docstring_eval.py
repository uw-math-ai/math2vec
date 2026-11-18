#!/usr/bin/env python3
"""Does the +A1 model actually retrieve better from DOCSTRING-style queries?

The main experiment evaluated only base-style queries (verbose LaTeX prose) and
found the +A1 arm slightly worse. This script tests the hypothesis that explains
that result: A1 improved docstring-style retrieval, which the main eval never
measured.

THE HELD-OUT SET IS FREE. The 1,497 A1 records whose concept_id landed in the
dev set were dropped from training to prevent leakage (`drop_dev_id` in the
[extra] line). No model has ever seen them, and their Lean statements are
already in the 133,621-document eval corpus. They are a clean docstring-style
query set that cost nothing to build.

For each model this measures TWO things on the SAME theorems:

  docstring query -> Lean signature   (A1's Mathlib docstring as the query)
  base-NL query   -> Lean signature   (the base dataset's LaTeX prose, control)

The control matters: it isolates "this model is better at docstrings" from
"these happen to be easy theorems". Expected if the register hypothesis holds:
the +A1 model wins on docstring queries and loses on base-NL queries.

Corpus construction, wrapping, encoding and scoring are taken from the trainer
(`eval_retrieval`'s logic, `encode_texts`, `search_topk`), so numbers are
directly comparable to metrics.json.

NEEDS A GPU -- run via a1_docstring_eval.slurm.

    python a1_docstring_eval.py \
      --models checkpoints/mv3_qwen8b_paper_ep2 checkpoints/mv3_qwen8b_a1_ep2
"""
import argparse
import importlib.util
import json
import os
import sys

TRAINER = "train_qwen_mnrl_multiview_v3_tg.py"


def import_trainer(path=None):
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in [p for p in (path, os.path.join(here, TRAINER),
                             os.path.join(os.getcwd(), TRAINER)) if p]:
        if os.path.isfile(cand):
            spec = importlib.util.spec_from_file_location("mv3_trainer", cand)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["mv3_trainer"] = mod
            spec.loader.exec_module(mod)
            print(f"imported trainer from {cand}")
            return mod
    sys.exit(f"ERROR: could not find {TRAINER}; pass --trainer /path/to/it")


def build_corpus(records, doc_field):
    """Mirrors eval_retrieval: corpus is every record holding doc_field."""
    idx, docs = {}, []
    for r in records:
        t = r.views_by_name.get(doc_field)
        if t:
            idx[r.concept_id] = len(docs)
            docs.append(t)
    return idx, docs


def score(T, model, queries, gold, corpus_docs, instruction, wrap_q, wrap_d,
          doc_prefix, k, batch_size, device, doc_emb=None):
    """Encode, retrieve, and compute recall/MRR exactly as eval_retrieval does."""
    q = [T.wrap_query(x, instruction) for x in queries] if wrap_q else list(queries)
    d = [T.wrap_doc(x, doc_prefix) for x in corpus_docs] if wrap_d else corpus_docs
    if doc_emb is None:
        doc_emb = T.encode_texts(model, d, batch_size=batch_size, device=device)
    q_emb = T.encode_texts(model, q, batch_size=batch_size, device=device)

    ks = sorted({1, 5, k})
    I = T.search_topk(q_emb, doc_emb, max(ks))
    hits = {ki: 0 for ki in ks}
    rr = 0.0
    for i in range(len(q)):
        ret = I[i].tolist()
        g = gold[i]
        for ki in ks:
            if g in ret[:ki]:
                hits[ki] += 1
        if g in ret[:k]:
            rr += 1.0 / (ret[:k].index(g) + 1)
    n = len(q)
    m = {f"recall@{ki}": hits[ki] / n for ki in ks}
    m[f"mrr@{k}"] = rr / n
    m["n_queries"] = n
    m["corpus_size"] = len(corpus_docs)
    return m, doc_emb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True,
                    help="run directories (the trainer saved each model in its own)")
    ap.add_argument("--base", default="data/MathlibViews.jsonl")
    ap.add_argument("--a1", default="data/a1_kept_concepts_v4.19.0.jsonl")
    ap.add_argument("--config_from", default=None,
                    help="metrics.json to replay settings from (default: first model's)")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--batch_size", type=int, default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--trainer", default=None)
    ap.add_argument("--out", default="docstring_eval.json")
    args = ap.parse_args()

    T = import_trainer(args.trainer)

    cfg_path = args.config_from or os.path.join(args.models[0], "metrics.json")
    if not os.path.isfile(cfg_path):
        sys.exit(f"ERROR: {cfg_path} not found -- need a run's config to match settings")
    cfg = json.load(open(cfg_path)).get("config", {})
    seed      = int(cfg.get("seed", 42))
    dev_frac  = float(cfg.get("dev_frac", 0.1))
    max_rows  = cfg.get("max_rows")
    instr     = cfg.get("instruction")
    wrap_q    = bool(cfg.get("wrap_query", True))
    wrap_d    = bool(cfg.get("wrap_doc", False))
    doc_prefix= cfg.get("doc_prefix", "Document")
    bs        = args.batch_size or int(cfg.get("eval_batch_size", 8))
    k         = args.k

    print("=" * 72)
    print(f"split: seed={seed} dev_frac={dev_frac} max_rows={max_rows}")
    print(f"eval : k={k} batch_size={bs} wrap_q={wrap_q} wrap_d={wrap_d}")
    print("=" * 72)

    # --- reproduce the exact train/dev split the runs used ---
    records = T.load_concepts(dataset_name=None, split=cfg.get("split", "train"),
                              max_rows=max_rows, local_jsonl=args.base)
    train_records, dev_records = T.group_split_records(records, dev_frac=dev_frac, seed=seed)
    print(f"\nbase: {len(records):,} concepts -> train {len(train_records):,} / "
          f"dev {len(dev_records):,}")

    # --- the held-out docstring queries: A1 records whose concept_id is in dev ---
    dev_ids = {r.concept_id for r in dev_records}
    a1_docstrings = {}
    with open(args.a1) as f:
        for line in f:
            r = json.loads(line)
            cid = r["concept_id"]
            if cid in dev_ids:
                t = (r.get("views", {}) or {}).get("nl_informal")
                if t and t.strip():
                    a1_docstrings[cid] = t

    print(f"A1 docstrings for dev theorems: {len(a1_docstrings):,}")
    print("  (should equal drop_dev_id from the [extra] line -- 1,497 for this run)")

    corpus_idx, corpus_docs = build_corpus(train_records + dev_records, "lean_signature")
    print(f"corpus: {len(corpus_docs):,} lean_signature documents")

    # Queries, and the base-NL control on exactly the same theorems.
    dev_by_id = {r.concept_id: r for r in dev_records}
    doc_q, doc_gold, base_q, base_gold, both = [], [], [], [], 0
    for cid, text in a1_docstrings.items():
        if cid not in corpus_idx:
            continue
        doc_q.append(text)
        doc_gold.append(corpus_idx[cid])
        bn = dev_by_id[cid].views_by_name.get("nl_informal")
        if bn:
            base_q.append(bn)
            base_gold.append(corpus_idx[cid])
            both += 1

    print(f"\ndocstring queries usable      : {len(doc_q):,}")
    print(f"base-NL control on same set   : {len(base_q):,}")
    if not doc_q:
        sys.exit("ERROR: no usable docstring queries -- check the split reproduced")

    from sentence_transformers import SentenceTransformer
    results = {}
    for mp in args.models:
        name = os.path.basename(os.path.normpath(mp))
        print(f"\n{'='*72}\nMODEL: {name}\n{'='*72}")
        if not os.path.exists(mp):
            print(f"  SKIP -- path does not exist: {mp}")
            continue
        model = SentenceTransformer(mp, device=args.device)

        print("  [1/2] docstring query -> lean_signature")
        dm, doc_emb = score(T, model, doc_q, doc_gold, corpus_docs, instr,
                            wrap_q, wrap_d, doc_prefix, k, bs, args.device)
        print("  [2/2] base-NL query  -> lean_signature  (control, same theorems)")
        bm, _ = score(T, model, base_q, base_gold, corpus_docs, instr,
                      wrap_q, wrap_d, doc_prefix, k, bs, args.device, doc_emb=doc_emb)

        results[name] = {"docstring_query": dm, "base_nl_query": bm}
        for label, m in (("docstring", dm), ("base-NL  ", bm)):
            print(f"    {label}  R@1={m['recall@1']:.4f}  R@5={m['recall@5']:.4f}  "
                  f"R@{k}={m[f'recall@{k}']:.4f}  MRR@{k}={m[f'mrr@{k}']:.4f}")
        del model

    # ---------------- comparison ----------------
    names = list(results)
    if len(names) >= 2:
        paper = next((n for n in names if "paper" in n), names[0])
        a1    = next((n for n in names if n != paper), names[1])
        print(f"\n{'='*72}\nCOMPARISON: {a1}  vs  {paper}\n{'='*72}")
        hdr = f"{'query style':<14}{'metric':<10}{paper[:18]:>19}{a1[:18]:>19}{'delta':>10}"
        print(hdr); print("-" * len(hdr))
        verdict = {}
        for style, key in (("docstring", "docstring_query"), ("base-NL", "base_nl_query")):
            for metric in ("recall@1", "recall@5", f"recall@{k}", f"mrr@{k}"):
                p, a = results[paper][key][metric], results[a1][key][metric]
                print(f"{style:<14}{metric:<10}{p:>19.4f}{a:>19.4f}{a-p:>+10.4f}")
                if metric == "recall@1":
                    verdict[style] = a - p
            print()

        d_doc, d_base = verdict.get("docstring", 0.0), verdict.get("base-NL", 0.0)

        # Noise floor: with this many queries, how big must a delta be to mean
        # anything? Conservative (unpaired) 2-sigma on the difference of two
        # proportions. Printed so small deltas are not over-read.
        import math
        nq = results[paper]["docstring_query"]["n_queries"]
        pa = results[paper]["docstring_query"]["recall@1"]
        pb = results[a1]["docstring_query"]["recall@1"]
        se = math.sqrt(pa*(1-pa)/nq + pb*(1-pb)/nq)
        floor = 2*se
        print(f"NOISE FLOOR  n={nq:,} queries -> 1 sigma = {se:.4f}, "
              f"2 sigma = {floor:.4f} on R@1")
        print(f"             deltas smaller than ~{floor:.3f} are not distinguishable "
              f"from chance.\n")
        print("VERDICT")
        print(f"  docstring-style R@1 change: {d_doc:+.4f}")
        print(f"  base-NL-style   R@1 change: {d_base:+.4f}")
        if d_doc > max(0.005, floor) and d_doc > d_base:
            print("\n  => A1 HELPS docstring-style retrieval. The main eval missed a real\n"
                  "     gain because it only ever asks base-style questions. Give A1 its\n"
                  "     own view field rather than merging it into nl_informal.")
        elif d_doc > d_base + max(0.005, floor):
            print("\n  => Directionally supports the register hypothesis: A1 does relatively\n"
                  "     better on docstrings than on base-NL, though the absolute gain is\n"
                  "     small. A separate view field is still worth testing.")
        else:
            if abs(d_doc) < floor and abs(d_base) < floor:
                print("\n  => INCONCLUSIVE. Both deltas are inside the noise floor. This test\n"
                      "     cannot separate the models at this sample size.")
            else:
                print("\n  => NO docstring-style gain either. The register hypothesis does not\n"
                      "     explain the result; A1 as extra NL views did not help this model.\n"
                      "     Reconsider before spending more GPU time on it.")

    json.dump({"results": results,
               "n_docstring_queries": len(doc_q),
               "n_base_queries": len(base_q),
               "corpus_size": len(corpus_docs),
               "k": k,
               "split": {"seed": seed, "dev_frac": dev_frac, "max_rows": max_rows}},
              open(args.out, "w"), indent=2)
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
