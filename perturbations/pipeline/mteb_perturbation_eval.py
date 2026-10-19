"""Score an embedding model on perturbation results as an MTEB reranking task.

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
        --out data/blueprint-review/mteb

Writes ``<out>/mteb_scores.json`` (nDCG@10, MAP, MRR, … as computed by
``mteb``), ``<out>/similarity_by_perturbation.csv`` (mean anchor–variant cosine
per perturbation) and ``<out>/task_stats.json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wiggle.registry import SEMANTIC_CLASSES  # noqa: E402

DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TASK_NAME = "WigglePerturbationReranking"


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


def similarity_table(rows: list[dict[str, Any]], model_name: str) -> list[dict[str, Any]]:
    """Mean cosine(anchor, variant) per perturbation over all applied variants."""
    import numpy as np
    from sentence_transformers import SentenceTransformer

    pairs = [(r["original_type_str"], r["variant"], r["perturbation"])
             for r in rows if r.get("status") == "applied" and r.get("variant")]
    if not pairs:
        return []
    model = SentenceTransformer(model_name)
    texts = sorted({t for a, v, _ in pairs for t in (a, v)})
    index = {t: i for i, t in enumerate(texts)}
    emb = model.encode(texts, batch_size=256, normalize_embeddings=True,
                       show_progress_bar=False)
    sims = defaultdict(list)
    for a, v, p in pairs:
        sims[p].append(float(np.dot(emb[index[a]], emb[index[v]])))
    return sorted(
        ({"perturbation": p, "class": SEMANTIC_CLASSES.get(p, "graded"), "n": len(s),
          "mean_cosine": round(sum(s) / len(s), 4), "min_cosine": round(min(s), 4)}
         for p, s in sims.items()),
        key=lambda d: d["mean_cosine"],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--results", type=Path, required=True,
                    help="results.jsonl from run_benchmark_review.py")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--batch-size", type=int, default=128)
    args = ap.parse_args()

    import mteb

    rows = load_rows(args.results)
    data = build_rerank_data(rows)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "task_stats.json").write_text(json.dumps(data["stats"], indent=2) + "\n")
    print(json.dumps(data["stats"]), flush=True)
    if not data["queries"]:
        print("No anchor has both an equivalent and a non-equivalent variant.", file=sys.stderr)
        return 1

    result = mteb.evaluate(
        mteb.get_model(args.model),
        make_task(data),
        cache=None,
        encode_kwargs={"batch_size": args.batch_size},
        show_progress_bar=False,
    )
    scores = result.task_results[0].scores
    (args.out / "mteb_scores.json").write_text(
        json.dumps({"model": args.model, "task": TASK_NAME, "scores": scores},
                   indent=2, default=str) + "\n"
    )
    test = scores["test"][0]
    print(f"{args.model}: " + ", ".join(
        f"{k}={test[k]:.4f}" for k in ("ndcg_at_10", "map_at_1000", "mrr_at_10")
        if k in test), flush=True)

    table = similarity_table(rows, args.model)
    with open(args.out / "similarity_by_perturbation.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["perturbation", "class", "n", "mean_cosine", "min_cosine"])
        w.writeheader()
        w.writerows(table)
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
