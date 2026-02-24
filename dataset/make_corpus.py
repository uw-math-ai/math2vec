import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def load_blueprints(path: Path) -> list[dict]:
    # Load the full blueprint export.
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def sample_theorems(blueprints: list[dict], k: int, seed: int) -> list[dict]:
    # Build a flat pool of valid theorems (requires both LaTeX and highlighted).
    pool = []
    for record in blueprints:
        for thm in record.get("theorems", []):
            latex = thm.get("LaTeX")
            highlighted = thm.get("highlighted")
            if latex and highlighted:
                pool.append({
                    "LaTeX": latex,
                    "highlighted": highlighted,
                })

    if not pool:
        return []

    # Change the seed to get a different random sample while keeping it reproducible.
    # You can pass a new value via --seed or change the default in parse_args.
    random.seed(seed)
    sample_size = min(k, len(pool))
    return random.sample(pool, sample_size)


def regroup_by_blueprint(blueprints: list[dict], sample: list[dict]) -> list[dict]:
    # Kept for compatibility; output is now a flat list without blueprint URLs.
    _ = blueprints
    return sample


def write_json(path: Path, payload: list[dict]) -> None:
    # Write the sampled theorems to the target JSON file.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    default_input = script_dir / "blueprints.json"
    default_output = repo_root / "benchmarking" / "data" / "corpus.json"

    parser = argparse.ArgumentParser(
        description="Sample 100 theorems from blueprints.json into corpus.json"
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument("--output", type=Path, default=default_output)
    # Use --seed to change the randomization and get a different sample.
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    # Load, sample, and write a flat list of theorems.
    blueprints = load_blueprints(args.input)
    sample = sample_theorems(blueprints, args.count, args.seed)
    filtered = regroup_by_blueprint(blueprints, sample)
    write_json(args.output, filtered)
    print(f"Wrote {len(sample)} theorems to {args.output}")


if __name__ == "__main__":
    main()
