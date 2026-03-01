"""
Docstring for benchmarking.src.evaluation

This script contains functions and classes for evaluating the performance of various embedding models.

It takes in the embeddings generated for various queries
and compares them again ground truth data to compute metrics.
Then, it takes the metric scores and generates evaluation reports,
visualizations, and summaries.
TODO: Reconsider how to structure getting rankings and ground truth data.
TODO: Refector this code to handle multiple types of evaluation (retrieval, bitext mining)

"""

import metrics

"""
@Behavior: Computes evaluation metrics specific to bitext mining tasks, 
           given identified pairs and ground truth pairs.
@Parameters: embedded_index_pairs (list of tuples): List of index pairs identified by the embedding-based pairing function.
             corpus_index_pairs (list of tuples): List of index pairs from the ground truth corpus data.
@Returns: dict: A dictionary of computed metric scores specific to bitext mining.
TODO: Consider what specific metrics are relevant for bitext mining and implement them here.
- Currently we are only computing Percent Correct Pairs, but we may want to add more metrics relevant to bitext mining in the future.
"""
def compute_bitext_mining_metrics(embedded_index_pairs, corpus_index_pairs):
    return {"Percent Correct Pairs": metrics.percent_correct_pairs(embedded_index_pairs, corpus_index_pairs)}

"""
@Behavior: Custom graphing function to visualize the quality of the identified pairs in bitext mining.
            - This is a quick visualization to see if the identified pairs cluster around the diagonal, which would indicate good pairing.
@Parameters: embedded_index_pairs (list of tuples): List of index pairs identified by the embedding-based pairing function.
@Returns: A matplotlib figure object visualizing the identified pairs.
TODO: Consider what specific visualizations are most informative for evaluating bitext mining performance.
            - Currently we are plotting the identified index pairs to see if they cluster around the diagonal
"""
def generate_pairing_eval_graph(embedded_index_pairs):
    import matplotlib.pyplot as plt
    # quick visualization of the index pairs to see if they cluster around the diagonal (indicating good pairing)

    plt.figure(figsize=(10, 10))
    plt.scatter(
        [idx_pair[0] for idx_pair in embedded_index_pairs],
        [idx_pair[1] for idx_pair in embedded_index_pairs],
        alpha=0.5,
        label="Paired Indices",
    )
    plt.xlabel("LaTeX Index")
    plt.ylabel("Lean Index (Nearest Neighbor)")
    plt.title("Pairing Visualization")
    plt.legend()
    return plt

"""
@Behavior: Computes evaluation metrics for retrieval tasks, given rankings and ground truth data.
@Parameters: rankings (list of list): The ranked lists of retrieved items for each query.
             ground_truth (list of set): The sets of relevant items for each query.
             K (int): The cutoff rank for metrics like Precision@K and Recall@K.
@Returns: dict: A dictionary of computed metric scores for retrieval tasks.
TODO: Consider what specific metrics are relevant for retrieval tasks and implement them here.
"""
def compute_retrieval_metrics(rankings, ground_truth, K):
    metrics_dict = {}
    metrics_dict["Precision@K"] = metrics.precision_at_k(K, rankings, ground_truth)
    metrics_dict["Recall@K"] = metrics.recall_at_k(K, rankings, ground_truth)
    metrics_dict["Reciprocal Rank"] = metrics.reciprocal_ranks(rankings, ground_truth)
    return metrics_dict

"""
@Behavior: Generates an evaluation report based on computed metrics.
@Parameters: metrics_dict (dict): A dictionary of computed metric scores.
@Returns: None

TODO: Clarify the input format for metrics_dict. 
    Currently we are assuming it maps metric names to lists of per-query scores, 
    but we may want to also support overall averages in the future.
TODO: Consider report generation algorithms and formats (e.g., text, HTML, PDF).
"""

def generate_evaluation_report(metrics_dict):
    for metric_name, scores in metrics_dict.items():
        print(f"{metric_name}: {scores}")

