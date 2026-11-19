from pathlib import Path

import pandas as pd

# Login using e.g. `huggingface-cli login` to access this dataset
df = pd.read_parquet("hf://datasets/m-a-p/FineLeanCorpus/train-00000-of-00001.parquet")

# keep only medium problems with difficulty 3 to 6 (non-numeric difficulty becomes NaN and is dropped)
df["difficulty"] = pd.to_numeric(df["difficulty"], errors="coerce")
medium = df[df["difficulty"].between(3, 6)]

out_path = Path(__file__).with_name("medium_flc.json")
medium.to_json(out_path, orient="records", indent=2, force_ascii=False)
print(f"Saved {len(medium)} of {len(df)} problems (difficulty 3-6, medium) to {out_path}")
