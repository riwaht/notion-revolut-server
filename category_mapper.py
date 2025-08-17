# category_mapper.py

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

DEFAULT_CATEGORY = "Others"

def categorize_transaction(description: str) -> str:
    """
    Map a transaction description to a category based on keywords.
    """
    if not description:
        return DEFAULT_CATEGORY

    description = description.lower()

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in description:
                return category

    return DEFAULT_CATEGORY
