"""judgeLLM.model_loader

Reusable model loading helpers for the judgeLLM experiments.
This module is intentionally separate from the runner so the loading
infrastructure can be reused without mixing in batch orchestration.
"""

from __future__ import annotations

import os
from typing import Any

from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline

DEFAULT_MODEL_NAME = "Qwen/Qwen3-8B"  # Qwen3-8B-Instruct is the smallest Qwen model, and should be fast to load and run on a single GPU.


def load_qwen_model(model_name: str = DEFAULT_MODEL_NAME) -> Any:
	"""Load the Qwen causal LM and return a text-generation pipeline."""

	hf_token = os.environ.get("HUGGINGFACEHUB_API_TOKEN")
	if hf_token is None:
		print("Warning: HUGGINGFACEHUB_API_TOKEN not set; public models only.")

	tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
	model = AutoModelForCausalLM.from_pretrained(
		model_name,
		trust_remote_code=True,
		device_map="auto",
	)
	return pipeline("text-generation", model=model, tokenizer=tokenizer)
