"""
Docstring for benchmarking.src.data

This module provides functions to load the test dataset from a JSON file
and give the sample theorems back to the main pipeline.
"""

from pathlib import Path
import json

"""
TODO: Alter this once NL statements are added to the dataset to adapt to the new format
TODO: add extra error handling and validation for the input JSON structure

@Behavior: Load theorem records from a corpus JSON file in the data folder.
@Parameters: path to a corpus JSON file
                        - Supports both:
                            1) flat theorem entries (e.g., corpus.json)
                            2) blueprint-grouped entries with a "theorems" array (e.g., corpus_blueprints.json)
@Returns: A list of dictionaries, each mapping "LaTeX" to the LaTeX string and "Lean" to the corresponding Lean code.
"""

def load_corpus(path: Path) -> list[dict]:
    # Read and parse the JSON payload from disk.
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    # The top-level structure must be a list of records.
    if not isinstance(payload, list):
        raise ValueError("Corpus JSON must be a list of theorem records.")

    def add_theorem(item: dict, output: list[dict]) -> None:
        # Normalize a theorem record to the benchmark schema expected downstream.
        latex = item.get("LaTeX")
        highlighted = item.get("highlighted")
        # The Lean code is stored under the "highlighted" key in the JSON.
        if latex and highlighted:
            output.append({"LaTeX": latex, "Lean": highlighted})

    theorems = []
    # Handle both supported formats:
    # - grouped blueprint records with "theorems": [...]
    # - flat theorem records directly at top level
    for item in payload:
        if not isinstance(item, dict):
            continue
        if "theorems" in item and isinstance(item["theorems"], list):
            # Blueprint format: extract each theorem from the nested list.
            for theorem in item["theorems"]:
                if isinstance(theorem, dict):
                    add_theorem(theorem, theorems)
        else:
            # Flat format: treat this item itself as a theorem record.
            add_theorem(item, theorems)

    return theorems