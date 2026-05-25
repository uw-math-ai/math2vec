#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
train_qwen_mnrl_multiview.py

Multi-view contrastive fine-tuning, using CachedMultipleNegativesRankingLoss
with two loaders:

  Loader 1 (base): all training concepts. Each example is a randomly-sampled
    pair of views from the same concept, RE-SAMPLED PER __getitem__ CALL (i.e.
    per epoch the same concept can produce different view pairs). Covers
    NL <-> Lean, Lean <-> Lean, NL <-> NL (rephrasings) via stochastic pairing
    — SimCLR-style.

  Loader 2 (reverse + hard neg): subset of training concepts with non-empty
    hard_negatives.nl. Each example is [Lean_anchor, nl_positive, hn_1, ..., hn_N].
    Anchor is forced to be a Lean view so the positive and hard negatives are
    both NL — same modality. This prevents the model from learning a
    "detect modality" shortcut. Also re-sampled per __getitem__.

Key fixes vs the previous version:
  1. Per-epoch view resampling via torch Dataset subclasses (was: one fixed
     sampling for the whole run, which neutralized the SimCLR-style stochastic
     regularization).
  2. LR schedule: use scheduler='warmupconstant' so LR ramps up over
     warmup_steps then HOLDS CONSTANT (was: default WarmupLinear scheduler
     computed t_total from min(loader_lengths)*epochs with two unequal loaders,
     causing LR to hit 0 around epoch 1.5 of 3. Note: steps_per_epoch can't fix
     this — newer sentence-transformers silently ignores it when epochs > 1.)
  3. Per-pair-type evaluation suite: in addition to the primary NL->Lean
     retrieval task, evaluate every (query_field, doc_field) pair that the
     multi-view training claims to help (NL rephrasing -> Lean, Lean type ->
     Lean signature, reverse Lean -> NL, etc.) so we can see WHERE the gains
     concentrate.
  4. Tokenizer consistency: both baseline and FT loads pass
     fix_mistral_regex=True so they tokenize identically (was: warning when
     loading FT checkpoint indicated baseline/FT used different tokenization).

Hard negatives are read directly from the dataset's `hard_negatives.nl` field.

Run:
    python train_qwen_mnrl_multiview.py

    # smoke test
    python train_qwen_mnrl_multiview.py \\
        --model_name "sentence-transformers/all-MiniLM-L6-v2" \\
        --max_rows 500 \\
        --batch_size 8 \\
        --hard_neg_batch_size 4 \\
        --device cpu \\
        --output_dir /tmp/multiview_test
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    import faiss  # type: ignore
    _HAVE_FAISS = True
except Exception:
    faiss = None  # type: ignore
    _HAVE_FAISS = False

from torch.utils.data import Dataset, DataLoader
from sentence_transformers import SentenceTransformer, InputExample, losses
from datasets import load_dataset


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

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


def safe_str(x) -> str:
    return x if isinstance(x, str) else ""


def join_if_list(x) -> str:
    if isinstance(x, list):
        return "/".join(str(t) for t in x if t is not None)
    if isinstance(x, str):
        return x
    return ""


def load_st_model(
    name_or_path: str,
    device: Optional[str],
    max_seq_len: int,
) -> SentenceTransformer:
    """Load a SentenceTransformer with the fix_mistral_regex tokenizer flag.

    The Qwen3-Embedding tokenizer (and several other recent SentencePiece-style
    tokenizers) has a regex pattern bug that newer transformers libraries warn
    about. Passing fix_mistral_regex=True corrects it. We apply this to BOTH
    baseline and FT model loads so tokenization is consistent across the A/B.

    Falls back to a plain load if the version of sentence-transformers or
    transformers doesn't support the flag — in that case baseline/FT may
    tokenize slightly differently, but the warning will be informative.
    """
    try:
        m = SentenceTransformer(
            name_or_path,
            device=device,
            model_kwargs={"torch_dtype": "auto"},
            tokenizer_kwargs={"fix_mistral_regex": True},
        )
    except (TypeError, ValueError) as e:
        print(f"[tokenizer] fix_mistral_regex not applied ({type(e).__name__}: {e}); "
              f"loading {name_or_path} without it.")
        m = SentenceTransformer(
            name_or_path,
            device=device,
            model_kwargs={"torch_dtype": "auto"},
        )
    m.max_seq_length = max_seq_len
    return m


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

# Named view fields we care about for per-pair-type eval. Order doesn't matter
# here — it's just the set of canonical keys we'll look up by name later.
NAMED_VIEW_FIELDS = (
    "nl_informal",
    "nl_informal_2",
    "nl_formal",
    "nl_concise",
    "lean_type",
    "lean_signature",
)


@dataclass
class ConceptRecord:
    """One concept's data — all views and hard negatives in one place."""
    concept_id: str
    nl_views: List[str]        # ordered list for training (anchor/positive sampling)
    lean_views: List[str]      # ordered list for training
    nl_hard_negs: List[str]
    module_name: str
    # Named view map for per-pair-type eval — keyed by canonical view name.
    # nl_rephrasings (list) is NOT included here because it can have multiple
    # entries; rephrasings still feed training via nl_views.
    views_by_name: Dict[str, str] = field(default_factory=dict)


def extract_record(row: dict) -> Optional[ConceptRecord]:
    """Parse one row of the dataset into a ConceptRecord.
    Returns None if essential fields are missing."""
    concept_id = row.get("concept_id") or ""
    views_dict = row.get("views") or {}
    hn_dict = row.get("hard_negatives") or {}
    metadata = row.get("metadata") or {}

    views_by_name: Dict[str, str] = {}

    # ---- NL views (for training: ordered list with nl_informal first) ----
    nl_views: List[str] = []

    nl_informal = safe_str(views_dict.get("nl_informal", "")).strip()
    if nl_informal:
        nl_views.append(nl_informal)
        views_by_name["nl_informal"] = nl_informal

    # nl_rephrasings: list OR string. Only contributes to nl_views (training);
    # not stored as a single named view because it can have multiple entries.
    rephrasings = views_dict.get("nl_rephrasings")
    if isinstance(rephrasings, list):
        nl_views.extend(safe_str(r).strip() for r in rephrasings if safe_str(r).strip())
    elif isinstance(rephrasings, str) and rephrasings.strip():
        nl_views.append(rephrasings.strip())

    # Additional named NL views: nl_informal_2, nl_formal, nl_concise
    for extra_key in ("nl_informal_2", "nl_formal", "nl_concise"):
        extra = safe_str(views_dict.get(extra_key, "")).strip()
        if extra:
            nl_views.append(extra)
            views_by_name[extra_key] = extra

    # ---- Lean views ----
    lean_views: List[str] = []
    for key in ("lean_type", "lean_signature"):
        v = safe_str(views_dict.get(key, "")).strip()
        if v:
            lean_views.append(v)
            views_by_name[key] = v

    # ---- Hard negatives (NL only) ----
    nl_hns: List[str] = []
    raw_nl_hns = hn_dict.get("nl") or []
    for hn in raw_nl_hns:
        if isinstance(hn, dict):
            stmt = safe_str(hn.get("statement", "")).strip()
        else:
            stmt = safe_str(hn).strip()
        if stmt:
            nl_hns.append(stmt)

    # Sanity: need at least one NL view and one Lean view to do anything useful
    if not nl_views or not lean_views or not concept_id:
        return None

    module_name = join_if_list(metadata.get("module_name", "")) or "UNKNOWN"

    return ConceptRecord(
        concept_id=concept_id,
        nl_views=nl_views,
        lean_views=lean_views,
        nl_hard_negs=nl_hns,
        module_name=module_name,
        views_by_name=views_by_name,
    )


def load_concepts(
    dataset_name: Optional[str],
    split: str,
    max_rows: Optional[int],
    local_jsonl: Optional[str] = None,
) -> List[ConceptRecord]:
    """Load and parse records from either a HF dataset or a local JSONL file."""
    records: List[ConceptRecord] = []
    skipped = 0

    if local_jsonl:
        print(f"Reading from local JSONL: {local_jsonl}")
        with open(local_jsonl, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if max_rows is not None and i >= max_rows:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    skipped += 1
                    continue
                rec = extract_record(row)
                if rec is None:
                    skipped += 1
                    continue
                records.append(rec)
        source = local_jsonl
    else:
        if not dataset_name:
            raise ValueError("Must provide either --dataset_name or --local_jsonl")
        print(f"Reading from HF dataset: {dataset_name}")
        ds = load_dataset(dataset_name, split=split)
        n = len(ds) if max_rows is None else min(len(ds), max_rows)
        for i in range(n):
            rec = extract_record(ds[i])
            if rec is None:
                skipped += 1
                continue
            records.append(rec)
        source = dataset_name

    print(f"Loaded {len(records)} concept records from {source} (skipped {skipped} malformed)")
    return records


# ---------------------------------------------------------------------------
# Train/dev split by module (prevents leakage of related theorems)
# ---------------------------------------------------------------------------

def group_split_records(
    records: List[ConceptRecord],
    dev_frac: float,
    seed: int,
) -> Tuple[List[ConceptRecord], List[ConceptRecord]]:
    rng = random.Random(seed)
    groups = sorted({r.module_name for r in records})
    rng.shuffle(groups)
    n_dev = max(1, int(round(len(groups) * dev_frac)))
    dev_groups = set(groups[:n_dev])
    train = [r for r in records if r.module_name not in dev_groups]
    dev = [r for r in records if r.module_name in dev_groups]
    return train, dev


# ---------------------------------------------------------------------------
# Training Datasets — resample views on every __getitem__ (per-epoch variation)
# ---------------------------------------------------------------------------

class MultiViewBaseDataset(Dataset):
    """Base dataset: each __getitem__ randomly samples 2 views (anchor, positive)
    from the union of nl_views + lean_views for the given concept.

    Because __getitem__ is called fresh every epoch (DataLoader doesn't cache),
    the same concept produces different view pairs across epochs. This is the
    SimCLR-style stochastic pairing the writeup describes.
    """

    def __init__(
        self,
        records: List[ConceptRecord],
        instruction: str,
        reverse_instruction: str,
        wrap_q: bool,
        wrap_d: bool,
        doc_prefix: str,
    ):
        # Only keep concepts with at least 2 total views (otherwise can't pair)
        self.records = [
            r for r in records
            if len(r.nl_views) + len(r.lean_views) >= 2
        ]
        self.instruction = instruction
        self.reverse_instruction = reverse_instruction
        self.wrap_q = wrap_q
        self.wrap_d = wrap_d
        self.doc_prefix = doc_prefix

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> InputExample:
        r = self.records[idx]
        all_views = (
            [(v, "nl") for v in r.nl_views] +
            [(v, "lean") for v in r.lean_views]
        )
        # random.sample uses the global random state, which is seeded by
        # set_seed(). With num_workers=0 this is deterministic per run but
        # produces different pairs across epochs.
        (anchor_text, anchor_mod), (positive_text, _) = random.sample(all_views, 2)

        if self.wrap_q:
            instr = self.instruction if anchor_mod == "nl" else self.reverse_instruction
            anchor_text = wrap_query(anchor_text, instr)
        if self.wrap_d:
            positive_text = wrap_doc(positive_text, self.doc_prefix)

        return InputExample(texts=[anchor_text, positive_text])


class MultiViewHNDataset(Dataset):
    """Hard-negative dataset: anchor is a random Lean view, positive is a random
    NL view, hard negatives are random NL hard-neg statements.

    Anchor MUST be Lean so positive and hard negatives share modality (NL),
    preventing a "detect modality" shortcut.

    Re-samples Lean anchor / NL positive / which N hard negs on every __getitem__.
    """

    def __init__(
        self,
        records: List[ConceptRecord],
        n_hn: int,
        reverse_instruction: str,
        wrap_q: bool,
        wrap_d: bool,
        doc_prefix: str,
    ):
        self.records = [
            r for r in records
            if len(r.nl_hard_negs) >= n_hn and r.lean_views and r.nl_views
        ]
        self.n_hn = n_hn
        self.reverse_instruction = reverse_instruction
        self.wrap_q = wrap_q
        self.wrap_d = wrap_d
        self.doc_prefix = doc_prefix

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> InputExample:
        r = self.records[idx]
        anchor_text = random.choice(r.lean_views)
        positive_text = random.choice(r.nl_views)
        hns = random.sample(r.nl_hard_negs, self.n_hn)

        if self.wrap_q:
            anchor_text = wrap_query(anchor_text, self.reverse_instruction)
        if self.wrap_d:
            positive_text = wrap_doc(positive_text, self.doc_prefix)
            hns = [wrap_doc(h, self.doc_prefix) for h in hns]

        return InputExample(texts=[anchor_text, positive_text, *hns])


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

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
    nq = q_emb.shape[0]
    nd = doc_emb.shape[0]
    k = min(k, nd)

    if _HAVE_FAISS:
        dim = doc_emb.shape[1]
        index = faiss.IndexFlatIP(dim)  # type: ignore
        index.add(doc_emb)
        _, I = index.search(q_emb, k)
        return I

    sims = q_emb @ doc_emb.T
    I = np.argpartition(-sims, kth=k - 1, axis=1)[:, :k]
    row = np.arange(nq)[:, None]
    I = I[row, np.argsort(-sims[row, I], axis=1)]
    return I


def eval_retrieval(
    model: SentenceTransformer,
    train_records: List[ConceptRecord],
    dev_records: List[ConceptRecord],
    query_field: str,
    doc_field: str,
    instruction: str,
    wrap_q: bool,
    wrap_d: bool,
    doc_prefix: str,
    k: int,
    batch_size: int,
    device: Optional[str],
    extra_ks: Tuple[int, ...] = (1, 5),
) -> Optional[Dict[str, float]]:
    """Retrieve dev concepts' query_field against (train+dev) doc_field corpus.

    Returns None if no dev concept has both query_field and doc_field, or if
    no corpus concept has doc_field.

    Concepts are only included in the corpus if they have doc_field; only
    included in dev queries if they have BOTH query_field and doc_field (so
    the gold target exists in the corpus).
    """
    all_records = train_records + dev_records

    # Corpus: all concepts with doc_field. Track concept_id -> corpus index.
    corpus_idx_map: Dict[str, int] = {}
    corpus_docs: List[str] = []
    for r in all_records:
        text = r.views_by_name.get(doc_field)
        if text:
            corpus_idx_map[r.concept_id] = len(corpus_docs)
            corpus_docs.append(text)

    if not corpus_docs:
        return None

    # Dev queries: dev concepts with both query_field AND doc_field (need
    # doc_field so gold exists in corpus).
    dev_queries: List[str] = []
    dev_gold: List[int] = []
    for r in dev_records:
        q_text = r.views_by_name.get(query_field)
        if q_text and r.concept_id in corpus_idx_map:
            dev_queries.append(q_text)
            dev_gold.append(corpus_idx_map[r.concept_id])

    n_dev_used = len(dev_queries)
    if n_dev_used == 0:
        return None

    if wrap_q:
        dev_queries = [wrap_query(q, instruction) for q in dev_queries]
    if wrap_d:
        corpus_docs = [wrap_doc(d, doc_prefix) for d in corpus_docs]

    doc_emb = encode_texts(model, corpus_docs, batch_size=batch_size, device=device)
    q_emb = encode_texts(model, dev_queries, batch_size=batch_size, device=device)

    all_ks = sorted(set((k,) + extra_ks))
    max_k = max(all_ks)
    I = search_topk(q_emb, doc_emb, max_k)

    hits: Dict[int, int] = {ki: 0 for ki in all_ks}
    rr = 0.0
    for qi in range(n_dev_used):
        retrieved = I[qi].tolist()
        gold = dev_gold[qi]
        for ki in all_ks:
            if gold in retrieved[:ki]:
                hits[ki] += 1
        if gold in retrieved[:k]:
            rank = retrieved[:k].index(gold) + 1
            rr += 1.0 / rank

    metrics: Dict[str, float] = {f"recall@{ki}": hits[ki] / n_dev_used for ki in all_ks}
    metrics[f"mrr@{k}"] = rr / n_dev_used
    metrics["n_dev_used"] = float(n_dev_used)
    metrics["corpus_size"] = float(len(corpus_docs))
    return metrics


# Pair types evaluated post-train. Each tuple is:
#   (query_field, doc_field, instruction_kind, description)
# instruction_kind is "forward" (NL-style query) or "reverse" (Lean-style query).
PAIR_TYPES: List[Tuple[str, str, str, str]] = [
    ("nl_informal",   "lean_signature", "forward", "NL -> Lean signature (PRIMARY)"),
    ("nl_informal",   "lean_type",      "forward", "NL -> Lean type"),
    ("nl_informal_2", "lean_signature", "forward", "NL rephrasing -> Lean signature"),
    ("nl_informal_2", "nl_informal",    "forward", "NL rephrasing -> NL informal (NL<->NL)"),
    ("lean_type",     "lean_signature", "reverse", "Lean type -> Lean signature (Lean<->Lean)"),
    ("lean_signature","nl_informal",    "reverse", "Lean signature -> NL informal (REVERSE)"),
]


def eval_all_pair_types(
    model: SentenceTransformer,
    train_records: List[ConceptRecord],
    dev_records: List[ConceptRecord],
    instruction: str,
    reverse_instruction: str,
    wrap_q: bool,
    wrap_d: bool,
    doc_prefix: str,
    k: int,
    batch_size: int,
    device: Optional[str],
) -> Dict[str, Dict]:
    """Run retrieval eval across all PAIR_TYPES and return a results dict.
    Each entry: {description, recall@1, recall@5, recall@k, mrr@k, n_dev_used, corpus_size}
    or {description, skipped: True} if no concepts have the required views.
    """
    results: Dict[str, Dict] = {}
    for q_field, d_field, instr_kind, desc in PAIR_TYPES:
        key = f"{q_field}__to__{d_field}"
        instr = instruction if instr_kind == "forward" else reverse_instruction
        print(f"\n--- Eval pair: {desc} ({q_field} -> {d_field}) ---")
        m = eval_retrieval(
            model=model,
            train_records=train_records,
            dev_records=dev_records,
            query_field=q_field,
            doc_field=d_field,
            instruction=instr,
            wrap_q=wrap_q,
            wrap_d=wrap_d,
            doc_prefix=doc_prefix,
            k=k,
            batch_size=batch_size,
            device=device,
        )
        if m is None:
            print(f"  SKIPPED (no concepts have both {q_field} and {d_field})")
            results[key] = {"description": desc, "skipped": True}
        else:
            print(f"  n_dev={int(m['n_dev_used'])}, corpus={int(m['corpus_size'])}")
            print(f"  R@1={m['recall@1']:.4f}  R@5={m['recall@5']:.4f}  "
                  f"R@{k}={m[f'recall@{k}']:.4f}  MRR@{k}={m[f'mrr@{k}']:.4f}")
            results[key] = {"description": desc, **m}
    return results


def print_pair_type_comparison(
    base_results: Dict[str, Dict],
    ft_results: Dict[str, Dict],
    k: int,
) -> None:
    """Print a side-by-side baseline vs FT table for all pair types."""
    print()
    print("=" * 100)
    print("Per-pair-type comparison (Baseline -> FT, Δ)")
    print("=" * 100)
    header = f"{'Pair type':<48} {'n':>5}  {'R@1':>16}  {'R@5':>16}  {'MRR@'+str(k):>16}"
    print(header)
    print("-" * 100)
    for q_field, d_field, _instr, desc in PAIR_TYPES:
        key = f"{q_field}__to__{d_field}"
        b = base_results.get(key, {})
        f = ft_results.get(key, {})
        if b.get("skipped") or f.get("skipped"):
            print(f"{desc:<48} {'--':>5}  {'(skipped)':>16}")
            continue
        n = int(b.get("n_dev_used", 0))
        def fmt(metric: str) -> str:
            bv = b.get(metric, 0.0)
            fv = f.get(metric, 0.0)
            d = fv - bv
            sign = "+" if d >= 0 else ""
            return f"{bv:.4f}->{fv:.4f}({sign}{d:.3f})"
        print(f"{desc:<48} {n:>5}  {fmt('recall@1'):>16}  "
              f"{fmt('recall@5'):>16}  {fmt(f'mrr@{k}'):>16}")
    print("=" * 100)


# ---------------------------------------------------------------------------
# Per-pair-type contrastive loss diagnostic
#
# MNRL/CachedMNRL loss is, for a batch of N (anchor, positive) pairs:
#   sims = scale * cos_sim(A, P)           # shape (N, N)
#   loss = cross_entropy(sims, labels=[0,1,...,N-1])
# scale = 20.0 (sentence-transformers default for both MNRL and CachedMNRL).
# Cached only differs in HOW it computes — same math.
#
# Per-pair-type measurement: build batches where every example uses the same
# (q_field, d_field) pair type. The resulting batch-level loss is then a clean
# measurement of "how well the model contrastively distinguishes this pair
# type's positives from in-batch negatives".
# ---------------------------------------------------------------------------

def eval_pair_type_loss(
    model: SentenceTransformer,
    records: List[ConceptRecord],
    query_field: str,
    doc_field: str,
    instruction: str,
    wrap_q: bool,
    wrap_d: bool,
    doc_prefix: str,
    batch_size: int,
    n_batches: int,
    device: Optional[str],
    seed: int,
    scale: float = 20.0,
) -> Optional[float]:
    """Compute the average MNRL contrastive loss for a single pair type by
    constructing homogeneous batches. Returns None if not enough records.

    For each batch of `batch_size` (anchor, positive) pairs of THIS pair type:
        sims = scale * (anchor_emb @ positive_emb.T)
        loss = CE(sims, identity_labels)
    Returns mean loss across `n_batches`.
    """
    import torch
    import torch.nn.functional as F

    # Collect all eligible (q_text, d_text) pairs of this type
    pairs: List[Tuple[str, str]] = []
    for r in records:
        q = r.views_by_name.get(query_field)
        d = r.views_by_name.get(doc_field)
        if q and d:
            pairs.append((q, d))

    if len(pairs) < batch_size:
        return None  # Not enough pairs to form even one full batch

    # Shuffle deterministically
    rng = random.Random(seed)
    rng.shuffle(pairs)

    n_batches_actual = min(n_batches, len(pairs) // batch_size)
    if n_batches_actual == 0:
        return None

    losses = []
    for bi in range(n_batches_actual):
        batch = pairs[bi * batch_size : (bi + 1) * batch_size]
        anchors = [p[0] for p in batch]
        positives = [p[1] for p in batch]

        if wrap_q:
            anchors = [wrap_query(a, instruction) for a in anchors]
        if wrap_d:
            positives = [wrap_doc(p, doc_prefix) for p in positives]

        with torch.no_grad():
            anchor_emb = model.encode(
                anchors, batch_size=batch_size, convert_to_tensor=True,
                normalize_embeddings=True, show_progress_bar=False, device=device,
            )
            positive_emb = model.encode(
                positives, batch_size=batch_size, convert_to_tensor=True,
                normalize_embeddings=True, show_progress_bar=False, device=device,
            )
            sims = scale * (anchor_emb @ positive_emb.T)
            labels = torch.arange(len(batch), device=sims.device)
            # Use float32 for the loss computation to match training
            loss = F.cross_entropy(sims.float(), labels)
        losses.append(loss.item())

    return float(np.mean(losses))


def eval_all_pair_type_losses(
    model: SentenceTransformer,
    records: List[ConceptRecord],
    instruction: str,
    reverse_instruction: str,
    wrap_q: bool,
    wrap_d: bool,
    doc_prefix: str,
    batch_size: int,
    n_batches: int,
    device: Optional[str],
    seed: int,
) -> Dict[str, Optional[float]]:
    """Run eval_pair_type_loss across all PAIR_TYPES."""
    results: Dict[str, Optional[float]] = {}
    for q_field, d_field, instr_kind, desc in PAIR_TYPES:
        key = f"{q_field}__to__{d_field}"
        instr = instruction if instr_kind == "forward" else reverse_instruction
        print(f"  [loss-eval] {desc} ({q_field} -> {d_field})")
        loss = eval_pair_type_loss(
            model=model,
            records=records,
            query_field=q_field,
            doc_field=d_field,
            instruction=instr,
            wrap_q=wrap_q,
            wrap_d=wrap_d,
            doc_prefix=doc_prefix,
            batch_size=batch_size,
            n_batches=n_batches,
            device=device,
            seed=seed,
        )
        if loss is None:
            print(f"    SKIPPED (not enough pairs)")
            results[key] = None
        else:
            print(f"    contrastive loss = {loss:.4f}")
            results[key] = loss
    return results


def print_pair_type_loss_comparison(
    base_losses: Dict[str, Optional[float]],
    ft_losses: Dict[str, Optional[float]],
) -> None:
    """Print a side-by-side baseline vs FT loss table for all pair types."""
    print()
    print("=" * 90)
    print("Per-pair-type contrastive loss (Baseline -> FT, Δ)")
    print("Lower = model distinguishes this pair type's positive from negatives better.")
    print("=" * 90)
    header = f"{'Pair type':<50} {'Baseline':>10}  {'FT':>10}  {'Δ':>10}"
    print(header)
    print("-" * 90)
    for q_field, d_field, _instr, desc in PAIR_TYPES:
        key = f"{q_field}__to__{d_field}"
        b = base_losses.get(key)
        f = ft_losses.get(key)
        if b is None or f is None:
            print(f"{desc:<50} {'(skipped)':>32}")
            continue
        d = f - b
        sign = "+" if d >= 0 else ""
        print(f"{desc:<50} {b:>10.4f}  {f:>10.4f}  {sign}{d:>9.4f}")
    print("=" * 90)
    print("Note: down = improved (lower loss = better contrastive separation)")
    print("      up   = degraded (model worse at distinguishing this direction)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()

    # Dataset
    ap.add_argument("--dataset_name", type=str, default="ACDRepo/math_embedder_training",
                    help="HF dataset name (ignored if --local_jsonl is set)")
    ap.add_argument("--local_jsonl", type=str, default=None,
                    help="Local path to JSONL file (one record per line, same schema). "
                         "Overrides --dataset_name when provided.")
    ap.add_argument("--split", type=str, default="train")
    ap.add_argument("--max_rows", type=int, default=None)

    # Model
    ap.add_argument("--model_name", type=str, default="Qwen/Qwen3-Embedding-8B")
    ap.add_argument("--output_dir", type=str, default="checkpoints/multiview_mathlib")
    ap.add_argument("--device", type=str, default=None)

    # Wrap
    ap.add_argument(
        "--instruction",
        type=str,
        default="Retrieve the corresponding Lean theorem statement for the given informal math description.",
    )
    ap.add_argument(
        "--reverse_instruction",
        type=str,
        default="Retrieve the informal math description for the given Lean theorem statement.",
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
    ap.add_argument("--loss", type=str, default="cached",
                    choices=["cached", "plain"],
                    help="'cached' for CachedMNRL (GPU, large batch); 'plain' for MNRL (Mac/CPU compatible)")

    # Hard negatives
    ap.add_argument("--hard_neg_batch_size", type=int, default=16)
    ap.add_argument("--n_hard_negs", type=int, default=3)

    # Eval
    ap.add_argument("--k_eval", type=int, default=10)
    ap.add_argument("--eval_batch_size", type=int, default=256)
    ap.add_argument("--skip_pair_type_eval", action="store_true",
                    help="Skip the per-pair-type eval suite (saves time on smoke tests)")
    ap.add_argument("--skip_pair_type_loss_eval", action="store_true",
                    help="Skip the per-pair-type contrastive-loss diagnostic. "
                         "Useful for smoke tests where you only want to validate "
                         "the pipeline runs.")
    ap.add_argument("--pair_loss_batch_size", type=int, default=16,
                    help="Batch size for per-pair-type contrastive loss eval. "
                         "Should be the same as training batch_size for "
                         "comparability to training-time loss values.")
    ap.add_argument("--pair_loss_n_batches", type=int, default=30,
                    help="How many homogeneous batches to average per pair type. "
                         "30 batches @ 16 = ~480 pairs per type, enough to be stable.")

    # Checkpoints
    ap.add_argument("--checkpoint_dir", type=str, default="checkpoints/ckpt_multiview")
    ap.add_argument("--checkpoint_save_steps", type=int, default=2000)

    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(args.checkpoint_dir, exist_ok=True)

    set_seed(args.seed)

    # -------------------------------------------------------------------
    # Load data
    # -------------------------------------------------------------------
    print("=== Load dataset ===")
    records = load_concepts(
        dataset_name=args.dataset_name,
        split=args.split,
        max_rows=args.max_rows,
        local_jsonl=args.local_jsonl,
    )

    train_records, dev_records = group_split_records(records, dev_frac=args.dev_frac, seed=args.seed)
    print(f"Train concepts: {len(train_records)} | Dev concepts: {len(dev_records)}")

    train_records_with_hn = [r for r in train_records if len(r.nl_hard_negs) >= args.n_hard_negs]
    print(f"Train concepts with >= {args.n_hard_negs} NL hard negatives: {len(train_records_with_hn)}")

    if not train_records or not dev_records:
        raise RuntimeError("Train or dev split is empty. Adjust --dev_frac or --max_rows.")

    # -------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------
    nl_view_counts = [len(r.nl_views) for r in train_records]
    lean_view_counts = [len(r.lean_views) for r in train_records]
    print(f"[diag] NL views per concept   — min={min(nl_view_counts)}, "
          f"avg={np.mean(nl_view_counts):.2f}, max={max(nl_view_counts)}")
    print(f"[diag] Lean views per concept — min={min(lean_view_counts)}, "
          f"avg={np.mean(lean_view_counts):.2f}, max={max(lean_view_counts)}")
    if max(nl_view_counts) > 1:
        print(f"[diag] some concepts have >1 NL view (rephrasings present)")

    # Coverage of each named view across train concepts (useful for per-pair eval)
    print("[diag] Named-view coverage on train:")
    for name in NAMED_VIEW_FIELDS:
        n_with = sum(1 for r in train_records if name in r.views_by_name)
        pct = 100.0 * n_with / len(train_records)
        print(f"        {name:<18} {n_with:>7} / {len(train_records)} ({pct:.1f}%)")

    # -------------------------------------------------------------------
    # Load model
    # -------------------------------------------------------------------
    print("=== Load base model ===")
    model = load_st_model(args.model_name, args.device, args.max_seq_len)

    # -------------------------------------------------------------------
    # Baseline eval — both primary task AND per-pair-type suite
    # -------------------------------------------------------------------
    print("=== Baseline eval: primary (NL -> Lean signature) ===")
    base_primary = eval_retrieval(
        model=model,
        train_records=train_records,
        dev_records=dev_records,
        query_field="nl_informal",
        doc_field="lean_signature",
        instruction=args.instruction,
        wrap_q=args.wrap_query,
        wrap_d=args.wrap_doc,
        doc_prefix=args.doc_prefix,
        k=args.k_eval,
        batch_size=args.eval_batch_size,
        device=args.device,
    )
    if base_primary is None:
        raise RuntimeError("Baseline primary eval returned None — check that "
                           "concepts have nl_informal and lean_signature views.")

    print(f"Baseline Recall@1:           {base_primary['recall@1']:.4f}")
    print(f"Baseline Recall@5:           {base_primary['recall@5']:.4f}")
    print(f"Baseline Recall@{args.k_eval}: {base_primary[f'recall@{args.k_eval}']:.4f}")
    print(f"Baseline MRR@{args.k_eval}:    {base_primary[f'mrr@{args.k_eval}']:.4f}")

    base_per_pair: Dict[str, Dict] = {}
    if not args.skip_pair_type_eval:
        print("\n=== Baseline eval: per-pair-type suite ===")
        base_per_pair = eval_all_pair_types(
            model=model,
            train_records=train_records,
            dev_records=dev_records,
            instruction=args.instruction,
            reverse_instruction=args.reverse_instruction,
            wrap_q=args.wrap_query,
            wrap_d=args.wrap_doc,
            doc_prefix=args.doc_prefix,
            k=args.k_eval,
            batch_size=args.eval_batch_size,
            device=args.device,
        )

    base_pair_losses: Dict[str, Optional[float]] = {}
    if not args.skip_pair_type_loss_eval:
        print("\n=== Baseline eval: per-pair-type contrastive loss ===")
        print(f"  (batch_size={args.pair_loss_batch_size}, "
              f"n_batches={args.pair_loss_n_batches} per type)")
        base_pair_losses = eval_all_pair_type_losses(
            model=model,
            records=dev_records,
            instruction=args.instruction,
            reverse_instruction=args.reverse_instruction,
            wrap_q=args.wrap_query,
            wrap_d=args.wrap_doc,
            doc_prefix=args.doc_prefix,
            batch_size=args.pair_loss_batch_size,
            n_batches=args.pair_loss_n_batches,
            device=args.device,
            seed=args.seed,
        )

    # -------------------------------------------------------------------
    # Build per-epoch-resampling datasets (FIX #1: SimCLR-style)
    # -------------------------------------------------------------------
    print("\n=== Build multi-view datasets (per-epoch resampling) ===")

    base_dataset = MultiViewBaseDataset(
        train_records,
        instruction=args.instruction,
        reverse_instruction=args.reverse_instruction,
        wrap_q=args.wrap_query,
        wrap_d=args.wrap_doc,
        doc_prefix=args.doc_prefix,
    )
    base_loader = DataLoader(
        base_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        drop_last=True,
        num_workers=0,  # multi-worker needs worker_init_fn for proper seeding
    )
    print(f"Base dataset: {len(base_dataset)} concepts (batch_size={args.batch_size}, "
          f"~{len(base_dataset) // args.batch_size} batches/epoch)")

    hn_loader = None
    hn_dataset = None
    if train_records_with_hn:
        hn_dataset = MultiViewHNDataset(
            train_records_with_hn,
            n_hn=args.n_hard_negs,
            reverse_instruction=args.reverse_instruction,
            wrap_q=args.wrap_query,
            wrap_d=args.wrap_doc,
            doc_prefix=args.doc_prefix,
        )
        if len(hn_dataset) > 0:
            hn_loader = DataLoader(
                hn_dataset,
                batch_size=args.hard_neg_batch_size,
                shuffle=True,
                drop_last=True,
                num_workers=0,
            )
            n_batches = len(hn_dataset) // args.hard_neg_batch_size
            print(f"HN dataset: {len(hn_dataset)} concepts "
                  f"(batch_size={args.hard_neg_batch_size}, ~{n_batches} batches/epoch)")

    # -------------------------------------------------------------------
    # Loss
    # -------------------------------------------------------------------
    if args.loss == "cached":
        mnrl_loss = losses.CachedMultipleNegativesRankingLoss(model=model)
        print("=== Loss: CachedMultipleNegativesRankingLoss (GPU recommended) ===")
    else:
        mnrl_loss = losses.MultipleNegativesRankingLoss(model=model)
        print("=== Loss: MultipleNegativesRankingLoss (Mac/CPU compatible) ===")

    train_objectives = [(base_loader, mnrl_loss)]
    if hn_loader is not None:
        train_objectives.append((hn_loader, mnrl_loss))
        print(f"[training] 2 objectives: base, hard-neg")
    else:
        print(f"[training] 1 objective: base (no hard negatives in dataset)")

    # -------------------------------------------------------------------
    # LR schedule fix (FIX #2): use warmupconstant.
    # Why: in newer sentence-transformers, `steps_per_epoch` is silently
    # ignored when epochs > 1 (the lib prints "Setting steps_per_epoch
    # alongside epochs > 1 no longer works"). The default WarmupLinear
    # scheduler then computes t_total from min(loader_lengths) * epochs,
    # which is wrong with two unequal loaders — LR hits 0 mid-training.
    # warmupconstant sidesteps the bug entirely: warmup up to peak LR,
    # then hold constant. No decay, no t_total dependency.
    # -------------------------------------------------------------------
    print(f"[lr schedule] scheduler=warmupconstant, warmup_steps={args.warmup_steps}")
    print(f"[lr schedule] base_loader={len(base_loader)} batches/epoch, "
          f"hn_loader={len(hn_loader) if hn_loader is not None else 0} batches/epoch")

    t0 = time.time()
    model.fit(
        train_objectives=train_objectives,
        epochs=args.epochs,
        scheduler='warmupconstant',         # ← LR fix
        warmup_steps=args.warmup_steps,
        output_path=args.output_dir,
        show_progress_bar=True,
        checkpoint_path=args.checkpoint_dir,
        checkpoint_save_steps=args.checkpoint_save_steps,
    )
    print(f"Training time: {time.time() - t0:.1f}s")
    print(f"Saved model to: {args.output_dir}")

    # -------------------------------------------------------------------
    # Post-train eval
    # -------------------------------------------------------------------
    print("\n=== Post-train eval: primary (NL -> Lean signature) ===")
    ft_model = load_st_model(args.output_dir, args.device, args.max_seq_len)
    ft_primary = eval_retrieval(
        model=ft_model,
        train_records=train_records,
        dev_records=dev_records,
        query_field="nl_informal",
        doc_field="lean_signature",
        instruction=args.instruction,
        wrap_q=args.wrap_query,
        wrap_d=args.wrap_doc,
        doc_prefix=args.doc_prefix,
        k=args.k_eval,
        batch_size=args.eval_batch_size,
        device=args.device,
    )
    assert ft_primary is not None

    print(f"FT Recall@1:           {ft_primary['recall@1']:.4f}")
    print(f"FT Recall@5:           {ft_primary['recall@5']:.4f}")
    print(f"FT Recall@{args.k_eval}: {ft_primary[f'recall@{args.k_eval}']:.4f}")
    print(f"FT MRR@{args.k_eval}:    {ft_primary[f'mrr@{args.k_eval}']:.4f}")

    print()
    print("=== Delta on primary task (FT - Baseline) ===")
    for ki in sorted({1, 5, args.k_eval}):
        d = ft_primary[f"recall@{ki}"] - base_primary[f"recall@{ki}"]
        sign = "+" if d >= 0 else ""
        print(f"  Recall@{ki}: {sign}{d:.4f}")
    d_mrr = ft_primary[f"mrr@{args.k_eval}"] - base_primary[f"mrr@{args.k_eval}"]
    sign = "+" if d_mrr >= 0 else ""
    print(f"  MRR@{args.k_eval}: {sign}{d_mrr:.4f}")

    ft_per_pair: Dict[str, Dict] = {}
    if not args.skip_pair_type_eval:
        print("\n=== Post-train eval: per-pair-type suite ===")
        ft_per_pair = eval_all_pair_types(
            model=ft_model,
            train_records=train_records,
            dev_records=dev_records,
            instruction=args.instruction,
            reverse_instruction=args.reverse_instruction,
            wrap_q=args.wrap_query,
            wrap_d=args.wrap_doc,
            doc_prefix=args.doc_prefix,
            k=args.k_eval,
            batch_size=args.eval_batch_size,
            device=args.device,
        )
        print_pair_type_comparison(base_per_pair, ft_per_pair, args.k_eval)

    ft_pair_losses: Dict[str, Optional[float]] = {}
    if not args.skip_pair_type_loss_eval:
        print("\n=== Post-train eval: per-pair-type contrastive loss ===")
        print(f"  (batch_size={args.pair_loss_batch_size}, "
              f"n_batches={args.pair_loss_n_batches} per type)")
        ft_pair_losses = eval_all_pair_type_losses(
            model=ft_model,
            records=dev_records,
            instruction=args.instruction,
            reverse_instruction=args.reverse_instruction,
            wrap_q=args.wrap_query,
            wrap_d=args.wrap_doc,
            doc_prefix=args.doc_prefix,
            batch_size=args.pair_loss_batch_size,
            n_batches=args.pair_loss_n_batches,
            device=args.device,
            seed=args.seed,
        )
        print_pair_type_loss_comparison(base_pair_losses, ft_pair_losses)

    # -------------------------------------------------------------------
    # Write metrics
    # -------------------------------------------------------------------
    metrics_path = os.path.join(args.output_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "baseline": {"k": args.k_eval, **base_primary},
                "finetuned": {"k": args.k_eval, **ft_primary},
                "baseline_per_pair_type": base_per_pair,
                "finetuned_per_pair_type": ft_per_pair,
                "baseline_per_pair_type_loss": base_pair_losses,
                "finetuned_per_pair_type_loss": ft_pair_losses,
                "config": vars(args),
                "counts": {
                    "concepts_total": len(records),
                    "train": len(train_records),
                    "dev": len(dev_records),
                    "train_with_hn": len(train_records_with_hn),
                    "base_dataset_size": len(base_dataset),
                    "hn_dataset_size": len(hn_dataset) if hn_dataset is not None else 0,
                },
                "view_stats": {
                    "nl_views_per_concept_avg": float(np.mean(nl_view_counts)),
                    "nl_views_per_concept_max": int(max(nl_view_counts)),
                    "lean_views_per_concept_avg": float(np.mean(lean_view_counts)),
                    "named_view_coverage_train": {
                        name: sum(1 for r in train_records if name in r.views_by_name)
                        for name in NAMED_VIEW_FIELDS
                    },
                },
                "lr_schedule": {
                    "scheduler": "warmupconstant",
                    "warmup_steps": args.warmup_steps,
                    "base_loader_batches_per_epoch": len(base_loader),
                    "hn_loader_batches_per_epoch": len(hn_loader) if hn_loader is not None else 0,
                },
                "method": "Multi-view contrastive (SimCLR-style stochastic pairing, per-epoch resampling) + reverse-direction NL hard negatives",
                "faiss_available": _HAVE_FAISS,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
    print(f"\nWrote metrics: {metrics_path}")


if __name__ == "__main__":
    main()
