"""
Lexical (non-neural) similarity over Lean statements.

This module exists to answer one question: **how much of a perturbation is
visible to a model that only does word matching?**

The motivating observation is that contrastive training on natural-language
math pairs underperformed, and the suspected cause is that the model learned
surface token overlap rather than logical content. A Lean perturbation dataset
is only useful as a training signal where those two things *disagree* — where
a pair is lexically near but logically far, or lexically far but logically
identical. Everything here is deliberately dumb: bag-of-tokens, character
n-grams, and sequence alignment. If a dumb model can already separate a
perturbation from its anchor, that perturbation teaches an embedder nothing.

Three views of "surface similarity", from coarsest to finest:

  * ``jaccard`` — set overlap of Lean tokens. Order-blind and count-blind;
    this is literally "does the same vocabulary appear?".
  * ``tfidf_cosine`` — corpus-weighted bag of tokens or character n-grams.
    Rare identifiers (``MeasureTheory.MemLp``) dominate, common syntax
    (``∀``, ``:``) is discounted. The closest cheap stand-in for what a
    lexical retriever actually scores.
  * ``sequence_ratio`` — order-aware alignment over the token stream. Catches
    reorderings that the two bag-of-words measures are blind to.

None of these require torch, transformers, or network access.
"""

from __future__ import annotations

import difflib
import re
from typing import Iterable, Sequence

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

__all__ = [
    "lean_tokens",
    "jaccard",
    "sequence_ratio",
    "tfidf_cosine_matrix",
    "SIMILARITY_VIEWS",
]


# ── Tokenisation ──────────────────────────────────────────────────────────────
# Three alternatives, tried in order:
#   1. a dotted ASCII identifier — `MeasureTheory.MemLp`, `hp'`, `Nat.succ_le`
#      kept whole, because the namespace is the strongest topical signal a
#      bag-of-words model has;
#   2. a run of digits — numeric literals matter for `const_to_zero_one`;
#   3. any single remaining non-space character — this is what catches the
#      unicode that Lean is made of (`∀ ∃ ↔ → ¬ ≤ α β ℕ`), each as its own
#      token. A `\w+` tokeniser would silently drop all of it.
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_'!?]*(?:\.[A-Za-z0-9_'!?]+)*|\d+|\S")


def lean_tokens(statement: str) -> list[str]:
    """Split a Lean statement into tokens for lexical comparison."""
    return _TOKEN_RE.findall(statement)


def _tokens_for_sklearn(statement: str) -> list[str]:
    """Adapter so ``TfidfVectorizer`` can use :func:`lean_tokens` directly."""
    return lean_tokens(statement)


# ── Pairwise measures ─────────────────────────────────────────────────────────


def jaccard(a: str, b: str) -> float:
    """Set overlap of the two token streams, in ``[0, 1]``.

    The purest word-matching score: order and repetition are discarded, so a
    perturbation that only reorders or rebrackets scores a perfect 1.0.
    """
    ta, tb = set(lean_tokens(a)), set(lean_tokens(b))
    if not ta and not tb:
        return 1.0
    union = ta | tb
    return len(ta & tb) / len(union) if union else 1.0


def sequence_ratio(a: str, b: str) -> float:
    """Order-aware alignment similarity over tokens, in ``[0, 1]``.

    ``difflib``'s ratio rather than a true edit distance: it is quadratic in
    the same way but ships with Python, and on statements of this length
    (tens to low hundreds of tokens) the difference is not measurable.
    """
    return difflib.SequenceMatcher(None, lean_tokens(a), lean_tokens(b)).ratio()


def tfidf_cosine_matrix(
    statements: Sequence[str], *, analyzer: str = "token"
) -> np.ndarray:
    """Return the full cosine-similarity matrix for ``statements``.

    Args:
        statements: the corpus. IDF is fitted on exactly this set, so pass
            anchors, variants, and background statements together — fitting
            on the variants alone would make the shared boilerplate look rare.
        analyzer: ``"token"`` for Lean-token TF-IDF, ``"char"`` for character
            3–5-grams. The character view is the one that survives renaming:
            it still sees ``MemLp`` inside ``MeasureTheory.MemLp``.

    Rows are L2-normalised by ``TfidfVectorizer``, so the Gram matrix *is* the
    cosine matrix and no separate normalisation step is needed.
    """
    if analyzer == "token":
        vec = TfidfVectorizer(
            analyzer="word",
            tokenizer=_tokens_for_sklearn,
            preprocessor=lambda s: s,
            token_pattern=None,
            lowercase=False,
        )
    elif analyzer == "char":
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=False)
    else:
        raise ValueError(f"analyzer must be 'token' or 'char', got {analyzer!r}")

    matrix = vec.fit_transform(statements)
    return (matrix @ matrix.T).toarray()


# ── The set of views the analysis reports on ──────────────────────────────────
# Keyed by the name used in reports. Each entry is (human label, pairwise fn or
# None). ``None`` means the view is matrix-valued and computed in bulk by
# :func:`tfidf_cosine_matrix`; see ``analyze_geometry`` for the dispatch.

SIMILARITY_VIEWS: dict[str, str] = {
    "tfidf_token": "TF-IDF over Lean tokens (bag of words)",
    "tfidf_char": "TF-IDF over character 3–5-grams (subword surface form)",
    "jaccard": "Token-set overlap (order-blind word matching)",
    "sequence": "Token-sequence alignment (order-aware)",
}


def pairwise_view(view: str, a: str, b: str) -> float:
    """Compute one pairwise similarity for the views that support it."""
    if view == "jaccard":
        return jaccard(a, b)
    if view == "sequence":
        return sequence_ratio(a, b)
    raise ValueError(f"{view!r} is matrix-valued; use tfidf_cosine_matrix")


def summarise(values: Iterable[float]) -> dict[str, float]:
    """Mean / std / min / max of a similarity sample, as plain floats."""
    arr = np.asarray(list(values), dtype=float)
    if arr.size == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan"),
                "min": float("nan"), "max": float("nan")}
    return {
        "n": int(arr.size),
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "min": float(arr.min()),
        "max": float(arr.max()),
    }
