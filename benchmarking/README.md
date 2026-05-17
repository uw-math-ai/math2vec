# Math2Vec Benchmark

This is the benchmark built for math2vec - a retrieval-focused text embedder evaluation framework.

## FrenzyMath Benchmark

The maintained benchmark for informal-language to Lean shared-space retrieval is:

- runner: [`benchmarking/src/frenzymath_benchmark.py`](C:/Users/kedar/OneDrive/Desktop/OneDrive%20All%20Files/Documents/Playground/math2vec/benchmarking/src/frenzymath_benchmark.py)
- full documentation: [`benchmarking/FRENZYMATH_BENCHMARK.md`](C:/Users/kedar/OneDrive/Desktop/OneDrive%20All%20Files/Documents/Playground/math2vec/benchmarking/FRENZYMATH_BENCHMARK.md)
- Tillicum operational runbook: [`benchmarking/TILLICUM_FRENZYMATH_RUNBOOK.md`](C:/Users/kedar/OneDrive/Desktop/OneDrive%20All%20Files/Documents/Playground/math2vec/benchmarking/TILLICUM_FRENZYMATH_RUNBOOK.md)

If you are trying to benchmark models on FrenzyMath, use that script and document, not the older blueprints-oriented pipeline below.

## Architecture Overview

A retrieval-focused benchmark evaluates how well an embedding model can encode text such that semantically similar items are close in the embedding space, enabling effective retrieval of relevant documents given a query.

## Dependencies
- faiss-cpu
- numpy

## Structure of Benchmarking Directory

```
benchmarking/
├── README.md (this file)
├── data/               # Datasets and ground truth
├── src/
│   ├── data.py         # Dataset loading and preprocessing
│   ├── encoder.py      # Embedding model interface
|   ├── evaluation.py   # Evaluation algorithm & report generator
|   ├── metrics.py      # Evaluation metric functions
│   └── retriever.py    # Similarity search and ranking
```

### Core Components

1. **Data Layer** - Corpus and query management
2. **Encoder Interface** - Abstraction for different embedding models
3. **Retriever** - Similarity search and ranking
4. **Evaluation Module** - Metrics computation and reporting

---

## Key Design Decisions

### 1. Dataset Design

**Decision: What type of retrieval task?**
- **Question-Answer Retrieval**: Given a question, retrieve relevant answers
- **Document-Query Retrieval**: Given a search query, retrieve relevant documents
- **Symmetric Retrieval**: Both sides are similar types (e.g., paraphrase detection)
- **Cross-lingual Retrieval**: Query in one language, retrieve in another

Leo's answer: Theorem-query retrieval, given a search query, retrieve relevant theorems. Also some Cross-lingual Retrieval - query in NL, get results in LaTeX and Lean.

**Decision: Dataset composition**
- Size of corpus (hundreds, thousands, millions of documents?)
- Number of queries
- Number of relevant documents per query (1-to-1, 1-to-many?)
- Domain specificity (mathematics-focused for math2vec?)

Leo's answer: 10 queries, 100 theorems/documents

**Decision: Ground truth labeling**
- Binary relevance (relevant/not relevant)
- Graded relevance (0-4 scale)
- Human-annotated vs. automatically generated

### 2. Embedding Model Interface

**Decision: What models to support?**
- OpenAI embeddings (text-embedding-3-small, text-embedding-3-large)
- Open-source models (sentence-transformers, instructor models)
- Custom fine-tuned models
- API-based vs. local models

**Decision: Batching strategy**
- Batch size for encoding
- Handling of varying text lengths
- Memory constraints

**Decision: Normalization**
- L2 normalization of embeddings
- Standardization/centering

### 3. Retrieval Strategy

**Decision: Similarity metric**
- Cosine similarity (most common for normalized embeddings)
- Dot product (for non-normalized)
- Euclidean distance
- Custom metrics

**Decision: Search approach**
- Exact search (brute force, good for smaller corpora)
- Approximate Nearest Neighbor (ANN) search (FAISS, Annoy, HNSW)
- Hybrid search (combining dense + sparse retrieval)

**Decision: Retrieval depth**
- How many top-k results to retrieve? (10, 100, 1000?)
- Does k vary by use case?

### 4. Evaluation Metrics

**Decision: Which metrics to compute?**

**Ranking Metrics:**
- **Mean Reciprocal Rank (MRR)**: Average of reciprocal ranks of first relevant document
- **Recall@k**: Proportion of relevant documents in top-k results
- **Precision@k**: Proportion of top-k results that are relevant
- **NDCG@k**: Normalized Discounted Cumulative Gain (handles graded relevance)
- **MAP (Mean Average Precision)**: Mean of average precision across all queries

**Distance-based Metrics:**
- Average similarity score of relevant pairs
- Separation between relevant and irrelevant items

**Decision: Primary metric for comparison**
- Which metric best represents your use case?
- Should you optimize for early precision (MRR, P@1) or overall recall?

### 5. Benchmark Execution

**Decision: Evaluation protocol**
- Cross-validation or fixed train/test split?
- Multiple test sets for robustness?
- Zero-shot (no fine-tuning) or allow fine-tuning on training data?

**Decision: Computational efficiency**
- Time limits for encoding?
- Memory constraints?
- Should speed be part of the evaluation?

**Decision: Output format**
- JSON results file
- Leaderboard/comparison table
- Per-query detailed results
- Visualization (t-SNE, confusion matrices)

### 6. Extensibility

**Decision: How to handle new models/datasets?**
- Plugin architecture for encoders
- Standardized dataset format
- Configuration files vs. code changes

**Decision: Reproducibility**
- Random seed handling
- Version tracking (model versions, code versions)
- Caching of embeddings

---

## Suggested Implementation Pipeline

```
1. Load/Prepare Dataset
   ↓
2. Initialize Encoder (with model config)
   ↓
3. Encode Corpus → Cache embeddings
   ↓
4. Encode Queries → Cache embeddings
   ↓
5. Build/Load Retriever (with similarity metric)
   ↓
6. For each query: Retrieve top-k documents
   ↓
7. Compute metrics using retrieved results + ground truth
   ↓
8. Aggregate and report results
```

---

## Adding a New Model (and using it from CLI)

This benchmark is designed so any model can be plugged in, as long as it matches the encoder interface.

### 1) Implement your model class in `benchmarking/src/model.py`

Your class must:
- expose `self.embedding_dim`
- expose `self.metadata` (recommended, using `ModelMetadata`)
- implement `encode(self, texts: List[str], **kwargs) -> np.ndarray`

Template:

```python
class MyCustomModel:
   def __init__(self, ...):
      self.embedding_dim = 768
      self.metadata = ModelMetadata(
         name="my-custom-model",
         model_type="custom",
         embedding_dim=self.embedding_dim,
         description="My trained embedding model",
      )

   def encode(self, texts, **kwargs):
      # Return shape: (len(texts), embedding_dim)
      return embeddings_numpy_array
```

### 2) Import it in `benchmarking/src/main.py`

Example:

```python
from model import SentenceTransformerModel, RandomEmbedder, MyCustomModel
```

### 3) Add a CLI tag in `parse_args()`

Extend `--model-type` choices:

```python
parser.add_argument(
   "--model-type",
   choices=["sentence-transformer", "random", "my-custom"],
   default="sentence-transformer",
)
```

### 4) Wire model creation in `main()`

Add a branch for your new tag:

```python
if args.model_type == "random":
   model_instance = RandomEmbedder()
elif args.model_type == "my-custom":
   model_instance = MyCustomModel(...)
else:
   model_instance = SentenceTransformerModel(model_name=args.model_name, device=args.device)
```

### 5) Run your model from CLI

```bash
python benchmarking/src/main.py --model-type my-custom
```

### Notes

- Keep output shape consistent: `(batch_size, embedding_dim)`.
- Return a NumPy array (`np.ndarray`) from `encode`.
- If your model needs extra config (checkpoint path, seed, etc.), add additional CLI args in `parse_args()` and pass them into your model constructor.
- Current implemented tags are:
  - `sentence-transformer`
  - `random`

---

## Questions to Answer Before Implementation

1. **What is your specific math retrieval task?** (e.g., find similar theorems, retrieve proofs, match problem-solution pairs)
2. **Do you have an existing dataset, or do you need to create one?**
3. **What scale are you targeting?** (small academic benchmark vs. large-scale production)
4. **Will you support multiple datasets or start with one?**
5. **Do you want to compare against baseline models immediately?**
6. **What are the expected input text characteristics?** (LaTeX math, natural language, mixed?)

---

