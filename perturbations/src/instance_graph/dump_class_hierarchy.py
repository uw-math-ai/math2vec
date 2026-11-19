"""
dump_class_hierarchy.py

Dump the Mathlib typeclass ``extends`` hierarchy to JSONL by running the
``#wiggle_dump_class_hierarchy`` command defined in ``Wiggle.lean``.

Each output line is one class:

    {"name": "Mathlib.Algebra.Field", "parents": ["CommRing", ...]}

``name`` and ``parents`` are fully-qualified Lean names exactly as Lean prints
them; :mod:`typeclass_mutate` derives short names (last dotted component) when
it loads the file. This dump is the single source of truth for the typeclass
hierarchy used by the typeclass-mutation perturbations — it replaces the old
hand-maintained ``_HARDCODED_PARENTS`` / ``_PROP_TC_PARENTS`` maps and the
Mathlib-docs HTML scrape.

Regenerate after a Mathlib/Lean toolchain bump:

    python src/instance_graph/dump_class_hierarchy.py
"""

import argparse
import os
import subprocess

# PROJECT_DIR is the Lake project root (two levels up from src/instance_graph/).
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUTPUT = os.path.join(PROJECT_DIR, "data", "class_hierarchy.jsonl")


def dump_hierarchy(output_path: str, timeout: int) -> None:
    tmp_path = os.path.join(PROJECT_DIR, "_dump_class_hierarchy_tmp.lean")
    code = "import Wiggle\n\n#wiggle_dump_class_hierarchy\n"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)

        result = subprocess.run(
            ["lake", "env", "lean", tmp_path],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        if result.returncode != 0 or "error:" in output:
            raise RuntimeError(output)

        rows = [line for line in output.splitlines() if line.startswith("{")]
        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                f.write(row + "\n")
        print(f"Wrote {len(rows)} classes to {output_path}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dump the Mathlib typeclass extends-hierarchy as JSONL."
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    dump_hierarchy(args.output, args.timeout)


if __name__ == "__main__":
    main()
