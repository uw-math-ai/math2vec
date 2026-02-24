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

@Behavior: Load theorems from the corpus JSON file in the data folder.
@Parameters: path to corpus.json
            - This is expected to be the corpus.json file in the benchmarking/data directory
@Returns: A list of dictionaries, each mapping "LaTeX" to the LaTeX string and "Lean" to the corresponding Lean code.
"""

def load_corpus(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("Corpus JSON must be a list of theorem records.")

    def add_theorem(item: dict, output: list[dict]) -> None:
        latex = item.get("LaTeX")
        highlighted = item.get("highlighted")
        # The Lean code is stored under the "highlighted" key in the JSON.
        if latex and highlighted:
            output.append({"LaTeX": latex, "Lean": highlighted})

    theorems = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if "theorems" in item and isinstance(item["theorems"], list):
            for theorem in item["theorems"]:
                if isinstance(theorem, dict):
                    add_theorem(theorem, theorems)
        else:
            add_theorem(item, theorems)

    return theorems