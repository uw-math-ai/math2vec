"""
Docstring for benchmarking.src.metrics

This module provides various metric functions used to evaluate the performance of embedding models.
It includes implementations for common metrics such as Recall@K, Precision@K, Mean Reciprocal Rank (MRR),
and Normalized Discounted Cumulative Gain (NDCG).

Yes my code looks like it came straight out of CSE 12X

TODO: Add more metrics as needed.
TODO: Should Recall and Precision return average across all queries or lists of per-query scores?
- Jan 28th, 2026 - We think they should return lists of per-query scores for more flexibility.
"""


"""
@Behavior: Computes the Recall at K for a set of rankings against ground truth data.
@Parameters: k (int): The cutoff rank.
             rankings (list of list): The ranked lists of retrieved items for each query.
             ground_truth (list of set): The sets of relevant items for each query.
@Returns: list of float: A list of recall at K scores, one per query.
                - If there are no relevant items for a query, its recall is considered 0.0
                - If there are no rankings provided, returns an empty list.
"""
def recall_at_k(k, rankings, ground_truth):
    # TODO: Think about edge cases/exceptions
    if not rankings:
        return []
    
    recalls = [] # List to store recall for each query
    for query_rankings, query_ground_truth in zip(rankings, ground_truth):
        if len(query_ground_truth) == 0:
            # If no relevant items, recall is 0
            recalls.append(0.0)
        else:
            # Get top-k retrieved items
            top_k = set(query_rankings[:k])
            # Count how many relevant items are in top-k
            relevant_in_topk = len(top_k & query_ground_truth)
            # Recall = relevant in top-k / total relevant
            recall = relevant_in_topk / len(query_ground_truth)
            recalls.append(recall) # Append recall for this query
    
    return recalls # Return list of per-query recall scores

"""
@Behavior: Computes the precision at K for a set of rankings against ground truth data.
@Parameters: k (int): The cutoff rank.
             rankings (list of list): The ranked lists of retrieved items for each query.
             ground_truth (list of set): The sets of relevant items for each query.
@Returns: list of float: A list of precision at K scores, one per query.
                - If there are no rankings provided, returns an empty list.
"""
def precision_at_k(k, rankings, ground_truth):
    # TODO: Think about edge cases/exceptions
    if not rankings:
        return []
    
    precisions = [] # List to store precision for each query
    for query_rankings, query_ground_truth in zip(rankings, ground_truth):
        # Get top-k retrieved items
        top_k = set(query_rankings[:k])
        # Count how many relevant items are in top-k
        relevant_in_topk = len(top_k & query_ground_truth)
        # Precision = relevant in top-k / k
        precision = relevant_in_topk / k if k > 0 else 0.0
        precisions.append(precision) # Append precision for this query
    
    return precisions # Return list of per-query precision scores

"""
def mean_reciprocal_rank(rankings, ground_truth):
"""

"""
def normalized_discounted_cumulative_gain(rankings, ground_truth):
"""