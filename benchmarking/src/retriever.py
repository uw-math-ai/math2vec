"""
Docstring for benchmarking.src.retriever
"""

import numpy as np
import faiss


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

    # throw exceptions for bad inputs
    # TODO: implement exception handling

    # normalize queries and corpus to unit length for cosine similarity
    # faiss.normalize_L2(queries)
    # faiss.normalize_L2(corpus)
    # TODO: decide if we want to normalize here or in the encoder

    # make a faiss index for vectors with len(corpus[0]) dimensions
    dimension = len(corpus[0])
    index = faiss.IndexFlatIP(dimension)   # build the index

    # add corpus vectors to the index
    index.add(corpus)

    # perform search to retrieve top-k documents for each query
    D, I = index.search(queries, K)     # actual search

    # I is a numpy array of shape (num_queries, k) with indices of top-k documents
    return I, D  # Return the indices and similarity scores of top-k retrieved documents for each query

