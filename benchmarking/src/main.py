"""
Docstring for benchmarking.src.main
"""

# Main entry point for benchmarking

# import necessary modules
import data
import encoder
import retriever
import evaluation

# TODO: implement main function to run the benchmarking process

# This will likely involve:
# 1. Loading the dataset (queries and corpus) with data.py
# 2. Encoding the queries and corpus into vector representations using encoder.py
# 3. Calling retriever.py to get top-k results
# 4. Evaluating the results using evaluation.py

K = 10 # number of neighbors to retrieve, passed to retriever and evaluation functions 

# TODO: figure out how to index the corpus and queries so that we can match retrieved results to ground truth for evaluation
def main():
    corpus_tokens, query_tokens, ground_truth = data.load_fake_dataset() # Load dataset
    print("dataset loaded") # this is just debugging, remove later
    corpus_vectors = encoder.encode_texts(corpus_tokens) # Encode corpus
    print("corpus encoded")
    query_vectors = encoder.encode_texts(query_tokens) # Encode queries
    print("queries encoded")
    rankings, _ = retriever.retrieve_top_k(query_vectors, corpus_vectors, K) # Retrieve top-k results
            # no need for the similarity scores right now, just the rankings for evaluation
    print("retrieval done")

    # identify the which retrieved documents correspond to which ground truth relevant items for evaluation
    print(rankings)

    # for now, just identify which indices in the corpus correspond to the items in the ground truth
    ground_truth_indices = []
    for query_ground_truth in ground_truth:
        indices_for_query = []
        for relevant_item in query_ground_truth:
            if relevant_item in corpus_tokens:
                index = corpus_tokens.index(relevant_item)
                indices_for_query.append(index)
        ground_truth_indices.append(set(indices_for_query)) # Store as set for easier evaluation

    print(ground_truth_indices)

    #TODO: There might be some problem with how we are structuring the rankings and ground truth data

    metrics_dict = evaluation.compute_evaluation_metrics(rankings, ground_truth_indices, K) # Compute evaluation metrics
    evaluation.generate_evaluation_report(metrics_dict) # Generate evaluation report


if __name__ == "__main__":
    main()


