#!/bin/bash
# ---------------------------------------------------------------------------
# Post-job collection: wall time, GPU-hours, [extra] counts, and (optionally)
# archiving to the backed-up project folder. Login node; no GPU.
#
#   bash collect.sh mv3_qwen8b_a1_ep2
#   bash collect.sh mv3_qwen8b_a1_ep2 mv3_qwen8b_paper_ep2
#   bash collect.sh --archive mv3_qwen8b_a1_ep2 mv3_qwen8b_paper_ep2
#
# Writes checkpoints/<RUN>/runinfo.json, which report.py picks up for the
# Wall / GPU-h columns. Re-runnable. --archive only ever copies, never deletes.
# ---------------------------------------------------------------------------
set -euo pipefail

WORK=/gpfs/scrubbed/$USER/mathlib-ft
ARCHIVE_ROOT=/gpfs/projects/mathai/math2vec/experiments/$USER/a1_docstrings

DO_ARCHIVE=0
if [ "${1:-}" = "--archive" ]; then DO_ARCHIVE=1; shift; fi
if [ $# -eq 0 ]; then
  echo "usage: bash collect.sh [--archive] RUN_NAME [RUN_NAME ...]" >&2
  exit 2
fi

cd "$WORK"

for RUN in "$@"; do
  echo "================================================================"
  echo "RUN: $RUN"
  echo "================================================================"

  OUT="checkpoints/$RUN"
  if [ ! -d "$OUT" ]; then
    echo "  no output dir $OUT -- job may not have started or RUN name is wrong"
    continue
  fi

  # Both arms share --job-name=mv3_qwen8b, so find the log by its RUN= echo line.
  LOG=$(grep -l "RUN=$RUN\( \|$\)" logs/*.out 2>/dev/null | xargs -r ls -t 2>/dev/null | head -1 || true)
  if [ -z "${LOG:-}" ]; then
    echo "  WARNING: no log in logs/ contains 'RUN=$RUN'"
    JOBID=""
  else
    echo "  log: $LOG"
    JOBID=$(basename "$LOG" .out | sed 's/.*_//')
  fi

  ELAPSED="?"; GPUH="?"; STATE="?"
  if [ -n "$JOBID" ]; then
    echo "  --- sacct ---"
    sacct -j "$JOBID" -X -P -o JobID,JobName,State,Elapsed,ElapsedRaw,AllocTRES,Start,End \
      | column -t -s'|' | sed 's/^/  /' || echo "  sacct unavailable"
    LINE=$(sacct -j "$JOBID" -X -n -P -o State,Elapsed,ElapsedRaw,AllocTRES 2>/dev/null | head -1 || true)
    if [ -n "${LINE:-}" ]; then
      STATE=$(echo "$LINE"   | cut -d'|' -f1)
      ELAPSED=$(echo "$LINE" | cut -d'|' -f2)
      RAW=$(echo "$LINE"     | cut -d'|' -f3)
      TRES=$(echo "$LINE"    | cut -d'|' -f4)
      NGPU=$(echo "$TRES" | tr ',' '\n' | awk -F= '/gres\/gpu=/{print $2}' | head -1)
      NGPU=${NGPU:-1}
      GPUH=$(awk -v s="${RAW:-0}" -v g="$NGPU" 'BEGIN{printf "%.2f", s/3600*g}')
      echo "  state=$STATE  elapsed=$ELAPSED  gpus=$NGPU  GPU-hours=$GPUH"
    fi
  fi

  # Sidecar for report.py
  python3 - "$OUT" "$ELAPSED" "$GPUH" "$STATE" "${JOBID:-}" "${LOG:-}" <<'PY'
import json, sys
out, elapsed, gpuh, state, jobid, log = sys.argv[1:7]
json.dump({"elapsed": elapsed, "gpu_hours": gpuh, "state": state,
           "job_id": jobid, "log": log},
          open(f"{out}/runinfo.json", "w"), indent=2)
print(f"  wrote {out}/runinfo.json")
PY

  if [ -n "${LOG:-}" ]; then
    echo "  --- [extra] counts from the log ---"
    grep '^\[extra\]' "$LOG" | sed 's/^/  /' || echo "  (none -- this arm ran without EXTRA)"
    echo "  --- any errors / OOM ---"
    grep -iE 'Traceback|CUDA out of memory|Error|CANCELLED|DUE TO' "$LOG" | head -5 | sed 's/^/  /' \
      || echo "  (none)"
  fi

  if [ -f "$OUT/metrics.json" ]; then
    echo "  metrics.json: present"
  else
    echo "  metrics.json: MISSING -- job did not reach the end of training"
  fi

  if [ "$DO_ARCHIVE" = "1" ]; then
    DEST="$ARCHIVE_ROOT/$RUN"
    echo "  --- archiving to $DEST ---"
    mkdir -p "$DEST"
    [ -f "$OUT/metrics.json" ] && cp -v "$OUT/metrics.json" "$DEST/"
    [ -f "$OUT/runinfo.json" ] && cp -v "$OUT/runinfo.json" "$DEST/"
    [ -n "${LOG:-}" ] && cp -v "$LOG" "$DEST/"
    for f in "$OUT"/eval_*.json; do [ -f "$f" ] && cp -v "$f" "$DEST/"; done
    echo "  NOTE: the model weights themselves stay on scratch (tens of GB)."
  fi
  echo
done

if [ "$DO_ARCHIVE" = "1" ]; then
  echo "Archived under $ARCHIVE_ROOT"
  ls -R "$ARCHIVE_ROOT" 2>/dev/null | head -40
fi

echo
echo "Next: python report.py checkpoints/<RUN> [checkpoints/<OTHER_RUN>]"
