#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

# Arguments
# 
# 
# 
# 
# 

import argparse
import json
import os
import random
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import faiss  # type: ignore
    _HAVE_FAISS = True
except Exception:
    faiss = None  # type: ignore
    _HAVE_FAISS = False

from torch.utils.data import DataLoader
from sentence_transformers import SentenceTransformer, InputExample, losses
from datasets import load_dataset


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except Exception:
        pass


def l2_normalize(x: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    n = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(n, eps)


def wrap_query(text: str, instruction: str) -> str:
    return f"Instruct: {instruction}\nQuery: {text}"


def wrap_doc(text: str, doc_prefix: str = "Document") -> str:
    return f"{doc_prefix}: {text}"


@dataclass
class PairExample:
    q: str
    d: str
    key: str
    group: str


def safe_str(x) -> str:
    return x if isinstance(x, str) else ""


def join_if_list(x) -> str:
    if isinstance(x, list):
        return "/".join(str(t) for t in x if t is not None)
    if isinstance(x, str):
        return x
    return ""


def make_key(row: dict, key_field: str, fallback_fields: Tuple[str, ...]) -> str:
    k = row.get(key_field, None)
    if k is not None:
        return str(k)
    parts = []
    for f in fallback_fields:
        v = row.get(f, None)
        parts.append(join_if_list(v) if isinstance(v, list) else str(v))
    return "|".join(parts)


def build_pairs_from_hf_dataset(
    ds,
    query_field: str,
    doc_field: str,
    key_field: str,
    group_field: str,
    max_rows: Optional[int],
) -> List[PairExample]:
    pairs: List[PairExample] = []
    n = len(ds) if max_rows is None else min(len(ds), max_rows)

    fallback_fields = ("module_name", "name", "start", "stop")

    for i in range(n):
        row = ds[i]
        q = safe_str(row.get(query_field, "")).strip()
        d = safe_str(row.get(doc_field, "")).strip()
        if not q or not d:
            continue

        group = join_if_list(row.get(group_field, "")).strip() or "UNKNOWN_GROUP"
        key = make_key(row, key_field=key_field, fallback_fields=fallback_fields)
        pairs.append(PairExample(q=q, d=d, key=key, group=group))

    return pairs


def dedup_exact_pairs(pairs: List[PairExample]) -> List[PairExample]:
    """
    Remove only exact duplicate training examples.
    We intentionally do NOT deduplicate by `key` / `index`, because in this
    dataset the same index is not guaranteed to mean the same theorem.
    """
    seen = set()
    out = []
    for p in pairs:
        sig = (p.q, p.d, p.group)
        if sig in seen:
            continue
        seen.add(sig)
        out.append(p)
    return out


def group_split(
    pairs: List[PairExample],
    dev_frac: float,
    seed: int,
) -> Tuple[List[PairExample], List[PairExample]]:
    """
    Split by group (e.g. module_name) to reduce leakage across train/dev.
    """
    rng = random.Random(seed)
    groups = sorted({p.group for p in pairs})
    rng.shuffle(groups)
    n_dev = max(1, int(round(len(groups) * dev_frac)))
    dev_groups = set(groups[:n_dev])
    train = [p for p in pairs if p.group not in dev_groups]
    dev = [p for p in pairs if p.group in dev_groups]
    return train, dev


def encode_texts(
    model: SentenceTransformer,
    texts: List[str],
    batch_size: int,
    device: Optional[str],
) -> np.ndarray:
    emb = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
        device=device,
    )
    return l2_normalize(emb).astype(np.float32)


def search_topk(q_emb: np.ndarray, doc_emb: np.ndarray, k: int) -> np.ndarray:
    """
    Return indices I with shape (nq, k). Uses FAISS if available, else numpy.
    Assumes embeddings are float32 and normalized, so dot product = cosine similarity.
    """
    nq = q_emb.shape[0]
    nd = doc_emb.shape[0]
    k = min(k, nd)

    if _HAVE_FAISS:
        dim = doc_emb.shape[1]
        index = faiss.IndexFlatIP(dim)  # type: ignore
        index.add(doc_emb)
        _, I = index.search(q_emb, k)
        return I

    sims = q_emb @ doc_emb.T  # (nq, nd)
    I = np.argpartition(-sims, kth=k - 1, axis=1)[:, :k]
    row = np.arange(nq)[:, None]
    I = I[row, np.argsort(-sims[row, I], axis=1)]
    return I


def eval_retrieval_full_corpus(
    model: SentenceTransformer,
    train_pairs: List[PairExample],
    dev_pairs: List[PairExample],
    instruction: str,
    wrap_q: bool,
    wrap_d: bool,
    doc_prefix: str,
    k: int,
    batch_size: int,
    device: Optional[str],
    extra_ks: Tuple[int, ...] = (1, 5),
) -> Dict[str, float]:
 
    """...Computes Recall@k and MRR@k for k and all values in extra_ks."""
    all_ks = sorted(set((k,) + extra_ks))
    empty: Dict[str, float] = {f"recall@{ki}": 0.0 for ki in all_ks}
    empty[f"mrr@{k}"] = 0.0
    if not dev_pairs:
        return empty

    corpus_pairs = train_pairs + dev_pairs
    corpus_docs = [wrap_doc(p.d, doc_prefix) for p in corpus_pairs] if wrap_d else [p.d for p in corpus_pairs]

    dev_queries = [wrap_query(p.q, instruction) for p in dev_pairs] if wrap_q else [p.q for p in dev_pairs]
    dev_gold = [len(train_pairs) + i for i in range(len(dev_pairs))]

    doc_emb = encode_texts(model, corpus_docs, batch_size=batch_size, device=device)
    q_emb = encode_texts(model, dev_queries, batch_size=batch_size, device=device)

    max_k = max(all_ks)
    I = search_topk(q_emb, doc_emb, max_k)  # one pass covers every threshold

    hits: Dict[int, int] = {ki: 0 for ki in all_ks}
    rr = 0.0
    for qi in range(len(dev_pairs)):
        retrieved = I[qi].tolist() # length = max_k
        gold = dev_gold[qi]
        for ki in all_ks:
            if gold in retrieved[:ki]:
                hits[ki] += 1
            if gold in retrieved[:k]:  # MRR only at primary k
                rank = retrieved[:k].index(gold) + 1
                rr += 1.0 / rank

    n = len(dev_pairs)
    metrics = {f"recall@{ki}": hits[ki] / n for ki in all_ks}
    metrics[f"mrr@{k}"] = rr / n
    return metrics


def main() -> None:
    ap = argparse.ArgumentParser()

    # Dataset
    ap.add_argument("--dataset_name", type=str, default="FrenzyMath/mathlib_informal_v4.19.0")
    ap.add_argument("--subset", type=str, default="default")
    ap.add_argument("--split", type=str, default="train")
    ap.add_argument("--max_rows", type=int, default=10000)

    ap.add_argument("--query_field", type=str, default="informal_description")
    ap.add_argument("--doc_field", type=str, default="signature")
    ap.add_argument("--key_field", type=str, default="index")
    ap.add_argument("--group_field", type=str, default="module_name")

    # Model
    ap.add_argument("--model_name", type=str, default="Qwen/Qwen3-Embedding-8B")
    ap.add_argument("--output_dir", type=str, default="checkpoints/mnrl_mathlib_informal")
    ap.add_argument("--device", type=str, default=None)

    # Wrap
    ap.add_argument(
        "--instruction",
        type=str,
        default="Retrieve the corresponding Lean theorem statement for the given informal math description.",
    )
    ap.add_argument("--wrap_query", action="store_true")
    ap.add_argument("--wrap_doc", action="store_true")
    ap.add_argument("--doc_prefix", type=str, default="Document")

    # Split + seed
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dev_frac", type=float, default=0.1)

    # Training
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch_size", type=int, default=64)
    ap.add_argument("--max_seq_len", type=int, default=128)
    ap.add_argument("--warmup_steps", type=int, default=200)

    # Eval
    ap.add_argument("--k_eval", type=int, default=10)
    ap.add_argument("--eval_batch_size", type=int, default=256)

    # Checkpoints
    ap.add_argument("--checkpoint_dir", type=str, default="checkpoints/ckpt_mnrl_mathlib_informal")
    ap.add_argument("--checkpoint_save_steps", type=int, default=2000)

    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.checkpoint_dir, exist_ok=True)

    set_seed(args.seed)

    print("=== Load HF dataset ===")
    ds_dict = load_dataset(args.dataset_name, args.subset)
    ds = ds_dict[args.split]
    print(f"Loaded {args.dataset_name} split={args.split} rows={len(ds)}")

    print("=== Build pairs ===")
    pairs = build_pairs_from_hf_dataset(
        ds,
        query_field=args.query_field,
        doc_field=args.doc_field,
        key_field=args.key_field,
        group_field=args.group_field,
        max_rows=args.max_rows,
    )
    print(f"Pairs after empty-filter: {len(pairs)}")
    pairs = dedup_exact_pairs(pairs)
    print(f"Pairs after exact-pair dedup: {len(pairs)}")

    train_pairs, dev_pairs = group_split(pairs, dev_frac=args.dev_frac, seed=args.seed)
    print(f"Train={len(train_pairs)} Dev={len(dev_pairs)} (grouped by {args.group_field})")
    if not train_pairs or not dev_pairs:
        raise RuntimeError("Train/dev split empty. Adjust --dev_frac or --max_rows.")

    print("=== Load base model ===")
    model = SentenceTransformer(args.model_name, device=args.device)
    model.max_seq_length = args.max_seq_len

    print("=== Baseline eval (dev queries vs full corpus docs) ===")
    base = eval_retrieval_full_corpus(
        model=model,
        train_pairs=train_pairs,
        dev_pairs=dev_pairs,
        instruction=args.instruction,
        wrap_q=args.wrap_query,
        wrap_d=args.wrap_doc,
        doc_prefix=args.doc_prefix,
        k=args.k_eval,
        batch_size=args.eval_batch_size,
        device=args.device,
    )

    print(f"Baseline Recall@1:          {base['recall@1']:.4f}")
    print(f"Baseline Recall@5:          {base['recall@5']:.4f}")
    print(f"Baseline Recall@{args.k_eval}: {base[f'recall@{args.k_eval}']:.4f}")
    print(f"Baseline MRR@{args.k_eval}:    {base[f'mrr@{args.k_eval}']:.4f}")

    print("=== Build MNRL training set (pairs; in-batch negatives) ===")
    def _q(p: PairExample) -> str:
        return wrap_query(p.q, args.instruction) if args.wrap_query else p.q

    def _d(p: PairExample) -> str:
        return wrap_doc(p.d, args.doc_prefix) if args.wrap_doc else p.d

    train_examples = [InputExample(texts=[_q(p), _d(p)]) for p in train_pairs]
    train_loader = DataLoader(train_examples, batch_size=args.batch_size, shuffle=True, drop_last=True)

    print("=== Fine-tune with CachedMultipleNegativesRankingLoss ===")
    # print("=== Fine-tune with MultipleNegativesRankingLoss ===")
    # mnrl_loss = losses.MultipleNegativesRankingLoss(model=model)
    mnrl_loss = losses.CachedMultipleNegativesRankingLoss(model=model)

    t0 = time.time()
    model.fit(
        train_objectives=[(train_loader, mnrl_loss)],
        epochs=args.epochs,
        warmup_steps=args.warmup_steps,
        output_path=args.output_dir,
        show_progress_bar=True,
        checkpoint_path=args.checkpoint_dir,
        checkpoint_save_steps=args.checkpoint_save_steps,
    )
    print(f"Training time: {time.time() - t0:.1f}s")
    print(f"Saved model to: {args.output_dir}")

    print("=== Post-train eval (dev queries vs full corpus docs) ===")
    ft_model = SentenceTransformer(args.output_dir, device=args.device)
    ft_model.max_seq_length = args.max_seq_len
    ft = eval_retrieval_full_corpus(
        model=ft_model,
        train_pairs=train_pairs,
        dev_pairs=dev_pairs,
        instruction=args.instruction,
        wrap_q=args.wrap_query,
        wrap_d=args.wrap_doc,
        doc_prefix=args.doc_prefix,
        k=args.k_eval,
        batch_size=args.eval_batch_size,
        device=args.device,
    )

    print(f"FT Recall@1:          {ft['recall@1']:.4f}")
    print(f"FT Recall@5:          {ft['recall@5']:.4f}")
    print(f"FT Recall@{args.k_eval}: {ft[f'recall@{args.k_eval}']:.4f}")
    print(f"FT MRR@{args.k_eval}:    {ft[f'mrr@{args.k_eval}']:.4f}")

    metrics_path = os.path.join(args.output_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "baseline": {"k": args.k_eval, **base},
                "finetuned": {"k": args.k_eval, **ft},
                "config": vars(args),
                "counts": {"pairs_total": len(pairs), "train": len(train_pairs), "dev": len(dev_pairs)},
                "eval_setting": "dev queries vs (train+dev) doc corpus; gold is dev doc index in full corpus",
                "faiss_available": _HAVE_FAISS,
                "method": "MultipleNegativesRankingLoss (in-batch negatives)",
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Wrote metrics: {metrics_path}")


if __name__ == "__main__":
    main()