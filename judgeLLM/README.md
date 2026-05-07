# judgeLLM

Quick prototyping utilities for asking Qwen3-0.6B whether a statement and a shifted statement are mathematically equivalent.

## Files

- `model_loader.py`: reusable model-loading helpers.
- `equivalence_runner.py`: reads a JSON array of pairs, runs the model, and writes a JSON array of results.
- `equivalence_prompt.md`: editable prompt template loaded directly by the runner.
- `hard_negatives.json`: sample input file.

## Run

```bash
python judgeLLM/equivalence_runner.py --input judgeLLM/hard_negatives.json --output judgeLLM/equivalence_results.json
```

## Output format

The runner writes a single JSON array. Each output object keeps the original input fields and adds the judgement fields such as `pair_id`, `equivalent`, `confidence`, `rationale`, `assumptions_used`, `parse_status`, and `raw_model_output`.
