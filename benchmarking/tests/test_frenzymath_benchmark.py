import logging
from pathlib import Path

import numpy as np
import pytest

import frenzymath_benchmark as fb


class DummyModel:
    model_name = "dummy-model"

    def encode(self, texts, **kwargs):
        vectors = []
        for text in texts:
            if text.endswith("1"):
                vectors.append([1.0, 0.0, 0.0])
            elif text.endswith("2"):
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return np.asarray(vectors, dtype=np.float32)


def test_parse_args_rejects_invalid_batch_size():
    with pytest.raises(ValueError, match="--batch-size"):
        fb.parse_args(["--batch-size", "0"])


def test_parse_args_defaults_to_test_queries_against_all_splits():
    args = fb.parse_args([])

    assert args.query_split == "test"
    assert args.corpus_splits == ["train", "val", "test"]


def test_compute_retrieval_summary_perfect_alignment():
    embeddings = np.asarray(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float32,
    )

    query_keys = ["test:0", "test:1", "test:2"]
    corpus_keys = ["train:0", "test:0", "test:1", "test:2"]
    corpus_embeddings = np.asarray(
        [[0.5, 0.5, 0.5], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        dtype=np.float32,
    )

    summary, rankings, scores = fb.compute_retrieval_summary(
        embeddings,
        corpus_embeddings,
        query_keys=query_keys,
        corpus_keys=corpus_keys,
    )

    assert summary["exact_match_at_1"] == pytest.approx(1.0)
    assert summary["recall_at_1"] == pytest.approx(1.0)
    assert summary["recall_at_5"] == pytest.approx(1.0)
    assert summary["recall_at_10"] == pytest.approx(1.0)
    assert summary["mrr"] == pytest.approx(1.0)
    assert len(rankings) == 3
    assert len(scores) == 3


def test_main_success_writes_run_artifacts(monkeypatch):
    pairs = [
        {"informal": "desc1", "lean": "type1", "row_index": 0, "row_key": "test:0"},
        {"informal": "desc2", "lean": "type2", "row_index": 1, "row_key": "test:1"},
        {"informal": "desc3", "lean": "type3", "row_index": 2, "row_key": "test:2"},
    ]
    dumped = {}

    monkeypatch.setattr(fb, "build_model", lambda args: DummyModel())
    monkeypatch.setattr(
        fb,
        "load_pairs",
        lambda args: {
            "query_rows": pairs,
            "corpus_rows": pairs,
            "query_original_size": 3,
            "query_selected_row_count_before_empty_filter": 3,
            "query_dropped_rows_due_to_missing_or_empty_text": 0,
            "query_dropped_rows_due_to_missing_corpus_match": 0,
            "corpus_original_sizes_by_split": {"test": 3},
            "corpus_selected_row_count_before_truncation": 3,
            "corpus_selected_row_count_before_empty_filter": 3,
            "corpus_dropped_rows_due_to_missing_or_empty_text": 0,
        },
    )
    monkeypatch.setattr(fb, "build_run_directory", lambda args: Path("fake-run-dir"))
    monkeypatch.setattr(fb, "setup_logging", lambda run_dir: logging.getLogger("test"))
    monkeypatch.setattr(
        fb,
        "_json_dump",
        lambda path, payload: dumped.__setitem__(str(path), payload),
    )

    exit_code = fb.main(
        [
            "--model-type",
            "random",
            "--results-dir",
            "fake-results-dir",
            "--save-rankings",
        ]
    )

    assert exit_code == 0
    assert "fake-run-dir\\config.json" in dumped
    assert "fake-run-dir\\invocation.json" in dumped
    assert "fake-run-dir\\results.json" in dumped
    assert "fake-run-dir\\summary.json" in dumped
    assert "fake-run-dir\\rankings.json" in dumped

    results = dumped["fake-run-dir\\results.json"]
    assert results["run_status"] == "success"
    assert results["dataset"]["evaluated_pairs"] == 3
    assert results["config"]["corpus_splits"] == ["train", "val", "test"]
    assert results["metrics"]["informal_to_lean"]["exact_match_at_1"] == pytest.approx(1.0)


def test_main_failure_writes_failure_manifest(monkeypatch):
    dumped = {}
    monkeypatch.setattr(
        fb,
        "build_model",
        lambda args: (_ for _ in ()).throw(RuntimeError("model boom")),
    )
    monkeypatch.setattr(fb, "build_run_directory", lambda args: Path("fake-run-dir"))
    monkeypatch.setattr(fb, "setup_logging", lambda run_dir: logging.getLogger("test"))
    monkeypatch.setattr(
        fb,
        "_json_dump",
        lambda path, payload: dumped.__setitem__(str(path), payload),
    )

    with pytest.raises(RuntimeError, match="model boom"):
        fb.main(
            [
                "--model-type",
                "random",
                "--results-dir",
                "fake-results-dir",
            ]
        )

    failure = dumped["fake-run-dir\\failure.json"]
    assert failure["run_status"] == "failed"
    assert failure["error_type"] == "RuntimeError"
    assert "model boom" in failure["error_message"]
