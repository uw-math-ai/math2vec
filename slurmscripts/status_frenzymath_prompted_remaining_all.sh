#!/bin/bash

set -euo pipefail

RESULTS_DIR="${RESULTS_DIR:-/gpfs/scrubbed/$USER/math2vec_runs/frenzymath}"
LOG_DIR="${LOG_DIR:-/gpfs/scrubbed/$USER/math2vec_logs/frenzymath}"
OUTPUT_MODE="text"

if [[ "${1:-}" == "--json" ]]; then
  OUTPUT_MODE="json"
fi

python - "$@" <<'PY'
import json
import os
import subprocess
import sys
from pathlib import Path

results_dir = Path(os.environ["RESULTS_DIR"])
log_dir = Path(os.environ["LOG_DIR"])
output_mode = "json" if len(sys.argv) > 1 and sys.argv[1] == "--json" else "text"

task_prompts = {
    "informal_to_type": "Instruct: Find the most mathematically similar Lean type to this statement\nQuery: ",
    "type_to_informal": "Instruct: Find the most mathematically similar statement as a Lean type\nQuery: ",
    "informal_to_signature": "Instruct: Find the most mathematically similar Lean signature to this statement\nQuery: ",
    "signature_to_informal": "Instruct: Find the most mathematically similar statement as a Lean signature\nQuery: ",
    "type_to_signature": "Instruct: Find the most mathematically similar Lean signature to this Lean type\nQuery: ",
    "signature_to_type": "Instruct: Find the most mathematically similar Lean type to this Lean signature\nQuery: ",
}
task_order = [
    "informal_to_type",
    "type_to_informal",
    "informal_to_signature",
    "signature_to_informal",
    "type_to_signature",
    "signature_to_type",
]
models = [
    "Qwen/Qwen3-Embedding-4B",
    "Qwen/Qwen3-Embedding-8B",
    "Octen/Octen-Embedding-8B",
    "nvidia/llama-embed-nemotron-8b",
    "tencent/KaLM-Embedding-Gemma3-12B-2511",
    "codefuse-ai/F2LLM-v2-14B",
    "microsoft/harrier-oss-v1-27b",
]

def slug(model_name: str) -> str:
    return model_name.lower().replace("/", "_").replace(":", "_")

try:
    squeue_text = subprocess.run(
        ["squeue", "-u", os.environ["USER"], "--noheader", "-o", "%j|%T|%M"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
except Exception:
    squeue_text = ""

running = {}
for line in squeue_text.splitlines():
    if not line.strip():
        continue
    job_name, state, elapsed = line.split("|", 2)
    for task in task_order:
        if task not in job_name:
            continue
        for model_name in models:
            if slug(model_name) in job_name:
                running[(task, model_name)] = {
                    "status": "RUNNING",
                    "elapsed": elapsed,
                    "job_name": job_name,
                }

def classify_run(run_dir: Path):
    payload = None
    kind = None
    payload_path = None
    for candidate, run_kind in [(run_dir / "results.json", "DONE"), (run_dir / "failure.json", "FAILED")]:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
            kind = run_kind
            payload_path = candidate
            break
        except Exception:
            continue
    if payload is None:
        return None

    config = payload.get("config", {})
    task_preset = config.get("task_preset")
    model_name = config.get("model_name")
    resolved = config.get("resolved_query_encoding_settings", {})
    prompt = resolved.get(task_preset, {}).get("prompt")
    if task_preset not in task_prompts:
        return None
    if model_name not in models:
        return None
    if prompt != task_prompts[task_preset]:
        return None
    if config.get("query_split") != "test":
        return None
    if config.get("corpus_splits") != ["train", "val", "test"]:
        return None
    return {
        "task": task_preset,
        "model_name": model_name,
        "status": kind,
        "run_dir": str(run_dir),
        "payload_path": str(payload_path),
        "created_at_utc": payload.get("created_at_utc"),
        "error_message": payload.get("error_message"),
        "total_seconds": payload.get("timing_seconds", {}).get("total"),
    }

latest = {}
if results_dir.exists():
    for run_dir in sorted(results_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        classified = classify_run(run_dir)
        if classified is None:
            continue
        key = (classified["task"], classified["model_name"])
        if key not in latest:
            latest[key] = classified

status_payload = {}
for task in task_order:
    status_payload[task] = {}
    for model_name in models:
        key = (task, model_name)
        if key in running:
            status_payload[task][model_name] = running[key]
            continue
        if key in latest:
            status_payload[task][model_name] = latest[key]
            continue
        status_payload[task][model_name] = {
            "status": "NOT_STARTED",
        }

if output_mode == "json":
    print(json.dumps(status_payload, indent=2, ensure_ascii=True))
    raise SystemExit(0)

print("prompted FrenzyMath campaign status")
print(f"results_dir={results_dir}")
print(f"log_dir={log_dir}")
print()

for task in task_order:
    print(task)
    for model_name in models:
        item = status_payload[task][model_name]
        status = item["status"]
        if status == "RUNNING":
            print(f"  {model_name}: RUNNING elapsed={item['elapsed']} job={item['job_name']}")
        elif status == "DONE":
            total_text = "unknown"
            total_seconds = item.get("total_seconds")
            if isinstance(total_seconds, (int, float)):
                total_text = f"{total_seconds/60:.1f}m"
            print(f"  {model_name}: DONE total={total_text} run_dir={item['run_dir']}")
        elif status == "FAILED":
            print(f"  {model_name}: FAILED run_dir={item['run_dir']} error={item.get('error_message')}")
        else:
            print(f"  {model_name}: NOT_STARTED")
    print()
PY
