#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/tillicum_setup.sh — one-time Tillicum setup. Run on the LOGIN node
# (it is all downloads; nothing here is compute-heavy):
#
#     bash scripts/tillicum_setup.sh
#
# Idempotent: re-running skips whatever is already installed. Installs into
# $TILLICUM_BASE (default /gpfs/projects/mathai/$USER, see tillicum_env.sh):
#     elan (Lean toolchain manager)   → $ELAN_HOME
#     conda env with requirements.txt → $WIGGLE_ENV
#     prebuilt Mathlib .olean cache   → <project>/.lake
#     embedding models for MTEB eval  → $HF_HOME (Qwen3-Embedding-8B is ~16 GB)
#
# Compiling Wiggle.lean itself (`lake build Wiggle`) is left to the test job,
# since login nodes are not for compute.
# ─────────────────────────────────────────────────────────────────────────────

set -eo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/.." && pwd)"
# shellcheck source=tillicum_env.sh
source "$HERE/tillicum_env.sh"

echo "project root : $PROJECT_ROOT"
echo "base dir     : $TILLICUM_BASE"
echo "elan home    : $ELAN_HOME"
echo "conda env    : $WIGGLE_ENV"
echo

if [[ "$(hostname)" != tillicum-login* ]]; then
    echo "warning: expected a tillicum-login node, got $(hostname)" >&2
fi

mkdir -p "$TILLICUM_BASE" "$XDG_CACHE_HOME" "$CONDA_PKGS_DIRS" "$(dirname "$WIGGLE_ENV")"

# ── 1. elan ──────────────────────────────────────────────────────────────────
if [[ -x "$ELAN_HOME/bin/elan" ]]; then
    echo "[1/4] elan already installed: $("$ELAN_HOME/bin/elan" --version)"
else
    echo "[1/4] installing elan into $ELAN_HOME"
    curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
        | sh -s -- -y --no-modify-path --default-toolchain none
fi

# ── 2. conda env ─────────────────────────────────────────────────────────────
if ! type module >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    source /etc/profile
fi
module load conda
eval "$(conda shell.bash hook)"
if [[ -d "$WIGGLE_ENV" ]]; then
    echo "[2/4] conda env exists: $WIGGLE_ENV"
else
    echo "[2/4] creating conda env at $WIGGLE_ENV"
    conda create -y --prefix "$WIGGLE_ENV" python=3.12
fi
conda activate "$WIGGLE_ENV"
pip install --upgrade pip
pip install torch --index-url "$WIGGLE_TORCH_INDEX"
pip install -r "$PROJECT_ROOT/requirements.txt"

# ── 3. Mathlib ───────────────────────────────────────────────────────────────
# Fetches Mathlib (git) plus its prebuilt .olean files so nothing has to be
# compiled from source. Also installs the toolchain pinned in lean-toolchain.
echo "[3/4] fetching Mathlib cache (first run: several GB, ~10 min)"
cd "$PROJECT_ROOT"
lake exe cache get

# ── 4. Embedding models ──────────────────────────────────────────────────────
# Download only (no loading: the 8B model would need ~30 GB of login-node
# RAM), at the revision mteb pins, which is what the offline job will ask for.
echo "[4/4] downloading embedding models into $HF_HOME: $WIGGLE_EMBED_MODELS"
mkdir -p "$HF_HOME" "$MTEB_CACHE"
# shellcheck disable=SC2086
python - $WIGGLE_EMBED_MODELS <<'EOF'
import sys
import mteb
from huggingface_hub import snapshot_download

for name in sys.argv[1:]:
    meta = mteb.get_model_meta(name)
    path = snapshot_download(name, revision=meta.revision)
    print(f"  {name} @ {meta.revision} -> {path}")
EOF

echo
echo "Setup done. Next, from $PROJECT_ROOT:"
echo "    sbatch scripts/tillicum_tests.slurm"
echo "    sbatch scripts/tillicum_blueprint.slurm"
