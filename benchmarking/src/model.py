"""
Model classes for generating embeddings.
Models must implement an encode method and can optionally have metadata.
"""

import numpy as np
from typing import List, Optional

from meta import ModelMetadata


class SentenceTransformerModel:
    """
    Wrapper for sentence-transformers models.
    """

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-Embedding-0.6B",
        metadata: Optional[ModelMetadata] = None,
        device: Optional[str] = None,
        dtype: Optional[str] = None,
    ):
        """
        @Parameters:
            model_name (str): Name or path of the sentence-transformers model
            metadata (ModelMetadata): Optional model metadata
        """

        self.model_name = model_name
        try:
            import torch
            from sentence_transformers import SentenceTransformer
        except ImportError as import_error:
            raise ImportError(
                "sentence-transformers is required to use "
                "`--model-type sentence-transformer`."
            ) from import_error

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = dtype
        model_kwargs = {}
        if dtype is not None:
            dtype_map = {
                "float16": torch.float16,
                "bfloat16": torch.bfloat16,
                "float32": torch.float32,
                "float64": torch.float64,
            }
            if dtype not in dtype_map:
                allowed = ", ".join(dtype_map.keys())
                raise ValueError(f"Unsupported dtype '{dtype}'. Allowed values: {allowed}")
            model_kwargs["torch_dtype"] = dtype_map[dtype]

        self.model = SentenceTransformer(
            model_name,
            device=self.device,
            model_kwargs=model_kwargs if model_kwargs else None,
        )
        if hasattr(self.model, "get_embedding_dimension"):
            self.embedding_dim = self.model.get_embedding_dimension()
        else:
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
                # calls the encode function from sentence-transformers, 
                # which returns a numpy array of shape (n_texts, embedding_dim)
        return embeddings


class random_embedder:
    """
    Model that generates completely random embeddings for input texts.
    """

    def __init__(
        self,
        embedding_dim: int = 384,
        metadata: Optional[ModelMetadata] = None,
        seed: Optional[int] = None,
    ):
        """
        @Parameters:
            embedding_dim (int): Dimension of embeddings to generate
            metadata (ModelMetadata): Optional model metadata
            seed (int): Optional random seed for reproducibility
        """

        if embedding_dim <= 0:
            raise ValueError("embedding_dim must be a positive integer")

        self.embedding_dim = embedding_dim
        self.rng = np.random.default_rng(seed)

        if metadata is None:
            self.metadata = ModelMetadata(
                name="random-embedder",
                model_type="random",
                embedding_dim=self.embedding_dim,
                description="Generates random embeddings independently of text content.",
                parameters={"seed": seed},
            )
        else:
            self.metadata = metadata

    def encode(self, texts: List[str], **kwargs) -> np.ndarray:
        """
        Generate random embeddings for a batch of texts.

        @Parameters:
            texts (list of str): Texts to encode
            **kwargs: Unused, present for interface compatibility

        @Returns:
            numpy.ndarray: Random embeddings, shape (len(texts), embedding_dim)
        """

        if not isinstance(texts, list):
            raise TypeError("texts must be a list of strings")

        return self.rng.standard_normal((len(texts), self.embedding_dim)).astype(np.float32)


RandomEmbedder = random_embedder
