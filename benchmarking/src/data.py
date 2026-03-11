"""
Docstring for benchmarking.src.data

This module provides functions to load the test dataset from a JSON file
and give the sample theorems back to the main pipeline.
"""

from pathlib import Path
import json
from datasets import load_dataset



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

def extract_latex_and_lean_from_hf_dataset(dataset, latex_key="signature", lean_key="informal_description"):
    """
    @Behavior: Extract LaTeX and Lean code from a Hugging Face dataset.
    @Parameters: dataset - a Hugging Face Dataset object containing the data
                 latex_key (str) - the column name to use for LaTeX strings (default: "signature")
                 lean_key (str) - the column name to use for Lean code (default: "informal_description")
    @Returns: A list of dictionaries, each mapping "LaTeX" to the LaTeX string and "Lean" to the corresponding Lean code.
    """
    extracted = []
    for record in dataset:
        latex = record.get(latex_key)
        lean = record.get(lean_key)
        if latex and lean:
            extracted.append({"LaTeX": latex, "Lean": lean})
    return extracted


"""
@Behavior: Load the FrenzyMath dataset using the Hugging Face datasets library.
@Parameters: random_sample (bool) - whether to return a random sample of the dataset
             num_samples (int) - the number of samples to return if random_sample is True
             columns (list of str) - which columns to return from the dataset 
                - (default: ["signature", "informal_description"])
@Returns: A Hugging Face Dataset object containing the FrenzyMath data.
"""
def load_frenzy_math(
    random_sample=True,
    num_samples=None,
    columns: list[str] | None = None,
):
    # Set default columns if none provided
    if columns is None:
        columns = ["signature", "informal_description"]

    # Load the single 'train' split (the dataset has no test/validation)
    ds = load_dataset("FrenzyMath/mathlib_informal_v4.19.0")["train"]

    # Validate that the requested columns exist in the dataset
    missing_columns = [column for column in columns if column not in ds.column_names]
    if missing_columns:
        raise ValueError(
            f"Requested columns not found in dataset: {missing_columns}. "
            f"Available columns: {ds.column_names}"
        )

    ds = ds.select_columns(columns)

    # If no sampling requested, return full dataset
    if not random_sample:
        return ds

    # If sampling requested but no num_samples provided, raise an error
    if num_samples is None:
        raise ValueError("num_samples must be provided when random_sample=True")

    # Shuffle and select the requested number of samples
    # Can input a seed into shuffle() for reproducibility
    sampled = ds.shuffle().select(range(num_samples))
    return sampled

"""
@Behavior: Quick call to load the blueprints dataset. 
    - This is a thin wrapper around load_corpus() that hardcodes the path to the blueprints JSON file.
    - Just to take the hardcoded path out of main.py and centralize it here in case we want to change it later.
"""
def load_blueprints() -> list[dict]:
    return load_corpus(Path("dataset/blueprints.json"))
