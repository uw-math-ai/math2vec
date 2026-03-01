"""
Docstring for benchmarking.src.metrics

This module provides various metric functions used to evaluate the performance of embedding models.
It includes implementations for common metrics such as Recall@K, Precision@K, Reciprocal Rank (RR),
and Normalized Discounted Cumulative Gain (NDCG).

Yes my code looks like it came straight out of CSE 12X. Comments galore!

TODO: Convert this to use numpy arrays for efficiency where applicable.
- Jan 28th, 2026 - We will start with simple list-based implementations for clarity, then optimize with numpy later.
    - This is low priority, since the benchmark won't take long to run even with lists

TODO: Add more metrics, specifically ones that are relevant for bitext mining, such as xsim

TODO: Should Recall and Precision return average across all queries or lists of per-query scores?
- Jan 28th, 2026 - currently returns per-query scores for more flexibility in analysis
"""

import math
import numpy as np

"""
@Behavior: Computes the 
@Parameters: Two lists of index pairs: one from the embedded results and one from the ground truth corpus.
             - embedded_index_pairs: List of tuples (query_idx, retrieved_idx)
                - this represents the identified pairs of related items based on the embeddings and pairing function
             - corpus_index_pairs: List of tuples (query_idx, relevant_idx)
                - this represents the ground truth pairs of related items based on the corpus data
@Returns: The percentage of correctly identified pairs out of all pairs in the embedded results.
"""
def percent_correct_pairs(embedded_index_pairs, corpus_index_pairs):
    # Convert corpus_index_pairs to a set for faster lookup
    corpus_set = set(corpus_index_pairs)
    # Count correctly identified pairs
    correct_count = sum(1 for pair in embedded_index_pairs if pair in corpus_set)
    # Return percentage of correct pairs
    total_count = len(embedded_index_pairs)
    return (correct_count / total_count * 100) if total_count > 0 else 0.0

"""
@Behavior: Computes the Hit at K for a set of rankings against ground truth data.
@Parameters: k (int): The cutoff rank.
                rankings (list of list): The ranked lists of retrieved items for each query.
                ground_truth (list of set): The sets of relevant items for each query.
@Returns: list of int: A list of hit at K scores (1 or 0), one per query.
                - 1 if at least one relevant item is in the top-k retrieved items, otherwise 0.
                - If there are no relevant items for a query, its hit is considered 0.
                - If there are no rankings provided, returns an empty list.
"""
def hit_at_k(k, rankings, ground_truth):
    # TODO: Think about edge cases/exceptions
    

    hits = []
    for query_rankings, query_ground_truth in zip(rankings, ground_truth):
        if len(query_ground_truth) == 0: # If no relevant items, hit is 0
            hits.append(0)
            continue # End this iteration and move to next query

        top_k = query_rankings[:k] if k > 0 else [] # Get top-k retrieved items
        hit = 1 if any(item in query_ground_truth for item in top_k) else 0 
                # Check if any of the top-k items are relevant
        hits.append(hit) # Append hit for this query

    return hits

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
@Behavior: Computes the Reciprocal Rank (RR) for a set of rankings against ground truth data.
    - RR = 1 / rank of first relevant item
    - To get Mean Reciprocal Rank (MRR), average the returned list.
@Parameters: rankings (list of list): The ranked lists of retrieved items for each query.
             ground_truth (list of set): The sets of relevant items for each query.
@Returns: list of float: A list of reciprocal rank scores, one per query.
                - If there are no relevant items for a query, its score is 0.0
                - If there are no rankings provided, returns an empty list.
"""
def reciprocal_ranks(rankings, ground_truth):
    # TODO: Think about edge cases/exceptions
    

    reciprocal_ranks = [] # List to store reciprocal rank for each query
    for query_rankings, query_ground_truth in zip(rankings, ground_truth):
        if len(query_ground_truth) == 0:
            reciprocal_ranks.append(0.0)
            continue

        rr = 0.0
        for idx, item in enumerate(query_rankings):
            if item in query_ground_truth:
                rr = 1.0 / (idx + 1)
                break
        reciprocal_ranks.append(rr)

    return reciprocal_ranks # Return list of per-query reciprocal rank scores

"""
@Behavior: Computes the Normalized Discounted Cumulative Gain (NDCG) for a set of rankings.
@Parameters: rankings (list of list): The ranked lists of retrieved items for each query.
             ground_truth (list of set): The sets of relevant items for each query.
@Returns: list of float: A list of NDCG scores, one per query.
                - If there are no relevant items for a query, its NDCG is 0.0
                - If there are no rankings provided, returns an empty list.
"""
def normalized_discounted_cumulative_gain(rankings, ground_truth):
    # TODO: Think about edge cases/exceptions
   

    ndcgs = [] # List to store NDCG for each query
    for query_rankings, query_ground_truth in zip(rankings, ground_truth):
        if len(query_ground_truth) == 0:
            ndcgs.append(0.0)
            continue

        # Compute DCG for the given ranking (binary relevance)
        dcg = 0.0
        for i, item in enumerate(query_rankings):
            if item in query_ground_truth:
                dcg += 1.0 / math.log2(i + 2)

        # Compute IDCG for the ideal ranking
        ideal_hits = min(len(query_ground_truth), len(query_rankings))
        idcg = 0.0
        for i in range(ideal_hits):
            idcg += 1.0 / math.log2(i + 2)

        ndcg = dcg / idcg if idcg > 0 else 0.0
        ndcgs.append(ndcg)

    return ndcgs # Return list of per-query NDCG scores