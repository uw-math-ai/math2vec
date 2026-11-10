#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_perturbation_mnrl.py

Fine-tune an embedding model to tell apart Lean statements that look alike but
say different things, using the Lean-certified perturbations exported by
perturbations/pipeline/export_training_data.py.

Two objectives, both CachedMultipleNegativesRankingLoss:

  Perturbation loader: one example per anchor per epoch,
    [Lean anchor, Lean equivalent variant, Lean hard negative x N].
    The positive is a rewrite Lean proved equivalent (contrapositive, De Morgan,
    premise order, ...); the hard negatives are near-identical statements that
    mean something else (negation, dropped hypothesis, swapped quantifiers,
    weakened typeclass, ...). All three are Lean, so the model cannot separate
    them by modality. The positive and negatives are re-sampled on every
    __getitem__, so each epoch sees different pairings. One example per anchor
    keeps an anchor's own variants from turning up as in-batch negatives.

  Retention loader (--retention_rows > 0): informal description -> Lean
    signature pairs from FrenzyMath/mathlib_informal (the train_qwen_mnrl_v2.py
    task), so the model keeps its retrieval ability while it learns the finer
    distinctions. Split by Lean module; only the train side is used here.

Evaluation, before and after training:

  * perturbation dev set (held-out projects): for each anchor, rank its
    equivalent variants against its hard negatives -- MRR, P@1, and how often
    an equivalent beats a negative, overall and per negative class;
  * NL -> Lean retrieval on the retention dev modules (Recall@1/5/10, MRR@10),
    to check that nothing was lost.

Run:
    python train_perturbation_mnrl.py \\
        --train_jsonl ../perturbations/data/blueprint-review/training/train.jsonl \\
        --dev_jsonl   ../perturbations/data/blueprint-review/training/dev.jsonl

    # smoke test (CPU, tiny model, no retention data)
    python train_perturbation_mnrl.py --train_jsonl ... --dev_jsonl ... \\
        --model_name sentence-transformers/all-MiniLM-L6-v2 --device cpu \\
        --loss plain --batch_size 4 --retention_rows 0 --output_dir /tmp/pert_test
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import numpy as np
from torch.utils.data import DataLoader, Dataset
from sentence_transformers import InputExample, losses

from train_qwen_mnrl_multiview_v3_tg import load_st_model
from train_qwen_mnrl_v2 import (
    build_pairs_from_hf_dataset,
    dedup_exact_pairs,
    eval_retrieval_full_corpus,
    group_split,
    set_seed,
    wrap_query,
)

# Same wording as perturbations/pipeline/mteb_perturbation_eval.py, so the
# fine-tuned model is queried there the way it was trained.
PERTURBATION_INSTRUCTION = (
    "Given a Lean 4 theorem statement, retrieve statements that are "
    "mathematically equivalent to it"
)
RETRIEVAL_INSTRUCTION = (
    "Retrieve the corresponding Lean theorem statement for the given informal math description."
)


def load_records(path: str) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


class PerturbationDataset(Dataset):
    """[anchor, equivalent, hard negatives...], re-sampled per __getitem__.

    Anchors with fewer than n_hn negatives sample them with replacement: a
    repeated negative only weighs that negative twice in the softmax.
    """

    def __init__(self, records: List[Dict[str, Any]], n_hn: int, wrap_q: bool):
        self.records = records
        self.n_hn = n_hn
        self.wrap_q = wrap_q

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> InputExample:
        r = self.records[idx]
        anchor = r["anchor"]
        if self.wrap_q:
            anchor = wrap_query(anchor, PERTURBATION_INSTRUCTION)
        positive = random.choice(r["positives"])["text"]
        negs = [n["text"] for n in r["negatives"]]
        if len(negs) >= self.n_hn:
            hns = random.sample(negs, self.n_hn)
        else:
            hns = [random.choice(negs) for _ in range(self.n_hn)]
        return InputExample(texts=[anchor, positive, *hns])


def eval_perturbations(model, records: List[Dict[str, Any]], wrap_q: bool,
                       batch_size: int, device: Optional[str]) -> Dict[str, Any]:
    """Rank each dev anchor's equivalents against its own hard negatives."""
    if not records:
        return {}
    queries = [wrap_query(r["anchor"], PERTURBATION_INSTRUCTION) if wrap_q else r["anchor"]
               for r in records]
    docs = sorted({c["text"] for r in records for c in r["positives"] + r["negatives"]})
    index = {t: i for i, t in enumerate(docs)}
    enc = dict(batch_size=batch_size, convert_to_numpy=True, normalize_embeddings=True,
               show_progress_bar=False, device=device)
    q_emb = np.asarray(model.encode(queries, **enc), dtype=np.float32)
    d_emb = np.asarray(model.encode(docs, **enc), dtype=np.float32)

    rr, p1, pos_cos, neg_cos = [], [], [], []
    wins: Dict[str, float] = defaultdict(float)
    pairs: Dict[str, int] = defaultdict(int)
    for qi, r in enumerate(records):
        pos = [float(d_emb[index[c["text"]]] @ q_emb[qi]) for c in r["positives"]]
        neg = [(float(d_emb[index[c["text"]]] @ q_emb[qi]), c["class"]) for c in r["negatives"]]
        ranked = sorted([(s, 1) for s in pos] + [(s, 0) for s, _ in neg], key=lambda x: -x[0])
        first = next(i for i, (_, lab) in enumerate(ranked) if lab)
        rr.append(1.0 / (first + 1))
        p1.append(float(ranked[0][1]))
        pos_cos += pos
        neg_cos += [s for s, _ in neg]
        for p in pos:
            for s, cls in neg:
                w = 1.0 if p > s else 0.5 if p == s else 0.0
                wins[cls] += w
                pairs[cls] += 1
                wins["all"] += w
                pairs["all"] += 1
    return {
        "anchors": len(records),
        "mrr": float(np.mean(rr)),
        "p_at_1": float(np.mean(p1)),
        "equivalent_beats_negative": {c: wins[c] / pairs[c] for c in sorted(pairs)},
        "mean_cos_equivalent": float(np.mean(pos_cos)),
        "mean_cos_negative": float(np.mean(neg_cos)),
    }


def print_perturbation_metrics(tag: str, m: Dict[str, Any]) -> None:
    print(f"{tag} perturbation dev ({m['anchors']} anchors): "
          f"MRR={m['mrr']:.4f} P@1={m['p_at_1']:.4f} "
          f"cos(equiv)={m['mean_cos_equivalent']:.4f} cos(neg)={m['mean_cos_negative']:.4f}")
    for cls, v in m["equivalent_beats_negative"].items():
        print(f"    equivalent > {cls:<14} {v:.4f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train_jsonl", required=True,
                    help="train.jsonl from export_training_data.py")
    ap.add_argument("--dev_jsonl", required=True,
                    help="dev.jsonl from export_training_data.py")

    ap.add_argument("--model_name", default="Qwen/Qwen3-Embedding-8B",
                    help="HF model ID or local path")
    ap.add_argument("--output_dir", default="checkpoints/perturbation_mnrl")
    ap.add_argument("--checkpoint_dir", default="checkpoints/ckpt_perturbation_mnrl")
    ap.add_argument("--checkpoint_save_steps", type=int, default=2000)
    ap.add_argument("--device", default=None)
    ap.add_argument("--wrap_query", action="store_true",
                    help="prefix queries with the instruction (recommended for Qwen3)")

    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--n_hard_negs", type=int, default=3)
    ap.add_argument("--max_seq_len", type=int, default=256,
                    help="Lean statements with many binders run past 128 tokens")
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--warmup_steps", type=int, default=100)
    ap.add_argument("--loss", default="cached", choices=["cached", "plain"],
                    help="'cached' for CachedMNRL (GPU); 'plain' for MNRL (CPU smoke tests)")
    ap.add_argument("--mini_batch_size", type=int, default=8,
                    help="CachedMNRL forward chunk; lower it if the GPU runs out of memory")

    ap.add_argument("--retention_dataset", default="FrenzyMath/mathlib_informal_v4.19.0")
    ap.add_argument("--retention_rows", type=int, default=20000,
                    help="NL -> Lean pairs mixed in to keep retrieval ability; 0 disables")
    ap.add_argument("--retention_dev_frac", type=float, default=0.1)
    ap.add_argument("--k_eval", type=int, default=10)
    ap.add_argument("--eval_batch_size", type=int, default=32)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.checkpoint_dir, exist_ok=True)
    set_seed(args.seed)

    print("=== Load perturbation data ===")
    train_records = load_records(args.train_jsonl)
    dev_records = load_records(args.dev_jsonl)
    print(f"Train anchors: {len(train_records)} | Dev anchors: {len(dev_records)}")
    if not train_records or not dev_records:
        raise RuntimeError("Empty train or dev perturbation set; check export_training_data.py output.")

    ret_train, ret_dev = [], []
    if args.retention_rows > 0:
        from datasets import load_dataset

        print(f"=== Load retention data: {args.retention_dataset} ===")
        ds = load_dataset(args.retention_dataset, split="train")
        pairs = dedup_exact_pairs(build_pairs_from_hf_dataset(
            ds, query_field="informal_description", doc_field="signature",
            key_field="index", group_field="module_name", max_rows=args.retention_rows))
        ret_train, ret_dev = group_split(pairs, dev_frac=args.retention_dev_frac, seed=args.seed)
        print(f"Retention train={len(ret_train)} dev={len(ret_dev)} (grouped by module_name)")

    print("=== Load base model ===")
    model = load_st_model(args.model_name, args.device, args.max_seq_len)

    def evaluate(tag: str, m) -> Dict[str, Any]:
        out: Dict[str, Any] = {"perturbation": eval_perturbations(
            m, dev_records, args.wrap_query, args.eval_batch_size, args.device)}
        print_perturbation_metrics(tag, out["perturbation"])
        if ret_dev:
            out["retrieval"] = eval_retrieval_full_corpus(
                model=m, train_pairs=ret_train, dev_pairs=ret_dev,
                instruction=RETRIEVAL_INSTRUCTION, wrap_q=args.wrap_query, wrap_d=False,
                doc_prefix="Document", k=args.k_eval, batch_size=args.eval_batch_size,
                device=args.device)
            print(f"{tag} NL->Lean retrieval: " + ", ".join(
                f"{k}={v:.4f}" for k, v in out["retrieval"].items()))
        return out

    print("=== Baseline eval ===")
    baseline = evaluate("Baseline", model)

    print("=== Build training objectives ===")
    loss = (losses.CachedMultipleNegativesRankingLoss(model=model, mini_batch_size=args.mini_batch_size)
            if args.loss == "cached" else losses.MultipleNegativesRankingLoss(model=model))
    pert_loader = DataLoader(PerturbationDataset(train_records, args.n_hard_negs, args.wrap_query),
                             batch_size=args.batch_size, shuffle=True, drop_last=True)
    objectives = [(pert_loader, loss)]
    print(f"[training] perturbation loader: {len(pert_loader)} batches/epoch")
    if ret_train:
        ret_examples = [InputExample(texts=[
            wrap_query(p.q, RETRIEVAL_INSTRUCTION) if args.wrap_query else p.q, p.d])
            for p in ret_train]
        ret_loader = DataLoader(ret_examples, batch_size=args.batch_size, shuffle=True, drop_last=True)
        objectives.append((ret_loader, loss))
        print(f"[training] retention loader: {len(ret_loader)} batches/epoch")
    if len(pert_loader) == 0:
        raise RuntimeError(f"Fewer train anchors ({len(train_records)}) than --batch_size.")

    # warmupconstant: with two loaders of different lengths the default
    # WarmupLinear schedule decays to zero early (see train_qwen_mnrl_multiview_v3_tg.py).
    t0 = time.time()
    model.fit(
        train_objectives=objectives,
        epochs=args.epochs,
        scheduler="warmupconstant",
        warmup_steps=args.warmup_steps,
        optimizer_params={"lr": args.lr},
        output_path=args.output_dir,
        show_progress_bar=True,
        checkpoint_path=args.checkpoint_dir,
        checkpoint_save_steps=args.checkpoint_save_steps,
    )
    train_seconds = time.time() - t0
    print(f"Training time: {train_seconds:.1f}s; saved to {args.output_dir}")

    print("=== Post-train eval ===")
    finetuned = evaluate("Finetuned", load_st_model(args.output_dir, args.device, args.max_seq_len))

    metrics_path = os.path.join(args.output_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as fh:
        json.dump({
            "baseline": baseline,
            "finetuned": finetuned,
            "config": vars(args),
            "counts": {"train_anchors": len(train_records), "dev_anchors": len(dev_records),
                       "retention_train": len(ret_train), "retention_dev": len(ret_dev)},
            "train_seconds": round(train_seconds, 1),
        }, fh, indent=2, ensure_ascii=False)
    print(f"Wrote metrics: {metrics_path}")


if __name__ == "__main__":
    main()
