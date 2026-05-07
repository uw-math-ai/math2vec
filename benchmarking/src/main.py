"""
Docstring for benchmarking.src.main
"""

# Main entry point for benchmarking

# import necessary modules
import argparse
import importlib
from pathlib import Path
import time
import json
import numpy as np
import data
from encoder import Encoder
from model import SentenceTransformerModel, RandomEmbedder
import retriever
import evaluation
import pairing

"""
sub-dependencies:
torch, transformers, sentence-transformers for the model and encoding
faiss for efficient nearest neighbor search in pairing
matplotlib for visualization in evaluation
"""

"""
GLOBAL VARIABLES
"""
K = 10 # number of neighbors to retrieve, passed to retriever and evaluation functions 

"""
@Behavior: parse command line arguments for model selection, batch size, max items to process, normalization, device, and optional embedding saving.
@Arguments:
    --model-type: Embedding backend to use
        (default: "sentence-transformer")
    --model-name: Name or path of the sentence-transformers model to use 
        (default: "sentence-transformers/all-MiniLM-L6-v2")
    --batch-size: Batch size for encoding 
        (default: 32)
    --max-items: Optional cap on number of theorem pairs to encode 
        (default: None, meaning no limit)
    --device: Force device, e.g. 'cpu' or 'cuda'
        (default: auto-detect)
    --save-embeddings: Persist generated embeddings and metadata to disk
    --save-dir: Directory where embedding files are written
        (default: "benchmarking/data/embeddings")
    --save-format: File format for saved embeddings
        (choices: "npz", "npy")
    --normalize / --no-normalize: Whether to L2-normalize embeddings 
        (default: True)
@Returns: argparse.Namespace with the parsed arguments.
"""
def parse_args():
    parser = argparse.ArgumentParser(description="Run embedding benchmark pipeline.")
    parser.add_argument(
        "--model-type",
        default="sentence-transformer",
        help="Embedding backend to use.",
    )
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
    parser.add_argument(
        "--dtype",
        choices=["float16", "bfloat16", "float32", "float64"],
        default=None,
        help="Optional torch dtype for sentence-transformer weights.",
    )
    parser.add_argument(
        "--save-embeddings",
        action="store_true",
        default=False,
        help="Save generated embeddings and metadata to disk.",
    )
    parser.add_argument(
        "--save-dir",
        default="benchmarking/data/embeddings",
        help="Directory where embedding files are written.",
    )
    parser.add_argument(
        "--save-format",
        choices=["npz", "npy"],
        default="npz",
        help="File format for saved embeddings.",
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

# TODO: what is this function for?
def _slugify(value: str) -> str:
    """
    Convert a value into a filesystem-safe filename fragment.
    """

    safe_characters = []
    for character in value:
        if character.isalnum() or character in {"-", "_", "."}:
            safe_characters.append(character)
        else:
            safe_characters.append("_")
    slug = "".join(safe_characters).strip("._")
    return slug or "model"

# TODO: what is this function for?
def save_embeddings(
    save_dir: Path,
    save_format: str,
    model_instance,
    latex_statements,
    lean_code,
    latex_embeddings: np.ndarray,
    lean_embeddings: np.ndarray,
    args,
):
    """
    Save the generated embeddings and a manifest that describes how they were produced.
    """

    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    model_name = getattr(model_instance, "model_name", None)
    if model_name is None and hasattr(model_instance, "metadata"):
        model_name = getattr(model_instance.metadata, "name", None)
    if model_name is None:
        model_name = args.model_type

    stem = f"{timestamp}_{_slugify(model_name)}_{'normalized' if args.normalize else 'raw'}"
    manifest_path = save_dir / f"{stem}.json"

    metadata = {
        "model_type": args.model_type,
        "model_name": model_name,
        "dtype": args.dtype,
        "normalized": args.normalize,
        "batch_size": args.batch_size,
        "max_items": args.max_items,
        "device": args.device,
        "save_format": save_format,
        "embedding_shapes": {
            "latex": list(latex_embeddings.shape),
            "lean": list(lean_embeddings.shape),
        },
    }

    if hasattr(model_instance, "metadata") and hasattr(model_instance.metadata, "to_dict"):
        metadata["model_metadata"] = model_instance.metadata.to_dict()

    manifest = {
        "metadata": metadata,
        "text_counts": {
            "latex": len(latex_statements),
            "lean": len(lean_code),
        },
        "files": {},
    }

    if save_format == "npz":
        embeddings_path = save_dir / f"{stem}.npz"
        np.savez_compressed(
            embeddings_path,
            latex_embeddings=latex_embeddings,
            lean_embeddings=lean_embeddings,
        )
        manifest["files"]["embeddings"] = embeddings_path.name
    else:
        latex_path = save_dir / f"{stem}_latex.npy"
        lean_path = save_dir / f"{stem}_lean.npy"
        np.save(latex_path, latex_embeddings)
        np.save(lean_path, lean_embeddings)
        manifest["files"]["latex_embeddings"] = latex_path.name
        manifest["files"]["lean_embeddings"] = lean_path.name

    manifest["files"]["manifest"] = manifest_path.name

    with manifest_path.open("w", encoding="utf-8") as manifest_file:
        json.dump(manifest, manifest_file, indent=2, ensure_ascii=True)

    return manifest_path


def main():
    args = parse_args() # parse command line arguments

    start = time.perf_counter() # start timer for debugging why this takes so long to run

    # initialize model instance here
    if args.model_type == "random":
        model_instance = RandomEmbedder()
    else:
        model_instance = SentenceTransformerModel(
            model_name=args.model_name,
            device=args.device,
            dtype=args.dtype,
        )
    
    # intialize encoder instance here, passing in the model instance
    encoder_instance = Encoder(model_instance, batch_size=args.batch_size, normalize=args.normalize)
        # turned normalization on, since we currently use cosine similarity

    model_loaded = time.perf_counter()
    print("Model and encoder initialized successfully.")
    if args.model_type == "random":
        print("Model: random-embedder")
    else:
        print(f"Model: {args.model_name}")
        print(f"Device: {model_instance.device}")
    print(f"Model load time: {model_loaded - start:.2f}s")
    print()

    # Load the dataset (queries and corpus) with data.py
    theorems = data.load_blueprints() # load theorems from the blueprints dataset
    
    # theorems = data.extract_latex_and_lean_from_hf_dataset(data.load_frenzy_math(random_sample=True, num_samples=1000)) 
        # extract LaTeX and Lean code from the Hugging Face dataset format
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

    if args.save_embeddings:
        manifest_path = save_embeddings(
            Path(args.save_dir),
            args.save_format,
            model_instance,
            latex_statements,
            lean_code,
            latex_embeddings,
            lean_embeddings,
            args,
        )
        print(f"Saved embeddings and manifest to {manifest_path.parent}")

    
    # print out timing and shapes of the resulting embeddings for debugging
    encoded = time.perf_counter()
    print(f"Embedding time: {encoded - model_loaded:.2f}s")
    print(f"Total elapsed time: {encoded - start:.2f}s")

    # find pairs of related embeddings using the pairing function in pairing.py
    # TODO: 
    embedding_pairs, index_pairs = pairing.find_pairs(latex_embeddings, lean_embeddings, normalized=args.normalize)
        # this makes the pairing direction latex -> lean, since we search for nearest neighbors 
        # in the lean embedding space for each latex embedding
    print(f"Found {len(embedding_pairs)} embedding pairs")

    percent_correct = evaluation.compute_bitext_mining_metrics(index_pairs, [(i, i) for i in range(len(theorems))])
    print(f"Percent of correct pairs: {percent_correct['Percent Correct Pairs']:.2f}%")

    # pair_graph = evaluation.generate_pairing_eval_graph(index_pairs)
    # pair_graph.show()
    



if __name__ == "__main__":
    main()


