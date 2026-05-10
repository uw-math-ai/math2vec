"""judgeLLM.equivalence_runner

Batch runner that loads statement / shifted-statement pairs from JSON,
asks the model whether they are mathematically equivalent, and writes the
results as a single JSON array.

THIS IS THE MAIN FILE FOR THE EQUIVALENCE JUDGEMENT EXPERIMENTS.
- Model loading & the specific prompt are in separate files.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable

from model_loader import DEFAULT_MODEL_NAME, load_qwen_model

# Default paths
DEFAULT_INPUT_PATH = Path(__file__).with_name("hard_negatives.json")
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("equivalence_results.json")
DEFAULT_PROMPT_PATH = Path(__file__).with_name("equivalence_prompt.md")

EXPECTED_RESPONSE_KEYS = {
	"pair_id",
	"equivalent",
	"confidence",
	"rationale",
	"assumptions_used",
	"parse_status",
}

# loads text from a file
# expects input .json file to be an array of objects
def load_text(path: Path) -> str:
	return path.read_text(encoding="utf-8")

# loads the input JSON array and validates it's a list of dicts
def load_input_records(path: Path) -> list[dict[str, Any]]:
	data = json.loads(load_text(path))
	if not isinstance(data, list):
		raise ValueError(f"Expected a JSON array in {path}, got {type(data).__name__}.")
	return data

# Normalization and parsing helpers for the model output
def normalize_whitespace(text: str) -> str:
	return re.sub(r"\s+", " ", text).strip()

# Extracts original statement text
def extract_statement_text(item: dict[str, Any]) -> str:
	for key in ("Input Statement", "statement", "original_statement", "original_text"):
		value = item.get(key)
		if isinstance(value, str) and value.strip():
			return value
	raise KeyError("Could not find an input statement field in the record.")

# Extracts shifted statement text
def extract_shifted_text(item: dict[str, Any]) -> str:
	for key in ("Hard Negative", "shifted_statement", "shifted_text", "candidate_statement"):
		value = item.get(key)
		if isinstance(value, str) and value.strip():
			return value
	raise KeyError("Could not find a shifted statement field in the record.")

# Builds the prompt by replacing placeholders in the template
def build_prompt(template: str, statement: str, shifted_statement: str) -> str:
	return (
		template.replace("{{statement}}", statement).replace("{{shifted_statement}}", shifted_statement)
	)

# Strips code fences and extra whitespace from the model output.
def strip_code_fences(text: str) -> str:
	cleaned = text.strip()
	if cleaned.startswith("```"):
		cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
		cleaned = re.sub(r"\s*```$", "", cleaned)
	return cleaned.strip()


def extract_first_json_object(text: str) -> str | None:
	"""Return the first balanced JSON object substring, ignoring surrounding text."""

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


def repair_json_string_escapes(text: str) -> str:
	"""Escape stray backslashes inside JSON strings while preserving valid escapes."""

	valid_escape_chars = {'"', "\\", "/", "b", "f", "n", "r", "t", "u"}
	result: list[str] = []
	in_string = False
	index = 0
	while index < len(text):
		char = text[index]
		if not in_string:
			result.append(char)
			if char == '"':
				in_string = True
			index += 1
			continue

		if char == "\\":
			next_char = text[index + 1] if index + 1 < len(text) else ""
			if next_char in valid_escape_chars:
				result.append(char)
				index += 1
				if index < len(text):
					result.append(text[index])
					if text[index] == '"':
						in_string = False
				index += 1
				continue
			result.append("\\\\")
			index += 1
			continue

		result.append(char)
		if char == '"':
			in_string = False
		index += 1

	return "".join(result)


def coerce_equivalent_value(value: Any) -> bool | str:
	if isinstance(value, bool):
		return value
	if isinstance(value, str):
		lowered = value.strip().lower()
		if lowered in {"true", "equivalent", "yes", "true,"}:
			return True
		if lowered in {"false", "not equivalent", "no", "false,"}:
			return False
		if lowered == "underspecified":
			return "Underspecified"
	raise ValueError("equivalent must be a boolean or 'Underspecified'.")


def coerce_assumptions(value: Any) -> list[str]:
	if value is None:
		return []
	if isinstance(value, list):
		return [str(item) for item in value]
	if isinstance(value, str) and value.strip():
		return [value.strip()]
	raise ValueError("assumptions_used must be a list of strings.")


def validate_parsed_response(parsed: dict[str, Any]) -> dict[str, Any]:
	missing_keys = EXPECTED_RESPONSE_KEYS.difference(parsed)
	if missing_keys:
		raise ValueError(f"Missing required keys: {sorted(missing_keys)}")

	validated = {
		"pair_id": str(parsed["pair_id"]),
		"equivalent": coerce_equivalent_value(parsed["equivalent"]),
		"confidence": float(parsed["confidence"]),
		"rationale": str(parsed["rationale"]),
		"assumptions_used": coerce_assumptions(parsed["assumptions_used"]),
		"parse_status": str(parsed["parse_status"]),
	}

	if validated["parse_status"] not in {"ok", "format_error"}:
		raise ValueError("parse_status must be 'ok' or 'format_error'.")
	if not 0.0 <= validated["confidence"] <= 1.0:
		raise ValueError("confidence must be between 0.0 and 1.0.")
	return validated


def extract_json_object(text: str) -> dict[str, Any]:
	first_object = extract_first_json_object(text)
	if first_object is None:
		raise ValueError("No JSON object found in model output.")

	try:
		parsed = json.loads(first_object)
	except json.JSONDecodeError:
		repaired_object = repair_json_string_escapes(first_object)
		parsed = json.loads(repaired_object)

	if not isinstance(parsed, dict):
		raise ValueError("Model output must be a JSON object.")
	return parsed

# Parses the model's raw output and returns a normalized record plus a status string.
def parse_model_response(raw_output: str) -> tuple[dict[str, Any] | None, str]:
	try:
		parsed = extract_json_object(raw_output)
		if "format_error" in parsed:
			return {"format_error": str(parsed["format_error"])} if isinstance(parsed["format_error"], str) else parsed, "format_error"
		validated = validate_parsed_response(parsed)
		return validated, "ok"
	except Exception:
		return None, "format_error"

# Builds a repair prompt to ask the model to fix its output if it was not valid JSON.
def build_repair_prompt(prompt_template: str) -> str:
	return (
		prompt_template
		+ "\n\nThe previous response was not valid JSON. "
		+ "Return only a valid JSON object matching the schema and no extra text."
	)

# Calls the model with the given prompt and returns the raw output string.
def call_model(generator: Any, prompt: str, max_new_tokens: int) -> str:
	outputs = generator(
		prompt,
		max_new_tokens=max_new_tokens,
		do_sample=False,
		temperature=0.0,
		top_p=1.0,
		num_return_sequences=1,
		return_full_text=False,
	)
	if not outputs:
		return ""
	first_output = outputs[0]
	if isinstance(first_output, dict):
		return str(first_output.get("generated_text", ""))
	return str(first_output)

# Main function to run a single statement pair through the model and parse the results.
def run_pair(
	generator: Any,
	prompt_template: str,
	item: dict[str, Any],
	pair_index: int,
	model_name: str,
	max_new_tokens: int,
) -> dict[str, Any]:
	statement = extract_statement_text(item)
	shifted_statement = extract_shifted_text(item)
	statement_normalized = normalize_whitespace(statement)
	shifted_normalized = normalize_whitespace(shifted_statement)
	pair_id = str(item.get("pair_id") or f"pair_{pair_index:04d}")

	prompt = build_prompt(prompt_template, statement_normalized, shifted_normalized)
	start = time.perf_counter()
	raw_output = call_model(generator, prompt, max_new_tokens=max_new_tokens)
	latency_ms = int((time.perf_counter() - start) * 1000)

	parsed, parse_status = parse_model_response(raw_output)
	retry_count = 0
	if parse_status != "ok":
		retry_count = 1
		repair_prompt = build_repair_prompt(prompt)
		repair_start = time.perf_counter()
		repair_output = call_model(generator, repair_prompt, max_new_tokens=max_new_tokens)
		repair_latency_ms = int((time.perf_counter() - repair_start) * 1000)
		repair_parsed, repair_status = parse_model_response(repair_output)
		latency_ms += repair_latency_ms
		if repair_status == "ok" and repair_parsed is not None:
			raw_output = repair_output
			parsed = repair_parsed
			parse_status = repair_status
	equivalent = None
	confidence = None
	rationale = ""
	assumptions_used: list[str] = []

	if parsed is not None:
		equivalent = parsed["equivalent"]
		confidence = parsed["confidence"]
		rationale = parsed["rationale"]
		assumptions_used = parsed["assumptions_used"]

	result = dict(item)
	result.update(
		{
			"pair_id": pair_id,
			"statement": statement,
			"shifted_statement": shifted_statement,
			"statement_normalized": statement_normalized,
			"shifted_statement_normalized": shifted_normalized,
			"equivalent": equivalent,
			"confidence": confidence,
			"rationale": rationale,
			"assumptions_used": assumptions_used,
			"parse_status": parse_status,
			"parsed_model_output": parsed,
			"raw_model_output": raw_output,
			"latency_ms": latency_ms,
			"model_name": model_name,
			"max_new_tokens": max_new_tokens,
			"retries": retry_count,
		}
	)
	return result

# Helper to save the results as a JSON array to a file.
def save_json_array(path: Path, records: Iterable[dict[str, Any]]) -> None:
	path.write_text(json.dumps(list(records), indent=2, ensure_ascii=False), encoding="utf-8")

# Main argument parsing and orchestration of the batch run.
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Judge mathematical equivalence for JSON pairs.")
	parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH, help="Path to the input JSON array.")
	parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH, help="Path to the output JSON array.")
	parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT_PATH, help="Path to the prompt template file.")
	parser.add_argument("--model", type=str, default=DEFAULT_MODEL_NAME, help="Hugging Face model id.")
	parser.add_argument("--max-new-tokens", type=int, default=256, help="Maximum number of new tokens to generate.")
	return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
	args = parse_args(argv)
	print(f"Loaded arguments: {args}")
	prompt_template = load_text(args.prompt)
	print(f"Loaded prompt template from {args.prompt} (length {len(prompt_template)} characters)")
	records = load_input_records(args.input)
	print(f"Loaded {len(records)} records from {args.input}")
	generator = load_qwen_model(args.model)
	print(f"Loaded model '{args.model}' and created text generation pipeline.")

	results = [
		run_pair(generator, prompt_template, item, index + 1, args.model, args.max_new_tokens)
		for index, item in enumerate(records)
	]
	save_json_array(args.output, results)
	print(f"Saved {len(results)} results to {args.output}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
