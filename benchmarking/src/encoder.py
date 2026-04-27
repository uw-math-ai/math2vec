"""
Encoder wrapper for embedding models.
Takes a model and encodes text into embeddings.
"""

import numpy as np
from typing import Callable, List, Union


class Encoder:
    """
    Wrapper class for encoding text into embeddings.

    @Attributes:
        model: The underlying model to use for encoding
        batch_size: Number of texts to encode at once
                - This is important for efficiency, especially with large models and datasets  
                - Large batch sizes = faster but more memory usage
                - Small batch sizes = slower but less memory usage 
                - Suggested: 32 or 64
        normalize: Whether to normalize embeddings to unit length
    """

    def __init__(self, model, batch_size: int = 32, normalize: bool = True):
        """
        @Parameters:
            model: A model object with an encode method
            batch_size (int): Batch size for encoding
            normalize (bool): Whether to L2-normalize embeddings
        """

        self.model = model
        self.batch_size = batch_size
        self.normalize = normalize

    def encode(self, texts: Union[str, List[str]], **kwargs) -> np.ndarray:
        """
        Encode texts into embeddings.

        @Parameters:
            texts (str or list of str): Text(s) to encode
            **kwargs: Additional arguments passed to the model's encode method

        @Returns:
            numpy.ndarray: Array of embeddings, shape (n_texts, embedding_dim)
        """

        progress_callback = kwargs.pop("progress_callback", None)

        # Handle single text input
        if isinstance(texts, str):
            texts = [texts]

        # Encode in batches
        all_embeddings = []
        total_batches = (len(texts) + self.batch_size - 1) // self.batch_size if texts else 0
        for batch_index, i in enumerate(range(0, len(texts), self.batch_size), start=1):
            batch = texts[i : i + self.batch_size]
            batch_embeddings = self.model.encode(batch, **kwargs)
            all_embeddings.append(batch_embeddings)
            if progress_callback is not None:
                progress_callback(
                    {
                        "batch_index": batch_index,
                        "total_batches": total_batches,
                        "batch_size": len(batch),
                        "texts_encoded": min(i + len(batch), len(texts)),
                        "total_texts": len(texts),
                    }
                )

        # Concatenate all batches
        embeddings = np.vstack(all_embeddings)

        # Normalize if requested
        if self.normalize:
            embeddings = self._normalize(embeddings)

        return embeddings

    def _normalize(self, embeddings: np.ndarray) -> np.ndarray:
        """
        L2-normalize embeddings to unit length.

        @Parameters:
            embeddings (numpy.ndarray): Embeddings to normalize

        @Returns:
            numpy.ndarray: Normalized embeddings
        """

        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)  # avoid division by zero
        return embeddings / norms
