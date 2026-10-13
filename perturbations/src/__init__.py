"""Wiggle perturbation library.

Importable modules:
    bounds              - regex-based inequality / numeric bound perturbations.
    typeclass_mutate    - Python text substitution guided by the Mathlib
                          typeclass hierarchy, verified via Lean compilation.

Subpackages:
    instance_graph      - dump_class_hierarchy.py: dumps Mathlib's `extends`
                          hierarchy to data/class_hierarchy.jsonl, which
                          typeclass_mutate reads. (Older instance-graph builders
                          live in archive/.)
"""
