"""
wiggle — Lean statement perturbation library.

Public API:

    from wiggle import (
        # Registry & truth propagation
        PERTURBATIONS, TRANSFORMS, PROPAGATION_RULES, Perturbation,
        is_true, compose_truth,

        # Chain runner & corpus pipeline
        apply_chain, run_pipeline,

        # Lean execution backend
        compile_lean, extract_goal,
        get_project_root,
    )

Transforms live under ``wiggle.transforms.*`` and are auto-collected into the
registry; you almost never import them directly.
"""

from wiggle.registry import (
    PERTURBATIONS,
    PROPAGATION_RULES,
    TRANSFORMS,
    Perturbation,
)
from wiggle.propagation import compose_truth, is_true
from wiggle.chains import apply_chain, normalize_statement, parse_extracted_lean
from wiggle.pipeline import run_pipeline
from wiggle.lean_runner import compile_lean, extract_goal, get_project_root
from wiggle.parallel import parse_duration, run_parallel
from wiggle.shards import ShardWriter, iter_shard_records, scan_completed_anchors

__all__ = [
    "PERTURBATIONS",
    "PROPAGATION_RULES",
    "TRANSFORMS",
    "Perturbation",
    "compose_truth",
    "is_true",
    "apply_chain",
    "normalize_statement",
    "parse_extracted_lean",
    "run_pipeline",
    "compile_lean",
    "extract_goal",
    "get_project_root",
    "run_parallel",
    "parse_duration",
    "ShardWriter",
    "scan_completed_anchors",
    "iter_shard_records",
]
