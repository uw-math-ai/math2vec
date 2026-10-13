import argparse
import json
import os

from typeclass_implication_table import BRACKET_RE
from typeclass_implication_table import class_expr_from_bracket
from typeclass_implication_table import head_symbol
from typeclass_implication_table import return_expr

# PROJECT_DIR is the Lake project root (two levels up from src/instance_graph/).
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_INSTANCES = os.path.join(PROJECT_DIR, "data", "mathlib_instances.jsonl")
DEFAULT_OUTPUT = os.path.join(PROJECT_DIR, "data", "instance_implications.jsonl")


def instance_edges(instance_path: str, direct_only: bool):
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    with open(instance_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            type_str = row["type"]
            target = return_expr(type_str)
            if not target:
                continue

            target_head = head_symbol(target)
            if not target_head:
                continue

            sources = tuple(
                source
                for source in (class_expr_from_bracket(match) for match in BRACKET_RE.findall(type_str))
                if source is not None
            )
            if not sources:
                continue
            if direct_only and len(sources) != 1:
                continue

            for source in sources:
                if source == target:
                    continue
                source_head = head_symbol(source)
                if not source_head:
                    continue
                key = (source, target, sources)
                if key in seen:
                    continue
                seen.add(key)

                yield {
                    "source": source,
                    "target": target,
                    "source_head": source_head,
                    "target_head": target_head,
                    "assumptions": list(sources),
                    "edge_kind": "direct" if len(sources) == 1 else "contextual",
                    "verification": "registered_instance",
                    "decl_name": row["name"],
                    "priority": row["priority"],
                    "attrKind": row["attrKind"],
                }


def write_jsonl(path: str, rows) -> int:
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build implication edges from Lean's registered instance dump."
    )
    parser.add_argument("--instances", default=DEFAULT_INSTANCES)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--direct-only",
        action="store_true",
        help="Only keep instances with one source assumption, so source alone implies target.",
    )
    args = parser.parse_args()

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    count = write_jsonl(args.output, instance_edges(args.instances, args.direct_only))
    print(f"Wrote {count} instance implication edges to {args.output}")


if __name__ == "__main__":
    main()
