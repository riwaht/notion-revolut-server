import os
import json
from sentence_transformers import SentenceTransformer, util

DEFAULT_CATEGORY = "Others"
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

# Precompute embeddings for individual keywords
def _compute_category_embeddings(keywords_map):
    return {
        category: [_model.encode(keyword) for keyword in keywords]
        for category, keywords in keywords_map.items()
    }

EXPENSE_EMBEDDINGS = _compute_category_embeddings(EXPENSE_KEYWORDS)
INCOME_EMBEDDINGS = _compute_category_embeddings(INCOME_KEYWORDS)

def _categorize_semantically(description: str, is_income: bool) -> str:
    if not description:
        return DEFAULT_CATEGORY

    desc_vec = _model.encode(description)
    embeddings = INCOME_EMBEDDINGS if is_income else EXPENSE_EMBEDDINGS

    best_category, best_score = None, 0.0
    for category, keyword_vecs in embeddings.items():
        # Find the best match among all keywords in this category
        for keyword_vec in keyword_vecs:
            score = float(util.cos_sim(desc_vec, keyword_vec))
            if score > best_score:
                best_category, best_score = category, score

    return best_category if best_score > 0.2 else DEFAULT_CATEGORY

def categorize_transaction(description: str, is_income: bool = False) -> str:
    if not description:
        return DEFAULT_CATEGORY

    description = description.lower().strip()

    # Hardcoded Savings override (removed savings transfer logic)
    if any(keyword in description for keyword in ["vault", "to usd", "to eur"]):
        return "Savings"

    keyword_map = INCOME_KEYWORDS if is_income else EXPENSE_KEYWORDS
    for category, keywords in keyword_map.items():
        for keyword in keywords:
            if keyword in description:
                return category

    return _categorize_semantically(description, is_income)
