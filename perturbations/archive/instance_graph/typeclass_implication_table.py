import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

# PROJECT_DIR is the Lake project root (two levels up from src/instance_graph/).
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_DATASET = "mathlib-initiative/mathlib-types"
DEFAULT_OUTPUT = os.path.join(PROJECT_DIR, "data", "typeclass_implications.jsonl")
DEFAULT_LEAN_CHECK_DIR = os.path.join(PROJECT_DIR, "data", "lean_synth_checks")

BRACKET_RE = re.compile(r"\[([^\[\]]+)\]")
FORALL_BINDER_RE = re.compile(r"[\{\(]\s*([^:\{\}\(\)\[\]]+?)\s*:\s*([^\{\}\(\)\[\],]+?)\s*[\}\)]")
UNIVERSE_RE = re.compile(r"\b[uv][A-Za-z0-9_]*\b")
IDENT_RE = re.compile(r"[A-Za-z_Α-Ωα-ω][A-Za-z0-9_'_Α-Ωα-ω₀-₉]*")

SKIP_TARGET_HEADS = {
    "Prop",
    "Sort",
    "Type",
    "True",
    "False",
    "Eq",
    "HEq",
    "Iff",
    "And",
    "Or",
    "Not",
    "Exists",
    "Subtype",
    "Sigma",
    "PSigma",
    "Prod",
    "Sum",
    "Option",
    "List",
    "Array",
    "Lean.Expr",
    "Lean.Syntax",
    "IO",
    "MetaM",
}


@dataclass(frozen=True)
class Candidate:
    decl_name: str
    module: str | None
    source: str
    target: str
    context_sources: tuple[str, ...]
    source_head: str
    target_head: str


def load_rows(dataset_path: str | None, limit: int | None) -> Iterator[dict[str, object]]:
    if dataset_path:
        yield from load_local_rows(dataset_path, limit)
        return

    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit(
            "Install optional dependencies first:\n"
            "  pip install datasets pandas pyarrow\n"
            "or pass --dataset-path with a local CSV/JSONL export of mathlib-types."
        ) from exc

    ds = load_dataset(DEFAULT_DATASET, split="train", streaming=True)
    for i, row in enumerate(ds):
        if limit is not None and i >= limit:
            break
        yield row


def load_local_rows(path: str, limit: int | None) -> Iterator[dict[str, object]]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".jsonl":
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if limit is not None and i >= limit:
                    break
                if line.strip():
                    yield json.loads(line)
        return

    if ext == ".csv":
        with open(path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if limit is not None and i >= limit:
                    break
                yield row
        return

    if ext == ".parquet":
        try:
            import pandas as pd
        except ImportError as exc:
            raise SystemExit("Reading parquet requires: pip install pandas pyarrow") from exc
        df = pd.read_parquet(path)
        if limit is not None:
            df = df.head(limit)
        yield from df.to_dict(orient="records")
        return

    raise SystemExit(f"Unsupported dataset file extension: {ext}")


def normalize_spaces(text: str) -> str:
    return " ".join(text.replace("∀", "forall").split())


def class_expr_from_bracket(content: str) -> str | None:
    text = normalize_spaces(content)
    if ":" in text:
        text = text.split(":", 1)[1].strip()
    if not text or text.startswith("Decidable "):
        return None
    return text


def head_symbol(expr: str) -> str | None:
    text = normalize_spaces(expr)
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1].strip()
    text = text.removeprefix("@").strip()
    if not text:
        return None
    raw = text.split()[0]
    raw = raw.split(".{", 1)[0]
    raw = raw.rstrip(",)")
    if raw in SKIP_TARGET_HEADS:
        return None
    return raw


def split_top_level(text: str, separators: set[str]) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    for i, ch in enumerate(text):
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0 and ch in separators:
            parts.append(text[start:i].strip())
            start = i + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def return_expr(type_str: str) -> str | None:
    text = normalize_spaces(type_str)
    comma_parts = split_top_level(text, {","})
    body = comma_parts[-1] if comma_parts else text
    arrow_parts = split_top_level(body.replace("->", "→"), {"→"})
    result = arrow_parts[-1] if arrow_parts else body
    return result.strip() or None


def extract_binders(type_str: str) -> list[tuple[list[str], str]]:
    binders: list[tuple[list[str], str]] = []
    for names_text, binder_type in FORALL_BINDER_RE.findall(type_str):
        names = [
            name
            for name in names_text.split()
            if name and not name.startswith("_") and IDENT_RE.fullmatch(name)
        ]
        if names:
            binders.append((names, binder_type.strip()))
    return binders


def names_used(exprs: Iterable[str]) -> set[str]:
    used: set[str] = set()
    heads = {head_symbol(expr) for expr in exprs}
    for expr in exprs:
        for token in IDENT_RE.findall(expr):
            if token not in heads:
                used.add(token)
    return used


def lean_prelude_for(type_str: str, exprs: Iterable[str]) -> str:
    expr_list = list(exprs)
    used = names_used(expr_list)
    lines: list[str] = ["import Mathlib", ""]

    universes = sorted(set(UNIVERSE_RE.findall(type_str)))
    if universes:
        lines.append("universe " + " ".join(universes))

    for names, binder_type in extract_binders(type_str):
        kept = [name for name in names if name in used]
        if kept:
            binder_parts = " ".join(f"{{{name} : {binder_type}}}" for name in kept)
            lines.append(f"variable {binder_parts}")

    return "\n".join(lines) + "\n"


def candidate_rows(rows: Iterable[dict[str, object]]) -> Iterator[tuple[Candidate, str]]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for row in rows:
        type_str = str(row.get("type") or "")
        if "[" not in type_str:
            continue

        sources = tuple(
            source
            for source in (class_expr_from_bracket(match) for match in BRACKET_RE.findall(type_str))
            if source is not None
        )
        if not sources:
            continue

        target = return_expr(type_str)
        if not target:
            continue

        target_head = head_symbol(target)
        if not target_head:
            continue

        source_heads = {head_symbol(source) for source in sources}
        if target_head not in source_heads and "." not in target_head and target_head[0].islower():
            continue

        for source in sources:
            source_head = head_symbol(source)
            if not source_head or source == target:
                continue
            key = (source, target, sources)
            if key in seen:
                continue
            seen.add(key)
            yield Candidate(
                decl_name=str(row.get("name") or ""),
                module=str(row.get("module") or "") or None,
                source=source,
                target=target,
                context_sources=sources,
                source_head=source_head,
                target_head=target_head,
            ), type_str


def safe_filename_part(text: str, max_len: int = 48) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return safe[:max_len] or "check"


def save_lean_check(
    tmp_path: str,
    save_dir: str | None,
    temp_id: int,
    ok: bool,
    output: str,
) -> None:
    if not save_dir:
        return
    os.makedirs(save_dir, exist_ok=True)
    prefix = "good" if ok else "bad"
    lean_path = os.path.join(save_dir, f"{prefix}_{temp_id:06d}.lean")
    output_path = os.path.join(save_dir, f"{prefix}_{temp_id:06d}.out")
    shutil.move(tmp_path, lean_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)


def lean_synth_succeeds(
    type_str: str,
    assumptions: Iterable[str],
    target: str,
    timeout: int,
    save_dir: str | None,
    temp_id: int,
) -> tuple[bool, str]:
    assumption_list = list(assumptions)
    prelude = lean_prelude_for(type_str, [*assumption_list, target])
    assumption_lines = "\n".join(
        f"variable [inst_{i} : {assumption}]" for i, assumption in enumerate(assumption_list)
    )
    code = f"{prelude}{assumption_lines}\n\n#synth {target}\n"

    with tempfile.NamedTemporaryFile("w", suffix=".lean", dir=PROJECT_DIR, delete=False, encoding="utf-8") as f:
        f.write(code)
        tmp_path = f.name
    try:
        result = subprocess.run(
            ["lake", "env", "lean", tmp_path],
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        ok = result.returncode == 0 and "error:" not in output
        save_lean_check(tmp_path, save_dir, temp_id, ok, output)
        tmp_path = ""
        return ok, output
    except subprocess.TimeoutExpired:
        output = "timeout"
        save_lean_check(tmp_path, save_dir, temp_id, False, output)
        tmp_path = ""
        return False, output
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def verified_edges(
    candidates: Iterable[tuple[Candidate, str]],
    max_candidates: int | None,
    timeout: int,
    save_dir: str | None,
) -> Iterator[dict[str, object]]:
    checked = 0
    temp_id = 0
    for candidate, type_str in candidates:
        if max_candidates is not None and checked >= max_candidates:
            break
        checked += 1

        temp_id += 1
        ok, output = lean_synth_succeeds(
            type_str,
            [candidate.source],
            candidate.target,
            timeout,
            save_dir,
            temp_id,
        )
        verification = "single_source_lean_synth"
        assumptions = [candidate.source]

        if not ok and candidate.target not in candidate.context_sources:
            temp_id += 1
            ok, output = lean_synth_succeeds(
                type_str,
                candidate.context_sources,
                candidate.target,
                timeout,
                save_dir,
                temp_id,
            )
            verification = "context_lean_synth"
            assumptions = list(candidate.context_sources)

        if not ok:
            continue

        yield {
            "source": candidate.source,
            "target": candidate.target,
            "source_head": candidate.source_head,
            "target_head": candidate.target_head,
            "assumptions": assumptions,
            "verification": verification,
            "decl_name": candidate.decl_name,
            "module": candidate.module,
        }


def write_jsonl(path: str, rows: Iterable[dict[str, object]]) -> int:
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a Lean-verified typeclass implication table from mathlib-types."
    )
    parser.add_argument("--dataset-path", help="Local mathlib-types CSV, JSONL, or parquet file.")
    parser.add_argument("--limit", type=int, help="Only scan the first N dataset rows.")
    parser.add_argument("--max-candidates", type=int, default=200, help="Only verify the first N candidates.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-candidate Lean timeout in seconds.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output JSONL path.")
    parser.add_argument(
        "--lean-check-dir",
        default=DEFAULT_LEAN_CHECK_DIR,
        help="Directory for generated Lean checks. Use empty string to disable saving.",
    )
    args = parser.parse_args()

    rows = load_rows(args.dataset_path, args.limit)
    candidates = candidate_rows(rows)
    save_dir = args.lean_check_dir or None
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    edges = verified_edges(candidates, args.max_candidates, args.timeout, save_dir)
    count = write_jsonl(args.output, edges)
    print(f"Wrote {count} verified edges to {args.output}")
    if save_dir:
        print(f"Saved Lean check files to {save_dir}")


if __name__ == "__main__":
    main()
