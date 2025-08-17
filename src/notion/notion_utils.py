# notion_utils.py

import json
import os
import requests
from datetime import datetime
from src.notion.category_mapper import categorize_transaction
from dotenv import load_dotenv
from forex_python.converter import CurrencyRates
from forex_python.converter import RatesNotAvailableError
from collections import defaultdict

# Set up global variables
CACHE_FILE = "exchange_rates_cache.json"
rates_cache = defaultdict(dict)
c = CurrencyRates()

# Load cache from file
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        raw = json.load(f)
        for date_str, currencies in raw.items():
            rates_cache[date_str] = currencies
else:
    rates_cache = defaultdict(dict)

# Save cache to file
def save_rates_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(rates_cache, f, indent=2)

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
    "Food": "12e364a1215e8144817beb04c569ea05",
    "Transport": "12e364a1215e81cdbe08f0a9cbb58a64",
    "Beauty": "12e364a1215e8041bba4dc6a1dfbf0ef",
    "Gifts": "12e364a1215e8103a271fd24cebd6148",
    "Health": "233364a1215e801ba547ed5e48b38d3d",
    "Subscription": "179364a1215e806481bffd675a74e97e",
    "Gym": "12e364a1215e81eea2fcc9acb982d790",
    "Savings": "12e364a1215e80c4bacfdee3004f32b3",
    "Travel": "12e364a1215e8083a389c6dbf7ef8dac",
    "Free Time": "12e364a1215e818e98d0e8abcdadf58c",
    "Necessities": "156364a1215e80dcbebddd89ba57b4ab",
    "Others": "12e364a1215e81999522f7421e1947f0",
    "Transaction": "156364a1215e80e380e6c328a7e5d2e4"
}

INCOME_CATEGORY_IDS = {
    "Salary": "12e364a1215e81e9814ce231403b1207",
    "Parents" : "12e364a1215e81ba8da4c0100297cdda",
    "Savings" : "12e364a1215e8054860de5b2986f8e04",
    "Repaid": "136364a1215e80fab733eb38739b9a1d",
    "Others": "12e364a1215e81acbb77f4e668d148d2",
}

ACCOUNT_IDS = {
    "PLN": "24e364a1215e80faba4ec73df82d4aac",
    "USD": "245364a1215e8082ba70c1831590fc89",
    "EUR": "245364a1215e8082ba70c1831590fc89",
    "SAVINGS": "24e364a1215e80778100e822ec199a0a",
    "DEFAULT": "12e364a1215e808daed4e333e7f3efd1",
}

c = CurrencyRates()

# TODO: Handle failed conversions
def convert_to_usd(amount: float, currency: str, date_str: str) -> float:
    """
    Convert a given amount to USD using historical exchange rates.
    :param amount: Amount in source currency
    :param currency: Source currency (e.g., "EUR", "PLN")
    :param date_str: Date in 'YYYY-MM-DD' format
    :return: Amount in USD (rounded to 2 decimals)
    """
    # Use cached rate if available
    if currency in rates_cache.get(date_str, {}):
        rate = float(rates_cache[date_str][currency])
    else:
        try:
            rate = c.get_rate(currency, "USD", datetime.strptime(date_str, "%Y-%m-%d").date())
            rates_cache[date_str][currency] = rate
            save_rates_cache()
        except RatesNotAvailableError:
            print(f"⚠️ Rate not available for {currency} on {date_str}, defaulting to original amount")
            return round(amount, 2)

    return round(amount * rate, 2)

def post_transaction_to_notion(tx, account, is_income=None):
    raw_amount = abs(tx["amount"])
    currency = tx["currency"]
    description = tx["description"]
    timestamp = tx["timestamp"]

    # Auto-detect income vs expense if not explicitly passed
    if is_income is None:
        if "exchanged to" in description.lower():
            is_income = tx["amount"] > 0
        else:
            is_income = tx["amount"] >= 0

    db_id = DB_IDS["income"] if is_income else DB_IDS["expenses"]

    # Determine account relation
    if "mb:" in description.lower() or "vault" in description.lower() or "savings" in description.lower():
        account_relation_id = ACCOUNT_IDS["SAVINGS"]
    else:
        account_relation_id = ACCOUNT_IDS.get(currency, ACCOUNT_IDS["DEFAULT"])

    # Determine category
    category_name = categorize_transaction(description, is_income=is_income)
    category_relation_id = (
        INCOME_CATEGORY_IDS.get(category_name)
        if is_income else CATEGORY_IDS.get(category_name)
    )

    # Convert timestamp to ISO 8601 date
    date_obj = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    date_str = date_obj.date().isoformat()

    # Convert to USD
    converted_amount = convert_to_usd(raw_amount, currency, date_str)

    # Build Notion properties
    properties = {
        "Name": {"title": [{"text": {"content": description}}]},
        "Amount": {"number": converted_amount},
        "Account": {"relation": [{"id": account_relation_id}]},
        "Category": {"relation": [{"id": category_relation_id}]} if category_relation_id else {},
        "Date": {"date": {"start": date_str}},
    }

    if not is_income:
        properties["Month"] = {"select": {"name": date_obj.strftime("%B")}}
        properties["Year"] = {"select": {"name": str(date_obj.year)}}

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }

    response = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)

    if response.status_code == 200:
        print(f"Added {description} to Notion ({'Income' if is_income else 'Expense'})")
    else:
        print(f"Failed to add {description} — {response.status_code}")
        print(response.text)
