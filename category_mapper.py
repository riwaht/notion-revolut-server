# category_mapper.py

# Expense category keywords
CATEGORY_KEYWORDS = {
    "Food": [
        "restaurant", "coffee", "kebab", "burger", "pizza", "bar", "food", "café", "cafe", "lunch", "dinner", "eatery"
    ],
    "Transport": [
        "uber", "taxi", "bolt", "bus", "train", "metro", "tram", "grab", "ride", "transport", "public transit"
    ],
    "Beauty": [
        "salon", "nail", "hair", "spa", "lashes", "wax", "beauty"
    ],
    "Gifts": [
        "gift", "souvenir", "present", "birthday", "anniversary"
    ],
    "Health": [
        "pharmacy", "med", "hospital", "clinic", "pill", "health"
    ],
    "Subscription": [
        "netflix", "spotify", "youtube", "prime", "subscription", "sub"
    ],
    "Gym": [
        "gym", "fitness", "membership", "workout", "training"
    ],
    "Savings": [
        "vault", "transfer to savings", "stash", "save"
    ],
    "Travel": [
        "airbnb", "hotel", "booking.com", "ryanair", "wizz", "flights", "flight", "trip", "travel", "trainline"
    ],
    "Free Time": [
        "museum", "park", "zoo", "game", "event", "festival", "ticket", "concert"
    ],
    "Necessities": [
        "grocery", "market", "aldi", "lidl", "biedronka", "carrefour", "monoprix", "essentials", "coop", "kaufland"
    ],
    "Others": []
}

# Income category keywords
INCOME_CATEGORY_KEYWORDS = {
    "Salary": ["salary", "paycheck", "wage", "employer"],
    "Parents": ["dad", "mom", "mother", "father", "parent", "family"],
    "Savings": ["revolut vault", "vault income", "interest"],
    "Repaid": ["repaid", "returned", "refund", "reimbursement", "payback"],
    "Others": []
}

DEFAULT_CATEGORY = "Others"

def categorize_transaction(description: str, is_income: bool = False) -> str:
    """
    Map a transaction description to a category based on keywords.
    """
    if not description:
        return DEFAULT_CATEGORY

    description = description.lower()

    category_map = INCOME_CATEGORY_KEYWORDS if is_income else CATEGORY_KEYWORDS

    for category, keywords in category_map.items():
        for keyword in keywords:
            if keyword in description:
                return category

    return DEFAULT_CATEGORY
