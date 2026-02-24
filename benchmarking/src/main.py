"""
Docstring for benchmarking.src.main
"""

# Main entry point for benchmarking

# import necessary modules
import argparse
from pathlib import Path
import time
import data
from encoder import Encoder
from model import SentenceTransformerModel
import retriever
import evaluation
import pairing

"""
GLOBAL VARIABLES
"""
K = 10 # number of neighbors to retrieve, passed to retriever and evaluation functions 

"""
@Behavior: parse command line arguments for model name, batch size, max items to process, normalization, and device to use.
@Arguments:
    --model-name: Name or path of the sentence-transformers model to use 
        (default: "sentence-transformers/all-MiniLM-L6-v2")
    --batch-size: Batch size for encoding 
        (default: 32)
    --max-items: Optional cap on number of theorem pairs to encode 
        (default: None, meaning no limit)
    --normalize / --no-normalize: Whether to L2-normalize embeddings 
        (default: True)
@Returns: argparse.Namespace with the parsed arguments.
"""
def parse_args():
    parser = argparse.ArgumentParser(description="Run embedding benchmark pipeline.")
    parser.add_argument(
        "--model-name",
        default="sentence-transformers/all-MiniLM-L6-v2",
        help="Sentence-Transformers model name or local path.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding generation.",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Optional cap on number of theorem pairs to encode.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Force device, e.g. 'cpu' or 'cuda'. Defaults to auto-detect.",
    )

    # Mutually exclusive group for normalization options
    normalize_group = parser.add_mutually_exclusive_group()
    normalize_group.add_argument(
        "--normalize",
        dest="normalize",
        action="store_true",
        help="L2-normalize embeddings in Encoder (default).",
    )
    normalize_group.add_argument(
        "--no-normalize",
        dest="normalize",
        action="store_false",
        help="Disable L2-normalization in Encoder.",
    )
    parser.set_defaults(normalize=True)
    return parser.parse_args()


# TODO: figure out how to index the corpus and queries so that we can match retrieved results to ground truth for evaluation
def main():
    args = parse_args() # parse command line arguments

    start = time.perf_counter() # start timer for debugging why this takes so long to run

    # initialize model instance here
    model_instance = SentenceTransformerModel(model_name=args.model_name, device=args.device)
    
    # intialize encoder instance here, passing in the model instance
    encoder_instance = Encoder(model_instance, batch_size=args.batch_size, normalize=args.normalize)
        # turned normalization on, since we currently use cosine similarity

    model_loaded = time.perf_counter()
    print("Model and encoder initialized successfully.")
    print(f"Model: {args.model_name}")
    print(f"Device: {model_instance.device}")
    print(f"Normalize embeddings: {args.normalize}")
    print(f"Model load time: {model_loaded - start:.2f}s")
    print()

    # Load the dataset (queries and corpus) with data.py
    theorems = data.load_corpus(Path("benchmarking/data/corpus_blueprints.json"))
    if not theorems:
        raise ValueError("No theorems loaded. Check the corpus JSON path/format.")

    # optionally limit the number of items to process for faster testing
    if args.max_items is not None:
        theorems = theorems[:args.max_items]

    print(f"Loaded {len(theorems)} theorem pairs")

    # process the theorems into list of latex statements and list of corresponding Lean code
    latex_statements = [theorem["LaTeX"] for theorem in theorems]
    lean_code = [theorem["Lean"] for theorem in theorems]

    # encode the LaTeX statements and Lean code into embeddings using the encoder instance
    latex_embeddings = encoder_instance.encode(latex_statements)
    lean_embeddings = encoder_instance.encode(lean_code)

    # print out timing and shapes of the resulting embeddings for debugging
    encoded = time.perf_counter()
    print(f"Encoded LaTeX embeddings shape: {latex_embeddings.shape}")
    print(f"Encoded Lean embeddings shape: {lean_embeddings.shape}")
    print(f"Embedding time: {encoded - model_loaded:.2f}s")
    print(f"Total elapsed time: {encoded - start:.2f}s")

    # find pairs of related embeddings using the pairing function in pairing.py
    embedding_pairs, index_pairs = pairing.find_pairs(latex_embeddings, lean_embeddings, normalized=args.normalize)
    print(f"Found {len(embedding_pairs)} embedding pairs")

    # print out the first 5 pairs of index pairs for mini-benchmarking
    # in an ideal world, with a perfect embedder, we expect (0, 0), (1, 1), etc
    print("First 5 index pairs (latex_idx, lean_idx):")
    for i in range(min(5, len(index_pairs))):
        print(index_pairs[i])

    # quick visualization of the index pairs to see if they cluster around the diagonal (indicating good pairing)
    import matplotlib.pyplot as plt

    plt.figure(figsize=(10, 10))
    plt.scatter(
        [idx_pair[0] for idx_pair in index_pairs],
        [idx_pair[1] for idx_pair in index_pairs],
        alpha=0.5,
        label="Paired Indices",
    )
    plt.xlabel("LaTeX Index")
    plt.ylabel("Lean Index (Nearest Neighbor)")
    plt.title("Pairing Visualization")
    plt.legend()
    plt.show()
    plt.close()
    




if __name__ == "__main__":
    main()


