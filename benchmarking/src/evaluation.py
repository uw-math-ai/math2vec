"""
Docstring for benchmarking.src.evaluation

This script contains functions and classes for evaluating the performance of various embedding models.

It takes in the embeddings generated for various queries
and compares them again ground truth data to compute metrics.
Then, it takes the metric scores and generates evaluation reports,
visualizations, and summaries.
TODO: Reconsider how to structure getting rankings and ground truth data.

"""

import metrics

"""
@Behavior: Computes various evaluation metrics given rankings and ground truth.
@Parameters: rankings (list of list): The ranked lists of retrieved items for each query.
             ground_truth (list of set): The sets of relevant items for each query.
             K (int): The cutoff rank for metrics that require it 
@Returns: dict: A dictionary of computed metric scores. Maps metric names to their scores.
TODO: Consider whether dictionary should map to lists of per-query scores or overall averages.
TODO: Is dictionary the best structure here?

Feb 6th, 2026 - Currently we are mapping metric names to lists of per-query scores for more flexibility in analysis and reporting.
- We may want to add an option to also compute and return overall averages in the future.
- Also these metrics are purely retrieval-related. Should later add Bitext Mining metrics as well.
"""
def compute_evaluation_metrics(rankings, ground_truth, K):
    # make dictionary to hold metric scores
    metrics_dict = {}

    # compute metrics using functions from metrics.py and store in dictionary
    metrics_dict['hit_at_k'] = metrics.hit_at_k(K, rankings, ground_truth)
    metrics_dict['recall_at_k'] = metrics.recall_at_k(K, rankings, ground_truth)
    metrics_dict['precision_at_k'] = metrics.precision_at_k(K, rankings, ground_truth)
    metrics_dict['reciprocal_rank'] = metrics.reciprocal_ranks(rankings, ground_truth)
    metrics_dict['ndcg_at_k'] = metrics.normalized_discounted_cumulative_gain(rankings, ground_truth)   
    
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

