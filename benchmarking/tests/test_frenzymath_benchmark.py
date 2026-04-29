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
    assert args.directions == ["informal_to_lean"]
    assert args.informal_to_lean_type_query_prompt == fb.DEFAULT_INFORMAL_TO_LEAN_TYPE_QUERY_PROMPT
    assert args.informal_to_lean_signature_query_prompt == fb.DEFAULT_INFORMAL_TO_LEAN_SIGNATURE_QUERY_PROMPT
    assert args.lean_type_to_informal_query_prompt == fb.DEFAULT_LEAN_TYPE_TO_INFORMAL_QUERY_PROMPT
    assert args.lean_signature_to_informal_query_prompt == fb.DEFAULT_LEAN_SIGNATURE_TO_INFORMAL_QUERY_PROMPT


def test_parse_args_rejects_per_direction_prompt_name_and_prompt_together():
    with pytest.raises(ValueError, match="informal-to-lean-query-prompt-name"):
        fb.parse_args(
            [
                "--informal-to-lean-query-prompt-name",
                "bitext_query",
                "--informal-to-lean-type-query-prompt",
                "custom prompt",
            ]
        )


def test_get_query_encode_kwargs_uses_direction_and_lean_field_specific_defaults():
    args = fb.parse_args([])

    informal_kwargs = fb.get_query_encode_kwargs(args, "informal_to_lean")
    lean_kwargs = fb.get_query_encode_kwargs(args, "lean_to_informal")

    assert informal_kwargs == {"prompt": fb.DEFAULT_INFORMAL_TO_LEAN_TYPE_QUERY_PROMPT}
    assert lean_kwargs == {"prompt": fb.DEFAULT_LEAN_TYPE_TO_INFORMAL_QUERY_PROMPT}

    signature_args = fb.parse_args(["--lean-field", "signature"])
    informal_signature_kwargs = fb.get_query_encode_kwargs(signature_args, "informal_to_lean")
    lean_signature_kwargs = fb.get_query_encode_kwargs(signature_args, "lean_to_informal")

    assert informal_signature_kwargs == {"prompt": fb.DEFAULT_INFORMAL_TO_LEAN_SIGNATURE_QUERY_PROMPT}
    assert lean_signature_kwargs == {"prompt": fb.DEFAULT_LEAN_SIGNATURE_TO_INFORMAL_QUERY_PROMPT}


def test_build_progress_callback_reports_first_middle_and_last(caplog):
    logger = logging.getLogger("progress-test")
    caplog.set_level(logging.INFO, logger="progress-test")
    callback = fb.build_progress_callback(logger, "Corpus encoding", total_texts=100)

    callback({"batch_index": 1, "total_batches": 20, "batch_size": 5, "texts_encoded": 5, "total_texts": 100})
    callback({"batch_index": 10, "total_batches": 20, "batch_size": 5, "texts_encoded": 50, "total_texts": 100})
    callback({"batch_index": 20, "total_batches": 20, "batch_size": 5, "texts_encoded": 100, "total_texts": 100})

    messages = [record.message for record in caplog.records]
    assert any("5.0%" in message for message in messages)
    assert any("50.0%" in message for message in messages)
    assert any("100.0%" in message for message in messages)


def test_save_embedding_artifacts_and_manifests(writable_tmp_path):
    run_dir = writable_tmp_path / "run"
    run_dir.mkdir()
    rows = [
        {
            "row_key": "test:0",
            "split": "test",
            "row_index_within_split": 0,
            "dataset_index": None,
            "informal": "desc1",
            "lean": "type1",
        }
    ]

    manifest_paths = fb.save_manifests(
        run_dir,
        {
            "query_rows": rows,
            "corpus_rows": rows,
        },
    )
    embedding_paths = fb.save_embedding_artifacts(
        run_dir,
        "float32",
        {
            "corpus_informal_embeddings": np.asarray([[1.0, 2.0]], dtype=np.float32),
        },
    )

    assert Path(manifest_paths["query_manifest_file"]).exists()
    assert Path(manifest_paths["corpus_manifest_file"]).exists()
    assert Path(embedding_paths["corpus_informal_embeddings_file"]).exists()


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
        {
            "informal": "desc1",
            "lean": "type1",
            "row_index": 0,
            "row_key": "test:0",
            "split": "test",
            "row_index_within_split": 0,
        },
        {
            "informal": "desc2",
            "lean": "type2",
            "row_index": 1,
            "row_key": "test:1",
            "split": "test",
            "row_index_within_split": 1,
        },
        {
            "informal": "desc3",
            "lean": "type3",
            "row_index": 2,
            "row_key": "test:2",
            "split": "test",
            "row_index_within_split": 2,
        },
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
        "save_manifests",
        lambda run_dir, pairing_metadata: {
            "query_manifest_file": str(run_dir / "query_manifest.jsonl"),
            "corpus_manifest_file": str(run_dir / "corpus_manifest.jsonl"),
        },
    )
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
    assert results["config"]["directions"] == ["informal_to_lean"]
    assert results["config"]["save_manifests"] is True
    assert results["artifact_paths"]["query_manifest_file"].endswith("query_manifest.jsonl")
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
