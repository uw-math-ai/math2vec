# Batch Pairwise Equivalence Plan — judgeLLM

This document describes a refined, implementation-oriented plan to ask one
LLM whether each statement / shifted-statement pair is mathematically
equivalent. The current target is quick prototyping with JSON input/output
files and an easily editable prompt block for Qwen3-0.6B.

## Goals

- Run one immutable task prompt (the "task contract") over each input pair.
- Produce structured, machine-parseable outputs for each pair.
- Keep the prompt easy to tweak in one obvious place.
- Ensure reproducibility via prompt/versioning and deterministic decoding.
- Provide retry/repair logic for format errors and low-confidence outputs.

## Top-level components

1. Prompt specification in [equivalence_prompt.md](equivalence_prompt.md) (single source of truth, versioned, easy to edit).
2. Model loading helpers in [model_loader.py](model_loader.py).
3. Pairwise JSON runner in [equivalence_runner.py](equivalence_runner.py).
4. Output parser / validator that enforces the result schema.
5. Persistence layer using JSON files for quick prototyping.
6. QA tooling: gold subset tests, basic statistics, and drift checks.

## Input normalization rules

- Read JSON input files such as [hard_negatives.json] and treat each array item as one pair record.
- For each item, preserve the original fields and assign a stable `pair_id`.
- Normalize both texts in a lightweight way: trim surrounding whitespace and normalize repeated internal spaces only if needed.
- Keep both `statement` and `shifted_statement` text exactly as source-of-truth fields.
- Compute a corpus checksum (SHA256) and record filename + checksum in run metadata.

## Task contract (prompt template)

- The prompt template is fixed and versioned, but it should live in one easily editable place.
- Best option for quick iteration: keep it as a single multiline string or dedicated prompt block that the runner reads directly.
- Only the current pair text is substituted into the template.
- Minimal example (store in a separate `prompt.txt` or embed in code):

"""
You are a strict mathematical equivalence judge.

Task:
- Decide whether the two mathematical statements are equivalent.
- Equivalent means they have the same mathematical meaning, not just similar wording.
- If they differ in hypotheses, quantifiers, conclusions, domains, or logical strength, mark them not equivalent.
- If the comparison is genuinely ambiguous, use `Underspecified`.

Rules:
- Avoid external assumptions unless necessary; list them under `assumptions_used`.

Input format:
- `statement`: the original statement.
- `shifted_statement`: the candidate hard negative / shifted statement.

Output JSON schema (exact keys required):
{
  "pair_id": string,
  "equivalent": true | false | "Underspecified",
  "confidence": number,  // 0.0-1.0
  "rationale": string,   // short explanation (1-3 sentences)
  "assumptions_used": [string],
  "parse_status": "ok" | "format_error"
}

If you cannot follow the format, return a single field: {"format_error": "<explain>"}.
"""

## Output/result contract

- Persist one record per pair in JSON, ideally as newline-delimited JSONL for append-only runs or as a JSON array for small one-off prototyping.
- Each result record should include:
  - `pair_id` (stable)
  - `statement`
  - `shifted_statement`
  - `equivalent`
  - `confidence`
  - `rationale`
  - `assumptions_used`
  - `parse_status`
  - `raw_model_output`
  - `latency_ms`
  - `tokens_in` / `tokens_out` (if available)
  - `retries`

- Also store run-level metadata: model id, prompt version, decoding settings, seed, timestamp, corpus checksum, and input/output filenames.

## Do I need a Statement class?

- Not strictly.
- For quick prototyping, a simple dict or dataclass-like record is enough.
- Use a class only if you want encapsulated helpers such as `normalize()`, `build_prompt()`, `validate()`, and `to_json()` in one place.
- Practical recommendation: start with a lightweight `PairRecord` structure and promote it to a class only if the pipeline starts accumulating logic.

## Inference runner behavior

- One pair per request (simpler parsing and error isolation).
- Build the prompt from the editable prompt block plus one pair record.
- Use deterministic decoding where possible (`temperature=0` or greedy); if sampling is used, fix seed.
- Timeouts: set a reasonable request timeout and record latency.
- On parse/format error, perform one automatic repair attempt by re-sending the prompt with:
  "The previous response did not follow the JSON schema. Please reply only with the required JSON object." If still fails, mark `parse_status=format_error` and save raw output.

## Concurrency and performance

- Run in small batches to avoid rate limits; default concurrency = 4 workers.
- Each worker reads pair records from an input queue and writes results atomically to JSON.
- For prototyping, a single-worker mode is easier to debug and enough to validate the prompt.
- If you later move to many files or many runs, add file locking or switch to JSONL/SQLite for safer concurrent writes.

## Quality assurance and testing

- Maintain a small gold subset of statement-pair examples with expected equivalence labels.
- On every run, evaluate on the gold subset first and compute accuracy and label-distribution diffs vs previous runs.
- Flag runs with large drift or low accuracy for manual review.

## Storage and reproducibility

- Default persistence: JSON input and JSON output files for quick prototyping.
- Recommended layout:
  - input file: `hard_negatives.json`
  - output file: `equivalence_results.json` or `equivalence_results.jsonl`
  - metadata file: `run_metadata.json`
- Keep output append-friendly if you expect to resume partial runs.
- Always write metadata alongside the results containing model, prompt version, seed, decoding settings, and corpus checksum.

## Implementation layout

- [model_loader.py](model_loader.py) should stay focused on loading the Qwen model and returning a generation pipeline.
- [equivalence_runner.py](equivalence_runner.py) should handle CLI args, input JSON loading, prompt assembly, model calls, parsing, retry, and output writing.
- [equivalence_prompt.md](equivalence_prompt.md) should be the only place where the judging prompt is edited during prompt iteration.

## CLI / developer ergonomics

- Provide flags or config knobs:
  - `--prompt-version` (string)
  - `--model` (string)
  - `--concurrency` (int)
  - `--in` / `--input` (path to JSON input)
  - `--out` (path to JSON output)
  - `--gold` (path to gold subset)
- The prompt should be easy to edit without digging through the runner logic.

## GPU and HPC (SLURM) setup

### Required packages

For GPU acceleration on HPC, ensure your environment includes:
- `torch>=2.0.0` with CUDA support (e.g., `torch==2.1.0` compiled for CUDA 12.1)
- `transformers>=4.30.0` (already in requirements)
- `cuda-toolkit` (often module-loaded on HPC; rarely pip-installed)
- `cudatoolkit` conda package if using conda environments

**Example conda requirements for GPU:**
```
torch==2.1.0+cu121  # or compatible version for your CUDA/HPC setup
transformers==4.57.6
cuda-toolkit  # if conda-available on your HPC
```

### SLURM job script essentials

When submitting to a SLURM cluster (e.g., Tillicum, XSEDE):
1. **Module loading**: Load CUDA and Python/conda modules provided by your HPC center.
2. **Cache directories**: Set `HF_HOME`, `TRANSFORMERS_CACHE`, `HUGGINGFACE_HUB_CACHE` to scratch or project paths to avoid home directory bottlenecks.
3. **GPU allocation**: Use `#SBATCH --gres=gpu:1` (or higher) and appropriate partition names.
4. **Memory and time**: Allocate sufficient GPU memory (32G+) and time (4h+ for full runs).

**Minimal SLURM template:**
```bash
#!/bin/bash
#SBATCH --job-name=judgellm_equiv
#SBATCH --output=logs/judgellm_%j.out
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=04:00:00

module purge
module load cuda/12.1
module load anaconda3
source ~/.bashrc

conda activate your_env_name
export HF_HOME=/gpfs/projects/$USER/hf_cache
mkdir -p $HF_HOME

cd $SLURM_SUBMIT_DIR
python judgeLLM/equivalence_runner.py \
    --input judgeLLM/hard_negatives.json \
    --output judgeLLM/equivalence_results.json \
    --max-new-tokens 256
```

### Device management in code

- `model_loader.py` already uses `device_map="auto"`, which will place the model on GPU if available.
- No additional code changes are required; PyTorch will automatically detect CUDA.
- To force CPU-only for debugging: set `CUDA_VISIBLE_DEVICES=""` before running.

### Performance notes

- Qwen3-0.6B on GPU (NVIDIA A100/H100) should process pairs in ~100–500 ms each.
- For full runs (100+ pairs), expect ~1–5 minutes total runtime on a single GPU.
- Consider multi-worker concurrency (future feature) for larger corpora.

## Next steps (suggested implementation order)

1. Keep the prompt in one editable block and finalize the equivalence rubric.
2. Implement a lightweight pair-record loader for JSON inputs.
3. Implement a single-threaded runner that reads the JSON file and calls the model for one pair at a time.
4. Add JSON schema validation and format-repair logic.
5. Add output persistence and run metadata.
6. Add gold subset tests and CI integration.

## Questions for you

- Do you want output as a single JSON array, JSONL, or both?
- Do you want the prompt to live in `plan.md` as a reference copy, or in a separate prompt file that the runner loads directly?

-- End of plan
