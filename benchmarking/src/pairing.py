"""
This module contains the main function to run bitext mining evaluation on.

"""

import faiss
import numpy as np


"""
@Behavior: Pairs embeddings from two different languages 
           by finding the nearest neighbors in the embedding space.
@Parameters: language_1_embeddings (list of str): List of embeddings in the first language 
             language_2_embeddings (list of str): List of embeddings in the second language 
             normalized (bool): Whether the input embeddings are already L2-normalized. 
                                If False, the function will normalize them before computing similarities.
@Returns: tuple of lists: A tuple containing two lists:
                          1. List of pairs of related embeddings. 
                             Each pair is a tuple (embedding_from_language_1, embedding_from_language_2).
                          2. List of corresponding index pairs (i, j) 
                             where i is the index in language_1_embeddings and j is the index in language_2_embeddings.
"""
def find_pairs(language_1_embeddings, language_2_embeddings, normalized=True):

   # Convert input lists to numpy arrays and ensure they are of type float32
   language_1_embeddings = np.asarray(language_1_embeddings, dtype=np.float32)
   language_2_embeddings = np.asarray(language_2_embeddings, dtype=np.float32)

   # Check that both embedding arrays are non-empty 
   # and have the same number of dimensions
   if language_1_embeddings.size == 0 or language_2_embeddings.size == 0:
      raise ValueError("Both embedding inputs must be non-empty.")

   if language_1_embeddings.ndim != 2 or language_2_embeddings.ndim != 2:
      raise ValueError("Both embedding inputs must be 2D arrays with shape (n_vectors, dim).")

   if language_1_embeddings.shape[1] != language_2_embeddings.shape[1]:
      raise ValueError(
         "Embedding dimensions must match: "
         f"got {language_1_embeddings.shape[1]} and {language_2_embeddings.shape[1]}."
      )

   # normalize if needed
   if not normalized:
      language_1_embeddings = language_1_embeddings.copy()
      language_2_embeddings = language_2_embeddings.copy()
      faiss.normalize_L2(language_1_embeddings)
      faiss.normalize_L2(language_2_embeddings)

   # Build a FAISS index for the second language embeddings
   embedding_dim = language_2_embeddings.shape[1]
   index = faiss.IndexFlatIP(embedding_dim)
   index.add(language_2_embeddings)

   # Search for the nearest neighbor in language_2 for each embedding in language_1
   _, nearest_indices = index.search(language_1_embeddings, 1)

   # Create pairs of embeddings based on the nearest neighbor indices
   embedding_pairs = []
   index_pairs = []
   for i, row in enumerate(nearest_indices):
      neighbor_idx = int(row[0])
      embedding_pairs.append((language_1_embeddings[i], language_2_embeddings[neighbor_idx]))
      index_pairs.append((i, neighbor_idx))

   return embedding_pairs, index_pairs
