"""
Metadata definitions for benchmarking.
"""

from typing import Dict, Any, Optional


class ModelMetadata:
    """
    Metadata for a model.
    """

    def __init__(
        self,
        name: str,
        model_type: str,
        embedding_dim: int,
        description: str = "",
        max_seq_length: Optional[int] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        @Parameters:
            name (str): Name of the model
            model_type (str): Type of model (e.g., "sentence-transformer", "openai", "custom")
            embedding_dim (int): Dimension of embeddings produced
            description (str): Description of the model
            max_seq_length (int): Maximum sequence length the model can handle
            parameters (dict): Additional model parameters
        """

        self.name = name
        self.model_type = model_type
        self.embedding_dim = embedding_dim
        self.description = description
        self.max_seq_length = max_seq_length
        self.parameters = parameters or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert model metadata to dictionary.

        @Returns:
            dict: Dictionary representation of model metadata
        """

        return {
            "name": self.name,
            "model_type": self.model_type,
            "embedding_dim": self.embedding_dim,
            "description": self.description,
            "max_seq_length": self.max_seq_length,
            "parameters": self.parameters,
        }
