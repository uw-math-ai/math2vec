#!/usr/bin/env python3
"""Build the baseline-vs-fine-tuned comparison tables from metrics.json.

CPU only -- reads what the trainer already wrote. No GPU, no model loading.

    # one run: shows base Qwen3-8B vs this run's fine-tuned model
    python report.py checkpoints/mv3_qwen8b_a1_ep2

    # two runs: adds the cross-run A1-vs-paper comparison (the experiment)
    python report.py checkpoints/mv3_qwen8b_paper_ep2 checkpoints/mv3_qwen8b_a1_ep2

    # markdown for pasting into a writeup
    python report.py --markdown checkpoints/*_ep2 > results.md

Each argument is a run directory (or a metrics.json path directly).
"""
import argparse
import json
import os
import sys

# Same order as PAIR_TYPES in train_qwen_mnrl_multiview_v3_tg.py
PAIR_ORDER = [
    ("nl_informal__to__lean_signature", "NL -> Lean signature (PRIMARY)"),
    ("nl_informal__to__lean_type",      "NL -> Lean type"),
    ("nl_informal_2__to__lean_signature", "NL rephrasing -> Lean signature"),
    ("nl_informal_2__to__nl_informal",  "NL rephrasing -> NL informal"),
    ("lean_type__to__lean_signature",   "Lean type -> Lean signature"),
    ("lean_signature__to__nl_informal", "Lean signature -> NL informal (REVERSE)"),
]


def load_run(path):
    mp = path if path.endswith(".json") else os.path.join(path, "metrics.json")
    if not os.path.isfile(mp):
        sys.exit(f"ERROR: no metrics.json at {mp}\n"
                 f"       If the job is still running, it has not been written yet.")
    with open(mp) as f:
        d = json.load(f)
    cfg = d.get("config", {})
    run = os.path.basename(os.path.normpath(cfg.get("output_dir") or os.path.dirname(mp)))
    extra = d.get("counts", {}).get("extra_train") or {}
    d["_run"] = run
    d["_path"] = mp
    d["_is_a1"] = bool(extra.get("extra_in"))
    # optional sidecar from collect.sh
    ri = os.path.join(os.path.dirname(mp), "runinfo.json")
    d["_runinfo"] = json.load(open(ri)) if os.path.isfile(ri) else {}
    return d


def fmt(v, nd=4):
    return "n/a" if v is None else f"{v:.{nd}f}"


def delta(new, old, nd=4):
    if new is None or old is None:
        return "n/a"
    d = new - old
    return f"{'+' if d >= 0 else ''}{d:.{nd}f}"


def metric_keys(block):
    k = int(block.get("k", 10))
    return [("Recall@1", "recall@1"), ("Recall@5", "recall@5"),
            (f"Recall@{k}", f"recall@{k}"), (f"MRR@{k}", f"mrr@{k}")]


class Table:
    """Plain-text or markdown table."""

    def __init__(self, headers, md=False):
        self.headers, self.rows, self.md = headers, [], md

    def add(self, *cells):
        self.rows.append([str(c) for c in cells])

    def render(self):
        if self.md:
            out = ["| " + " | ".join(self.headers) + " |",
                   "|" + "|".join("---" for _ in self.headers) + "|"]
            out += ["| " + " | ".join(r) + " |" for r in self.rows]
            return "\n".join(out)
        w = [max(len(self.headers[i]), *(len(r[i]) for r in self.rows)) if self.rows
             else len(self.headers[i]) for i in range(len(self.headers))]
        sep = "  ".join("-" * x for x in w)
        out = ["  ".join(h.ljust(w[i]) for i, h in enumerate(self.headers)), sep]
        out += ["  ".join(r[i].ljust(w[i]) for i in range(len(r))) for r in self.rows]
        return "\n".join(out)


def head(title, md):
    print(("\n## " if md else "\n=== ") + title + ("" if md else " ===") + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+", help="run directories or metrics.json paths")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()
    md = args.markdown

    runs = [load_run(p) for p in args.runs]
    # baseline arm (no EXTRA) first, A1 arm second
    runs.sort(key=lambda d: d["_is_a1"])

    head("Runs", md)
    t = Table(["Run", "Model", "EXTRA", "Epochs", "Train", "Dev", "Wall", "GPU-h"], md)
    for d in runs:
        c, n, ri = d.get("config", {}), d.get("counts", {}), d["_runinfo"]
        t.add(d["_run"],
              (c.get("model_name") or "?").split("/")[-1],
              os.path.basename(c.get("extra_train_jsonl") or "") or "none",
              c.get("epochs", "?"),
              f"{n.get('train', 0):,}",
              f"{n.get('dev', 0):,}",
              ri.get("elapsed", "?"),
              ri.get("gpu_hours", "?"))
    print(t.render())

    # ---- dev-set identity: the experiment is only valid if these match ----
    if len(runs) > 1:
        head("Dev-set identity check", md)
        sigs = set()
        t = Table(["Run", "concepts_total", "train", "dev", "n_dev_used", "corpus_size"], md)
        for d in runs:
            n, b = d.get("counts", {}), d.get("baseline", {})
            nd, cs = int(b.get("n_dev_used", -1)), int(b.get("corpus_size", -1))
            sigs.add((n.get("concepts_total"), n.get("train"), n.get("dev"), nd, cs))
            t.add(d["_run"], f"{n.get('concepts_total', 0):,}", f"{n.get('train', 0):,}",
                  f"{n.get('dev', 0):,}", f"{nd:,}", f"{cs:,}")
        print(t.render())
        if len(sigs) == 1:
            print("\nOK: identical dev set and eval corpus -- the runs are comparable.")
        else:
            print("\n*** WARNING: dev set / corpus DIFFER across runs. ***\n"
                  "The cross-run comparison below is NOT valid. Check that both runs used\n"
                  "the same --local_jsonl, --seed, --dev_frac and --max_rows.")
        for key in ("local_jsonl", "seed", "dev_frac", "max_rows", "model_name",
                    "batch_size", "max_seq_len", "warmup_steps", "epochs", "n_hard_negs"):
            vals = {str(d.get("config", {}).get(key)) for d in runs}
            if len(vals) > 1:
                print(f"  note: config.{key} differs across runs: {sorted(vals)}")

    # ---- [extra] counts ----
    for d in runs:
        extra = d.get("counts", {}).get("extra_train") or {}
        if not extra:
            continue
        head(f"[extra] counts -- {d['_run']}", md)
        t = Table(["Statistic", "Concepts"], md)
        labels = {
            "extra_in": "read from EXTRA file",
            "drop_dev_id": "dropped: concept_id is a dev target",
            "drop_dev_module": "dropped: module is a dev module",
            "merged_into_train": "merged into an existing train concept",
            "nl_views_added": "   NL views appended by those merges",
            "new_train_only": "added as NEW training-only concepts",
        }
        for k, lbl in labels.items():
            if k in extra:
                t.add(lbl, f"{extra[k]:,}")
        print(t.render())
        kept = extra.get("merged_into_train", 0) + extra.get("new_train_only", 0)
        if extra.get("extra_in"):
            print(f"\nKept {kept:,} / {extra['extra_in']:,} "
                  f"({100 * kept / extra['extra_in']:.1f}%); "
                  f"dropped {extra.get('drop_dev_id', 0) + extra.get('drop_dev_module', 0):,} "
                  f"to avoid dev leakage.")

    # ---- within-run: base model vs fine-tuned ----
    for d in runs:
        b, f_ = d.get("baseline", {}), d.get("finetuned", {})
        if not b or not f_:
            continue
        head(f"Primary NL -> Lean signature: base model vs fine-tuned -- {d['_run']}", md)
        t = Table(["Metric", "Baseline", "Fine-tuned", "Delta"], md)
        for lbl, key in metric_keys(b):
            t.add(lbl, fmt(b.get(key)), fmt(f_.get(key)), delta(f_.get(key), b.get(key)))
        print(t.render())

    # ---- cross-run: the actual experiment ----
    base_arm = next((d for d in runs if not d["_is_a1"]), None)
    a1_arm = next((d for d in runs if d["_is_a1"]), None)
    if base_arm and a1_arm:
        head("EXPERIMENT: paper recipe vs + A1 docstrings (both fine-tuned)", md)
        p, a = base_arm.get("finetuned", {}), a1_arm.get("finetuned", {})
        t = Table(["Metric", "Paper recipe", "+ A1 docstrings", "Delta"], md)
        for lbl, key in metric_keys(base_arm.get("baseline", {})):
            t.add(lbl, fmt(p.get(key)), fmt(a.get(key)), delta(a.get(key), p.get(key)))
        print(t.render())

        head("All pair types: paper recipe vs + A1 docstrings (fine-tuned)", md)
        pp, ap_ = base_arm.get("finetuned_per_pair_type", {}), a1_arm.get("finetuned_per_pair_type", {})
        k = int(base_arm.get("baseline", {}).get("k", 10))
        t = Table(["Pair type", "n_dev", f"Paper R@1/R@{k}/MRR@{k}",
                   f"+A1 R@1/R@{k}/MRR@{k}", f"dR@1", f"dMRR@{k}"], md)
        for key, desc in PAIR_ORDER:
            pr, ar = pp.get(key, {}), ap_.get(key, {})
            if pr.get("skipped") and ar.get("skipped"):
                t.add(desc, "-", "skipped (views absent)", "skipped (views absent)", "-", "-")
                continue
            trip = lambda r: "/".join(fmt(r.get(x), 3) for x in ("recall@1", f"recall@{k}", f"mrr@{k}"))
            t.add(desc, f"{int(ar.get('n_dev_used', pr.get('n_dev_used', 0))):,}",
                  trip(pr), trip(ar),
                  delta(ar.get("recall@1"), pr.get("recall@1"), 4),
                  delta(ar.get(f"mrr@{k}"), pr.get(f"mrr@{k}"), 4))
        print(t.render())

        pl, al = (base_arm.get("finetuned_per_pair_type_loss") or {},
                  a1_arm.get("finetuned_per_pair_type_loss") or {})
        if pl or al:
            head("Per-pair-type contrastive loss, fine-tuned (lower is better)", md)
            t = Table(["Pair type", "Paper recipe", "+ A1 docstrings", "Delta"], md)
            for key, desc in PAIR_ORDER:
                if pl.get(key) is None and al.get(key) is None:
                    continue
                t.add(desc, fmt(pl.get(key)), fmt(al.get(key)),
                      delta(al.get(key), pl.get(key)))
            print(t.render())
    else:
        head("Cross-run comparison", md)
        have = "the A1 arm" if a1_arm else "the paper baseline"
        want = "paper baseline" if a1_arm else "A1 arm"
        print(f"Only {have} was supplied, so the paper-vs-A1 table is omitted.\n"
              f"Pass both run directories to get it. To produce the {want}:\n")
        if a1_arm:
            print("  sbatch --export=ALL,RUN=mv3_qwen8b_paper_ep2 run.slurm")
        else:
            print("  sbatch --export=ALL,RUN=mv3_qwen8b_a1_ep2,"
                  "EXTRA=data/a1_kept_concepts_v4.19.0.jsonl run.slurm")

    head("Per-pair-type detail: base vs fine-tuned, each run", md)
    for d in runs:
        bp, fp = d.get("baseline_per_pair_type", {}), d.get("finetuned_per_pair_type", {})
        if not bp and not fp:
            continue
        k = int(d.get("baseline", {}).get("k", 10))
        print(("### " if md else "-- ") + d["_run"] + "\n")
        t = Table(["Pair type", "n_dev", "Base R@1", "FT R@1", "d R@1",
                   f"Base MRR@{k}", f"FT MRR@{k}", f"d MRR@{k}"], md)
        for key, desc in PAIR_ORDER:
            br, fr = bp.get(key, {}), fp.get(key, {})
            if br.get("skipped") or fr.get("skipped") or (not br and not fr):
                t.add(desc, "-", "skipped", "skipped", "-", "skipped", "skipped", "-")
                continue
            t.add(desc, f"{int(fr.get('n_dev_used', 0)):,}",
                  fmt(br.get("recall@1")), fmt(fr.get("recall@1")),
                  delta(fr.get("recall@1"), br.get("recall@1")),
                  fmt(br.get(f"mrr@{k}")), fmt(fr.get(f"mrr@{k}")),
                  delta(fr.get(f"mrr@{k}"), br.get(f"mrr@{k}")))
        print(t.render())
        print()

    print("\nSource files:")
    for d in runs:
        print(f"  {d['_run']}: {d['_path']}")


if __name__ == "__main__":
    main()
