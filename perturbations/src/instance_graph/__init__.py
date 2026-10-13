"""Mathlib hierarchy/instance dump utilities.

CLI entry point, runnable from the project root:

    dump_class_hierarchy   - dump Mathlib's typeclass `extends` hierarchy as
                             JSONL (writes data/class_hierarchy.jsonl), which
                             typeclass_mutate.py reads. Run via
                             `python src/instance_graph/dump_class_hierarchy.py`.
"""
