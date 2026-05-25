"""
Model classes for generating embeddings.
Models must implement an encode method and can optionally have metadata.
"""

import os
import gc

import numpy as np
from typing import List, Optional

from meta import ModelMetadata


DEFAULT_TRUST_REMOTE_CODE_MODELS = {
    "nvidia/llama-embed-nemotron-8b",
}


def should_trust_remote_code(model_name: str) -> bool:
    configured = os.environ.get("TRUST_REMOTE_CODE_MODELS", "")
    configured_models = set()
    for item in configured.split(","):
        item = item.strip()
        if item:
            configured_models.add(item)
    allowed_models = DEFAULT_TRUST_REMOTE_CODE_MODELS | configured_models
    return model_name in allowed_models


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
        sentence_transformer_init_kwargs = {}
        if self.device == "cuda" and hasattr(torch.backends, "cuda"):
            if hasattr(torch.backends.cuda, "enable_cudnn_sdp"):
                torch.backends.cuda.enable_cudnn_sdp(False)
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

        hf_token = (
            os.environ.get("HF_TOKEN")
            or os.environ.get("HUGGING_FACE_HUB_TOKEN")
            or os.environ.get("HUGGINGFACE_HUB_TOKEN")
        )
        if hf_token:
            sentence_transformer_init_kwargs["token"] = hf_token
        if should_trust_remote_code(model_name):
            sentence_transformer_init_kwargs["trust_remote_code"] = True

        self.model = SentenceTransformer(
            model_name,
            device=self.device,
            model_kwargs=model_kwargs if model_kwargs else None,
            **sentence_transformer_init_kwargs,
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

        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True, **kwargs)
            return embeddings
        except RuntimeError:
            if self.device == "cuda":
                gc.collect()
                try:
                    import torch

                    torch.cuda.empty_cache()
                except Exception:
                    pass
            raise


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
