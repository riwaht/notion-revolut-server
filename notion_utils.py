# notion_utils.py

import os
import requests
from datetime import datetime
from category_mapper import categorize_transaction
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

DB_IDS = {
    "expenses": os.getenv("EXPENSES_DB_ID", "default_expenses_db_id"),
    "income": os.getenv("INCOME_DB_ID", "default_income_db_id"),
}

# Static mappings from names to Notion relation IDs
CATEGORY_IDS = {
    "Food": "💰food-id",
    "Transport": "🚗transport-id",
    "Beauty": "💄beauty-id",
    "Gifts": "🎁gifts-id",
    "Health": "🧪health-id",
    "Subscription": "📦subscription-id",
    "Gym": "🏋️‍♀️gym-id",
    "Savings": "🏦savings-id",
    "Travel": "✈️travel-id",
    "Free Time": "🎭free-time-id",
    "Necessities": "🛒necessities-id",
    "Others": "📂others-id",
}

ACCOUNT_IDS = {
    "PLN": "card-polish-id",
    "USD": "card-international-id",
    "EUR": "card-international-id",
    "DEFAULT": "card-international-id"
}


def post_transaction_to_notion(tx, account, is_income=False):
    db_id = DB_IDS["income"] if is_income else DB_IDS["expenses"]

    amount = abs(tx["amount"])
    currency = tx["currency"]
    description = tx["description"]
    timestamp = tx["timestamp"]

    # Determine account relation
    account_relation_id = ACCOUNT_IDS.get(currency, ACCOUNT_IDS["DEFAULT"])

    # Determine category
    category_name = categorize_transaction(description)
    category_relation_id = CATEGORY_IDS.get(category_name)

    # Convert timestamp to ISO 8601 date (yyyy-mm-dd)
    date_obj = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    date_str = date_obj.date().isoformat()

    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Name": {"title": [{"text": {"content": description}}]},
            "Amount": {"number": amount},
            "Account": {"relation": [{"id": account_relation_id}]},
            "Category": {"relation": [{"id": category_relation_id}]} if not is_income else {},
            "Date": {"date": {"start": date_str}},
            "Month": {"select": {"name": date_obj.strftime("%B")}},
            "Year": {"number": date_obj.year},
        }
    }

    response = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)

    if response.status_code == 200:
        print(f"✅ Added {description} to Notion ({'Income' if is_income else 'Expense'})")
    else:
        print(f"❌ Failed to add {description} — {response.status_code}")
        print(response.text)
