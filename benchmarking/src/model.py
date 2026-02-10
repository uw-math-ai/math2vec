"""
Model classes for generating embeddings.
Models must implement an encode method and can optionally have metadata.
"""

import numpy as np
from typing import List, Optional
from sentence_transformers import SentenceTransformer

from benchmarking.src.meta import ModelMetadata


class SentenceTransformerModel:
    """
    Wrapper for sentence-transformers models.
    """

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", metadata: Optional[ModelMetadata] = None):
        """
        @Parameters:
            model_name (str): Name or path of the sentence-transformers model
            metadata (ModelMetadata): Optional model metadata
        """

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        # Get max sequence length if available
        max_seq_len = None
        if hasattr(self.model, 'max_seq_length'):
            max_seq_len = self.model.max_seq_length

        # Create or store metadata
        if metadata is None:
            self.metadata = ModelMetadata(
                name=model_name,
                model_type="sentence-transformer",
                embedding_dim=self.embedding_dim,
                description=f"Sentence transformer model: {model_name}",
                max_seq_length=max_seq_len,
            )
        else:
            self.metadata = metadata

    def encode(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Encode texts using sentence-transformers.

        @Parameters:
            texts (list of str): Texts to encode
            **kwargs: Additional arguments for model.encode()

        @Returns:
            numpy.ndarray: Embeddings, shape (len(texts), embedding_dim)
        """

        embeddings = self.model.encode(texts, convert_to_numpy=True, **kwargs)
        return embeddings
