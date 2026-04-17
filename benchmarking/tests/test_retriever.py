import numpy as np

import retriever


def test_retrieve_top_k_numpy_fallback(monkeypatch):
    monkeypatch.setattr(retriever, "faiss", None)

    queries = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    corpus = np.array(
        [[1.0, 0.0], [0.2, 0.8], [0.0, 1.0]],
        dtype=np.float32,
    )

    indices, scores = retriever.retrieve_top_k(queries, corpus, 2)

    assert indices.tolist() == [[0, 1], [2, 1]]
    assert scores.shape == (2, 2)


def test_retrieve_top_k_rejects_bad_inputs():
    queries = np.array([1.0, 0.0], dtype=np.float32)
    corpus = np.array([[1.0, 0.0]], dtype=np.float32)

    try:
        retriever.retrieve_top_k(queries, corpus, 1)
    except ValueError as error:
        assert "2D arrays" in str(error)
    else:
        raise AssertionError("Expected ValueError for non-2D queries.")
