#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Same recipe as train_qwen_mnrl_v2.py (FrenzyMath mathlib_informal pairs, Cached MNRL,
group-split dev set), plus an --extra_json file of medium-difficulty problems
("11-20 training run.json") mixed into TRAINING ONLY.

Each extra row has statement / lean_code / hard_negative{nl, lean}. It yields:
  - positive pair (statement -> lean_code)
  - hard-negative pair (hard_negative.nl -> hard_negative.lean)
The batch sampler keeps all pairs of one problem in the same batch, so the
near-duplicate Lean statements act as in-batch hard negatives for each other.
Everything stays 2-text pairs, so a single loader / single objective is used.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from collections import OrderedDict
from typing import Iterator, List

import torch
from datasets import load_dataset
from sentence_transformers import InputExample, SentenceTransformer, losses

# The cuDNN SDPA backend fails here ("No valid execution plans built");
# fall back to the flash / memory-efficient kernels.
torch.backends.cuda.enable_cudnn_sdp(False)
from torch.utils.data import DataLoader

from train_qwen_mnrl_v2 import (
    build_pairs_from_hf_dataset,
    dedup_exact_pairs,
    eval_retrieval_full_corpus,
    group_split,
    set_seed,
    wrap_doc,
    wrap_query,
)


def clean_lean(code: str) -> str:
    """Drop the `import ...` header and trailing `:= by sorry` so the doc looks like
    a Mathlib signature."""
    lines = [l for l in code.splitlines() if not l.strip().startswith("import ")]
    out = "\n".join(lines).strip()
    return re.sub(r"\s*:=\s*by\s+sorry\s*$", "", out).strip()


class UnitBatchSampler:
    """Batches of ~batch_size examples; each unit (a list of dataset indices) stays together."""

    def __init__(self, units: List[List[int]], batch_size: int, seed: int):
        self.units, self.batch_size, self.seed, self.epoch = units, batch_size, seed, 0

    def _batches(self) -> List[List[int]]:
        rng = random.Random(self.seed + self.epoch)
        order = list(range(len(self.units)))
        rng.shuffle(order)
        batches, cur = [], []
        for u in order:
            unit = self.units[u]
            if cur and len(cur) + len(unit) > self.batch_size:
                batches.append(cur)
                cur = []
            cur = cur + unit
        if len(cur) >= self.batch_size:  # drop a short last batch
            batches.append(cur)
        return batches

    def __iter__(self) -> Iterator[List[int]]:
        batches = self._batches()
        self.epoch += 1
        return iter(batches)

    def __len__(self) -> int:
        return len(self._batches())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset_name", default="FrenzyMath/mathlib_informal_v4.19.0")
    ap.add_argument("--subset", default="default")
    ap.add_argument("--split", default="train")
    ap.add_argument("--max_rows", type=int, default=200000)
    ap.add_argument("--query_field", default="informal_description")
    ap.add_argument("--doc_field", default="signature")
    ap.add_argument("--key_field", default="index")
    ap.add_argument("--group_field", default="module_name")
    ap.add_argument("--extra_json", default="finetune/11-20 training run.json")
    ap.add_argument("--model_name", default="Qwen/Qwen3-Embedding-8B")
    ap.add_argument("--output_dir", default="checkpoints/mix_extra")
    ap.add_argument("--checkpoint_dir", default="checkpoints/ckpt_mix_extra")
    ap.add_argument("--device", default=None)
    ap.add_argument(
        "--instruction",
        default="Retrieve the corresponding Lean theorem statement for the given informal math description.",
    )
    ap.add_argument("--wrap_query", action="store_true")
    ap.add_argument("--wrap_doc", action="store_true")
    ap.add_argument("--doc_prefix", default="Document")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--dev_frac", type=float, default=0.1)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch_size", type=int, default=16)
    ap.add_argument("--max_seq_len", type=int, default=128)
    ap.add_argument("--warmup_steps", type=int, default=200)
    ap.add_argument("--k_eval", type=int, default=10)
    ap.add_argument("--eval_batch_size", type=int, default=8)
    ap.add_argument("--checkpoint_save_steps", type=int, default=2000)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.checkpoint_dir, exist_ok=True)
    set_seed(args.seed)

    print("=== Load base dataset ===")
    ds = load_dataset(args.dataset_name, args.subset)[args.split]
    pairs = dedup_exact_pairs(build_pairs_from_hf_dataset(
        ds, args.query_field, args.doc_field, args.key_field, args.group_field, args.max_rows))
    train_pairs, dev_pairs = group_split(pairs, args.dev_frac, args.seed)
    print(f"Base pairs={len(pairs)} train={len(train_pairs)} dev={len(dev_pairs)}")
    if not train_pairs or not dev_pairs:
        raise RuntimeError("Train/dev split empty.")

    def q(t: str) -> str:
        return wrap_query(t, args.instruction) if args.wrap_query else t

    def d(t: str) -> str:
        return wrap_doc(t, args.doc_prefix) if args.wrap_doc else t

    examples: List[InputExample] = [InputExample(texts=[q(p.q), d(p.d)]) for p in train_pairs]
    units: List[List[int]] = [[i] for i in range(len(examples))]

    print(f"=== Load extra training rows: {args.extra_json} ===")
    with open(args.extra_json, encoding="utf-8") as f:
        extra_rows = json.load(f)
    # One unit per problem id: its positive pair + each hard-negative pair (deduped).
    by_id: "OrderedDict[object, set]" = OrderedDict()
    for r in extra_rows:
        hn = r["hard_negative"]
        s = by_id.setdefault(r["id"], set())
        s.add((r["statement"].strip(), clean_lean(r["lean_code"])))
        s.add((hn["nl"].strip(), clean_lean(hn["lean"])))
    for pair_set in by_id.values():
        unit = []
        for nl, lean in sorted(pair_set):
            unit.append(len(examples))
            examples.append(InputExample(texts=[q(nl), d(lean)]))
        units.append(unit)
    print(f"Extra: {len(extra_rows)} rows -> {len(by_id)} problems, "
          f"{len(examples) - len(train_pairs)} extra pairs")

    loader = DataLoader(
        examples,
        batch_sampler=UnitBatchSampler(units, args.batch_size, args.seed),
        collate_fn=lambda b: b,
    )
    # Legacy model.fit() needs the SentenceTransformer collate; set it after model load.

    print("=== Load base model ===")
    model = SentenceTransformer(args.model_name, device=args.device)
    model.max_seq_length = args.max_seq_len
    loader.collate_fn = model.smart_batching_collate

    print("=== Baseline eval ===")
    ev = dict(train_pairs=train_pairs, dev_pairs=dev_pairs, instruction=args.instruction,
              wrap_q=args.wrap_query, wrap_d=args.wrap_doc, doc_prefix=args.doc_prefix,
              k=args.k_eval, batch_size=args.eval_batch_size, device=args.device)
    base = eval_retrieval_full_corpus(model=model, **ev)
    print("Baseline:", base)

    print("=== Fine-tune with CachedMultipleNegativesRankingLoss ===")
    loss = losses.CachedMultipleNegativesRankingLoss(model=model)
    t0 = time.time()
    model.fit(
        train_objectives=[(loader, loss)],
        epochs=args.epochs,
        warmup_steps=args.warmup_steps,
        output_path=args.output_dir,
        show_progress_bar=True,
        checkpoint_path=args.checkpoint_dir,
        checkpoint_save_steps=args.checkpoint_save_steps,
    )
    print(f"Training time: {time.time() - t0:.1f}s; saved to {args.output_dir}")

    print("=== Post-train eval ===")
    ft_model = SentenceTransformer(args.output_dir, device=args.device)
    ft_model.max_seq_length = args.max_seq_len
    ft = eval_retrieval_full_corpus(model=ft_model, **ev)
    print("Finetuned:", ft)

    with open(os.path.join(args.output_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"baseline": base, "finetuned": ft, "config": vars(args),
                   "counts": {"base_train": len(train_pairs), "dev": len(dev_pairs),
                              "extra_rows": len(extra_rows), "extra_problems": len(by_id)}},
                  f, indent=2)


if __name__ == "__main__":
    main()
