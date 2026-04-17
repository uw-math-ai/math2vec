"""
Docstring for benchmarking.src.retriever
"""

import numpy as np

try:
    import faiss  # type: ignore
except ImportError:
    faiss = None


# perform retrieval using FAISS
"""
@Behavior: Retrieves the top-k relevant documents for each query from the corpus using FAISS.
@Parameters: queries (numpy array of vectors): The query vectors.
                - Assumes each vector is of the same dimension as corpus vectors
                - Assumes each vector is normalized
             corpus (numpy array of vectors): The corpus vectors.  
                - Assumes each vector is of the same dimension as query vectors
                - Assumes each vector is normalized
             K (int): The number of top documents to retrieve per query.
@Returns: numpy array of numpy arrays: numpy array where each element 
            is an array of indices of the top-k retrieved documents for each query.
          numpy array of numpy arrays: numpy array where each element
            is an array of similarity scores of the top-k retrieved documents for each query.
"""
def retrieve_top_k(queries, corpus, K):
    queries = np.asarray(queries, dtype=np.float32)
    corpus = np.asarray(corpus, dtype=np.float32)

    if queries.ndim != 2 or corpus.ndim != 2:
        raise ValueError("queries and corpus must both be 2D arrays of shape (n, dim).")
    if queries.shape[1] != corpus.shape[1]:
        raise ValueError(
            "queries and corpus must have the same embedding dimension: "
            f"got {queries.shape[1]} and {corpus.shape[1]}."
        )
    if len(corpus) == 0:
        raise ValueError("corpus must be non-empty.")
    if len(queries) == 0:
        raise ValueError("queries must be non-empty.")
    if K <= 0:
        raise ValueError("K must be a positive integer.")

    K = min(K, len(corpus))

    if faiss is not None:
        dimension = corpus.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(corpus)
        scores, indices = index.search(queries, K)
        return indices, scores

    similarity = np.matmul(queries, corpus.T)
    sorted_indices = np.argsort(-similarity, axis=1)[:, :K]
    sorted_scores = np.take_along_axis(similarity, sorted_indices, axis=1)
    return sorted_indices, sorted_scores

