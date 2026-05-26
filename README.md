# Project

This project is aimed at training and evaluating a text embedding model that works well on mathematical content across two modalities: natural language (LaTeX) and formal Lean 4 code.

## Origins

This project grew out of prior work in large-scale mathematical theorem retrieval systems that provide semantic search over millions of mathematical theorems from sources such as arXiv, the Stacks Project, and other mathematical corpora. These systems demonstrate that embedding-based retrieval works well for informal mathematics, but their embedders are not designed for formal mathematics (Lean 4 code). math2vec addresses this gap: rather than building another search index, it focuses on benchmarking and improving embedders that must bridge both modalities — informal LaTeX and formal Lean — to enable the next generation of theorem search tools that span the informal/formal divide.

## Goals

To develop a benchmark for evaluating text embedding models on how well they perform across both mathematical modalities. This benchmark focuses on retrieval and pairing (bitext mining) tasks.

To gather and clean a dataset of mathematics with both natural language and Lean 4 statements.

To develop (or identify) an embedder that performs well on both natural-language mathematics and formal Lean proofs — enabling applications like theorem search, premise selection, and formalization assistance.

## Repository structure

dataset/       — dataset construction pipelines
finetunue/ - model finetuning 
benchmarking/  — embedding benchmark and evaluation
judge/ - pipeline to judge synthetic data

## Dataset

- LeanBlueprintParser.py — extracts theorem statements from community Lean 4 blueprint projects using web scraping tools, producing blueprints.json.
- TheoremTranslatorV2.py — translates/restates theorems via an LLM API and saves results to timestamped CSVs.

## Benchmarking

- Supports any sentence-transformers-compatible model (default: Qwen/Qwen3-Embedding-0.6B) plus a random-vector baseline.
- Evaluation metrics: Precision@K, Recall@K, Mean Reciprocal Rank, and Percent Correct Pairs (bitext mining).

Run:

cd benchmarking
pip install -r requirements.txt
python src/main.py

## Notes

This repository is intended for research benchmarking of cross-modal mathematical embeddings and does not depend on any specific external organizational infrastructure.
