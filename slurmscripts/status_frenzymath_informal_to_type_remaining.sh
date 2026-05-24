#!/bin/bash

set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/gpfs/scrubbed/$USER/math2vec_runs/frenzymath}"
LOG_DIR="${LOG_DIR:-/gpfs/scrubbed/$USER/math2vec_logs/frenzymath}"

python - <<'PY'
import json
import os
import subprocess
from pathlib import Path

results_dir = Path(os.environ["RESULTS_DIR"])
log_dir = Path(os.environ["LOG_DIR"])
target_task = "informal_to_type"
target_prompt = "Instruct: Find the most mathematically similar Lean type to this statement\nQuery: "
targets = [
    "Qwen/Qwen3-Embedding-8B",
    "nvidia/llama-embed-nemotron-8b",
    "tencent/KaLM-Embedding-Gemma3-12B-2511",
    "codefuse-ai/F2LLM-v2-14B",
    "microsoft/harrier-oss-v1-27b",
]

try:
    squeue_text = subprocess.run(
        ["squeue", "-u", os.environ["USER"], "--noheader", "-o", "%j|%T|%M"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
except Exception:
    squeue_text = ""

running_by_model = {}
for line in squeue_text.splitlines():
    if not line.strip():
        continue
    job_name, state, elapsed = line.split("|", 2)
    for model_name in targets:
        model_slug = model_name.lower().replace("/", "_").replace(":", "_")
        if target_task in job_name and model_slug in job_name:
            running_by_model[model_name] = {
                "state": state,
                "elapsed": elapsed,
                "job_name": job_name,
            }

def classify_run(run_dir: Path):
    results_path = run_dir / "results.json"
    failure_path = run_dir / "failure.json"
    payload = None
    kind = None
    path = None
    if results_path.exists():
        try:
            payload = json.loads(results_path.read_text(encoding="utf-8"))
            kind = "success"
            path = results_path
        except Exception:
            payload = None
    if payload is None and failure_path.exists():
        try:
            payload = json.loads(failure_path.read_text(encoding="utf-8"))
            kind = "failure"
            path = failure_path
        except Exception:
            payload = None
    if payload is None:
        return None
    config = payload.get("config", {})
    resolved = config.get("resolved_query_encoding_settings", {})
    task_settings = resolved.get(target_task, {})
    if (
        config.get("task_preset") != target_task
        or config.get("model_name") not in targets
        or task_settings.get("prompt") != target_prompt
        or config.get("query_split") != "test"
        or config.get("corpus_splits") != ["train", "val", "test"]
    ):
        return None
    return {
        "kind": kind,
        "model_name": config.get("model_name"),
        "run_dir": str(run_dir),
        "path": str(path),
        "created_at_utc": payload.get("created_at_utc"),
        "error_message": payload.get("error_message"),
        "total_seconds": payload.get("timing_seconds", {}).get("total"),
    }

latest_by_model = {}
if results_dir.exists():
    for run_dir in sorted(results_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        classified = classify_run(run_dir)
        if classified is None:
            continue
        model_name = classified["model_name"]
        if model_name not in latest_by_model:
            latest_by_model[model_name] = classified

print("informal_to_type prompted status")
print(f"results_dir={results_dir}")
print(f"log_dir={log_dir}")
print()

for model_name in targets:
    if model_name in running_by_model:
        running = running_by_model[model_name]
        print(f"{model_name}: RUNNING elapsed={running['elapsed']} job={running['job_name']}")
        continue
    latest = latest_by_model.get(model_name)
    if latest is None:
        print(f"{model_name}: NOT_STARTED")
        continue
    if latest["kind"] == "success":
        total_seconds = latest["total_seconds"]
        total_text = "unknown"
        if isinstance(total_seconds, (int, float)):
            total_text = f"{total_seconds/60:.1f}m"
        print(f"{model_name}: DONE total={total_text} run_dir={latest['run_dir']}")
    else:
        print(f"{model_name}: FAILED run_dir={latest['run_dir']} error={latest['error_message']}")
PY
