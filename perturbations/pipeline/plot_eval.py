"""Draw the diagrams for a perturbation + MTEB run.

Reads a run directory written by ``scripts/tillicum_blueprint.slurm`` (or by
``run_benchmark_review.py`` and ``mteb_perturbation_eval.py`` by hand) and
writes PNGs plus ``summary.md`` to ``<run>/figures/``::

    python pipeline/plot_eval.py --run data/blueprint-review

Figures (each is skipped if its inputs are missing):

* ``funnel.png`` — declarations → anchors → elaborating → with variants → MTEB queries
* ``perturbation_outcomes.png`` — what happened to each perturbation across anchors
* ``mteb_scores.png`` — nDCG@10 / MAP / MRR / P@1 per model
* ``pairwise_by_negative.png`` — how often an equivalent rewrite beats each kind of negative
* ``cosine_by_class.png`` — anchor–variant cosine distribution per semantic class
* ``cosine_by_perturbation.png`` — mean anchor–variant cosine per perturbation, per model
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CLASS_COLORS = {
    "equivalent": "#2a9d8f",
    "entailed": "#e9c46a",
    "graded": "#f4a261",
    "contradictory": "#e76f51",
}
STATUS_COLORS = {
    "applied": "#2a9d8f",
    "not_applicable": "#bdbdbd",
    "lean_rejected": "#e76f51",
    "tactic_failed": "#f4a261",
    "noop": "#8ab6d6",
    "needs_lean": "#9e9e9e",
    "error": "#6d0000",
}
METRICS = [("ndcg_at_10", "nDCG@10"), ("map_at_1000", "MAP"),
           ("mrr_at_10", "MRR@10"), ("precision_at_1", "P@1")]


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _short(model: str) -> str:
    return model.split("/")[-1]


def load_models(mteb_dir: Path) -> list[dict[str, Any]]:
    """One entry per evaluated model: its name, scores and diagnostic tables."""
    models = []
    for scores_path in sorted(mteb_dir.glob("*/mteb_scores.json")):
        d = scores_path.parent
        blob = json.loads(scores_path.read_text())
        models.append({
            "name": blob["model"],
            "device": blob.get("device", "?"),
            "scores": blob["scores"]["test"][0],
            "cosines": _csv(d / "variant_cosines.csv"),
            "by_perturbation": _csv(d / "similarity_by_perturbation.csv"),
            "pairwise": _csv(d / "pairwise_by_negative.csv"),
        })
    return models


def plot_funnel(run: Path, anchors: list[dict], results: list[dict],
                task_stats: dict, figs: Path) -> list[tuple[str, int]] | None:
    stats_files = list(run.glob("*.stats.json"))
    prep = json.loads(stats_files[0].read_text()) if stats_files else {}
    stages = []
    if prep:
        stages.append(("scraped declarations", prep.get("declarations", 0)))
        stages.append(("unique theorem / lemma", prep.get("anchors", 0)))
    if anchors:
        stages.append(("processed", len(anchors)))
        stages.append(("elaborate vs Mathlib", sum(1 for a in anchors if not a.get("skipped"))))
    if results:
        stages.append(("≥1 variant produced",
                       len({r["source_id"] for r in results if r["status"] == "applied"})))
    if task_stats:
        stages.append(("MTEB queries (≥1 pos & neg)", task_stats.get("queries", 0)))
    if len(stages) < 2:
        return None

    fig, ax = plt.subplots(figsize=(8, 0.6 * len(stages) + 1))
    labels = [s for s, _ in stages][::-1]
    values = [v for _, v in stages][::-1]
    bars = ax.barh(labels, values, color="#457b9d")
    for b, v in zip(bars, values):
        ax.text(b.get_width(), b.get_y() + b.get_height() / 2, f" {v:,}",
                va="center", fontsize=9)
    ax.set_xlabel("count")
    ax.set_title("Blueprint corpus → perturbation benchmark")
    ax.set_xlim(0, max(values) * 1.15)
    fig.tight_layout()
    fig.savefig(figs / "funnel.png", dpi=150)
    plt.close(fig)
    return stages


def plot_outcomes(results: list[dict], figs: Path) -> None:
    from wiggle.registry import SEMANTIC_CLASSES

    if not results:
        return
    counts: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        counts[r["perturbation"]][r["status"]] += 1
    perts = sorted(counts, key=lambda p: counts[p]["applied"] / max(1, sum(counts[p].values())))
    statuses = [s for s in STATUS_COLORS if any(counts[p][s] for p in perts)]

    fig, ax = plt.subplots(figsize=(9, 0.32 * len(perts) + 1.5))
    left = [0.0] * len(perts)
    for s in statuses:
        frac = [counts[p][s] / sum(counts[p].values()) for p in perts]
        ax.barh(perts, frac, left=left, color=STATUS_COLORS[s], label=s.replace("_", " "))
        left = [a + b for a, b in zip(left, frac)]
    for tick, p in zip(ax.get_yticklabels(), perts):
        tick.set_color(CLASS_COLORS.get(SEMANTIC_CLASSES.get(p, "graded"), "black"))
    n_anchors = len({r["source_id"] for r in results})
    ax.set_xlabel(f"fraction of {n_anchors:,} elaborating anchors")
    ax.set_xlim(0, 1)
    ax.set_title("Perturbation outcomes (label colour = semantic class)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.04), ncol=len(statuses),
              fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(figs / "perturbation_outcomes.png", dpi=150)
    plt.close(fig)


def plot_scores(models: list[dict], figs: Path) -> None:
    if not models:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.8 / len(models)
    for i, m in enumerate(models):
        xs = [j + i * width for j in range(len(METRICS))]
        vals = [m["scores"].get(k, 0.0) for k, _ in METRICS]
        bars = ax.bar(xs, vals, width, label=_short(m["name"]))
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.3f}", ha="center",
                    va="bottom", fontsize=8)
    ax.set_xticks([j + width * (len(models) - 1) / 2 for j in range(len(METRICS))])
    ax.set_xticklabels([label for _, label in METRICS])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    ax.set_title("MTEB reranking: equivalent rewrites vs hard negatives")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(figs / "mteb_scores.png", dpi=150)
    plt.close(fig)


def plot_pairwise(models: list[dict], figs: Path) -> None:
    models = [m for m in models if m["pairwise"]]
    if not models:
        return
    classes = [c for c in ("contradictory", "graded", "entailed", "all")
               if any(p["negative_class"] == c for m in models for p in m["pairwise"])]
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.8 / len(models)
    for i, m in enumerate(models):
        table = {p["negative_class"]: float(p["equivalent_ranked_higher"]) for p in m["pairwise"]}
        xs = [j + i * width for j in range(len(classes))]
        vals = [table.get(c, 0.0) for c in classes]
        bars = ax.bar(xs, vals, width, label=_short(m["name"]))
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center",
                    va="bottom", fontsize=8)
    ax.axhline(0.5, color="grey", linestyle="--", linewidth=1)
    ax.text(len(classes) - 0.5, 0.51, "chance", color="grey", fontsize=8, ha="right")
    ax.set_xticks([j + width * (len(models) - 1) / 2 for j in range(len(classes))])
    ax.set_xticklabels([f"vs {c}" for c in classes])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("P(equivalent rewrite closer to anchor)")
    ax.set_title("Does the embedding prefer the same theorem over a near miss?")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(figs / "pairwise_by_negative.png", dpi=150)
    plt.close(fig)


def plot_cosine_by_class(models: list[dict], figs: Path) -> None:
    models = [m for m in models if m["cosines"]]
    if not models:
        return
    classes = list(CLASS_COLORS)
    fig, axes = plt.subplots(1, len(models), figsize=(4.5 * len(models), 4), squeeze=False)
    for ax, m in zip(axes[0], models):
        data = [[float(r["cosine"]) for r in m["cosines"] if r["class"] == c] for c in classes]
        keep = [i for i, d in enumerate(data) if d]
        bp = ax.boxplot([data[i] for i in keep], patch_artist=True, showfliers=False)
        for patch, i in zip(bp["boxes"], keep):
            patch.set_facecolor(CLASS_COLORS[classes[i]])
        ax.set_xticks(range(1, len(keep) + 1))
        ax.set_xticklabels([classes[i] for i in keep], rotation=20)
        ax.set_title(_short(m["name"]))
        ax.set_ylabel("cosine(anchor, variant)")
    fig.suptitle("Ideally equivalent ≈ 1 and the others clearly lower")
    fig.tight_layout()
    fig.savefig(figs / "cosine_by_class.png", dpi=150)
    plt.close(fig)


def plot_cosine_by_perturbation(models: list[dict], figs: Path) -> None:
    models = [m for m in models if m["by_perturbation"]]
    if not models:
        return
    n = max(len(m["by_perturbation"]) for m in models)
    fig, axes = plt.subplots(1, len(models), figsize=(5.5 * len(models), 0.3 * n + 1.5),
                             squeeze=False)
    for ax, m in zip(axes[0], models):
        rows = sorted(m["by_perturbation"], key=lambda r: float(r["mean_cosine"]))
        ax.barh([r["perturbation"] for r in rows], [float(r["mean_cosine"]) for r in rows],
                color=[CLASS_COLORS.get(r["class"], "grey") for r in rows])
        lo = min(float(r["mean_cosine"]) for r in rows)
        ax.set_xlim(max(0.0, lo - 0.05), 1.0)
        ax.set_xlabel("mean cosine(anchor, variant)")
        ax.set_title(_short(m["name"]))
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in CLASS_COLORS.values()]
    fig.legend(handles, list(CLASS_COLORS), loc="lower center", ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(figs / "cosine_by_perturbation.png", dpi=150)
    plt.close(fig)


def write_summary(figs: Path, stages, models: list[dict], task_stats: dict) -> None:
    lines = ["# Perturbation embedding eval", ""]
    if stages:
        lines += ["## Data", "", "| stage | count |", "|---|---|"]
        lines += [f"| {s} | {v:,} |" for s, v in stages]
        lines.append("")
    if task_stats:
        lines.append(f"MTEB task: {task_stats.get('queries', 0):,} queries, "
                     f"{task_stats.get('positives', 0):,} equivalent rewrites, "
                     f"{task_stats.get('negatives', 0):,} hard negatives.")
        lines.append("")
    if models:
        lines += ["## Scores", "",
                  "| model | " + " | ".join(label for _, label in METRICS)
                  + " | equiv > negative |",
                  "|---|" + "---|" * (len(METRICS) + 1)]
        for m in models:
            overall = next((p["equivalent_ranked_higher"] for p in m["pairwise"]
                            if p["negative_class"] == "all"), "–")
            lines.append(f"| {m['name']} | "
                         + " | ".join(f"{m['scores'].get(k, 0):.4f}" for k, _ in METRICS)
                         + f" | {overall} |")
        lines.append("")
    lines.append("## Figures")
    lines.append("")
    for png in sorted(figs.glob("*.png")):
        lines.append(f"![{png.stem}]({png.name})")
        lines.append("")
    (figs / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--mteb-dir", type=Path, help="default <run>/mteb")
    args = ap.parse_args()

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    mteb_dir = args.mteb_dir or args.run / "mteb"
    figs = args.run / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    anchors = _jsonl(args.run / "anchors.jsonl")
    results = _jsonl(args.run / "results.jsonl")
    task_stats_path = mteb_dir / "task_stats.json"
    task_stats = json.loads(task_stats_path.read_text()) if task_stats_path.exists() else {}
    models = load_models(mteb_dir)

    stages = plot_funnel(args.run, anchors, results, task_stats, figs)
    plot_outcomes(results, figs)
    plot_scores(models, figs)
    plot_pairwise(models, figs)
    plot_cosine_by_class(models, figs)
    plot_cosine_by_perturbation(models, figs)
    write_summary(figs, stages, models, task_stats)
    print(f"wrote {figs}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
