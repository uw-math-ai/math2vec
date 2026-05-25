from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


TASK_DEFAULT_PROMPTS = {
    "informal_to_type": "Instruct: Find the most mathematically similar Lean type to this statement\nQuery: ",
    "type_to_informal": "Instruct: Find the most mathematically similar statement as a Lean type\nQuery: ",
    "informal_to_signature": "Instruct: Find the most mathematically similar Lean signature to this statement\nQuery: ",
    "signature_to_informal": "Instruct: Find the most mathematically similar statement as a Lean signature\nQuery: ",
    "type_to_signature": "Instruct: Find the most mathematically similar Lean signature to this Lean type\nQuery: ",
    "signature_to_type": "Instruct: Find the most mathematically similar Lean type to this Lean signature\nQuery: ",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect the newest successful FrenzyMath run for each model/task pair "
            "and export a flat results table plus an audit table."
        )
    )
    parser.add_argument(
        "--results-dir",
        required=True,
        help="Directory containing FrenzyMath run subdirectories.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where the summary CSV/JSON files should be written.",
    )
    parser.add_argument(
        "--run-label",
        default="FULL",
        help="Only include runs whose config.run_label matches this value.",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_success_run(run_dir: Path, required_run_label: str) -> dict[str, Any] | None:
    results_path = run_dir / "results.json"
    if not results_path.exists():
        return None

    try:
        payload = load_json(results_path)
    except Exception:
        return None

    if payload.get("run_status") != "success":
        return None

    config = payload.get("config", {})
    if config.get("run_label") != required_run_label:
        return None

    task_preset = config.get("task_preset")
    model_name = config.get("model_name")
    if not task_preset or not model_name:
        return None

    resolved_settings = config.get("resolved_query_encoding_settings", {})
    task_prompt = resolved_settings.get(task_preset, {}).get("prompt")
    expected_prompt = TASK_DEFAULT_PROMPTS.get(task_preset)

    artifact_paths = payload.get("artifact_paths", {})
    query_cache_metadata_path = artifact_paths.get("query_field_embeddings_cache_metadata_file")
    corpus_cache_metadata_path = artifact_paths.get("corpus_field_embeddings_cache_metadata_file")

    query_cache_metadata = None
    corpus_cache_metadata = None
    if query_cache_metadata_path:
        query_cache_metadata_file = Path(query_cache_metadata_path)
        if query_cache_metadata_file.exists():
            try:
                query_cache_metadata = load_json(query_cache_metadata_file)
            except Exception:
                query_cache_metadata = None
    if corpus_cache_metadata_path:
        corpus_cache_metadata_file = Path(corpus_cache_metadata_path)
        if corpus_cache_metadata_file.exists():
            try:
                corpus_cache_metadata = load_json(corpus_cache_metadata_file)
            except Exception:
                corpus_cache_metadata = None

    query_cache_prompt = None
    if query_cache_metadata is not None:
        query_cache_prompt = (
            query_cache_metadata.get("cache_spec", {})
            .get("query_encoding_settings", {})
            .get("prompt")
        )

    corpus_cache_prompt = None
    if corpus_cache_metadata is not None:
        corpus_cache_prompt = (
            corpus_cache_metadata.get("cache_spec", {})
            .get("query_encoding_settings", {})
            .get("prompt")
        )

    audit = {
        "task_prompt_matches_default": task_prompt == expected_prompt,
        "query_cache_prompt_matches_task_prompt": (
            query_cache_prompt == task_prompt if query_cache_prompt is not None else None
        ),
        "corpus_cache_prompt_is_empty": (
            corpus_cache_prompt in (None, "") if corpus_cache_metadata is not None else None
        ),
        "query_embeddings_source": artifact_paths.get("query_embeddings_source"),
    }

    return {
        "run_dir": str(run_dir),
        "created_at_utc": payload.get("created_at_utc"),
        "task_preset": task_preset,
        "model_name": model_name,
        "payload": payload,
        "audit": audit,
    }


def flatten_success_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = record["payload"]
    config = payload["config"]
    dataset = payload["dataset"]
    timings = payload["timing_seconds"]
    design = payload["design_decisions"]
    task = record["task_preset"]
    metrics_payload = payload["metrics"][task]

    flattened = {
        "created_at_utc": record["created_at_utc"],
        "run_dir": record["run_dir"],
        "model_name": record["model_name"],
        "task_preset": task,
        "query_field_name": design["task"]["query_field_name"],
        "doc_field_name": design["task"]["doc_field_name"],
        "prompt": config["resolved_query_encoding_settings"][task].get("prompt"),
        "dataset_name": config["dataset_name"],
        "query_split": config["query_split"],
        "corpus_splits": ",".join(config["corpus_splits"]),
        "batch_size": config["batch_size"],
        "dtype": config["dtype"],
        "normalize": config["normalize"],
        "num_queries": metrics_payload["num_queries"],
        "top_k_evaluated": metrics_payload["top_k_evaluated"],
        "exact_match_at_1": metrics_payload["exact_match_at_1"],
        "recall_at_1": metrics_payload["recall_at_1"],
        "recall_at_5": metrics_payload["recall_at_5"],
        "recall_at_10": metrics_payload["recall_at_10"],
        "mrr": metrics_payload["mrr"],
        "query_original_size": dataset["query_original_size"],
        "evaluated_pairs": dataset["evaluated_pairs"],
        "corpus_selected_row_count_before_empty_filter": dataset["corpus_selected_row_count_before_empty_filter"],
        "model_load_seconds": timings["model_load"],
        "dataset_load_seconds": timings["dataset_load"],
        "encoding_seconds": timings["encoding"],
        "retrieval_seconds": timings["retrieval"],
        "total_seconds": timings["total"],
        "query_embeddings_source": record["audit"]["query_embeddings_source"],
        "task_prompt_matches_default": record["audit"]["task_prompt_matches_default"],
        "query_cache_prompt_matches_task_prompt": record["audit"]["query_cache_prompt_matches_task_prompt"],
        "corpus_cache_prompt_is_empty": record["audit"]["corpus_cache_prompt_is_empty"],
    }
    return flattened


def main() -> int:
    args = parse_args()
    results_dir = Path(args.results_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    newest_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for run_dir in sorted(results_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        classified = classify_success_run(run_dir, required_run_label=args.run_label)
        if classified is None:
            continue
        key = (classified["task_preset"], classified["model_name"])
        if key not in newest_by_key:
            newest_by_key[key] = classified

    flattened_rows = []
    audit_rows = []
    for key in sorted(newest_by_key.keys()):
        record = newest_by_key[key]
        flattened_rows.append(flatten_success_record(record))
        audit_rows.append(
            {
                "task_preset": record["task_preset"],
                "model_name": record["model_name"],
                "run_dir": record["run_dir"],
                **record["audit"],
            }
        )

    results_df = pd.DataFrame(flattened_rows)
    audit_df = pd.DataFrame(audit_rows)

    results_csv = output_dir / "latest_full_success_results.csv"
    results_json = output_dir / "latest_full_success_results.json"
    audit_csv = output_dir / "latest_full_success_audit.csv"
    audit_json = output_dir / "latest_full_success_audit.json"

    results_df.to_csv(results_csv, index=False)
    audit_df.to_csv(audit_csv, index=False)
    results_json.write_text(
        results_df.to_json(orient="records", indent=2),
        encoding="utf-8",
    )
    audit_json.write_text(
        audit_df.to_json(orient="records", indent=2),
        encoding="utf-8",
    )

    summary_payload = {
        "results_dir": str(results_dir),
        "output_dir": str(output_dir),
        "num_latest_success_runs": len(results_df),
        "results_csv": str(results_csv),
        "results_json": str(results_json),
        "audit_csv": str(audit_csv),
        "audit_json": str(audit_json),
    }
    (output_dir / "latest_full_success_summary.json").write_text(
        json.dumps(summary_payload, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )

    print(json.dumps(summary_payload, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
