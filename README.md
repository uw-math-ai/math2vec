# math2vec

**math2vec** is a project aimed at training and evaluating a text embedding model that works well on mathematical content across two modalities: natural language (LaTeX) and formal Lean 4 code.

## Origins

math2vec grew out of [TheoremSearch](https://github.com/uw-math-ai/TheoremSearch), a project providing semantic search over 9 million mathematical theorems from arXiv, the Stacks Project, and other sources. TheoremSearch demonstrated that embedding-based retrieval works well for informal math, but its embedders were not designed for formal mathematics (Lean 4 code). math2vec addresses this gap: rather than building another search index, it focuses on benchmarking and improving embedders that must bridge both modalities — informal LaTeX and formal Lean — to enable the next generation of theorem search tools that span the informal/formal divide.

## Goals

To develop a benchmark for evaluating text embedding models on how well they perform across both mathematical modalities. This benchmark focuses on retrieval and pairing (bixtext mining) tasks.

To gather and clean a dataset of mathematics with both natural language and Lean 4 statements.

To develop (or identify) an embedder that performs well on both natural-language mathematics and formal Lean proofs — enabling applications like theorem search, premise selection, and formalization assistance.

## Repository structure

```
dataset/       — dataset construction pipeline
benchmarking/  — embedding benchmark and evaluation
```

### Dataset

- `LeanBlueprintParser.py` — scrapes theorem statements from community Lean 4 blueprint projects (sphere eversion, FLT, Carleson, etc.) using Selenium/BeautifulSoup, producing `blueprints.json`.
- `TheoremTranslatorV2.py` — translates/restates theorems via an LLM (DeepSeek via Nebius API) and saves results to timestamped CSVs.

### Benchmarking

- Supports any `sentence-transformers`-compatible model (default: `Qwen/Qwen3-Embedding-0.6B`) plus a random-vector baseline.
- Evaluation metrics: Precision@K, Recall@K, Mean Reciprocal Rank, and Percent Correct Pairs (bitext mining).
- Run with:

```bash
cd benchmarking
pip install -r requirements.txt
python src/main.py
```
 
