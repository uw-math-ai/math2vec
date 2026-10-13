# scripts/tillicum_env.sh — shared Tillicum environment, sourced (not executed)
# by scripts/tillicum_setup.sh and scripts/tillicum_tests.slurm.
#
# Everything heavy lives in project storage: $HOME is capped at 10 GB, and
# /gpfs/scrubbed is purged after 60 days of inactivity, which breaks conda envs.
#
# Override any of these before sourcing / submitting, e.g.
#     TILLICUM_BASE=/gpfs/projects/mathai/shared sbatch scripts/tillicum_tests.slurm

: "${TILLICUM_BASE:=/gpfs/projects/mathai/$USER}"
: "${ELAN_HOME:=$TILLICUM_BASE/elan}"
: "${WIGGLE_ENV:=$TILLICUM_BASE/envs/wiggle}"

export TILLICUM_BASE ELAN_HOME WIGGLE_ENV
export PATH="$ELAN_HOME/bin:$PATH"

# `lake exe cache get` downloads ~5 GB of Mathlib archives into
# $XDG_CACHE_HOME/mathlib, and conda/pip cache into $HOME by default.
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$TILLICUM_BASE/cache}"
export MATHLIB_CACHE_DIR="${MATHLIB_CACHE_DIR:-$XDG_CACHE_HOME/mathlib}"
export CONDA_PKGS_DIRS="${CONDA_PKGS_DIRS:-$TILLICUM_BASE/conda/pkgs}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$XDG_CACHE_HOME/pip}"

# Packages in ~/.local shadow the env's own and have broken the pytest
# plugins before.
export PYTHONNOUSERSITE=1

# Load Tillicum's conda module and activate the Wiggle env. Batch shells are
# non-interactive, so make sure Lmod's `module` function exists first.
wiggle_activate() {
    if ! type module >/dev/null 2>&1; then
        # shellcheck disable=SC1091
        source /etc/profile
    fi
    module load conda
    eval "$(conda shell.bash hook)"
    conda activate "$WIGGLE_ENV"
}
