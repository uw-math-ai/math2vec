"""
FrenzyMath benchmark runner.

This file intentionally documents the benchmark contract in code because the
results are likely to be run later on remote GPUs by someone who did not write
the benchmark.

What this benchmark measures:
- It treats each dataset row as one aligned pair:
  `informal_description` <-> (`type` or `signature`)
- It embeds every informal string and every Lean-side string independently.
- It runs exact nearest-neighbor retrieval in a single shared embedding space.
- It can evaluate either retrieval direction or both, depending on CLI settings.
- Ground truth is exact row alignment only. Row i is relevant only to row i.

Important design consequences:
- This is a 1-to-1 retrieval benchmark, not a many-to-many semantic relevance benchmark.
- Scores reflect how well a model recovers the exact paired row, not whether
  several formally equivalent rows might also be "reasonable" results.
- Choosing `--lean-field type` versus `--lean-field signature` changes the task.
  `type` is usually richer and is the default. `signature` is shorter and may
  be easier or harder depending on the model.
- Query instructions are direction-specific by default so instruction-aware
  models such as Harrier receive the explicitly requested retrieval prompt.
- By default the benchmark uses the held-out `test` split and L2-normalizes
  embeddings, which makes inner product equivalent to cosine similarity.
- Retrieval uses exact search. When FAISS is installed it uses FAISS; otherwise
  it falls back to a NumPy exact similarity computation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import platform
import socket
import subprocess
import sys
import time
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

import data
import metrics
import retriever
from encoder import Encoder
from model import RandomEmbedder, SentenceTransformerModel


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RESULTS_DIR = REPO_ROOT / "benchmarking" / "results" / "frenzymath"
DEFAULT_TOP_K_VALUES = (1, 5, 10)
DEFAULT_INFORMAL_TO_LEAN_TYPE_QUERY_PROMPT = (
    "Instruct: Find the most mathematically similar Lean type to this statement\n"
    "Query: "
)
DEFAULT_INFORMAL_TO_LEAN_SIGNATURE_QUERY_PROMPT = (
    "Instruct: Find the most mathematically similar Lean signature to this statement\n"
    "Query: "
)
DEFAULT_LEAN_TYPE_TO_INFORMAL_QUERY_PROMPT = (
    "Instruct: Find the most mathematically similar statement as a Lean type\n"
    "Query: "
)
DEFAULT_LEAN_SIGNATURE_TO_INFORMAL_QUERY_PROMPT = (
    "Instruct: Find the most mathematically similar statement as a Lean signature\n"
    "Query: "
)


@dataclass
class BenchmarkConfig:
    dataset_name: str
    query_split: str
    corpus_splits: list[str]
    directions: list[str]
    informal_field: str
    lean_field: str
    model_type: str
    model_name: str
    batch_size: int
    device: str | None
    dtype: str | None
    max_query_items: int | None
    max_corpus_items: int | None
    seed: int
    query_shuffle: bool
    corpus_shuffle: bool
    normalize: bool
    informal_to_lean_query_prompt_name: str | None
    informal_to_lean_type_query_prompt: str | None
    informal_to_lean_signature_query_prompt: str | None
    lean_to_informal_query_prompt_name: str | None
    lean_type_to_informal_query_prompt: str | None
    lean_signature_to_informal_query_prompt: str | None
    query_prompt_name: str | None
    query_prompt: str | None
    save_rankings: bool
    save_manifests: bool
    save_embeddings: bool
    save_embeddings_dtype: str
    results_dir: str


def parse_args(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark models on FrenzyMath by retrieving aligned informal and "
            "Lean statements in a shared embedding space."
        ),
        epilog=(
            "Most important arguments: --model-name, --directions, --lean-field, "
            "--query-split, --corpus-splits, --batch-size, and --device."
        ),
    )
    parser.add_argument(
        "--dataset-name",
        default="saharshb/mathlib-informal-split",
        help="Hugging Face dataset name. Defaults to the split FrenzyMath dataset.",
    )
    parser.add_argument(
        "--query-split",
        choices=["train", "val", "test"],
        default="test",
        help="Which split provides the benchmark queries. Defaults to test.",
    )
    parser.add_argument(
        "--split",
        dest="query_split",
        choices=["train", "val", "test"],
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--corpus-splits",
        default="train,val,test",
        help=(
            "Comma-separated splits used as the retrieval corpus. "
            "Default: train,val,test."
        ),
    )
    parser.add_argument(
        "--directions",
        default="informal_to_lean",
        help=(
            "Comma-separated retrieval directions to evaluate. "
            "Allowed values: informal_to_lean, lean_to_informal. "
            "Default: informal_to_lean."
        ),
    )
    parser.add_argument(
        "--informal-field",
        default="informal_description",
        help="Dataset column used as the informal-language side.",
    )
    parser.add_argument(
        "--lean-field",
        choices=["type", "signature"],
        default="type",
        help="Lean-side field to embed. Default: type.",
    )
    parser.add_argument(
        "--model-type",
        choices=["sentence-transformer", "random"],
        default="sentence-transformer",
        help="Embedding backend to use.",
    )
    parser.add_argument(
        "--model-name",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-Transformers model name or local path.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for encoding. Larger values use more memory.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Explicit device such as cpu or cuda. Defaults to auto-detect.",
    )
    parser.add_argument(
        "--dtype",
        choices=["float16", "bfloat16", "float32", "float64"],
        default=None,
        help="Optional torch dtype for loading sentence-transformer weights.",
    )
    parser.add_argument(
        "--max-query-items",
        type=int,
        default=None,
        help="Optional cap on query-side aligned pairs. Useful for smoke tests.",
    )
    parser.add_argument(
        "--max-items",
        dest="max_query_items",
        type=int,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--max-corpus-items",
        type=int,
        default=None,
        help="Optional cap on the retrieval corpus size. Useful for smoke tests only.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed used for dataset shuffling and reproducible random baselines.",
    )
    parser.add_argument(
        "--query-shuffle",
        action="store_true",
        default=False,
        help="Shuffle query rows before truncating with --max-query-items.",
    )
    parser.add_argument(
        "--corpus-shuffle",
        action="store_true",
        default=False,
        help="Shuffle corpus rows before truncating with --max-corpus-items.",
    )
    normalize_group = parser.add_mutually_exclusive_group()
    normalize_group.add_argument(
        "--normalize",
        dest="normalize",
        action="store_true",
        help="L2-normalize embeddings before retrieval. Default behavior.",
    )
    normalize_group.add_argument(
        "--no-normalize",
        dest="normalize",
        action="store_false",
        help="Disable L2 normalization.",
    )
    parser.set_defaults(normalize=True)
    parser.add_argument(
        "--results-dir",
        default=str(DEFAULT_RESULTS_DIR),
        help="Parent directory where benchmark run directories are created.",
    )
    parser.add_argument(
        "--save-rankings",
        action="store_true",
        default=False,
        help="Save full top-k rankings and scores for each query direction.",
    )
    parser.add_argument(
        "--save-manifests",
        action="store_true",
        default=True,
        help=(
            "Save query/corpus row manifests with stable hashes and identifiers. "
            "Enabled by default."
        ),
    )
    parser.add_argument(
        "--no-save-manifests",
        dest="save_manifests",
        action="store_false",
        help="Disable saving query/corpus row manifests.",
    )
    parser.add_argument(
        "--save-embeddings",
        action="store_true",
        default=False,
        help=(
            "Save encoded query/corpus embedding arrays for future re-analysis. "
            "Disabled by default because files can be large."
        ),
    )
    parser.add_argument(
        "--save-embeddings-dtype",
        choices=["float16", "float32"],
        default="float32",
        help=(
            "Dtype used when saving embeddings to disk. "
            "This does not affect retrieval math during the run."
        ),
    )
    parser.add_argument(
        "--informal-to-lean-query-prompt-name",
        default=None,
        help=(
            "Optional sentence-transformers prompt_name used when the query side "
            "is informal text and the corpus side is Lean."
        ),
    )
    parser.add_argument(
        "--informal-to-lean-type-query-prompt",
        default=None,
        help=(
            "Raw instruction prompt used when retrieving Lean type from informal "
            "queries. Defaults to the requested math-specific instruction."
        ),
    )
    parser.add_argument(
        "--informal-to-lean-signature-query-prompt",
        default=None,
        help=(
            "Raw instruction prompt used when retrieving Lean signature from "
            "informal queries. Defaults to the requested math-specific instruction."
        ),
    )
    parser.add_argument(
        "--lean-to-informal-query-prompt-name",
        default=None,
        help=(
            "Optional sentence-transformers prompt_name used when the query side "
            "is Lean and the corpus side is informal text."
        ),
    )
    parser.add_argument(
        "--lean-type-to-informal-query-prompt",
        default=None,
        help=(
            "Raw instruction prompt used when retrieving informal statements from "
            "Lean type queries. Defaults to the requested math-specific instruction."
        ),
    )
    parser.add_argument(
        "--lean-signature-to-informal-query-prompt",
        default=None,
        help=(
            "Raw instruction prompt used when retrieving informal statements from "
            "Lean signature queries. Defaults to the requested math-specific instruction."
        ),
    )
    parser.add_argument(
        "--query-prompt-name",
        default=None,
        help=(
            "Optional sentence-transformers prompt_name to apply to query encodes. "
            "Useful for models such as Harrier that expect instructed queries."
        ),
    )
    parser.add_argument(
        "--query-prompt",
        default=None,
        help="Optional raw prompt string to prepend to query encodes.",
    )
    args = parser.parse_args(argv)
    args.corpus_splits = [split.strip() for split in args.corpus_splits.split(",") if split.strip()]
    args.directions = [direction.strip() for direction in args.directions.split(",") if direction.strip()]
    if args.informal_to_lean_query_prompt_name is None and args.informal_to_lean_type_query_prompt is None:
        args.informal_to_lean_type_query_prompt = DEFAULT_INFORMAL_TO_LEAN_TYPE_QUERY_PROMPT
    if args.informal_to_lean_query_prompt_name is None and args.informal_to_lean_signature_query_prompt is None:
        args.informal_to_lean_signature_query_prompt = DEFAULT_INFORMAL_TO_LEAN_SIGNATURE_QUERY_PROMPT
    if args.lean_to_informal_query_prompt_name is None and args.lean_type_to_informal_query_prompt is None:
        args.lean_type_to_informal_query_prompt = DEFAULT_LEAN_TYPE_TO_INFORMAL_QUERY_PROMPT
    if args.lean_to_informal_query_prompt_name is None and args.lean_signature_to_informal_query_prompt is None:
        args.lean_signature_to_informal_query_prompt = DEFAULT_LEAN_SIGNATURE_TO_INFORMAL_QUERY_PROMPT
    validate_args(args)
    return args


def validate_args(args) -> None:
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be a positive integer.")
    if args.max_query_items is not None and args.max_query_items <= 0:
        raise ValueError("--max-query-items must be positive when provided.")
    if args.max_corpus_items is not None and args.max_corpus_items <= 0:
        raise ValueError("--max-corpus-items must be positive when provided.")
    if not args.corpus_splits:
        raise ValueError("--corpus-splits must contain at least one split.")
    allowed_directions = {"informal_to_lean", "lean_to_informal"}
    invalid_directions = [direction for direction in args.directions if direction not in allowed_directions]
    if invalid_directions:
        raise ValueError(
            f"Invalid direction(s): {invalid_directions}. "
            "Allowed values are informal_to_lean and lean_to_informal."
        )
    if not args.directions:
        raise ValueError("--directions must contain at least one direction.")
    if args.query_prompt_name is not None and args.query_prompt is not None:
        raise ValueError("Use only one of --query-prompt-name or --query-prompt.")
    if (
        args.informal_to_lean_query_prompt_name is not None
        and (
            args.informal_to_lean_type_query_prompt is not None
            or args.informal_to_lean_signature_query_prompt is not None
        )
    ):
        raise ValueError(
            "Use only one of --informal-to-lean-query-prompt-name or "
            "--informal-to-lean-*-query-prompt."
        )
    if (
        args.lean_to_informal_query_prompt_name is not None
        and (
            args.lean_type_to_informal_query_prompt is not None
            or args.lean_signature_to_informal_query_prompt is not None
        )
    ):
        raise ValueError(
            "Use only one of --lean-to-informal-query-prompt-name or "
            "--lean-*-to-informal-query-prompt."
        )


def _slugify(value: str) -> str:
    safe_characters = []
    for character in value:
        if character.isalnum() or character in {"-", "_", "."}:
            safe_characters.append(character)
        else:
            safe_characters.append("_")
    slug = "".join(safe_characters).strip("._")
    return slug or "value"


def _timestamp_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _aggregate(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.mean(values))


def build_progress_callback(logger: logging.Logger, stage_name: str, total_texts: int):
    stage_start = time.perf_counter()
    report_interval_batches = None

    def callback(progress: dict[str, int]) -> None:
        nonlocal report_interval_batches
        total_batches = progress["total_batches"]
        if total_batches == 0:
            return
        if report_interval_batches is None:
            report_interval_batches = max(1, total_batches // 20)

        batch_index = progress["batch_index"]
        should_report = (
            batch_index == 1
            or batch_index == total_batches
            or batch_index % report_interval_batches == 0
        )
        if not should_report:
            return

        elapsed = time.perf_counter() - stage_start
        texts_encoded = progress["texts_encoded"]
        percent = texts_encoded / total_texts * 100 if total_texts > 0 else 100.0
        logger.info(
            "%s progress: %s/%s texts (%.1f%%), batch %s/%s, elapsed %.1fs",
            stage_name,
            texts_encoded,
            total_texts,
            percent,
            batch_index,
            total_batches,
            elapsed,
        )

    return callback


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def _safe_package_version(package_name: str) -> str | None:
    try:
        from importlib.metadata import version

        return version(package_name)
    except Exception:
        return None


def _safe_git_commit(repo_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return None


def build_run_directory(args) -> Path:
    parent = Path(args.results_dir)
    timestamp = _timestamp_utc()
    model_part = _slugify(args.model_name if args.model_type != "random" else "random")
    corpus_part = _slugify("-".join(args.corpus_splits))
    run_dir = parent / f"{timestamp}_{_slugify(args.query_split)}_vs_{corpus_part}_{_slugify(args.lean_field)}_{model_part}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def setup_logging(run_dir: Path) -> logging.Logger:
    logger = logging.getLogger("frenzymath_benchmark")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    file_handler = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.propagate = False
    return logger


def benchmark_config_from_args(args) -> BenchmarkConfig:
    return BenchmarkConfig(
        dataset_name=args.dataset_name,
        query_split=args.query_split,
        corpus_splits=list(args.corpus_splits),
        directions=list(args.directions),
        informal_field=args.informal_field,
        lean_field=args.lean_field,
        model_type=args.model_type,
        model_name=args.model_name,
        batch_size=args.batch_size,
        device=args.device,
        dtype=args.dtype,
        max_query_items=args.max_query_items,
        max_corpus_items=args.max_corpus_items,
        seed=args.seed,
        query_shuffle=args.query_shuffle,
        corpus_shuffle=args.corpus_shuffle,
        normalize=args.normalize,
        informal_to_lean_query_prompt_name=args.informal_to_lean_query_prompt_name,
        informal_to_lean_type_query_prompt=args.informal_to_lean_type_query_prompt,
        informal_to_lean_signature_query_prompt=args.informal_to_lean_signature_query_prompt,
        lean_to_informal_query_prompt_name=args.lean_to_informal_query_prompt_name,
        lean_type_to_informal_query_prompt=args.lean_type_to_informal_query_prompt,
        lean_signature_to_informal_query_prompt=args.lean_signature_to_informal_query_prompt,
        query_prompt_name=args.query_prompt_name,
        query_prompt=args.query_prompt,
        save_rankings=args.save_rankings,
        save_manifests=args.save_manifests,
        save_embeddings=args.save_embeddings,
        save_embeddings_dtype=args.save_embeddings_dtype,
        results_dir=args.results_dir,
    )


def build_model(args):
    if args.model_type == "random":
        return RandomEmbedder(seed=args.seed)
    return SentenceTransformerModel(
        model_name=args.model_name,
        device=args.device,
        dtype=args.dtype,
    )


def dataset_to_rows(dataset, split_name: str, informal_key: str, lean_key: str):
    rows = []
    for row_index, record in enumerate(dataset):
        rows.append(
            {
                "row_key": f"{split_name}:{row_index}",
                "informal": record.get(informal_key),
                "lean": record.get(lean_key),
                "split": split_name,
                "row_index_within_split": row_index,
                "dataset_index": record.get("index"),
            }
        )
    return rows


def filter_valid_rows(rows):
    valid_rows = []
    dropped = 0
    for row in rows:
        if row["informal"] and row["lean"]:
            valid_rows.append(row)
        else:
            dropped += 1
    return valid_rows, dropped


def load_pairs(args):
    columns = [args.informal_field, args.lean_field]
    loaded_splits = data.load_mathlib_informal_splits(
        splits=sorted(set([args.query_split, *args.corpus_splits])),
        dataset_name=args.dataset_name,
        columns=columns,
    )

    query_dataset = loaded_splits[args.query_split]
    query_original_size = len(query_dataset)
    if args.query_shuffle:
        query_dataset = query_dataset.shuffle(seed=args.seed)
    if args.max_query_items is not None:
        query_dataset = query_dataset.select(range(min(args.max_query_items, len(query_dataset))))
    query_selected_rows = dataset_to_rows(
        query_dataset,
        split_name=args.query_split,
        informal_key=args.informal_field,
        lean_key=args.lean_field,
    )
    query_rows, query_dropped = filter_valid_rows(query_selected_rows)

    corpus_original_sizes = {split: len(loaded_splits[split]) for split in args.corpus_splits}
    ordered_corpus_splits = list(args.corpus_splits)
    if args.query_split in ordered_corpus_splits:
        ordered_corpus_splits = [args.query_split] + [
            split for split in ordered_corpus_splits if split != args.query_split
        ]

    corpus_rows = []
    for split in ordered_corpus_splits:
        corpus_rows.extend(
            dataset_to_rows(
                loaded_splits[split],
                split_name=split,
                informal_key=args.informal_field,
                lean_key=args.lean_field,
            )
        )
    corpus_selected_before_truncation = len(corpus_rows)
    if args.corpus_shuffle:
        rng = np.random.default_rng(args.seed)
        indices = rng.permutation(len(corpus_rows)).tolist()
        corpus_rows = [corpus_rows[index] for index in indices]
    if args.max_corpus_items is not None:
        corpus_rows = corpus_rows[: min(args.max_corpus_items, len(corpus_rows))]
    corpus_selected_rows = len(corpus_rows)
    corpus_rows, corpus_dropped = filter_valid_rows(corpus_rows)

    if not query_rows:
        raise ValueError(
            "No valid query rows were loaded. This usually means one of the "
            "selected columns is missing or contains empty values."
        )
    if not corpus_rows:
        raise ValueError(
            "No valid corpus rows were loaded. This usually means one of the "
            "selected columns is missing or contains empty values."
        )

    corpus_keys = {row["row_key"] for row in corpus_rows}
    matched_query_rows = [row for row in query_rows if row["row_key"] in corpus_keys]
    unmatched_query_count = len(query_rows) - len(matched_query_rows)
    if not matched_query_rows:
        raise ValueError(
            "None of the query rows have a corresponding row in the retrieval corpus. "
            "Check --query-split, --corpus-splits, and any query/corpus truncation."
        )

    return {
        "query_rows": matched_query_rows,
        "corpus_rows": corpus_rows,
        "query_original_size": query_original_size,
        "query_selected_row_count_before_empty_filter": len(query_selected_rows),
        "query_dropped_rows_due_to_missing_or_empty_text": query_dropped,
        "query_dropped_rows_due_to_missing_corpus_match": unmatched_query_count,
        "corpus_original_sizes_by_split": corpus_original_sizes,
        "corpus_selected_row_count_before_empty_filter": corpus_selected_rows,
        "corpus_dropped_rows_due_to_missing_or_empty_text": corpus_dropped,
        "corpus_selected_row_count_before_truncation": corpus_selected_before_truncation,
    }


def get_query_encode_kwargs(args, direction: str) -> dict[str, str]:
    encode_kwargs: dict[str, str] = {}

    if direction == "informal_to_lean":
        if args.informal_to_lean_query_prompt_name is not None:
            encode_kwargs["prompt_name"] = args.informal_to_lean_query_prompt_name
        elif args.lean_field == "type" and args.informal_to_lean_type_query_prompt is not None:
            encode_kwargs["prompt"] = args.informal_to_lean_type_query_prompt
        elif args.lean_field == "signature" and args.informal_to_lean_signature_query_prompt is not None:
            encode_kwargs["prompt"] = args.informal_to_lean_signature_query_prompt
    elif direction == "lean_to_informal":
        if args.lean_to_informal_query_prompt_name is not None:
            encode_kwargs["prompt_name"] = args.lean_to_informal_query_prompt_name
        elif args.lean_field == "type" and args.lean_type_to_informal_query_prompt is not None:
            encode_kwargs["prompt"] = args.lean_type_to_informal_query_prompt
        elif args.lean_field == "signature" and args.lean_signature_to_informal_query_prompt is not None:
            encode_kwargs["prompt"] = args.lean_signature_to_informal_query_prompt

    if not encode_kwargs:
        if args.query_prompt_name is not None:
            encode_kwargs["prompt_name"] = args.query_prompt_name
        elif args.query_prompt is not None:
            encode_kwargs["prompt"] = args.query_prompt

    return encode_kwargs


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_row_manifest_entry(row: dict[str, Any]) -> dict[str, Any]:
    informal = row["informal"]
    lean = row["lean"]
    pair_payload = json.dumps(
        {
            "informal": informal,
            "lean": lean,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return {
        "row_key": row["row_key"],
        "split": row["split"],
        "row_index_within_split": row["row_index_within_split"],
        "dataset_index": row.get("dataset_index"),
        "informal_hash": _hash_text(informal),
        "lean_hash": _hash_text(lean),
        "pair_hash": _hash_text(pair_payload),
        "informal_num_chars": len(informal),
        "lean_num_chars": len(lean),
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")


def save_manifests(run_dir: Path, pairing_metadata: dict[str, Any]) -> dict[str, str]:
    query_manifest_path = run_dir / "query_manifest.jsonl"
    corpus_manifest_path = run_dir / "corpus_manifest.jsonl"
    _write_jsonl(
        query_manifest_path,
        [build_row_manifest_entry(row) for row in pairing_metadata["query_rows"]],
    )
    _write_jsonl(
        corpus_manifest_path,
        [build_row_manifest_entry(row) for row in pairing_metadata["corpus_rows"]],
    )
    return {
        "query_manifest_file": str(query_manifest_path),
        "corpus_manifest_file": str(corpus_manifest_path),
    }


def _cast_embeddings_for_save(embeddings: np.ndarray, dtype_name: str) -> np.ndarray:
    dtype_map = {
        "float16": np.float16,
        "float32": np.float32,
    }
    return np.asarray(embeddings, dtype=dtype_map[dtype_name])


def save_embedding_artifacts(
    run_dir: Path,
    dtype_name: str,
    embedding_payload: dict[str, np.ndarray],
) -> dict[str, str]:
    saved_files = {}
    for artifact_name, embeddings in embedding_payload.items():
        path = run_dir / f"{artifact_name}.npy"
        np.save(path, _cast_embeddings_for_save(embeddings, dtype_name))
        saved_files[f"{artifact_name}_file"] = str(path)
    return saved_files


def compute_retrieval_summary(query_embeddings, corpus_embeddings, query_keys, corpus_keys):
    top_k_limit = min(max(DEFAULT_TOP_K_VALUES), len(corpus_embeddings))
    rankings, scores = retriever.retrieve_top_k(
        np.asarray(query_embeddings, dtype=np.float32),
        np.asarray(corpus_embeddings, dtype=np.float32),
        top_k_limit,
    )
    corpus_index_by_key = {key: index for index, key in enumerate(corpus_keys)}
    ranking_lists = [list(map(int, row)) for row in rankings]
    score_lists = [list(map(float, row)) for row in scores]
    target_indices = [corpus_index_by_key[key] for key in query_keys]
    ground_truth = [{target_index} for target_index in target_indices]

    summary = {
        "num_queries": len(ranking_lists),
        "top_k_evaluated": top_k_limit,
        "exact_match_at_1": _aggregate(
            [
                1.0 if retrieved and int(retrieved[0]) == target_index else 0.0
                for retrieved, target_index in zip(ranking_lists, target_indices)
            ]
        ),
        "mrr": _aggregate(metrics.reciprocal_ranks(ranking_lists, ground_truth)),
        "recall_at_1": _aggregate(metrics.recall_at_k(1, ranking_lists, ground_truth)),
        "recall_at_5": _aggregate(
            metrics.recall_at_k(min(5, top_k_limit), ranking_lists, ground_truth)
        ),
        "recall_at_10": _aggregate(
            metrics.recall_at_k(min(10, top_k_limit), ranking_lists, ground_truth)
        ),
    }

    return summary, ranking_lists, score_lists


def build_environment_metadata(model_instance) -> dict[str, Any]:
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "hostname": socket.gethostname(),
        "repo_root": str(REPO_ROOT),
        "git_commit": _safe_git_commit(REPO_ROOT),
        "packages": {
            "numpy": _safe_package_version("numpy"),
            "datasets": _safe_package_version("datasets"),
            "huggingface_hub": _safe_package_version("huggingface_hub"),
            "sentence-transformers": _safe_package_version("sentence-transformers"),
            "transformers": _safe_package_version("transformers"),
            "torch": _safe_package_version("torch"),
            "faiss-cpu": _safe_package_version("faiss-cpu"),
        },
        "retrieval_backend": "faiss" if retriever.faiss is not None else "numpy-fallback",
        "resolved_model_name": getattr(model_instance, "model_name", None),
    }


def build_results_payload(
    args,
    model_instance,
    pairing_metadata: dict[str, Any],
    metrics_payload: dict[str, Any],
    timings: dict[str, float],
    artifact_paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "benchmark_name": "frenzymath_shared_space_retrieval",
        "run_status": "success",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": asdict(benchmark_config_from_args(args)),
        "dataset": {
            "query_original_size": pairing_metadata["query_original_size"],
            "query_selected_row_count_before_empty_filter": pairing_metadata["query_selected_row_count_before_empty_filter"],
            "query_dropped_rows_due_to_missing_or_empty_text": pairing_metadata["query_dropped_rows_due_to_missing_or_empty_text"],
            "query_dropped_rows_due_to_missing_corpus_match": pairing_metadata["query_dropped_rows_due_to_missing_corpus_match"],
            "corpus_original_sizes_by_split": pairing_metadata["corpus_original_sizes_by_split"],
            "corpus_selected_row_count_before_truncation": pairing_metadata["corpus_selected_row_count_before_truncation"],
            "corpus_selected_row_count_before_empty_filter": pairing_metadata["corpus_selected_row_count_before_empty_filter"],
            "corpus_dropped_rows_due_to_missing_or_empty_text": pairing_metadata["corpus_dropped_rows_due_to_missing_or_empty_text"],
            "evaluated_pairs": len(pairing_metadata["query_rows"]),
            "ground_truth_definition": "Row i matches only row i.",
        },
        "design_decisions": {
            "retrieval_task": "exact aligned-pair retrieval",
            "directions": list(args.directions),
            "query_space": f"Queries come from the `{args.query_split}` split only.",
            "retrieval_corpus_space": "Retrieval corpus is built from these splits: " + ", ".join(args.corpus_splits),
            "normalization": (
                "Embeddings are L2-normalized before retrieval."
                if args.normalize
                else "Embeddings are used without L2 normalization."
            ),
            "similarity": "inner product over encoded vectors",
            "interpretation_caveat": (
                "This benchmark rewards recovery of the exact paired row only. "
                "Semantically related but different rows are counted as incorrect."
            ),
        },
        "environment": build_environment_metadata(model_instance),
        "metrics": metrics_payload,
        "timing_seconds": timings,
        "artifact_paths": artifact_paths,
    }


def save_success_artifacts(run_dir: Path, results: dict[str, Any], rankings_payload: dict[str, Any] | None) -> None:
    _json_dump(run_dir / "results.json", results)
    _json_dump(run_dir / "summary.json", results["metrics"])
    if rankings_payload is not None:
        _json_dump(run_dir / "rankings.json", rankings_payload)
    latest_payload = {
        "latest_run_dir": str(run_dir),
        "results_file": str(run_dir / "results.json"),
        "summary_file": str(run_dir / "summary.json"),
        "rankings_file": str(run_dir / "rankings.json") if rankings_payload is not None else None,
        "artifact_paths": results.get("artifact_paths", {}),
    }
    _json_dump(run_dir.parent / "LATEST_RUN.json", latest_payload)
    (run_dir.parent / "LATEST_RUN.txt").write_text(str(run_dir), encoding="utf-8")


def save_failure_artifacts(run_dir: Path, args, error: Exception) -> None:
    payload = {
        "benchmark_name": "frenzymath_shared_space_retrieval",
        "run_status": "failed",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": asdict(benchmark_config_from_args(args)),
        "error_type": type(error).__name__,
        "error_message": str(error),
        "traceback": traceback.format_exc(),
    }
    _json_dump(run_dir / "failure.json", payload)


def print_human_summary(results: dict[str, Any]) -> None:
    config = results["config"]
    dataset = results["dataset"]
    print("FrenzyMath benchmark complete.")
    print(f"Model: {config['model_name']}")
    print(f"Dataset: {config['dataset_name']}")
    print(f"Query split: {config['query_split']}")
    print(f"Retrieval corpus splits: {', '.join(config['corpus_splits'])}")
    print(f"Directions: {', '.join(config['directions'])}")
    print(f"Informal field: {config['informal_field']}")
    print(f"Lean field: {config['lean_field']}")
    print(f"Pairs evaluated: {dataset['evaluated_pairs']}")
    print(f"Query rows dropped for empty/missing text: {dataset['query_dropped_rows_due_to_missing_or_empty_text']}")
    print(f"Query rows dropped for missing corpus match: {dataset['query_dropped_rows_due_to_missing_corpus_match']}")
    print(f"Corpus rows dropped for empty/missing text: {dataset['corpus_dropped_rows_due_to_missing_or_empty_text']}")
    print(f"Retrieval backend: {results['environment']['retrieval_backend']}")
    if results.get("artifact_paths"):
        print("Extra artifacts saved:")
        for artifact_name, artifact_path in sorted(results["artifact_paths"].items()):
            print(f"  {artifact_name}: {artifact_path}")
    print()

    for direction, summary in results["metrics"].items():
        print(direction)
        print(f"  ExactMatch@1: {summary['exact_match_at_1']:.4f}")
        print(f"  Recall@1:     {summary['recall_at_1']:.4f}")
        print(f"  Recall@5:     {summary['recall_at_5']:.4f}")
        print(f"  Recall@10:    {summary['recall_at_10']:.4f}")
        print(f"  MRR:          {summary['mrr']:.4f}")
        print()


def run_benchmark(args, logger: logging.Logger, run_dir: Path) -> dict[str, Any]:
    overall_start = time.perf_counter()
    logger.info("Loading model.")
    model_start = time.perf_counter()
    model_instance = build_model(args)
    model_elapsed = time.perf_counter() - model_start

    logger.info("Loading dataset pairs.")
    dataset_start = time.perf_counter()
    pairing_metadata = load_pairs(args)
    dataset_elapsed = time.perf_counter() - dataset_start

    query_rows = pairing_metadata["query_rows"]
    corpus_rows = pairing_metadata["corpus_rows"]

    logger.info(
        "Encoding %s query rows against a retrieval corpus of %s rows.",
        len(query_rows),
        len(corpus_rows),
    )
    encode_start = time.perf_counter()
    encoder_instance = Encoder(
        model_instance,
        batch_size=args.batch_size,
        normalize=args.normalize,
    )
    corpus_informal_texts = [row["informal"] for row in corpus_rows]
    corpus_lean_texts = [row["lean"] for row in corpus_rows]

    corpus_informal_embeddings = encoder_instance.encode(
        corpus_informal_texts,
        progress_callback=build_progress_callback(
            logger,
            "Corpus informal encoding",
            len(corpus_informal_texts),
        ),
    )
    corpus_lean_embeddings = encoder_instance.encode(
        corpus_lean_texts,
        progress_callback=build_progress_callback(
            logger,
            "Corpus Lean encoding",
            len(corpus_lean_texts),
        ),
    )
    encode_elapsed = time.perf_counter() - encode_start

    logger.info("Computing retrieval metrics.")
    retrieval_start = time.perf_counter()
    query_keys = [row["row_key"] for row in query_rows]
    corpus_keys = [row["row_key"] for row in corpus_rows]
    metrics_payload = {}
    rankings_payload = {} if args.save_rankings else None
    artifact_paths: dict[str, str] = {}
    query_informal_embeddings = None
    query_lean_embeddings = None

    if "informal_to_lean" in args.directions:
        logger.info("Evaluating informal_to_lean retrieval.")
        query_informal_texts = [row["informal"] for row in query_rows]
        informal_query_encode_kwargs = get_query_encode_kwargs(args, "informal_to_lean")
        query_informal_embeddings = encoder_instance.encode(
            query_informal_texts,
            progress_callback=build_progress_callback(
                logger,
                "Query informal encoding",
                len(query_informal_texts),
            ),
            **informal_query_encode_kwargs,
        )
        informal_to_lean, informal_rankings, informal_scores = compute_retrieval_summary(
            query_informal_embeddings,
            corpus_lean_embeddings,
            query_keys=query_keys,
            corpus_keys=corpus_keys,
        )
        metrics_payload["informal_to_lean"] = informal_to_lean
        if rankings_payload is not None:
            rankings_payload["informal_to_lean"] = {
                "query_row_keys": list(query_keys),
                "corpus_row_keys": list(corpus_keys),
                "rankings": informal_rankings,
                "scores": informal_scores,
            }

    if "lean_to_informal" in args.directions:
        logger.info("Evaluating lean_to_informal retrieval.")
        query_lean_texts = [row["lean"] for row in query_rows]
        lean_query_encode_kwargs = get_query_encode_kwargs(args, "lean_to_informal")
        query_lean_embeddings = encoder_instance.encode(
            query_lean_texts,
            progress_callback=build_progress_callback(
                logger,
                "Query Lean encoding",
                len(query_lean_texts),
            ),
            **lean_query_encode_kwargs,
        )
        lean_to_informal, lean_rankings, lean_scores = compute_retrieval_summary(
            query_lean_embeddings,
            corpus_informal_embeddings,
            query_keys=query_keys,
            corpus_keys=corpus_keys,
        )
        metrics_payload["lean_to_informal"] = lean_to_informal
        if rankings_payload is not None:
            rankings_payload["lean_to_informal"] = {
                "query_row_keys": list(query_keys),
                "corpus_row_keys": list(corpus_keys),
                "rankings": lean_rankings,
                "scores": lean_scores,
            }
    retrieval_elapsed = time.perf_counter() - retrieval_start

    if args.save_manifests:
        logger.info("Saving query/corpus manifests.")
        artifact_paths.update(save_manifests(run_dir, pairing_metadata))

    if args.save_embeddings:
        logger.info("Saving embedding arrays as %s.", args.save_embeddings_dtype)
        embedding_payload = {
            "corpus_informal_embeddings": corpus_informal_embeddings,
            "corpus_lean_embeddings": corpus_lean_embeddings,
        }
        if query_informal_embeddings is not None:
            embedding_payload["query_informal_embeddings"] = query_informal_embeddings
        if query_lean_embeddings is not None:
            embedding_payload["query_lean_embeddings"] = query_lean_embeddings
        artifact_paths.update(
            save_embedding_artifacts(
                run_dir,
                args.save_embeddings_dtype,
                embedding_payload,
            )
        )

    total_elapsed = time.perf_counter() - overall_start
    timings = {
        "model_load": model_elapsed,
        "dataset_load": dataset_elapsed,
        "encoding": encode_elapsed,
        "retrieval": retrieval_elapsed,
        "total": total_elapsed,
    }
    results = build_results_payload(
        args,
        model_instance,
        pairing_metadata=pairing_metadata,
        metrics_payload=metrics_payload,
        timings=timings,
        artifact_paths=artifact_paths,
    )

    return {
        "results": results,
        "rankings_payload": rankings_payload,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_dir = build_run_directory(args)
    logger = setup_logging(run_dir)
    _json_dump(run_dir / "config.json", asdict(benchmark_config_from_args(args)))
    _json_dump(
        run_dir / "invocation.json",
        {
            "argv": sys.argv if argv is None else ["frenzymath_benchmark.py", *argv],
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "run_dir": str(run_dir),
            "latest_run_pointer_file": str(run_dir.parent / "LATEST_RUN.json"),
        },
    )

    try:
        logger.info("Starting benchmark. Run directory: %s", run_dir)
        payload = run_benchmark(args, logger, run_dir)
        results = payload["results"]
        rankings_payload = payload["rankings_payload"]
        save_success_artifacts(run_dir, results, rankings_payload)
        print_human_summary(results)
        print(f"Saved run artifacts to: {run_dir}")
        print(f"Latest run pointer: {run_dir.parent / 'LATEST_RUN.json'}")
        logger.info("Benchmark completed successfully.")
        return 0
    except Exception as error:
        logger.exception("Benchmark failed.")
        save_failure_artifacts(run_dir, args, error)
        print(f"Benchmark failed. See: {run_dir}")
        raise


if __name__ == "__main__":
    raise SystemExit(main())
