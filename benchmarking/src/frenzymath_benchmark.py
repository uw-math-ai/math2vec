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
import gc
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
DEFAULT_TYPE_TO_SIGNATURE_QUERY_PROMPT = (
    "Instruct: Find the most mathematically similar Lean signature to this Lean type\n"
    "Query: "
)
DEFAULT_SIGNATURE_TO_TYPE_QUERY_PROMPT = (
    "Instruct: Find the most mathematically similar Lean type to this Lean signature\n"
    "Query: "
)
TASK_PRESETS = {
    "informal_to_type": {
        "query_field_name": "informal_description",
        "doc_field_name": "type",
    },
    "type_to_informal": {
        "query_field_name": "type",
        "doc_field_name": "informal_description",
    },
    "informal_to_signature": {
        "query_field_name": "informal_description",
        "doc_field_name": "signature",
    },
    "signature_to_informal": {
        "query_field_name": "signature",
        "doc_field_name": "informal_description",
    },
    "type_to_signature": {
        "query_field_name": "type",
        "doc_field_name": "signature",
    },
    "signature_to_type": {
        "query_field_name": "signature",
        "doc_field_name": "type",
    },
}
TASK_PRESET_DEFAULT_PROMPTS = {
    "informal_to_type": DEFAULT_INFORMAL_TO_LEAN_TYPE_QUERY_PROMPT,
    "type_to_informal": DEFAULT_LEAN_TYPE_TO_INFORMAL_QUERY_PROMPT,
    "informal_to_signature": DEFAULT_INFORMAL_TO_LEAN_SIGNATURE_QUERY_PROMPT,
    "signature_to_informal": DEFAULT_LEAN_SIGNATURE_TO_INFORMAL_QUERY_PROMPT,
    "type_to_signature": DEFAULT_TYPE_TO_SIGNATURE_QUERY_PROMPT,
    "signature_to_type": DEFAULT_SIGNATURE_TO_TYPE_QUERY_PROMPT,
}


@dataclass
class BenchmarkConfig:
    dataset_name: str
    query_split: str
    corpus_splits: list[str]
    directions: list[str]
    task_preset: str | None
    query_field_name: str | None
    doc_field_name: str | None
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
    resolved_query_encoding_settings: dict[str, dict[str, str]]
    disable_default_direction_prompts: bool
    run_label: str | None
    reuse_run_dir: str | None
    auto_reuse_results: bool
    save_rankings: bool
    save_manifests: bool
    save_embeddings: bool
    save_embeddings_dtype: str
    embedding_cache_dir: str
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
        "--task-preset",
        choices=sorted(TASK_PRESETS.keys()),
        default=None,
        help=(
            "Optional single-task preset. When provided, the benchmark runs one "
            "explicit task with fixed query/document fields such as "
            "informal_to_type or type_to_signature."
        ),
    )
    parser.add_argument(
        "--query-field-name",
        default=None,
        help=(
            "Optional explicit dataset column used as the query side for the new "
            "single-task benchmark path."
        ),
    )
    parser.add_argument(
        "--doc-field-name",
        default=None,
        help=(
            "Optional explicit dataset column used as the retrieval corpus side "
            "for the new single-task benchmark path."
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
        "--run-label",
        default=None,
        help=(
            "Optional short label injected into the run directory name, "
            "for example FULL or DEBUG."
        ),
    )
    parser.add_argument(
        "--reuse-run-dir",
        default=None,
        help=(
            "Optional prior run directory to reuse compatible saved embedding "
            "arrays from."
        ),
    )
    parser.add_argument(
        "--auto-reuse-results",
        dest="auto_reuse_results",
        action="store_true",
        help=(
            "Automatically scan the results directory for a compatible prior run "
            "and reuse any matching saved embedding arrays."
        ),
    )
    parser.add_argument(
        "--no-auto-reuse-results",
        dest="auto_reuse_results",
        action="store_false",
        help="Disable automatic scan for reusable embedding artifacts.",
    )
    parser.set_defaults(auto_reuse_results=True)
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
    parser.add_argument(
        "--disable-default-direction-prompts",
        action="store_true",
        default=False,
        help=(
            "Disable the built-in direction-specific prompts. This is useful for "
            "pure no-prompt benchmarking runs."
        ),
    )
    parser.add_argument(
        "--embedding-cache-dir",
        default=None,
        help=(
            "Directory for reusable embedding caches and resumable partial "
            "artifacts. Defaults to <results-dir>/_embedding_cache."
        ),
    )
    args = parser.parse_args(argv)
    args.corpus_splits = [split.strip() for split in args.corpus_splits.split(",") if split.strip()]
    args.directions = [direction.strip() for direction in args.directions.split(",") if direction.strip()]
    if args.embedding_cache_dir is None:
        args.embedding_cache_dir = str(Path(args.results_dir) / "_embedding_cache")
    if not args.disable_default_direction_prompts:
        if args.informal_to_lean_query_prompt_name is None and args.informal_to_lean_type_query_prompt is None:
            args.informal_to_lean_type_query_prompt = DEFAULT_INFORMAL_TO_LEAN_TYPE_QUERY_PROMPT
        if args.informal_to_lean_query_prompt_name is None and args.informal_to_lean_signature_query_prompt is None:
            args.informal_to_lean_signature_query_prompt = DEFAULT_INFORMAL_TO_LEAN_SIGNATURE_QUERY_PROMPT
        if args.lean_to_informal_query_prompt_name is None and args.lean_type_to_informal_query_prompt is None:
            args.lean_type_to_informal_query_prompt = DEFAULT_LEAN_TYPE_TO_INFORMAL_QUERY_PROMPT
        if args.lean_to_informal_query_prompt_name is None and args.lean_signature_to_informal_query_prompt is None:
            args.lean_signature_to_informal_query_prompt = DEFAULT_LEAN_SIGNATURE_TO_INFORMAL_QUERY_PROMPT
    validate_args(args)
    task_spec = resolve_single_task_spec(args)
    if task_spec is not None:
        args.directions = [task_spec["task_label"]]
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
    if args.task_preset is not None and (
        args.query_field_name is not None or args.doc_field_name is not None
    ):
        raise ValueError(
            "Use either --task-preset or the explicit --query-field-name/--doc-field-name "
            "pair, not both."
        )
    if (args.query_field_name is None) != (args.doc_field_name is None):
        raise ValueError(
            "--query-field-name and --doc-field-name must be provided together."
        )
    allowed_directions = {"informal_to_lean", "lean_to_informal"}
    invalid_directions = [direction for direction in args.directions if direction not in allowed_directions]
    if invalid_directions:
        if args.task_preset is None and args.query_field_name is None:
            raise ValueError(
                f"Invalid direction(s): {invalid_directions}. "
                "Allowed values are informal_to_lean and lean_to_informal."
            )
    if not args.directions:
        if args.task_preset is None and args.query_field_name is None:
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
    if args.task_preset is not None:
        task_part = _slugify(args.task_preset)
    elif args.query_field_name is not None and args.doc_field_name is not None:
        task_part = _slugify(f"{args.query_field_name}_to_{args.doc_field_name}")
    else:
        task_part = _slugify("-".join(args.directions) + f"_{args.lean_field}")
    label_part = f"{_slugify(args.run_label)}_" if args.run_label else ""
    run_dir = parent / (
        f"{timestamp}_{label_part}{_slugify(args.query_split)}_vs_{corpus_part}_"
        f"{task_part}_{model_part}"
    )
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
        task_preset=args.task_preset,
        query_field_name=args.query_field_name,
        doc_field_name=args.doc_field_name,
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
        resolved_query_encoding_settings=build_resolved_query_encoding_settings(args),
        disable_default_direction_prompts=args.disable_default_direction_prompts,
        run_label=args.run_label,
        reuse_run_dir=args.reuse_run_dir,
        auto_reuse_results=args.auto_reuse_results,
        save_rankings=args.save_rankings,
        save_manifests=args.save_manifests,
        save_embeddings=args.save_embeddings,
        save_embeddings_dtype=args.save_embeddings_dtype,
        embedding_cache_dir=args.embedding_cache_dir,
        results_dir=args.results_dir,
    )


def resolve_single_task_spec(args) -> dict[str, str] | None:
    if args.task_preset is not None:
        preset = TASK_PRESETS[args.task_preset]
        return {
            "task_label": args.task_preset,
            "query_field_name": preset["query_field_name"],
            "doc_field_name": preset["doc_field_name"],
        }

    if args.query_field_name is not None and args.doc_field_name is not None:
        return {
            "task_label": f"{args.query_field_name}_to_{args.doc_field_name}",
            "query_field_name": args.query_field_name,
            "doc_field_name": args.doc_field_name,
        }

    return None


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


def get_single_task_query_encode_kwargs(args, task_label: str) -> dict[str, str]:
    if args.query_prompt_name is not None:
        return {
            "prompt_name": args.query_prompt_name,
        }
    if args.query_prompt is not None:
        return {
            "prompt": args.query_prompt,
        }
    if args.disable_default_direction_prompts:
        return {}
    default_prompt = TASK_PRESET_DEFAULT_PROMPTS.get(task_label)
    if default_prompt is None:
        return {}
    return {
        "prompt": default_prompt,
    }


def build_resolved_query_encoding_settings(args) -> dict[str, dict[str, str]]:
    task_spec = resolve_single_task_spec(args)
    if task_spec is not None:
        return {
            task_spec["task_label"]: get_single_task_query_encode_kwargs(
                args,
                task_spec["task_label"],
            )
        }

    settings: dict[str, dict[str, str]] = {}
    for direction in args.directions:
        settings[direction] = get_query_encode_kwargs(args, direction)
    return settings


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


def save_single_embedding_artifact(
    run_dir: Path,
    dtype_name: str,
    artifact_name: str,
    embeddings: np.ndarray,
) -> dict[str, str]:
    path = run_dir / f"{artifact_name}.npy"
    np.save(path, _cast_embeddings_for_save(embeddings, dtype_name))
    return {f"{artifact_name}_file": str(path)}


def dataset_to_text_rows(dataset, split_name: str, text_field_name: str):
    rows = []
    for row_index, record in enumerate(dataset):
        rows.append(
            {
                "row_key": f"{split_name}:{row_index}",
                "text": record.get(text_field_name),
                "text_field_name": text_field_name,
                "split": split_name,
                "row_index_within_split": row_index,
                "dataset_index": record.get("index"),
            }
        )
    return rows


def filter_valid_text_rows(rows):
    valid_rows = []
    dropped = 0
    for row in rows:
        if row["text"]:
            valid_rows.append(row)
        else:
            dropped += 1
    return valid_rows, dropped


def build_text_manifest_entry(row: dict[str, Any]) -> dict[str, Any]:
    text = row["text"]
    return {
        "row_key": row["row_key"],
        "split": row["split"],
        "row_index_within_split": row["row_index_within_split"],
        "dataset_index": row.get("dataset_index"),
        "text_field_name": row["text_field_name"],
        "text_hash": _hash_text(text),
        "text_num_chars": len(text),
    }


def save_text_row_manifest(path: Path, rows: list[dict[str, Any]]) -> str:
    _write_jsonl(path, [build_text_manifest_entry(row) for row in rows])
    return str(path)


def save_single_task_manifests(run_dir: Path, pairing_metadata: dict[str, Any]) -> dict[str, str]:
    query_manifest_path = run_dir / "query_manifest.jsonl"
    corpus_manifest_path = run_dir / "corpus_manifest.jsonl"
    query_field_corpus_manifest_path = run_dir / "query_field_corpus_manifest.jsonl"
    save_text_row_manifest(query_manifest_path, pairing_metadata["query_rows"])
    save_text_row_manifest(corpus_manifest_path, pairing_metadata["corpus_rows"])
    save_text_row_manifest(
        query_field_corpus_manifest_path,
        pairing_metadata["query_field_corpus_rows"],
    )
    return {
        "query_manifest_file": str(query_manifest_path),
        "corpus_manifest_file": str(corpus_manifest_path),
        "query_field_corpus_manifest_file": str(query_field_corpus_manifest_path),
    }


def load_single_task_pairs(args, task_spec: dict[str, str]) -> dict[str, Any]:
    query_field_name = task_spec["query_field_name"]
    doc_field_name = task_spec["doc_field_name"]
    columns = sorted(set([query_field_name, doc_field_name]))
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
    query_rows = dataset_to_text_rows(
        query_dataset,
        split_name=args.query_split,
        text_field_name=query_field_name,
    )
    query_selected_before_empty_filter = len(query_rows)
    query_rows, query_dropped = filter_valid_text_rows(query_rows)

    corpus_original_sizes = {split: len(loaded_splits[split]) for split in args.corpus_splits}
    ordered_corpus_splits = list(args.corpus_splits)
    if args.query_split in ordered_corpus_splits:
        ordered_corpus_splits = [args.query_split] + [
            split for split in ordered_corpus_splits if split != args.query_split
        ]

    corpus_rows = []
    for split in ordered_corpus_splits:
        corpus_rows.extend(
            dataset_to_text_rows(
                loaded_splits[split],
                split_name=split,
                text_field_name=doc_field_name,
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
    corpus_rows, corpus_dropped = filter_valid_text_rows(corpus_rows)

    query_field_corpus_rows = []
    for split in ordered_corpus_splits:
        query_field_corpus_rows.extend(
            dataset_to_text_rows(
                loaded_splits[split],
                split_name=split,
                text_field_name=query_field_name,
            )
        )
    query_field_corpus_rows, query_field_corpus_dropped = filter_valid_text_rows(
        query_field_corpus_rows
    )

    if not query_rows:
        raise ValueError(
            "No valid query rows were loaded for this task. This usually means the "
            "selected query field is missing or empty."
        )
    if not corpus_rows:
        raise ValueError(
            "No valid corpus rows were loaded for this task. This usually means the "
            "selected document field is missing or empty."
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
        "task_label": task_spec["task_label"],
        "query_field_name": query_field_name,
        "doc_field_name": doc_field_name,
        "query_rows": matched_query_rows,
        "corpus_rows": corpus_rows,
        "query_field_corpus_rows": query_field_corpus_rows,
        "query_original_size": query_original_size,
        "query_selected_row_count_before_empty_filter": query_selected_before_empty_filter,
        "query_dropped_rows_due_to_missing_or_empty_text": query_dropped,
        "query_dropped_rows_due_to_missing_corpus_match": unmatched_query_count,
        "corpus_original_sizes_by_split": corpus_original_sizes,
        "corpus_selected_row_count_before_empty_filter": corpus_selected_rows,
        "corpus_dropped_rows_due_to_missing_or_empty_text": corpus_dropped,
        "corpus_selected_row_count_before_truncation": corpus_selected_before_truncation,
        "query_field_corpus_dropped_rows_due_to_missing_or_empty_text": query_field_corpus_dropped,
    }


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def _load_embedding_file(path: Path) -> np.ndarray:
    return np.asarray(np.load(path), dtype=np.float32)


def _stable_json_string(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True)


def _hash_json_payload(payload: Any) -> str:
    return hashlib.sha256(_stable_json_string(payload).encode("utf-8")).hexdigest()


def _normalize_embeddings_array(embeddings: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    return embeddings / norms


def is_recoverable_batch_error(error: Exception) -> bool:
    message = str(error).lower()
    return (
        "out of memory" in message
        or "no valid execution plans built" in message
        or "cudnn frontend error" in message
        or "cuda error" in message
    )


def build_cache_rows_manifest(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_text_manifest_entry(row) for row in rows]


def build_embedding_cache_spec(
    args,
    artifact_kind: str,
    text_field_name: str,
    rows: list[dict[str, Any]],
    encode_kwargs: dict[str, str],
) -> dict[str, Any]:
    row_manifest = build_cache_rows_manifest(rows)
    return {
        "cache_schema_version": 1,
        "artifact_kind": artifact_kind,
        "dataset_name": args.dataset_name,
        "text_field_name": text_field_name,
        "model_type": args.model_type,
        "model_name": args.model_name,
        "normalize": args.normalize,
        "query_encoding_settings": dict(encode_kwargs),
        "row_manifest_hash": _hash_json_payload(row_manifest),
        "row_count": len(row_manifest),
    }


def cache_dir_from_spec(cache_root: Path, cache_spec: dict[str, Any]) -> Path:
    cache_key = _hash_json_payload(cache_spec)[:24]
    text_field_slug = _slugify(cache_spec["text_field_name"])
    artifact_slug = _slugify(cache_spec["artifact_kind"])
    return cache_root / f"{artifact_slug}_{text_field_slug}_{cache_key}"


def save_cache_metadata(path: Path, payload: dict[str, Any]) -> None:
    _json_dump(path, payload)


def encode_rows_with_persistent_cache(
    args,
    logger: logging.Logger,
    model_instance,
    rows: list[dict[str, Any]],
    text_field_name: str,
    artifact_kind: str,
    encode_kwargs: dict[str, str],
) -> tuple[np.ndarray, dict[str, str]]:
    cache_root = Path(args.embedding_cache_dir)
    cache_root.mkdir(parents=True, exist_ok=True)
    cache_spec = build_embedding_cache_spec(
        args,
        artifact_kind=artifact_kind,
        text_field_name=text_field_name,
        rows=rows,
        encode_kwargs=encode_kwargs,
    )
    artifact_dir = cache_dir_from_spec(cache_root, cache_spec)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    cache_metadata_path = artifact_dir / "cache_metadata.json"
    cache_manifest_path = artifact_dir / "rows_manifest.jsonl"
    cache_embeddings_path = artifact_dir / "embeddings.npy"

    if not cache_manifest_path.exists():
        save_text_row_manifest(cache_manifest_path, rows)

    existing_metadata = None
    if cache_metadata_path.exists():
        try:
            existing_metadata = _json_load(cache_metadata_path)
        except Exception:
            existing_metadata = None

    if existing_metadata is not None:
        existing_spec = existing_metadata.get("cache_spec")
        if existing_spec != cache_spec:
            raise ValueError(
                "Cache metadata exists but does not match the current cache specification: "
                f"{artifact_dir}"
            )
        if (
            existing_metadata.get("status") == "complete"
            and cache_embeddings_path.exists()
            and existing_metadata.get("rows_encoded") == len(rows)
        ):
            logger.info("Reusing completed embedding cache: %s", cache_embeddings_path)
            return _load_embedding_file(cache_embeddings_path), {
                f"{artifact_kind}_cache_dir": str(artifact_dir),
                f"{artifact_kind}_cache_embeddings_file": str(cache_embeddings_path),
                f"{artifact_kind}_cache_metadata_file": str(cache_metadata_path),
                f"{artifact_kind}_cache_manifest_file": str(cache_manifest_path),
            }

    metadata = {
        "cache_spec": cache_spec,
        "status": "in_progress",
        "rows_encoded": 0,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "cache_dir": str(artifact_dir),
        "embeddings_file": str(cache_embeddings_path),
        "rows_manifest_file": str(cache_manifest_path),
        "storage_dtype": args.save_embeddings_dtype,
        "batch_size_hint": args.batch_size,
        "last_successful_batch_size": None,
        "documentation": {
            "purpose": (
                "Reusable embedding cache for a single text field, model, prompt "
                "configuration, and exact row selection."
            ),
            "safe_to_reuse_when": (
                "cache_spec matches exactly, including dataset, model, field name, "
                "normalization, query prompt settings, and row_manifest_hash."
            ),
        },
    }
    if existing_metadata is not None:
        metadata["rows_encoded"] = int(existing_metadata.get("rows_encoded", 0))
        metadata["created_at_utc"] = existing_metadata.get(
            "created_at_utc",
            metadata["created_at_utc"],
        )
    if metadata["rows_encoded"] > 0 and not cache_embeddings_path.exists():
        logger.warning(
            "Cache metadata reported partial progress but the embeddings file is missing. Restarting this cache from scratch: %s",
            artifact_dir,
        )
        metadata["rows_encoded"] = 0
    save_cache_metadata(cache_metadata_path, metadata)

    memmap = None
    start_index = int(metadata["rows_encoded"])
    if cache_embeddings_path.exists() and start_index > 0:
        memmap = np.load(cache_embeddings_path, mmap_mode="r+")

    total_rows = len(rows)
    current_batch_size = args.batch_size
    batch_counter = 0
    next_report_fraction = 0.05

    batch_start = start_index
    while batch_start < total_rows:
        batch_counter += 1
        batch_end = min(batch_start + current_batch_size, total_rows)
        batch_texts = [row["text"] for row in rows[batch_start:batch_end]]
        try:
            batch_embeddings = np.asarray(
                model_instance.encode(batch_texts, **encode_kwargs),
                dtype=np.float32,
            )
        except RuntimeError as error:
            if not is_recoverable_batch_error(error) or current_batch_size <= 1:
                raise
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass
            next_batch_size = max(1, current_batch_size // 2)
            logger.warning(
                "%s cache hit a recoverable GPU batch failure at rows %s:%s with batch size %s. "
                "Error was: %s. Retrying with batch size %s.",
                artifact_kind,
                batch_start,
                batch_end,
                current_batch_size,
                error,
                next_batch_size,
            )
            current_batch_size = next_batch_size
            metadata["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
            metadata["last_recoverable_batch_error"] = str(error)
            metadata["current_retry_batch_size"] = current_batch_size
            save_cache_metadata(cache_metadata_path, metadata)
            continue
        if args.normalize:
            batch_embeddings = _normalize_embeddings_array(batch_embeddings)
        if memmap is None:
            save_dtype = np.float16 if args.save_embeddings_dtype == "float16" else np.float32
            memmap = np.lib.format.open_memmap(
                cache_embeddings_path,
                mode="w+",
                dtype=save_dtype,
                shape=(total_rows, batch_embeddings.shape[1]),
            )
            metadata["embedding_dim"] = int(batch_embeddings.shape[1])
        memmap[batch_start:batch_end] = _cast_embeddings_for_save(
            batch_embeddings,
            args.save_embeddings_dtype,
        )
        memmap.flush()
        metadata["rows_encoded"] = batch_end
        metadata["last_successful_batch_size"] = len(batch_texts)
        metadata["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
        save_cache_metadata(cache_metadata_path, metadata)

        completed_fraction = batch_end / total_rows if total_rows else 1.0
        should_report = (
            batch_counter == 1
            or batch_end == total_rows
            or completed_fraction >= next_report_fraction
        )
        if should_report:
            logger.info(
                "%s cache progress: %s/%s texts (%.1f%%), current batch size %s",
                artifact_kind,
                batch_end,
                total_rows,
                (batch_end / total_rows * 100.0) if total_rows else 100.0,
                len(batch_texts),
            )
            while completed_fraction >= next_report_fraction:
                next_report_fraction += 0.05
        batch_start = batch_end

    metadata["status"] = "complete"
    metadata["rows_encoded"] = total_rows
    metadata["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["updated_at_utc"] = metadata["completed_at_utc"]
    save_cache_metadata(cache_metadata_path, metadata)
    logger.info("Completed embedding cache: %s", cache_embeddings_path)
    return _load_embedding_file(cache_embeddings_path), {
        f"{artifact_kind}_cache_dir": str(artifact_dir),
        f"{artifact_kind}_cache_embeddings_file": str(cache_embeddings_path),
        f"{artifact_kind}_cache_metadata_file": str(cache_metadata_path),
        f"{artifact_kind}_cache_manifest_file": str(cache_manifest_path),
    }


def slice_query_embeddings_from_corpus_cache(
    query_rows: list[dict[str, Any]],
    corpus_rows: list[dict[str, Any]],
    corpus_embeddings: np.ndarray,
) -> np.ndarray:
    corpus_index_by_key = {}
    for index, row in enumerate(corpus_rows):
        corpus_index_by_key[row["row_key"]] = index
    query_indices = []
    for row in query_rows:
        query_indices.append(corpus_index_by_key[row["row_key"]])
    return np.asarray(corpus_embeddings[query_indices], dtype=np.float32)


def should_slice_query_from_corpus_cache(args, encode_kwargs: dict[str, str]) -> bool:
    return not encode_kwargs and args.query_split in args.corpus_splits


def _compatible_base_reuse_config(current_args, source_config: dict[str, Any]) -> bool:
    return (
        source_config.get("dataset_name") == current_args.dataset_name
        and source_config.get("model_type") == current_args.model_type
        and source_config.get("model_name") == current_args.model_name
        and source_config.get("lean_field") == current_args.lean_field
        and source_config.get("informal_field") == current_args.informal_field
        and source_config.get("normalize") == current_args.normalize
    )


def resolve_reuse_run_dir(args, logger: logging.Logger, current_run_dir: Path | None = None) -> Path | None:
    if args.reuse_run_dir is not None:
        return Path(args.reuse_run_dir)

    if not args.auto_reuse_results:
        return None

    results_dir = Path(args.results_dir)
    if not results_dir.exists():
        return None

    candidates = []
    for run_dir in sorted(results_dir.iterdir(), reverse=True):
        if current_run_dir is not None and run_dir == current_run_dir:
            continue
        if not run_dir.is_dir():
            continue
        config_path = run_dir / "config.json"
        if not config_path.exists():
            continue
        try:
            source_config = _json_load(config_path)
        except Exception:
            continue
        if _compatible_base_reuse_config(args, source_config):
            candidates.append(run_dir)

    if candidates:
        logger.info("Auto-selected reuse candidate run dir: %s", candidates[0])
        return candidates[0]

    return None


def load_reusable_embeddings(
    args,
    pairing_metadata: dict[str, Any],
    logger: logging.Logger,
    current_run_dir: Path | None = None,
):
    reusable_embeddings: dict[str, np.ndarray] = {}
    reused_artifact_paths: dict[str, str] = {}

    source_run_dir = resolve_reuse_run_dir(args, logger, current_run_dir=current_run_dir)
    if source_run_dir is None:
        return reusable_embeddings, reused_artifact_paths
    source_config_path = source_run_dir / "config.json"
    source_query_manifest_path = source_run_dir / "query_manifest.jsonl"
    source_corpus_manifest_path = source_run_dir / "corpus_manifest.jsonl"

    if not source_config_path.exists():
        logger.warning("Reuse run dir has no config.json: %s", source_run_dir)
        return reusable_embeddings, reused_artifact_paths
    if not source_query_manifest_path.exists() or not source_corpus_manifest_path.exists():
        logger.warning(
            "Reuse run dir is missing query/corpus manifests, so embeddings cannot be safely reused: %s",
            source_run_dir,
        )
        return reusable_embeddings, reused_artifact_paths

    source_config = _json_load(source_config_path)
    if not _compatible_base_reuse_config(args, source_config):
        logger.warning("Reuse run dir config is incompatible with current run: %s", source_run_dir)
        return reusable_embeddings, reused_artifact_paths

    current_query_manifest = [
        build_row_manifest_entry(row) for row in pairing_metadata["query_rows"]
    ]
    current_corpus_manifest = [
        build_row_manifest_entry(row) for row in pairing_metadata["corpus_rows"]
    ]
    source_query_manifest = _read_jsonl(source_query_manifest_path)
    source_corpus_manifest = _read_jsonl(source_corpus_manifest_path)

    if source_corpus_manifest == current_corpus_manifest:
        for artifact_name in ("corpus_informal_embeddings", "corpus_lean_embeddings"):
            path = source_run_dir / f"{artifact_name}.npy"
            if path.exists():
                reusable_embeddings[artifact_name] = _load_embedding_file(path)
                reused_artifact_paths[f"reused_{artifact_name}_file"] = str(path)
    else:
        logger.info("Reuse run dir corpus manifest does not match current corpus selection.")

    if source_query_manifest == current_query_manifest:
        source_settings = source_config.get("resolved_query_encoding_settings", {})
        current_settings = build_resolved_query_encoding_settings(args)

        if (
            "informal_to_lean" in args.directions
            and source_settings.get("informal_to_lean") == current_settings.get("informal_to_lean")
        ):
            path = source_run_dir / "query_informal_embeddings.npy"
            if path.exists():
                reusable_embeddings["query_informal_embeddings"] = _load_embedding_file(path)
                reused_artifact_paths["reused_query_informal_embeddings_file"] = str(path)

        if (
            "lean_to_informal" in args.directions
            and source_settings.get("lean_to_informal") == current_settings.get("lean_to_informal")
        ):
            path = source_run_dir / "query_lean_embeddings.npy"
            if path.exists():
                reusable_embeddings["query_lean_embeddings"] = _load_embedding_file(path)
                reused_artifact_paths["reused_query_lean_embeddings_file"] = str(path)
    else:
        logger.info("Reuse run dir query manifest does not match current query selection.")

    if reused_artifact_paths:
        logger.info(
            "Reusing compatible saved embedding artifacts: %s",
            json.dumps(reused_artifact_paths, ensure_ascii=True),
        )
    else:
        logger.info("No compatible saved embedding artifacts were found in reuse run dir.")

    return reusable_embeddings, reused_artifact_paths


def needs_corpus_informal_embeddings(args) -> bool:
    return "lean_to_informal" in args.directions


def needs_corpus_lean_embeddings(args) -> bool:
    return "informal_to_lean" in args.directions


def needs_query_informal_embeddings(args) -> bool:
    return "informal_to_lean" in args.directions


def needs_query_lean_embeddings(args) -> bool:
    return "lean_to_informal" in args.directions


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
    task_spec = resolve_single_task_spec(args)
    if task_spec is not None:
        task_metadata = {
            "task_label": task_spec["task_label"],
            "query_field_name": task_spec["query_field_name"],
            "doc_field_name": task_spec["doc_field_name"],
        }
        query_space_text = (
            f"Queries come from the `{args.query_split}` split only using the "
            f"`{task_spec['query_field_name']}` field."
        )
        corpus_space_text = (
            "Retrieval corpus is built from these splits using the "
            f"`{task_spec['doc_field_name']}` field: " + ", ".join(args.corpus_splits)
        )
    else:
        task_metadata = {
            "task_label": None,
            "query_field_name": args.informal_field if "informal_to_lean" in args.directions else args.lean_field,
            "doc_field_name": args.lean_field if "informal_to_lean" in args.directions else args.informal_field,
        }
        query_space_text = f"Queries come from the `{args.query_split}` split only."
        corpus_space_text = "Retrieval corpus is built from these splits: " + ", ".join(args.corpus_splits)

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
            "task": task_metadata,
            "resolved_query_encoding_settings": build_resolved_query_encoding_settings(args),
            "query_space": query_space_text,
            "retrieval_corpus_space": corpus_space_text,
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


def run_single_task_benchmark(args, logger: logging.Logger, run_dir: Path) -> dict[str, Any]:
    task_spec = resolve_single_task_spec(args)
    if task_spec is None:
        raise ValueError("Single-task benchmark path requires a resolved task spec.")

    overall_start = time.perf_counter()
    logger.info("Loading model.")
    model_start = time.perf_counter()
    model_instance = build_model(args)
    model_elapsed = time.perf_counter() - model_start

    logger.info("Loading single-task dataset pairs for %s.", task_spec["task_label"])
    dataset_start = time.perf_counter()
    pairing_metadata = load_single_task_pairs(args, task_spec)
    dataset_elapsed = time.perf_counter() - dataset_start

    artifact_paths: dict[str, str] = {}
    if args.save_manifests:
        logger.info("Saving query/corpus manifests before encoding.")
        artifact_paths.update(save_single_task_manifests(run_dir, pairing_metadata))

    query_rows = pairing_metadata["query_rows"]
    corpus_rows = pairing_metadata["corpus_rows"]
    query_field_corpus_rows = pairing_metadata["query_field_corpus_rows"]
    query_encode_kwargs = get_single_task_query_encode_kwargs(
        args,
        task_spec["task_label"],
    )

    logger.info(
        "Encoding task %s with %s query rows and %s corpus rows.",
        task_spec["task_label"],
        len(query_rows),
        len(corpus_rows),
    )
    logger.info(
        "Resolved query encoding settings: %s",
        json.dumps(build_resolved_query_encoding_settings(args), ensure_ascii=True),
    )

    encode_start = time.perf_counter()
    doc_embeddings, doc_cache_paths = encode_rows_with_persistent_cache(
        args,
        logger,
        model_instance,
        rows=corpus_rows,
        text_field_name=task_spec["doc_field_name"],
        artifact_kind="corpus_field_embeddings",
        encode_kwargs={},
    )
    artifact_paths.update(doc_cache_paths)

    query_source_paths: dict[str, str] = {}
    if should_slice_query_from_corpus_cache(args, query_encode_kwargs):
        logger.info(
            "No query prompt is active, so query embeddings will be sliced from the reusable corpus-level field cache."
        )
        query_corpus_embeddings, query_corpus_cache_paths = encode_rows_with_persistent_cache(
            args,
            logger,
            model_instance,
            rows=query_field_corpus_rows,
            text_field_name=task_spec["query_field_name"],
            artifact_kind="corpus_field_embeddings",
            encode_kwargs={},
        )
        artifact_paths.update(query_corpus_cache_paths)
        query_embeddings = slice_query_embeddings_from_corpus_cache(
            query_rows,
            query_field_corpus_rows,
            query_corpus_embeddings,
        )
        query_source_paths["query_embeddings_source"] = "sliced_from_corpus_field_cache"
        query_source_paths["query_embeddings_source_cache_file"] = query_corpus_cache_paths[
            "corpus_field_embeddings_cache_embeddings_file"
        ]
    else:
        query_embeddings, query_cache_paths = encode_rows_with_persistent_cache(
            args,
            logger,
            model_instance,
            rows=query_rows,
            text_field_name=task_spec["query_field_name"],
            artifact_kind="query_field_embeddings",
            encode_kwargs=query_encode_kwargs,
        )
        artifact_paths.update(query_cache_paths)
        query_source_paths["query_embeddings_source"] = "query_field_cache"
    artifact_paths.update(query_source_paths)
    encode_elapsed = time.perf_counter() - encode_start

    logger.info("Computing retrieval metrics.")
    retrieval_start = time.perf_counter()
    query_keys = [row["row_key"] for row in query_rows]
    corpus_keys = [row["row_key"] for row in corpus_rows]
    summary, rankings, scores = compute_retrieval_summary(
        query_embeddings,
        doc_embeddings,
        query_keys=query_keys,
        corpus_keys=corpus_keys,
    )
    metrics_payload = {
        task_spec["task_label"]: summary,
    }
    rankings_payload = None
    if args.save_rankings:
        rankings_payload = {
            task_spec["task_label"]: {
                "query_row_keys": list(query_keys),
                "corpus_row_keys": list(corpus_keys),
                "rankings": rankings,
                "scores": scores,
            }
        }
    retrieval_elapsed = time.perf_counter() - retrieval_start

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


def print_human_summary(results: dict[str, Any]) -> None:
    config = results["config"]
    dataset = results["dataset"]
    task_metadata = results.get("design_decisions", {}).get("task", {})
    print("FrenzyMath benchmark complete.")
    print(f"Model: {config['model_name']}")
    print(f"Dataset: {config['dataset_name']}")
    print(f"Query split: {config['query_split']}")
    print(f"Retrieval corpus splits: {', '.join(config['corpus_splits'])}")
    if task_metadata.get("task_label"):
        print(f"Task: {task_metadata['task_label']}")
        print(f"Query field: {task_metadata['query_field_name']}")
        print(f"Document field: {task_metadata['doc_field_name']}")
    else:
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
    if resolve_single_task_spec(args) is not None:
        return run_single_task_benchmark(args, logger, run_dir)

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
    artifact_paths: dict[str, str] = {}

    if args.save_manifests:
        logger.info("Saving query/corpus manifests before encoding.")
        artifact_paths.update(save_manifests(run_dir, pairing_metadata))

    logger.info(
        "Encoding %s query rows against a retrieval corpus of %s rows.",
        len(query_rows),
        len(corpus_rows),
    )
    logger.info(
        "Resolved query encoding settings: %s",
        json.dumps(build_resolved_query_encoding_settings(args), ensure_ascii=True),
    )
    encode_start = time.perf_counter()
    encoder_instance = Encoder(
        model_instance,
        batch_size=args.batch_size,
        normalize=args.normalize,
    )
    reusable_embeddings, reused_artifact_paths = load_reusable_embeddings(
        args,
        pairing_metadata,
        logger,
        current_run_dir=run_dir,
    )
    artifact_paths.update(reused_artifact_paths)

    corpus_informal_embeddings = None
    corpus_lean_embeddings = None
    query_informal_embeddings = None
    query_lean_embeddings = None

    if needs_corpus_informal_embeddings(args):
        corpus_informal_texts = [row["informal"] for row in corpus_rows]
        if "corpus_informal_embeddings" in reusable_embeddings:
            corpus_informal_embeddings = reusable_embeddings["corpus_informal_embeddings"]
        else:
            logger.info("Encoding only the corpus informal side required for this run.")
            corpus_informal_embeddings = encoder_instance.encode(
                corpus_informal_texts,
                progress_callback=build_progress_callback(
                    logger,
                    "Corpus informal encoding",
                    len(corpus_informal_texts),
                ),
            )
            if args.save_embeddings:
                artifact_paths.update(
                    save_single_embedding_artifact(
                        run_dir,
                        args.save_embeddings_dtype,
                        "corpus_informal_embeddings",
                        corpus_informal_embeddings,
                    )
                )

    if needs_corpus_lean_embeddings(args):
        corpus_lean_texts = [row["lean"] for row in corpus_rows]
        if "corpus_lean_embeddings" in reusable_embeddings:
            corpus_lean_embeddings = reusable_embeddings["corpus_lean_embeddings"]
        else:
            logger.info("Encoding only the corpus Lean side required for this run.")
            corpus_lean_embeddings = encoder_instance.encode(
                corpus_lean_texts,
                progress_callback=build_progress_callback(
                    logger,
                    "Corpus Lean encoding",
                    len(corpus_lean_texts),
                ),
            )
            if args.save_embeddings:
                artifact_paths.update(
                    save_single_embedding_artifact(
                        run_dir,
                        args.save_embeddings_dtype,
                        "corpus_lean_embeddings",
                        corpus_lean_embeddings,
                    )
                )
    encode_elapsed = time.perf_counter() - encode_start

    logger.info("Computing retrieval metrics.")
    retrieval_start = time.perf_counter()
    query_keys = [row["row_key"] for row in query_rows]
    corpus_keys = [row["row_key"] for row in corpus_rows]
    metrics_payload = {}
    rankings_payload = {} if args.save_rankings else None

    if "informal_to_lean" in args.directions:
        logger.info("Evaluating informal_to_lean retrieval.")
        query_informal_texts = [row["informal"] for row in query_rows]
        informal_query_encode_kwargs = get_query_encode_kwargs(args, "informal_to_lean")
        if "query_informal_embeddings" in reusable_embeddings:
            query_informal_embeddings = reusable_embeddings["query_informal_embeddings"]
        else:
            query_informal_embeddings = encoder_instance.encode(
                query_informal_texts,
                progress_callback=build_progress_callback(
                    logger,
                    "Query informal encoding",
                    len(query_informal_texts),
                ),
                **informal_query_encode_kwargs,
            )
            if args.save_embeddings:
                artifact_paths.update(
                    save_single_embedding_artifact(
                        run_dir,
                        args.save_embeddings_dtype,
                        "query_informal_embeddings",
                        query_informal_embeddings,
                    )
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
        if "query_lean_embeddings" in reusable_embeddings:
            query_lean_embeddings = reusable_embeddings["query_lean_embeddings"]
        else:
            query_lean_embeddings = encoder_instance.encode(
                query_lean_texts,
                progress_callback=build_progress_callback(
                    logger,
                    "Query Lean encoding",
                    len(query_lean_texts),
                ),
                **lean_query_encode_kwargs,
            )
            if args.save_embeddings:
                artifact_paths.update(
                    save_single_embedding_artifact(
                        run_dir,
                        args.save_embeddings_dtype,
                        "query_lean_embeddings",
                        query_lean_embeddings,
                    )
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
