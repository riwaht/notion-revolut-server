"""
Transaction categorization using keyword matching and semantic similarity with averaged embeddings.
"""

import json
import os

import numpy as np
from sentence_transformers import SentenceTransformer, util

DEFAULT_CATEGORY = "Other"
MODEL_NAME = "paraphrase-MiniLM-L6-v2"
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CATEGORIES_PATH = os.path.join(BASE_DIR, "data", "categories.json")

# Load categories from JSON
with open(CATEGORIES_PATH, "r") as f:
    all_categories = json.load(f)

EXPENSE_KEYWORDS = all_categories.get("expenses", {})
INCOME_KEYWORDS = all_categories.get("income", {})

# Load sentence transformer model once
_model = SentenceTransformer(MODEL_NAME)


def _compute_averaged_embeddings(keywords_map):
    """Compute averaged embedding for each category from its keywords."""
    embeddings = {}
    for category, keywords in keywords_map.items():
        if not keywords:
            continue
        keyword_embeddings = [_model.encode(keyword) for keyword in keywords]
        embeddings[category] = np.mean(keyword_embeddings, axis=0)
    return embeddings


EXPENSE_EMBEDDINGS = _compute_averaged_embeddings(EXPENSE_KEYWORDS)
INCOME_EMBEDDINGS = _compute_averaged_embeddings(INCOME_KEYWORDS)


def _categorize_semantically(description: str, is_income: bool) -> str:
    """Use semantic similarity with averaged category embeddings."""
    if not description:
        return DEFAULT_CATEGORY

    desc_vec = _model.encode(description)
    embeddings = INCOME_EMBEDDINGS if is_income else EXPENSE_EMBEDDINGS

    best_category, best_score = None, 0.0
    for category, avg_vec in embeddings.items():
        score = float(util.cos_sim(desc_vec, avg_vec))
        if score > best_score:
            best_category, best_score = category, score

    return best_category if best_score > 0.2 else DEFAULT_CATEGORY


def categorize_transaction(description: str, is_income: bool = False) -> str:
    """
    Categorize a transaction based on its description.

    Uses keyword matching first, then falls back to semantic similarity
    with averaged category embeddings.

    Args:
        description: Transaction description
        is_income: Whether this is an income transaction

    Returns:
        Category name
    """
    if not description:
        return DEFAULT_CATEGORY

    description_lower = description.lower().strip()

    # Check for transfer/exchange transactions first (highest priority)
    transfer_keywords = ["exchanged to", "exchanged from", "vault", "transfer"]
    if any(keyword in description_lower for keyword in transfer_keywords):
        return "Transfer"

    # Keyword-based matching
    keyword_map = INCOME_KEYWORDS if is_income else EXPENSE_KEYWORDS
    for category, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in description_lower:
                return category

    # Fall back to semantic similarity with averaged embeddings
    return _categorize_semantically(description, is_income)
