#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/tillicum_mathlib_full.slurm — perturb the full math2vec Mathlib
# corpus, certify the variants, then fine-tune.
#
# Future work. Do not submit this as the next job. One submission holds 4
# GPUs for 12 hours (about $43). The corpus is FrenzyMath/mathlib_informal_v4.19.0
# (on the order of 10^5 theorems). Perturb and certify will not finish in one
# allocation. Resubmit the same command; each phase resumes. Training starts
# only once every anchor has been perturbed and every perturbed anchor has
# been certified, so a partial run cannot overwrite a checkpoint.
#
# Prerequisite, once, on a login node: bash scripts/tillicum_setup.sh
# That caches the dataset, the Mathlib oleans, and Qwen3-Embedding-8B.
# Compute nodes are offline.
#
# Usage (from perturbations/):
#     sbatch scripts/tillicum_mathlib_full.slurm
#     # same command, again, until the log says the train phase ran
#
#     # cheap end-to-end check of the plumbing, not a result:
#     WIGGLE_MATHLIB_LIMIT=20 sbatch --qos=debug --gpus=1 --cpus-per-task=8 \
#         --mem=180G --time=00:30:00 scripts/tillicum_mathlib_full.slurm
#
# Knobs:
#     WIGGLE_MATHLIB_OUT     output dir (default data/mathlib-full)
#     WIGGLE_MATHLIB_LIMIT   first N anchors only
#     WIGGLE_RETAIN_ROWS     informal→Lean pairs mixed into training
#                            (default 200000, which is the whole cached corpus)
#     WIGGLE_TRAIN_ARGS      extra args for train_perturbation_mnrl.py
#     WIGGLE_FORCE_TRAIN=1   train on whatever is certified, even if unfinished
# ─────────────────────────────────────────────────────────────────────────────

#SBATCH --job-name=wiggle-mathlib
#SBATCH --account=mathai
#SBATCH --qos=normal
#SBATCH --gpus=4
#SBATCH --cpus-per-task=32
#SBATCH --mem=600G
#SBATCH --time=12:00:00
#SBATCH -o %x_%j.out

set -eo pipefail
JOB_START=$(date +%s)

find_project_root() {
    local d
    for d in "${WIGGLE_PROJECT:-}" \
             "${SLURM_SUBMIT_DIR:-}" \
             "${SLURM_SUBMIT_DIR:-}/perturbations" \
             "${SLURM_SUBMIT_DIR:-}/.." \
             "$(dirname "${BASH_SOURCE[0]}")/.."; do
        if [[ -n "$d" && -f "$d/Wiggle.lean" ]]; then
            (cd "$d" && pwd)
            return 0
        fi
    done
    return 1
}

if ! PROJECT_ROOT="$(find_project_root)"; then
    echo "error: cannot find Wiggle.lean; submit from perturbations/ or set WIGGLE_PROJECT" >&2
    exit 2
fi
cd "$PROJECT_ROOT"
FINETUNE_DIR="$(cd "$PROJECT_ROOT/../finetune" && pwd)"

# shellcheck source=tillicum_env.sh
source scripts/tillicum_env.sh
if ! wiggle_activate; then
    echo "error: could not activate $WIGGLE_ENV; run scripts/tillicum_setup.sh first" >&2
    exit 2
fi
if ! command -v lake >/dev/null 2>&1; then
    echo "error: lake not on PATH (ELAN_HOME=$ELAN_HOME); run scripts/tillicum_setup.sh first" >&2
    exit 2
fi

export HF_HUB_OFFLINE=1 HF_DATASETS_OFFLINE=1 TOKENIZERS_PARALLELISM=false

OUT="${WIGGLE_MATHLIB_OUT:-data/mathlib-full}"
ANCHORS="$OUT/mathlib_anchors.jsonl"
CPUS="${SLURM_CPUS_PER_TASK:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)}"
LIMIT_ARGS=()
[[ -n "${WIGGLE_MATHLIB_LIMIT:-}" ]] && LIMIT_ARGS=(--limit "$WIGGLE_MATHLIB_LIMIT")
mkdir -p "$OUT"

time_limit_seconds() {
    local t d=0 h=0 m=0 s=0
    t="$(squeue -h -j "${SLURM_JOB_ID:-0}" -o %l 2>/dev/null || true)"
    [[ -z "$t" || "$t" == UNLIMITED || "$t" == INVALID ]] && return 1
    [[ "$t" == *-* ]] && { d="${t%%-*}"; t="${t#*-}"; }
    IFS=: read -r -a parts <<< "$t"
    case ${#parts[@]} in
        3) h=${parts[0]}; m=${parts[1]}; s=${parts[2]} ;;
        2) m=${parts[0]}; s=${parts[1]} ;;
        1) m=${parts[0]} ;;
    esac
    echo $(( 10#$d * 86400 + 10#$h * 3600 + 10#$m * 60 + 10#$s ))
}

# Stop starting new Lean work 20 minutes before the wall clock, so the
# in-flight anchors can finish and the JSONL is not truncated.
DEADLINE=""
if LIMIT_S="$(time_limit_seconds)"; then
    DEADLINE=$(( JOB_START + LIMIT_S - 1200 ))
fi
past_deadline() {
    [[ -n "$DEADLINE" ]] && (( $(date +%s) >= DEADLINE ))
}

# perturb | certify | train | done
next_phase() {
    python - "$ANCHORS" "$OUT" "${WIGGLE_FORCE_TRAIN:-0}" <<'PY'
import json, sys
from pathlib import Path

anchors_path, out = Path(sys.argv[1]), Path(sys.argv[2])
force = sys.argv[3] == "1"

def ids(path, key):
    found = set()
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            found.add(json.loads(line)[key])
        except (json.JSONDecodeError, KeyError):
            continue
    return found

wanted = ids(anchors_path, "id")
perturbed = ids(out / "anchors.jsonl", "id")
if not wanted or (wanted - perturbed):
    print("perturb")
elif ids(out / "results.jsonl", "source_id") - ids(out / "certified.jsonl", "source_id"):
    print("certify")
elif (out / "TRAIN_COMPLETE").exists() and not force:
    print("done")
else:
    print("train")
PY
}

echo "──────────────────────────────────────────────────────────────────────"
echo " Full Mathlib perturbation + training"
echo " host    : $(hostname)"
echo " job id  : ${SLURM_JOB_ID:-<none>}"
echo " project : $PROJECT_ROOT"
echo " output  : $PROJECT_ROOT/$OUT"
echo " cpus    : $CPUS"
[[ -n "${WIGGLE_MATHLIB_LIMIT:-}" ]] && echo " limit   : $WIGGLE_MATHLIB_LIMIT"
[[ -n "$DEADLINE" ]] && echo " reserve : no new Lean work after $(date -d "@$DEADLINE")"
echo "──────────────────────────────────────────────────────────────────────"

echo; echo "══ prepare anchors"
# One-time: older runs keyed anchors by a non-unique dataset index and skipped
# statements that only needed universe declarations. No-op once repaired.
python -u pipeline/rekey_mathlib_run.py --run "$OUT"
python -u pipeline/prepare_mathlib_full_anchors.py \
    --out "$ANCHORS" "${LIMIT_ARGS[@]}"

echo; echo "══ build Wiggle"
lake build Wiggle

while true; do
    if past_deadline; then
        echo "time reserve reached during $(next_phase); resubmit the same command"
        exit 0
    fi
    PHASE="$(next_phase)"
    echo; echo "══ phase: $PHASE"
    DEADLINE_ARGS=()
    [[ -n "$DEADLINE" ]] && DEADLINE_ARGS=(--deadline-epoch "$DEADLINE")
    case "$PHASE" in
        perturb)
            python -u pipeline/run_benchmark_review.py \
                --anchors-file "$ANCHORS" \
                --skip-noncompiling --resume \
                "${DEADLINE_ARGS[@]}" \
                --num-workers "$CPUS" \
                --out "$OUT"
            ;;
        certify)
            python -u pipeline/certify_labels.py --run "$OUT" \
                --resume "${DEADLINE_ARGS[@]}" \
                --num-workers "$CPUS"
            ;;
        train)
            DATA="$OUT/training"
            BASE_MODEL="${WIGGLE_BASE_MODEL:-Qwen/Qwen3-Embedding-8B}"
            RUN_NAME="${WIGGLE_RUN_NAME:-mathlib_full}"
            CKPT="$TILLICUM_BASE/checkpoints/$RUN_NAME"
            read -r -a TRAIN_ARGS <<< "${WIGGLE_TRAIN_ARGS:-}"
            RETAIN="${WIGGLE_RETAIN_ROWS:-200000}"
            echo "══ export"
            python -u pipeline/export_training_data.py --run "$OUT"
            BASE_PATH="$(python - "$BASE_MODEL" <<'EOF'
import sys
import mteb
from huggingface_hub import snapshot_download
name = sys.argv[1]
print(snapshot_download(name, revision=mteb.get_model_meta(name).revision, local_files_only=True))
EOF
)"
            echo "══ train  base=$BASE_PATH  checkpoint=$CKPT"
            mkdir -p "$CKPT"
            (cd "$FINETUNE_DIR" && python -u train_perturbation_mnrl.py \
                --train_jsonl "$PROJECT_ROOT/$DATA/train.jsonl" \
                --dev_jsonl "$PROJECT_ROOT/$DATA/dev.jsonl" \
                --model_name "$BASE_PATH" \
                --device cuda \
                --wrap_query \
                --retention_rows "$RETAIN" \
                --epochs 1 \
                --output_dir "$CKPT" \
                --checkpoint_dir "$CKPT/steps" \
                "${TRAIN_ARGS[@]}")
            echo "══ MTEB eval on the dev projects"
            python -u pipeline/mteb_perturbation_eval.py \
                --results "$DATA/dev_certified.jsonl" \
                --models "$BASE_MODEL" "$CKPT" \
                --base-model "$BASE_MODEL" \
                --out "$DATA/mteb-$RUN_NAME"
            echo "job ${SLURM_JOB_ID:-local} $(date -Is)" > "$OUT/TRAIN_COMPLETE"
            echo "scores: $CKPT/metrics.json"
            exit 0
            ;;
        done)
            echo "perturb, certify, and training export already exist in $OUT"
            echo "set WIGGLE_FORCE_TRAIN=1 to train again"
            exit 0
            ;;
        *)
            echo "unknown phase: $PHASE" >&2
            exit 2
            ;;
    esac
done
