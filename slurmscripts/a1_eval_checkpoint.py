#!/usr/bin/env python3
"""Re-evaluate a saved model using the trainer's OWN eval functions.

NEEDS A GPU. Run it through a1_eval.slurm, not on the login node.

You usually do NOT need this: a1_run.slurm already evaluates the base model and
the fine-tuned model and writes both into metrics.json. Use a1_report.py for
that. This script is for the cases metrics.json cannot answer:

  * eval a mid-training checkpoint from checkpoint_dir
  * eval at a different k (--k 20)
  * eval the same model on a different concept file (--data other.jsonl)
  * re-eval after the fact if a run crashed after training but before eval

It imports eval_retrieval / eval_all_pair_types / group_split_records from
train_qwen_mnrl_multiview_v3_tg.py so the numbers are directly comparable to
metrics.json rather than a reimplementation that might differ subtly.

The train/dev split is reproduced exactly: group_split_records() shuffles the
sorted module list with random.Random(seed), so the same (data, seed, dev_frac,
max_rows) always yields the same dev set. EXTRA never affects the split.

    python a1_eval_checkpoint.py --run_dir checkpoints/mv3_qwen8b_a1_ep2
    python a1_eval_checkpoint.py --run_dir checkpoints/mv3_qwen8b_a1_ep2 --primary_only
    python a1_eval_checkpoint.py --run_dir checkpoints/mv3_qwen8b_a1_ep2 \
        --model_path checkpoints/ckpt_mv3_qwen8b_a1_ep2/checkpoint-8000 --tag step8000
"""
import argparse
import importlib.util
import json
import os
import sys

TRAINER = "train_qwen_mnrl_multiview_v3_tg.py"


def import_trainer(path=None):
    for cand in [p for p in (path, os.path.join(os.path.dirname(os.path.abspath(__file__)), TRAINER),
                             os.path.join(os.getcwd(), TRAINER)) if p]:
        if os.path.isfile(cand):
            spec = importlib.util.spec_from_file_location("mv3_trainer", cand)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["mv3_trainer"] = mod
            spec.loader.exec_module(mod)
            print(f"imported trainer from {cand}")
            return mod
    sys.exit(f"ERROR: could not find {TRAINER}. Pass --trainer /path/to/{TRAINER}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run_dir", required=True,
                    help="run directory holding metrics.json; its config is replayed")
    ap.add_argument("--model_path", default=None,
                    help="model to evaluate (default: --run_dir, where the trainer saved it)")
    ap.add_argument("--data", default=None, help="override config.local_jsonl")
    ap.add_argument("--k", type=int, default=None, help="override config.k_eval")
    ap.add_argument("--batch_size", type=int, default=None, help="override config.eval_batch_size")
    ap.add_argument("--primary_only", action="store_true",
                    help="only NL -> Lean signature; fits in a debug-QOS hour")
    ap.add_argument("--tag", default="recheck", help="output file suffix")
    ap.add_argument("--trainer", default=None)
    ap.add_argument("--device", default="cuda")
    args = ap.parse_args()

    T = import_trainer(args.trainer)

    mp = os.path.join(args.run_dir, "metrics.json")
    if not os.path.isfile(mp):
        sys.exit(f"ERROR: {mp} not found -- cannot replay the run's config.")
    stored = json.load(open(mp))
    cfg = stored.get("config", {})

    data = args.data or cfg.get("local_jsonl")
    model_path = args.model_path or args.run_dir
    k = args.k or int(cfg.get("k_eval", 10))
    bs = args.batch_size or int(cfg.get("eval_batch_size", 8))
    seed = int(cfg.get("seed", 42))
    dev_frac = float(cfg.get("dev_frac", 0.1))
    max_rows = cfg.get("max_rows")
    instruction = cfg.get("instruction")
    reverse_instruction = cfg.get("reverse_instruction")
    wrap_q = bool(cfg.get("wrap_query", True))
    wrap_d = bool(cfg.get("wrap_doc", False))
    doc_prefix = cfg.get("doc_prefix", "Document")

    print("=" * 70)
    print(f"model      : {model_path}")
    print(f"data       : {data}")
    print(f"split      : seed={seed} dev_frac={dev_frac} max_rows={max_rows}")
    print(f"eval       : k={k} batch_size={bs} wrap_q={wrap_q} wrap_d={wrap_d}")
    print(f"primary_only: {args.primary_only}")
    print("=" * 70)

    if not os.path.exists(model_path):
        sys.exit(f"ERROR: model path does not exist: {model_path}")

    records = T.load_concepts(dataset_name=None, split=cfg.get("split", "train"),
                              max_rows=max_rows, local_jsonl=data)
    train_records, dev_records = T.group_split_records(records, dev_frac=dev_frac, seed=seed)
    print(f"loaded {len(records):,} concepts -> train {len(train_records):,} / dev {len(dev_records):,}")

    # Sanity: did we rebuild the same split the run used?
    want_dev = stored.get("counts", {}).get("dev")
    if want_dev is not None and want_dev != len(dev_records):
        print(f"\n*** WARNING: dev size {len(dev_records):,} != metrics.json's "
              f"{want_dev:,}. The split was NOT reproduced; numbers below are not\n"
              f"    comparable to metrics.json. Check --data / seed / dev_frac / max_rows.\n")
    else:
        print("split reproduced: dev size matches metrics.json")

    from sentence_transformers import SentenceTransformer
    print(f"\nloading model (this takes a few minutes for 8B)...")
    model = SentenceTransformer(model_path, device=args.device)

    out = {"model_path": model_path, "data": data, "k": k,
           "split": {"seed": seed, "dev_frac": dev_frac, "max_rows": max_rows,
                     "n_train": len(train_records), "n_dev": len(dev_records)}}

    print("\n=== primary: NL -> Lean signature ===")
    primary = T.eval_retrieval(
        model=model, train_records=train_records, dev_records=dev_records,
        query_field="nl_informal", doc_field="lean_signature",
        instruction=instruction, wrap_q=wrap_q, wrap_d=wrap_d,
        doc_prefix=doc_prefix, k=k, batch_size=bs, device=args.device)
    if primary is None:
        sys.exit("ERROR: primary eval returned None (no dev concept has both views)")
    out["primary"] = primary
    for key in ("recall@1", "recall@5", f"recall@{k}", f"mrr@{k}"):
        print(f"  {key:<12} {primary[key]:.4f}")
    print(f"  n_dev_used   {int(primary['n_dev_used']):,}")
    print(f"  corpus_size  {int(primary['corpus_size']):,}")

    if not args.primary_only:
        print("\n=== all pair types ===")
        out["per_pair_type"] = T.eval_all_pair_types(
            model=model, train_records=train_records, dev_records=dev_records,
            instruction=instruction, reverse_instruction=reverse_instruction,
            wrap_q=wrap_q, wrap_d=wrap_d, doc_prefix=doc_prefix,
            k=k, batch_size=bs, device=args.device)

    # Compare against what the run recorded, when k matches.
    rec = stored.get("finetuned", {})
    if rec and int(rec.get("k", 10)) == k:
        print("\n=== this re-eval vs metrics.json 'finetuned' ===")
        print(f"  {'metric':<12} {'stored':>9} {'re-eval':>9} {'delta':>9}")
        for key in ("recall@1", "recall@5", f"recall@{k}", f"mrr@{k}"):
            a, b = rec.get(key), primary.get(key)
            if a is None or b is None:
                continue
            print(f"  {key:<12} {a:>9.4f} {b:>9.4f} {b - a:>+9.4f}")
        print("  (near-zero deltas are expected when re-evaluating the same saved model)")

    dest = os.path.join(args.run_dir, f"eval_{args.tag}.json")
    json.dump(out, open(dest, "w"), indent=2)
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
