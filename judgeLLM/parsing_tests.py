"""judgeLLM.parsing_tests

Debug helper for inspecting raw_model_output values stored in
equivalence_results.json.

This script re-parses the saved raw model outputs and reports:
- whether the current strict parser accepts them
- what the first balanced JSON object looks like
- where parsing fails if it does fail
"""

from __future__ import annotations

import json
import sys
import types
from collections import Counter
from pathlib import Path
from typing import Any


def ensure_transformers_stub() -> None:
	"""Provide a tiny stub if transformers is unavailable.

	The parser tests only need equivalence_runner's parsing helpers, not
	the actual model loader.
	"""

	if "transformers" in sys.modules:
		return

	stub = types.ModuleType("transformers")
	stub.AutoModelForCausalLM = object
	stub.AutoTokenizer = object
	stub.pipeline = lambda *args, **kwargs: None
	sys.modules["transformers"] = stub


ensure_transformers_stub()

from equivalence_runner import parse_model_response, strip_code_fences


DEFAULT_RESULTS_PATH = Path(__file__).with_name("equivalence_results.json")


def load_results(path: Path) -> list[dict[str, Any]]:
	data = json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(data, list):
		raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}.")
	return data


def first_balanced_json_object(text: str) -> str | None:
	"""Return the first balanced JSON object substring, if present."""

	cleaned = strip_code_fences(text)
	start = cleaned.find("{")
	if start == -1:
		return None

	depth = 0
	in_string = False
	escape = False
	for index in range(start, len(cleaned)):
		char = cleaned[index]
		if in_string:
			if escape:
				escape = False
			elif char == "\\":
				escape = True
			elif char == '"':
				in_string = False
			continue

		if char == '"':
			in_string = True
		elif char == "{":
			depth += 1
		elif char == "}":
			depth -= 1
			if depth == 0:
				return cleaned[start : index + 1]

	return None


def summarize_item(index: int, item: dict[str, Any]) -> dict[str, Any]:
	raw_output = str(item.get("raw_model_output", ""))
	parsed, parse_status = parse_model_response(raw_output)
	first_object = first_balanced_json_object(raw_output)
	first_object_status = "missing"
	first_object_error = None

	if first_object is not None:
		try:
			json.loads(first_object)
			first_object_status = "json_ok"
		except Exception as exc:
			first_object_status = "json_error"
			first_object_error = str(exc)

	return {
		"index": index + 1,
		"pair_id": item.get("pair_id"),
		"stored_parse_status": item.get("parse_status"),
		"strict_parse_status": parse_status,
		"strict_parser_accepted": parsed is not None,
		"first_object_status": first_object_status,
		"first_object_error": first_object_error,
		"raw_preview": raw_output[:220].replace("\n", "\\n"),
	}


def main() -> int:
	results = load_results(DEFAULT_RESULTS_PATH)
	
	print(f"Loaded {len(results)} result records from {DEFAULT_RESULTS_PATH}")
    
	summaries = [summarize_item(index, item) for index, item in enumerate(results)]

	for summary in summaries:
		print(
			f"[{summary['index']}] pair_id={summary['pair_id']} "
			f"stored={summary['stored_parse_status']} strict={summary['strict_parse_status']} "
			f"first_object={summary['first_object_status']}"
		)
		print(f"  preview: {summary['raw_preview']}")
		if summary["first_object_error"]:
			print(f"  first_object_error: {summary['first_object_error']}")
		print()

	counts = Counter(summary["strict_parse_status"] for summary in summaries)
	print("Summary:")
	for key, value in counts.items():
		print(f"  {key}: {value}")

	return 0


if __name__ == "__main__":
	raise SystemExit(main())
