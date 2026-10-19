#!/usr/bin/env python
"""Where do perturbed statements sit relative to their anchor?

Loads a perturbation run, embeds every anchor and variant with purely lexical
representations (see :mod:`wiggle.lexical`), and reports the geometry:

  * **Collapse** — how far a variant sits from its anchor, rescaled so that
    ``0`` is "as far as an unrelated theorem" and ``1`` is "the same point".
    The expectation going in is that most variants collapse: they are near-
    copies of the anchor in surface form no matter what they do logically.

  * **Retrieval** — given a variant, does the nearest anchor turn out to be
    its own? If yes, a lexical retriever cannot be hurt by the perturbation;
    if no, the perturbation moved the statement out of its own neighbourhood.

  * **Inversion** — the decisive test for the word-matching hypothesis. Within
    one anchor, take every (logically-equivalent variant, logically-different
    variant) pair and ask which one is lexically *closer* to the anchor. A
    model that scores by surface overlap is right by construction when the
    equivalent one wins and wrong when the other does. An inversion rate above
    50% means surface similarity is worse than a coin flip at recovering
    logical similarity, and that is exactly the signal an embedder has to
    learn instead of memorise.

Usage::

    python pipeline/analyze_geometry.py --run data/benchmark-review
    python pipeline/analyze_geometry.py --run data/deep-chains --cloud-anchor bench_000
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from itertools import combinations, product
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from wiggle.lexical import (  # noqa: E402
    SIMILARITY_VIEWS,
    lean_tokens,
    pairwise_view,
    summarise,
    tfidf_cosine_matrix,
)
from wiggle.registry import SEMANTIC_CLASSES, SEMANTIC_DISTANCE  # noqa: E402

# The view every headline number is quoted in. Token TF-IDF is the closest
# cheap stand-in for what a lexical retriever actually scores; the other three
# are reported alongside so a conclusion that depends on the choice is visible.
PRIMARY_VIEW = "tfidf_token"

CLASS_COLOURS = {
    "equivalent": "#2a9d8f",
    "entailed": "#e9c46a",
    "graded": "#f4a261",
    "contradictory": "#e63946",
}


# ── Loading ───────────────────────────────────────────────────────────────────


def load_variants(run_dir: Path) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Read a run directory into ``(anchors_by_id, variant_records)``.

    Handles both on-disk formats:

      * ``results.jsonl`` from ``run_benchmark_review.py`` — one row per
        (anchor, perturbation) attempt, most of which produced nothing;
      * ``nodes.jsonl`` from ``run_deep_chains.py`` — one row per surviving
        node of a perturbation tree, which carries a whole path rather than a
        single perturbation name.
    """
    for filename in ("nodes.jsonl", "results.jsonl"):
        path = run_dir / filename
        if path.exists():
            break
    else:
        raise SystemExit(f"no nodes.jsonl or results.jsonl under {run_dir}")

    anchors: dict[str, str] = {}
    variants: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        anchor_id = rec["source_id"]
        anchors.setdefault(anchor_id, rec["original_type_str"])

        statement = rec.get("variant") or rec.get("statement")
        if not statement:
            continue
        if rec.get("status") not in (None, "applied", "ok"):
            continue

        # A deep-chain run stores its root node too; that is the anchor itself,
        # not a variant, and it carries an empty path.
        if "path" in rec and not rec["path"]:
            continue
        path_steps = rec.get("path") or [rec["perturbation"]]
        variants.append(
            {
                "anchor_id": anchor_id,
                "declaration": rec.get("declaration", anchor_id),
                "statement": statement,
                "path": path_steps,
                "node_id": rec.get("node_id"),
                "parent_id": rec.get("parent_id"),
                # A chain is only as equivalence-preserving as its least
                # equivalence-preserving step, so the whole path is labelled by
                # the step that moves the meaning furthest.
                "last": path_steps[-1],
                "depth": rec.get("depth", len(path_steps)),
                "semantic_class": max(
                    (SEMANTIC_CLASSES.get(p, "graded") for p in path_steps),
                    key=lambda c: SEMANTIC_DISTANCE[c],
                ),
            }
        )

    if not variants:
        raise SystemExit(f"no usable variants in {path}")

    # Attributing a chain's whole drift to its last step inflates that step's
    # surface change by everything its ancestors already did. Recording where
    # each node came from lets the per-perturbation table measure one step at a
    # time. ``parent_pos`` of None means "the parent is the anchor".
    position = {v["node_id"]: i for i, v in enumerate(variants)
                if v["node_id"] is not None}
    for v in variants:
        v["parent_pos"] = position.get(v["parent_id"])

    return anchors, variants


def load_background_anchors(run_dir: Path) -> dict[str, str]:
    """Anchor statements from another run, used purely as a distance scale.

    A deep run usually targets a single theorem, which leaves nothing to
    measure "as far away as an unrelated theorem" against. Borrowing the
    anchors of the depth-1 review restores that scale without pretending they
    have variants of their own.
    """
    for filename in ("results.jsonl", "nodes.jsonl"):
        path = run_dir / filename
        if path.exists():
            break
    else:
        return {}

    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        out.setdefault(rec["source_id"], rec["original_type_str"])
    return out


# ── Similarity ────────────────────────────────────────────────────────────────


def similarity_matrices(
    statements: list[str], *, max_pairwise: int
) -> dict[str, np.ndarray]:
    """Similarity matrices over one shared corpus, keyed by view.

    All views live on the same index space so downstream code can treat them
    interchangeably. The two TF-IDF views come out of one vectorised call each
    and are cheap at any size. The two pairwise views are filled in with a
    Python loop over every pair, which is fine for a depth-1 review (tens of
    statements) and hopeless for a deep tree (hundreds) — above
    ``max_pairwise`` they are skipped, and the caller reports on whichever
    views came back.
    """
    n = len(statements)
    mats = {
        "tfidf_token": tfidf_cosine_matrix(statements, analyzer="token"),
        "tfidf_char": tfidf_cosine_matrix(statements, analyzer="char"),
    }
    if n > max_pairwise:
        return mats
    for view in ("jaccard", "sequence"):
        m = np.eye(n)
        for i, j in combinations(range(n), 2):
            m[i, j] = m[j, i] = pairwise_view(view, statements[i], statements[j])
        mats[view] = m
    return mats


def collapse(sim: float, background: float) -> float:
    """Rescale a raw similarity so 0 = unrelated theorem, 1 = same point."""
    if background >= 1.0:
        return 1.0
    return (sim - background) / (1.0 - background)


# ── Report ────────────────────────────────────────────────────────────────────


def fmt(x: float) -> str:
    return "—" if np.isnan(x) else f"{x:.3f}"


def mean_collapse_by_perturbation(
    variants: list[dict[str, Any]],
    mats: dict[str, np.ndarray],
    anchor_idx: dict[str, int],
    variant_idx: list[int],
    background: float,
    view: str = PRIMARY_VIEW,
) -> dict[str, float]:
    """Mean collapse per perturbation, measuring **one step** at a time.

    Each variant is compared against the statement the perturbation was
    actually applied to — its parent in the chain — not against the anchor.
    At depth 1 the two coincide; deeper, comparing to the anchor would charge
    the last step for all the drift its ancestors caused.
    """
    m = mats[view]
    by_pert: dict[str, list[int]] = defaultdict(list)
    for k, v in enumerate(variants):
        by_pert[v["last"]].append(k)

    def reference(k: int) -> int:
        parent = variants[k]["parent_pos"]
        if parent is None:
            return anchor_idx[variants[k]["anchor_id"]]
        return variant_idx[parent]

    return {
        pert: float(np.mean([
            collapse(m[variant_idx[k], reference(k)], background)
            for k in idxs
        ]))
        for pert, idxs in by_pert.items()
    }


def perturbation_rows(
    variants: list[dict[str, Any]],
    mats: dict[str, np.ndarray],
    anchor_idx: dict[str, int],
    variant_idx: list[int],
    background: float,
) -> list[tuple[str, str, int, float, float]]:
    """``(perturbation, class, n, surface_delta, meaning_delta)`` per perturbation."""
    counts: Counter[str] = Counter(v["last"] for v in variants)
    collapses = mean_collapse_by_perturbation(
        variants, mats, anchor_idx, variant_idx, background)

    rows = []
    for pert, c in collapses.items():
        cls = SEMANTIC_CLASSES.get(pert, "graded")
        rows.append((pert, cls, counts[pert], 1.0 - c, SEMANTIC_DISTANCE[cls]))
    return rows


def verdict_for(signal: float) -> str:
    """Turn the meaning-minus-surface gap into a one-phrase reading."""
    if signal >= 0.55:
        return "**hard negative** — looks the same, means something else"
    if signal >= 0.25:
        return "moderate negative — surface hints at the change"
    if signal > -0.15:
        return "aligned — surface overlap already gives the answer"
    if signal > -0.5:
        return "**hard positive** — looks different, means the same"
    return "**extreme positive** — further away than an unrelated theorem"


def build_report(
    anchors: dict[str, str],
    variants: list[dict[str, Any]],
    mats: dict[str, np.ndarray],
    anchor_idx: dict[str, int],
    variant_idx: list[int],
    figures: list[str],
) -> str:
    lines: list[str] = []
    add = lines.append

    ids = list(anchors)
    n_anchor_pairs = len(ids) * (len(ids) - 1) // 2

    add("# Where do the perturbed statements sit?")
    add("")
    n_with_variants = len({v["anchor_id"] for v in variants})
    n_background = sum(1 for a in anchors if a.startswith("bg:"))
    add(
        f"{len(variants)} variants across {n_with_variants} anchor"
        f"{'s' if n_with_variants != 1 else ''}, scored with {len(mats)} "
        "lexical (non-neural) similarity views. No model is involved: these "
        "numbers are what pure word matching can see."
    )
    if n_background:
        add("")
        add(f"_{n_background} further theorems are included as reference points "
            "only, to fix the distance scale._")
    add("")
    if len(mats) < len(SIMILARITY_VIEWS):
        skipped = [SIMILARITY_VIEWS[v] for v in SIMILARITY_VIEWS if v not in mats]
        add(f"_Skipped at this corpus size (quadratic): {', '.join(skipped)}. "
            "Raise `--max-pairwise` to include them._")
        add("")

    # ── Background: how far apart are two unrelated theorems? ─────────────────
    add("## Baseline — two unrelated theorems")
    add("")
    add(
        "Similarity between *different* anchors. This is the zero point: any "
        "two statements drawn from the benchmark sit about this far apart, so "
        "it is the scale against which 'close to the anchor' has to be read."
    )
    add("")
    add("| View | mean | std | min | max |")
    add("|---|---|---|---|---|")
    backgrounds: dict[str, float] = {}
    for view, label in SIMILARITY_VIEWS.items():
        if view not in mats:
            continue
        m = mats[view]
        vals = [m[anchor_idx[a], anchor_idx[b]] for a, b in combinations(ids, 2)]
        s = summarise(vals)
        backgrounds[view] = s["mean"]
        add(f"| {label} | **{fmt(s['mean'])}** | {fmt(s['std'])} | "
            f"{fmt(s['min'])} | {fmt(s['max'])} |")
    add("")
    add(f"_({n_anchor_pairs} anchor pairs.)_")
    add("")

    # ── Variants against their own anchor ─────────────────────────────────────
    add("## Variants against their own anchor")
    add("")
    add(
        "`collapse` rescales the raw similarity so that **0.0 means the variant "
        "is as far from its anchor as an unrelated theorem is, and 1.0 means it "
        "sits on the same point**."
    )
    add("")
    add("| View | raw similarity | collapse |")
    add("|---|---|---|")
    for view, label in SIMILARITY_VIEWS.items():
        if view not in mats:
            continue
        m = mats[view]
        raw = [m[variant_idx[k], anchor_idx[v["anchor_id"]]]
               for k, v in enumerate(variants)]
        s = summarise(raw)
        c = summarise([collapse(x, backgrounds[view]) for x in raw])
        add(f"| {label} | {fmt(s['mean'])} ± {fmt(s['std'])} | "
            f"**{fmt(c['mean'])}** ± {fmt(c['std'])} |")
    add("")

    # ── Depth ─────────────────────────────────────────────────────────────────
    m = mats[PRIMARY_VIEW]
    by_depth: dict[int, list[int]] = defaultdict(list)
    for k, v in enumerate(variants):
        by_depth[v["depth"]].append(k)
    if len(by_depth) > 1:
        add("## Does chaining move the statement further?")
        add("")
        add("One perturbation barely moves a statement. The question a deep "
            "run answers is whether *composing* them escapes the anchor's "
            "neighbourhood, or whether the tree just fills in the same tiny "
            "blob.")
        add("")
        add("| Depth | variants | mean collapse | min | still nearest to its anchor |")
        add("|---|---|---|---|---|")
        for depth in sorted(by_depth):
            idxs = by_depth[depth]
            cvals = [collapse(m[variant_idx[k],
                                anchor_idx[variants[k]["anchor_id"]]],
                              backgrounds[PRIMARY_VIEW]) for k in idxs]
            near = 0
            for k in idxs:
                sims = {a: m[variant_idx[k], anchor_idx[a]] for a in ids}
                if max(sims, key=sims.get) == variants[k]["anchor_id"]:
                    near += 1
            add(f"| {depth} | {len(idxs)} | {fmt(float(np.mean(cvals)))} | "
                f"{fmt(float(np.min(cvals)))} | "
                f"{near}/{len(idxs)} ({100 * near / len(idxs):.0f}%) |")
        add("")

    # ── Retrieval ─────────────────────────────────────────────────────────────
    hits = 0
    for k, v in enumerate(variants):
        sims = {a: m[variant_idx[k], anchor_idx[a]] for a in ids}
        if max(sims, key=sims.get) == v["anchor_id"]:
            hits += 1
    add("## Retrieval — does a variant still find its own anchor?")
    add("")
    add(
        f"**{hits}/{len(variants)} ({100 * hits / len(variants):.0f}%)** of "
        f"variants rank their own anchor first among all {len(anchors)} anchors "
        f"under {SIMILARITY_VIEWS[PRIMARY_VIEW].lower()}."
    )
    add("")

    # ── Per-perturbation breakdown ────────────────────────────────────────────
    add("## Per-perturbation")
    add("")
    add(
        "Grouped by the last step of the path. `surface Δ` is `1 − collapse`: "
        "how far that one perturbation moved the statement in surface terms, "
        "measured against **the statement it was applied to** rather than the "
        "anchor — otherwise a step deep in a chain is charged for all the "
        "drift its ancestors caused. `meaning Δ` is the logical distance "
        "implied by the truth-propagation table (0 equivalent, 0.34 entailed, "
        "0.67 graded, 1.0 contradictory)."
    )
    add("")
    add("`signal` is `meaning Δ − surface Δ`, the whole point of the exercise: "
        "**how much of the change is invisible to word matching**. Large "
        "positive means the meaning moved and the surface did not (a hard "
        "negative — the model has to read the logic). Large negative means the "
        "surface moved and the meaning did not (a hard positive). Near zero "
        "means surface overlap already gives away the answer, so the pair "
        "teaches an embedder nothing it doesn't already know.")
    add("")
    rows = perturbation_rows(variants, mats, anchor_idx, variant_idx,
                             backgrounds[PRIMARY_VIEW])

    # The primary view is a bag of words, so anything that only *reorders* is
    # invisible to it by construction. Reporting the order-aware view beside it
    # separates "genuinely hidden" from "hidden only from bag-of-words".
    ordered = None
    if "sequence" in mats:
        ordered = {
            pert: 1.0 - c
            for pert, c in mean_collapse_by_perturbation(
                variants, mats, anchor_idx, variant_idx,
                backgrounds["sequence"], "sequence").items()
        }
        add("| Perturbation | class | n | collapse | surface Δ | surface Δ (order-aware) | meaning Δ | signal | verdict |")
        add("|---|---|---|---|---|---|---|---|---|")
    else:
        add("| Perturbation | class | n | collapse | surface Δ | meaning Δ | signal | verdict |")
        add("|---|---|---|---|---|---|---|---|")

    for pert, cls, n, surface, meaning in sorted(
        rows, key=lambda r: -(r[4] - r[3])
    ):
        signal = meaning - surface
        cells = [f"`{pert}`", cls, str(n), fmt(1.0 - surface), fmt(surface)]
        if ordered is not None:
            cells.append(fmt(ordered[pert]))
        cells += [f"{meaning:.2f}", f"**{signal:+.2f}**", verdict_for(signal)]
        add("| " + " | ".join(cells) + " |")
    add("")

    if ordered is not None:
        add("The `order-aware` column repeats the measurement under "
            "token-sequence alignment instead of a bag of words, which "
            "separates two very different reasons a perturbation can score "
            "near zero.")
        add("")

        # A pure permutation leaves the token multiset untouched, so a bag of
        # words cannot see it even in principle. That is a structural blind
        # spot, quite unlike a one-token substitution that TF-IDF happens to
        # down-weight — worth telling apart rather than lumping by threshold.
        permuters: set[str] = set()
        for k, v in enumerate(variants):
            anchor_stmt = anchors[v["anchor_id"]]
            if Counter(lean_tokens(anchor_stmt)) == Counter(
                lean_tokens(v["statement"])
            ):
                permuters.add(v["last"])
        if permuters:
            add("**Pure reorderings** — "
                + ", ".join(f"`{p}`" for p in sorted(permuters))
                + " produce variants with *exactly* the anchor's token "
                "multiset. A bag-of-words model cannot distinguish them at "
                "any threshold; only the order-aware column sees anything.")
            add("")

        subs = [(p, cls) for p, cls, _, s, _ in rows
                if s < 0.05 and ordered[p] < 0.05 and p not in permuters]
        if subs:
            add("**Single-token substitutions** stay near zero in *both* "
                "columns. These swap one common symbol for another (`≤` for "
                "`<`, `0` for `1`); common symbols carry almost no IDF weight "
                "and almost no alignment cost, so they are hidden from lexical "
                "matching however it is measured. What that is worth depends "
                "entirely on whether the meaning moved with them:")
            add("")
            hidden_negs = [p for p, cls in subs if cls != "equivalent"]
            hidden_noops = [p for p, cls in subs if cls == "equivalent"]
            if hidden_negs:
                add("* meaning *did* move — "
                    + ", ".join(f"`{p}`" for p in sorted(hidden_negs))
                    + ". **The most reliable hard negatives in the set.**")
            if hidden_noops:
                add("* meaning did *not* move — "
                    + ", ".join(f"`{p}`" for p in sorted(hidden_noops))
                    + ". Invisible and equivalent, so the pair asserts "
                    "something the model already believes. No training signal "
                    "either way.")
            add("")

    # ── Inversion ─────────────────────────────────────────────────────────────
    add("## Inversion — is surface similarity even pointing the right way?")
    add("")
    inversions, comparisons = 0, 0
    by_equiv: dict[str, list[int]] = defaultdict(list)  # name -> [inverted, total]
    per_anchor: dict[str, list[int]] = defaultdict(list)
    for k, v in enumerate(variants):
        per_anchor[v["anchor_id"]].append(k)
    for anchor_id, idxs in per_anchor.items():
        equiv = [k for k in idxs if variants[k]["semantic_class"] == "equivalent"]
        diff = [k for k in idxs if variants[k]["semantic_class"] != "equivalent"]
        ai = anchor_idx[anchor_id]
        for ke, kd in product(equiv, diff):
            comparisons += 1
            tally = by_equiv.setdefault(variants[ke]["last"], [0, 0])
            tally[1] += 1
            if m[variant_idx[kd], ai] > m[variant_idx[ke], ai]:
                inversions += 1
                tally[0] += 1

    if comparisons:
        rate = 100 * inversions / comparisons
        add(
            f"Across {comparisons} (equivalent, non-equivalent) variant pairs "
            f"sharing an anchor, the **non-equivalent** variant was lexically "
            f"closer to the anchor **{inversions} times ({rate:.0f}%)**."
        )
        add("")
        if rate > 55:
            add(
                "> Surface similarity is **anti-correlated** with logical "
                "similarity here. A model scoring by word overlap does not "
                "merely fail to learn the logic — it is actively pulled the "
                "wrong way, which is a plausible explanation for the natural-"
                "language training result."
            )
        elif rate > 45:
            add(
                "> Surface similarity carries **essentially no information** "
                "about logical similarity — a coin flip. There is nothing here "
                "for a word-matching model to exploit, so whatever the model "
                "learns, it has to learn from the logic."
            )
        else:
            add(
                "> Surface similarity mostly points the right way, so a "
                "word-matching model can score well on this set without "
                "understanding it. These pairs are weak training signal."
            )
        add("")
        add(
            "The aggregate hides most of the story, because it is dominated by "
            "whichever equivalence-preserving perturbation fires most often. "
            "Split by the positive side of the pair:"
        )
        add("")
        add("| Equivalent variant | pairs | beaten by a non-equivalent variant |")
        add("|---|---|---|")
        for name in sorted(by_equiv, key=lambda k: -by_equiv[k][0] / by_equiv[k][1]):
            inv, tot = by_equiv[name]
            add(f"| `{name}` | {tot} | **{inv} ({100 * inv / tot:.0f}%)** |")
        add("")
        add(
            "A row near 100% is a perturbation whose *positive* pair a lexical "
            "model would rank below a *negative* pair of the same anchor — the "
            "exact case where word matching gives the wrong answer and logic "
            "gives the right one."
        )
        add("")

        # A positive that barely edits the string cannot be beaten and drags the
        # aggregate toward "surface works fine". Quote the rate without them.
        surface_by_pert = {r[0]: r[3] for r in rows}
        trivial = {p for p, s in surface_by_pert.items() if s < 0.05}
        nt_inv = sum(v[0] for k, v in by_equiv.items() if k not in trivial)
        nt_tot = sum(v[1] for k, v in by_equiv.items() if k not in trivial)
        if nt_tot and nt_tot < comparisons:
            add(
                f"Dropping positives that barely edit the string at all "
                f"({', '.join('`' + p + '`' for p in sorted(trivial & set(by_equiv)))} "
                f"— a positive that changes nothing cannot be beaten), the rate "
                f"is **{nt_inv}/{nt_tot} ({100 * nt_inv / nt_tot:.0f}%)**. "
                "That is the number to quote: among pairs where the "
                "equivalence-preserving rewrite actually rewrote something, "
                "surface similarity points the wrong way most of the time."
            )
    else:
        add("_Not enough equivalent/non-equivalent pairs on a shared anchor._")
    add("")

    if figures:
        add("## Figures")
        add("")
        for f in figures:
            add(f"![{f}]({f})")
            add("")

    return "\n".join(lines)


# ── Plots ─────────────────────────────────────────────────────────────────────


def plot_surface_vs_meaning(rows, out_path: Path) -> None:
    """The 2×2 that says which perturbations are worth training on."""
    xs = [r[3] for r in rows]
    xlo, xhi = min(-0.05, min(xs) - 0.08), max(1.05, max(xs) + 0.12)

    fig, ax = plt.subplots(figsize=(11, 7))
    ax.axhspan(0.5, 1.08, color="#e63946", alpha=0.05)
    ax.axhspan(-0.08, 0.5, color="#2a9d8f", alpha=0.05)

    # Labels are stacked per meaning-Δ row: only four distinct y values exist,
    # so left-to-right within a row with an alternating vertical offset is
    # enough to keep them legible without a label-repel dependency.
    by_row: dict[float, list] = defaultdict(list)
    for r in rows:
        by_row[r[4]].append(r)

    for meaning, group in by_row.items():
        group = sorted(group, key=lambda r: r[3])
        for i, (pert, cls, n, surface, _) in enumerate(group):
            ax.scatter(surface, meaning, s=40 + 18 * n,
                       color=CLASS_COLOURS[cls], edgecolor="black",
                       linewidth=0.6, alpha=0.9, zorder=3)
            dy = 14 + 13 * (i % 4)
            sign = 1 if meaning < 0.75 else -1
            ax.annotate(
                pert, (surface, meaning), fontsize=8,
                xytext=(0, sign * dy), textcoords="offset points",
                ha="center", zorder=4,
                arrowprops=dict(arrowstyle="-", linewidth=0.5,
                                color="#888", shrinkA=0, shrinkB=3),
            )

    ax.axvline(0.5, color="grey", linewidth=0.8, linestyle="--")
    ax.axhline(0.5, color="grey", linewidth=0.8, linestyle="--")
    ax.set_xlabel("surface change  (1 − collapse; 0 = same point as the anchor)")
    ax.set_ylabel("meaning change  (0 = equivalent, 1 = contradictory)")
    ax.set_title("Surface change vs meaning change\n"
                 "upper-left = hard negatives · lower-right = hard positives · "
                 "the diagonal = nothing to learn",
                 fontsize=11)
    ax.plot([xlo, xhi], [xlo, xhi], color="#999", linewidth=0.8,
            linestyle=":", zorder=1)
    ax.set_xlim(xlo, xhi)
    ax.set_ylim(-0.08, 1.08)
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=c,
                          markeredgecolor="black", label=k)
               for k, c in CLASS_COLOURS.items()]
    ax.legend(handles=handles, title="semantic class", loc="center right",
              fontsize=8)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_spectrum(rows, out_path: Path) -> None:
    """The learnability spectrum: perturbations ranked by hidden signal.

    One bar per perturbation, length = meaning Δ − surface Δ. Everything above
    the axis is change a word-matching model cannot see; everything below is
    surface churn that does not correspond to a change in meaning.
    """
    ranked = sorted(rows, key=lambda r: r[4] - r[3])
    labels = [r[0] for r in ranked]
    signal = [r[4] - r[3] for r in ranked]
    colours = [CLASS_COLOURS[r[1]] for r in ranked]

    fig, ax = plt.subplots(figsize=(9, 0.36 * len(ranked) + 2.6))
    ax.barh(range(len(ranked)), signal, color=colours,
            edgecolor="black", linewidth=0.5, alpha=0.9)
    for y, (r, s) in enumerate(zip(ranked, signal)):
        ax.text(s + (0.02 if s >= 0 else -0.02), y, f"n={r[2]}",
                va="center", ha="left" if s >= 0 else "right", fontsize=7,
                color="#444")

    ax.axvline(0, color="black", linewidth=1.0)
    ax.set_yticks(range(len(ranked)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("signal hidden from word matching   (meaning Δ − surface Δ)")
    ax.set_title(
        "Learnability spectrum\n"
        "right: meaning moved, words didn't — hard negative\n"
        "left: words moved, meaning didn't — hard positive",
        fontsize=10)
    lo, hi = min(signal), max(signal)
    ax.set_xlim(lo - 0.28, hi + 0.18)
    handles = [plt.Line2D([], [], marker="s", linestyle="", color=c,
                          markeredgecolor="black", label=k)
               for k, c in CLASS_COLOURS.items()]
    ax.legend(handles=handles, title="semantic class", loc="lower right",
              fontsize=8)
    ax.grid(alpha=0.2, axis="x")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_similarity_strip(variants, mats, anchor_idx, variant_idx,
                          background: float, out_path: Path) -> None:
    """Per-perturbation spread of collapse, so outliers stay visible."""
    m = mats[PRIMARY_VIEW]
    by_pert: dict[str, list[float]] = defaultdict(list)
    for k, v in enumerate(variants):
        by_pert[v["last"]].append(
            collapse(m[variant_idx[k], anchor_idx[v["anchor_id"]]], background)
        )
    order = sorted(by_pert, key=lambda p: np.mean(by_pert[p]))

    fig, ax = plt.subplots(figsize=(9, 0.32 * len(order) + 2.5))
    for y, pert in enumerate(order):
        vals = by_pert[pert]
        cls = SEMANTIC_CLASSES.get(pert, "graded")
        ax.scatter(vals, np.full(len(vals), y) + np.random.uniform(-0.12, 0.12, len(vals)),
                   color=CLASS_COLOURS[cls], s=32, alpha=0.8,
                   edgecolor="black", linewidth=0.4, zorder=3)
        ax.scatter([np.mean(vals)], [y], marker="|", s=340, color="black", zorder=4)

    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(order, fontsize=8)
    ax.axvline(0.0, color="#444", linewidth=1.0)
    ax.text(0.0, len(order) - 0.3, " unrelated theorem", fontsize=8, color="#444")
    ax.axvline(1.0, color="#444", linewidth=1.0)
    ax.text(1.0, len(order) - 0.3, " identical", fontsize=8, color="#444",
            ha="right")
    ax.set_xlabel("collapse toward the anchor  (0 = unrelated, 1 = same point)")
    ax.set_title("How far each perturbation actually moves the statement", fontsize=11)
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=c,
                          markeredgecolor="black", label=k)
               for k, c in CLASS_COLOURS.items()]
    ax.legend(handles=handles, title="semantic class", loc="lower right", fontsize=8)
    ax.grid(alpha=0.2, axis="x")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def annotate_with_leaders(ax, xy, labels) -> None:
    """Label near-coincident points by parking the text at the panel edges.

    A tight cloud puts many points within a few pixels of each other, so an
    offset annotation per point is unreadable. Instead each label goes into an
    evenly spaced slot down the left or right margin — whichever side its point
    is on — joined back to the point by a leader line.
    """
    if len(xy) == 0:
        return
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    # Split on the median rather than the panel midpoint: the cloud is rarely
    # centred, and an even split is what keeps either margin from overflowing.
    mid = float(np.median(xy[:, 0]))

    for side in ("left", "right"):
        idx = [i for i in range(len(xy))
               if (xy[i, 0] < mid) == (side == "left")]
        if not idx:
            continue
        idx.sort(key=lambda i: -xy[i, 1])
        span = y1 - y0
        slots = [y1 - span * (0.04 + 0.92 * (j + 0.5) / len(idx))
                 for j in range(len(idx))]
        text_x = x0 + (x1 - x0) * (0.015 if side == "left" else 0.985)
        for j, i in enumerate(idx):
            ax.annotate(
                labels[i], xy=(xy[i, 0], xy[i, 1]),
                xytext=(text_x, slots[j]), textcoords="data",
                fontsize=6, alpha=0.9,
                ha="left" if side == "left" else "right",
                va="center", zorder=6,
                arrowprops=dict(arrowstyle="-", linewidth=0.4, color="#aaa",
                                shrinkA=2, shrinkB=2),
            )


def plot_cloud(anchor_id, anchors, variants, mats, anchor_idx, variant_idx,
               out_path: Path) -> bool:
    """2-D MDS of one anchor's whole perturbation family.

    Every other anchor is plotted too, as grey crosses, so the cloud can be
    read against a real scale: if the family is a tight blob and the other
    theorems are far away, the perturbations are not moving anything.
    """
    from sklearn.manifold import MDS

    family = [k for k, v in enumerate(variants) if v["anchor_id"] == anchor_id]
    if len(family) < 3:
        return False

    rows = ([anchor_idx[a] for a in anchors] + [variant_idx[k] for k in family])
    m = mats[PRIMARY_VIEW][np.ix_(rows, rows)]
    dist = np.clip(1.0 - m, 0.0, None)
    np.fill_diagonal(dist, 0.0)

    coords = MDS(n_components=2, dissimilarity="precomputed",
                 random_state=0, normalized_stress="auto").fit_transform(dist)

    n_anchors = len(anchors)
    home = list(anchors).index(anchor_id)
    fam_xy = coords[n_anchors:]
    depths = np.array([variants[k]["depth"] for k in family])

    # Labelling every point stops being readable somewhere around 25, and a
    # deep tree is well past that.
    label_points = len(family) <= 25

    fig, (ax, right) = plt.subplots(1, 2, figsize=(15, 7.5))

    def frame(target) -> None:
        target.scatter(coords[:n_anchors, 0], coords[:n_anchors, 1], marker="x",
                       color="#bbb", s=55,
                       label="other anchors (unrelated theorems)")
        target.scatter(coords[home, 0], coords[home, 1], marker="*", s=460,
                       color="#1d3557", edgecolor="white", linewidth=1.2,
                       label="the anchor", zorder=5)
        target.set_xticks([])
        target.set_yticks([])
        target.grid(alpha=0.15)

    # The zoom box, decided up front so the two panels can divide the labelling
    # between them: the core is legible only on the right, the outliers only on
    # the left.
    lo_x, hi_x = np.percentile(fam_xy[:, 0], [4, 96])
    lo_y, hi_y = np.percentile(fam_xy[:, 1], [4, 96])
    # Labels are parked in the side margins, so widen them enough to hold text.
    pad_x = max((hi_x - lo_x) * (0.7 if label_points else 0.12), 1e-6)
    pad_y = max((hi_y - lo_y) * 0.12, 1e-6)
    box = (lo_x - pad_x, hi_x + pad_x, lo_y - pad_y, hi_y + pad_y)
    in_view = [i for i in range(len(family))
               if box[0] <= fam_xy[i, 0] <= box[1]
               and box[2] <= fam_xy[i, 1] <= box[3]]
    outliers = [i for i in range(len(family)) if i not in set(in_view)]

    def label_of(i: int) -> str:
        return " → ".join(variants[family[i]]["path"][-2:])

    # Left — the honest scale: the whole family against unrelated theorems.
    frame(ax)
    seen: set[str] = set()
    for i, k in enumerate(family):
        cls = variants[k]["semantic_class"]
        ax.scatter(fam_xy[i, 0], fam_xy[i, 1], color=CLASS_COLOURS[cls],
                   s=55, alpha=0.85, edgecolor="black", linewidth=0.5,
                   label=cls if cls not in seen else None, zorder=3)
        seen.add(cls)
    # Only the escapees get named here; naming the core too would just pile
    # text on a blob that the right panel resolves properly.
    for i in outliers:
        ax.annotate(label_of(i), fam_xy[i], fontsize=6, alpha=0.9,
                    xytext=(5, 3), textcoords="offset points")
    ax.set_title("Full scale — the family against unrelated theorems",
                 fontsize=10)
    ax.legend(fontsize=8, loc="best")

    # Right — the same cloud, zoomed to its dense core. At full scale the core
    # is a few pixels wide and any structure inside it is invisible; the far
    # outliers (alpha_rename and friends) set the scale on the left panel and
    # are deliberately allowed off-view here.
    frame(right)
    sizes = 28 + 26 * (depths - depths.min()) / max(np.ptp(depths), 1)
    for cls in sorted({variants[k]["semantic_class"] for k in family}):
        sel = [i for i, k in enumerate(family)
               if variants[k]["semantic_class"] == cls]
        right.scatter(fam_xy[sel, 0], fam_xy[sel, 1], color=CLASS_COLOURS[cls],
                      s=sizes[sel], alpha=0.85, edgecolor="black",
                      linewidth=0.5, zorder=3)
    right.set_xlim(box[0], box[1])
    right.set_ylim(box[2], box[3])
    right.set_title(
        f"Zoom on the core — {len(in_view)} of {len(family)} variants in view, "
        f"marker size = chain depth", fontsize=10)

    if label_points:
        annotate_with_leaders(right, fam_xy[in_view],
                              [label_of(i) for i in in_view])

    fig.suptitle(
        f"Perturbation cloud around `{anchor_id}`  —  "
        f"{len(family)} Lean-valid variants, MDS on lexical distance",
        fontsize=12)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return True


# ── Entry point ───────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path,
                    default=PROJECT_ROOT / "data" / "benchmark-review")
    ap.add_argument("--out", type=Path,
                    help="Output directory (default: <run>/geometry).")
    ap.add_argument("--cloud-anchor",
                    help="Anchor id to draw the cloud diagram for "
                         "(default: the one with the most variants).")
    ap.add_argument("--background", type=Path,
                    default=PROJECT_ROOT / "data" / "benchmark-review",
                    help="Run whose anchors supply the unrelated-theorem "
                         "distance scale when this run has too few of its own.")
    ap.add_argument("--max-pairwise", type=int, default=350,
                    help="Above this corpus size, skip the two quadratic "
                         "similarity views (default 350).")
    args = ap.parse_args()

    out_dir = args.out or args.run / "geometry"
    out_dir.mkdir(parents=True, exist_ok=True)

    anchors, variants = load_variants(args.run)
    n_with_variants = len({v["anchor_id"] for v in variants})

    if len(anchors) < 3 and args.background and args.background != args.run:
        extra = load_background_anchors(args.background)
        added = 0
        for aid, stmt in extra.items():
            if aid not in anchors:
                anchors[f"bg:{aid}"] = stmt
                added += 1
        if added:
            print(f"borrowed {added} background anchors from {args.background}",
                  flush=True)

    print(f"{len(variants)} variants across {n_with_variants} anchor(s), "
          f"{len(anchors)} reference points", flush=True)

    statements = list(anchors.values()) + [v["statement"] for v in variants]
    anchor_idx = {a: i for i, a in enumerate(anchors)}
    variant_idx = list(range(len(anchors), len(statements)))

    print("computing similarity matrices…", flush=True)
    mats = similarity_matrices(statements, max_pairwise=args.max_pairwise)

    m = mats[PRIMARY_VIEW]
    ids = list(anchors)
    background = float(np.mean(
        [m[anchor_idx[a], anchor_idx[b]] for a, b in combinations(ids, 2)]
    )) if len(ids) > 1 else 0.0

    rows = perturbation_rows(variants, mats, anchor_idx, variant_idx, background)

    figures: list[str] = []
    plot_spectrum(rows, out_dir / "spectrum.png")
    figures.append("spectrum.png")
    plot_surface_vs_meaning(rows, out_dir / "surface-vs-meaning.png")
    figures.append("surface-vs-meaning.png")
    plot_similarity_strip(variants, mats, anchor_idx, variant_idx, background,
                          out_dir / "collapse-by-perturbation.png")
    figures.append("collapse-by-perturbation.png")

    cloud_anchor = args.cloud_anchor
    if cloud_anchor is None:
        counts: dict[str, int] = defaultdict(int)
        for v in variants:
            counts[v["anchor_id"]] += 1
        cloud_anchor = max(counts, key=counts.get) if counts else None
    if cloud_anchor and plot_cloud(cloud_anchor, anchors, variants, mats,
                                   anchor_idx, variant_idx,
                                   out_dir / "cloud.png"):
        figures.append("cloud.png")

    report = build_report(anchors, variants, mats, anchor_idx, variant_idx,
                          figures)
    (out_dir / "report.md").write_text(report, encoding="utf-8")

    metrics = {
        "n_anchors": len(anchors),
        "n_variants": len(variants),
        "background_similarity": {
            view: float(np.mean([mats[view][anchor_idx[a], anchor_idx[b]]
                                 for a, b in combinations(ids, 2)]))
            for view in mats
        } if len(ids) > 1 else {},
        "per_perturbation": [
            {"perturbation": p, "semantic_class": c, "n": n,
             "surface_delta": s, "meaning_delta": md, "signal": md - s}
            for p, c, n, s, md in sorted(rows, key=lambda r: -(r[4] - r[3]))
        ],
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"\n  {out_dir / 'report.md'}")
    for f in figures:
        print(f"  {out_dir / f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
