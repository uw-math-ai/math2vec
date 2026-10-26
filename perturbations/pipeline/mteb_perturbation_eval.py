"""Score embedding models on perturbation results as an MTEB reranking task.

Each anchor whose perturbations produced both kinds of variant becomes one
query. Its candidate list is that anchor's own applied variants: the
``equivalent`` ones (contrapose, alpha_rename, curry, …; see
``wiggle.registry.SEMANTIC_CLASSES``) are relevant, and every other class
(graded, entailed, contradictory) is a hard negative — a near-identical string
that states a different theorem. A model that understands the mathematics
should rank the rewrites of the *same* statement above them.

Usage::

    python pipeline/mteb_perturbation_eval.py \\
        --results data/blueprint-review/results.jsonl \\
        --out data/blueprint-review/mteb \\
        --models Qwen/Qwen3-Embedding-8B sentence-transformers/all-MiniLM-L6-v2

Writes ``<out>/task_stats.json`` and, per model, ``<out>/<model>/``:

* ``mteb_scores.json`` — nDCG@10, MAP, MRR, … as computed by ``mteb``
* ``variant_cosines.csv`` — cosine(anchor, variant) for every applied variant
* ``similarity_by_perturbation.csv`` — the same, averaged per perturbation
* ``pairwise_by_negative.csv`` — how often an equivalent rewrite scores above
  a hard negative, split by the negative's semantic class

A model that fails (e.g. out of memory) is recorded in ``<out>/errors.json``
and the rest still run.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wiggle.registry import SEMANTIC_CLASSES  # noqa: E402

DEFAULT_MODELS = ["Qwen/Qwen3-Embedding-8B", "sentence-transformers/all-MiniLM-L6-v2"]
TASK_NAME = "WigglePerturbationReranking"
QUERY_INSTRUCTION = (
    "Given a Lean 4 theorem statement, retrieve statements that are "
    "mathematically equivalent to it"
)
REPORTED_SCORES = ("ndcg_at_10", "map_at_1000", "mrr_at_10", "precision_at_1")


def model_slug(name: str) -> str:
    return name.replace("/", "__")


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def build_rerank_data(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Group applied variants by anchor into queries, corpus, qrels and candidates.

    A variant text that appears under both an equivalent and a non-equivalent
    perturbation of the same anchor is dropped: its label would be
    contradictory. Variants identical to their anchor are dropped too.
    """
    by_anchor: dict[str, dict[str, Any]] = {}
    for r in rows:
        if r.get("status") != "applied" or not r.get("variant"):
            continue
        a = by_anchor.setdefault(
            r["source_id"], {"text": r["original_type_str"], "variants": defaultdict(list)}
        )
        a["variants"][" ".join(r["variant"].split())].append(r["perturbation"])

    queries: dict[str, str] = {}
    corpus: dict[str, str] = {}
    relevant_docs: dict[str, dict[str, int]] = {}
    top_ranked: dict[str, list[str]] = {}
    doc_info: dict[str, dict[str, str]] = {}
    stats = {"anchors_with_variants": len(by_anchor), "ambiguous_variants": 0,
             "skipped_no_positive": 0, "skipped_no_negative": 0}

    for qid, a in by_anchor.items():
        anchor_norm = " ".join(a["text"].split())
        labelled: list[tuple[str, str, int]] = []
        for text, perts in a["variants"].items():
            if text == anchor_norm:
                continue
            classes = {SEMANTIC_CLASSES.get(p, "graded") for p in perts}
            is_pos = classes == {"equivalent"}
            if "equivalent" in classes and not is_pos:
                stats["ambiguous_variants"] += 1
                continue
            labelled.append((text, perts[0], int(is_pos)))
        if not any(lab for _, _, lab in labelled):
            stats["skipped_no_positive"] += 1
            continue
        if all(lab for _, _, lab in labelled):
            stats["skipped_no_negative"] += 1
            continue

        queries[qid] = a["text"]
        relevant_docs[qid] = {}
        top_ranked[qid] = []
        for text, pert, lab in labelled:
            did = f"{qid}::{pert}"
            corpus[did] = text
            relevant_docs[qid][did] = lab
            top_ranked[qid].append(did)
            doc_info[did] = {"perturbation": pert, "class": SEMANTIC_CLASSES.get(pert, "graded")}

    stats["queries"] = len(queries)
    stats["documents"] = len(corpus)
    stats["positives"] = sum(v for q in relevant_docs.values() for v in q.values())
    stats["negatives"] = stats["documents"] - stats["positives"]
    return {"queries": queries, "corpus": corpus, "relevant_docs": relevant_docs,
            "top_ranked": top_ranked, "doc_info": doc_info, "stats": stats}


def make_task(data: dict[str, Any]):
    from datasets import Dataset
    from mteb.abstasks.retrieval import AbsTaskRetrieval
    from mteb.abstasks.task_metadata import TaskMetadata

    class WigglePerturbationReranking(AbsTaskRetrieval):
        metadata = TaskMetadata(
            name=TASK_NAME,
            description="For each Lean theorem statement, rank its "
            "meaning-preserving rewrites above meaning-changing hard negatives "
            "produced by the Wiggle perturbation pipeline.",
            reference="https://github.com/PatrickMassot/leanblueprint",
            dataset={"path": "local/wiggle-perturbations", "revision": "local"},
            type="Reranking",
            category="t2t",
            modalities=["text"],
            eval_splits=["test"],
            eval_langs=["eng-Latn"],
            main_score="ndcg_at_10",
            date=("2026-01-01", "2026-12-31"),
            domains=["Academic"],
            task_subtypes=[],
            license="not specified",
            annotations_creators="derived",
            dialect=[],
            sample_creation="created",
            bibtex_citation="",
            prompt={"query": QUERY_INSTRUCTION},
        )

        def load_data(self, num_proc: int | None = None, **kwargs: Any) -> None:
            self.dataset = {"default": {"test": {
                "queries": Dataset.from_list(
                    [{"id": k, "text": v} for k, v in data["queries"].items()]),
                "corpus": Dataset.from_list(
                    [{"id": k, "text": v, "title": ""} for k, v in data["corpus"].items()]),
                "relevant_docs": data["relevant_docs"],
                "top_ranked": data["top_ranked"],
            }}}
            self.data_loaded = True

    return WigglePerturbationReranking()


def load_model(name: str):
    """``mteb`` model for ``name``; models over 1B parameters load in bf16 on GPU."""
    import mteb
    import torch

    kwargs: dict[str, Any] = {}
    meta = mteb.get_model_meta(name)
    if torch.cuda.is_available() and (meta.n_parameters or 0) > 1_000_000_000:
        kwargs["model_kwargs"] = {"dtype": torch.bfloat16}
    return mteb.get_model(name, **kwargs)


def sentence_transformer_of(model: Any, name: str):
    """The SentenceTransformer inside an ``mteb`` wrapper, or a fresh one."""
    from sentence_transformers import SentenceTransformer

    inner = getattr(model, "model", None)
    if isinstance(inner, SentenceTransformer):
        return inner
    return SentenceTransformer(name)


def variant_cosines(rows: list[dict[str, Any]], st_model: Any, batch_size: int) -> list[dict[str, Any]]:
    """cosine(anchor, variant) for every applied variant, no instruction prompt."""
    import numpy as np

    pairs = [r for r in rows if r.get("status") == "applied" and r.get("variant")]
    if not pairs:
        return []
    texts = sorted({t for r in pairs for t in (r["original_type_str"], r["variant"])})
    index = {t: i for i, t in enumerate(texts)}
    emb = st_model.encode(texts, batch_size=batch_size, normalize_embeddings=True,
                          show_progress_bar=False, convert_to_numpy=True)
    emb = np.asarray(emb, dtype=np.float32)
    return [
        {"source_id": r["source_id"], "perturbation": r["perturbation"],
         "class": SEMANTIC_CLASSES.get(r["perturbation"], "graded"),
         "cosine": round(float(np.dot(emb[index[r["original_type_str"]]],
                                      emb[index[r["variant"]]])), 5)}
        for r in pairs
    ]


def summarize_by_perturbation(cos_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by: dict[str, list[float]] = defaultdict(list)
    for r in cos_rows:
        by[r["perturbation"]].append(r["cosine"])
    return sorted(
        ({"perturbation": p, "class": SEMANTIC_CLASSES.get(p, "graded"), "n": len(s),
          "mean_cosine": round(sum(s) / len(s), 4), "min_cosine": round(min(s), 4)}
         for p, s in by.items()),
        key=lambda d: d["mean_cosine"],
    )


def pairwise_by_negative(cos_rows: list[dict[str, Any]], data: dict[str, Any]) -> list[dict[str, Any]]:
    """Fraction of (equivalent, hard negative) pairs where the equivalent is closer.

    Only pairs within the same MTEB query count, split by the negative's class.
    Ties count half.
    """
    cos = {(r["source_id"], r["perturbation"]): r["cosine"] for r in cos_rows}
    wins: dict[str, float] = defaultdict(float)
    total: dict[str, int] = defaultdict(int)
    for qid, qrels in data["relevant_docs"].items():
        pos = [cos.get((qid, d.split("::", 1)[1])) for d, lab in qrels.items() if lab]
        for did, lab in qrels.items():
            if lab:
                continue
            neg = cos.get((qid, did.split("::", 1)[1]))
            cls = data["doc_info"][did]["class"]
            for p in pos:
                if p is None or neg is None:
                    continue
                total[cls] += 1
                wins[cls] += 1.0 if p > neg else 0.5 if p == neg else 0.0
    out = [{"negative_class": c, "pairs": total[c],
            "equivalent_ranked_higher": round(wins[c] / total[c], 4)} for c in sorted(total)]
    all_pairs = sum(total.values())
    if all_pairs:
        out.append({"negative_class": "all", "pairs": all_pairs,
                    "equivalent_ranked_higher": round(sum(wins.values()) / all_pairs, 4)})
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        if rows:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


def evaluate_model(name: str, rows: list[dict[str, Any]], data: dict[str, Any],
                   out: Path, batch_size: int) -> None:
    import mteb
    import torch

    out.mkdir(parents=True, exist_ok=True)
    device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    print(f"\n── {name} on {device}", flush=True)

    model = load_model(name)
    result = mteb.evaluate(
        model, make_task(data), cache=None,
        encode_kwargs={"batch_size": batch_size}, show_progress_bar=False,
    )
    scores = result.task_results[0].scores
    (out / "mteb_scores.json").write_text(json.dumps(
        {"model": name, "task": TASK_NAME, "device": device, "scores": scores},
        indent=2, default=str) + "\n")
    test = scores["test"][0]
    print("   " + ", ".join(f"{k}={test[k]:.4f}" for k in REPORTED_SCORES if k in test),
          flush=True)

    cos_rows = variant_cosines(rows, sentence_transformer_of(model, name), batch_size)
    write_csv(out / "variant_cosines.csv", cos_rows)
    write_csv(out / "similarity_by_perturbation.csv", summarize_by_perturbation(cos_rows))
    pairwise = pairwise_by_negative(cos_rows, data)
    write_csv(out / "pairwise_by_negative.csv", pairwise)
    for p in pairwise:
        print(f"   equivalent > {p['negative_class']}: {p['equivalent_ranked_higher']:.3f} "
              f"({p['pairs']} pairs)", flush=True)

    del model
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, required=True,
                    help="results.jsonl from run_benchmark_review.py")
    ap.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=64)
    args = ap.parse_args()

    rows = load_rows(args.results)
    data = build_rerank_data(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "task_stats.json").write_text(json.dumps(data["stats"], indent=2) + "\n")
    print(json.dumps(data["stats"]), flush=True)
    if not data["queries"]:
        print("No anchor has both an equivalent and a non-equivalent variant.", file=sys.stderr)
        return 1

    errors = {}
    for name in args.models:
        try:
            evaluate_model(name, rows, data, args.out / model_slug(name), args.batch_size)
        except Exception:  # one bad model shouldn't cost the others
            errors[name] = traceback.format_exc()
            print(f"   FAILED:\n{errors[name]}", file=sys.stderr, flush=True)
    (args.out / "errors.json").write_text(json.dumps(errors, indent=2) + "\n")
    print(f"\nwrote {args.out}", flush=True)
    return 1 if len(errors) == len(args.models) else 0


if __name__ == "__main__":
    sys.exit(main())
