# notion_utils.py

import json
import os
import requests
from datetime import datetime
from decimal import Decimal
from src.notion.category_mapper import categorize_transaction
from dotenv import load_dotenv
from src.utils.exchange_utils import converter
from collections import defaultdict
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
    "Transaction": "25a364a1215e800fad15f09941aa5e19",
    "Others": "12e364a1215e81acbb77f4e668d148d2",
}

ACCOUNT_IDS = {
    "PLN": "24e364a1215e80faba4ec73df82d4aac",
    "USD": "245364a1215e8082ba70c1831590fc89",  # Card International
    "EUR": "245364a1215e8082ba70c1831590fc89",  # Card International (same as USD)
    "SAVINGS": "24e364a1215e80778100e822ec199a0a",
    "DEFAULT": "12e364a1215e808daed4e333e7f3efd1",
}


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
    if "exchanged to" in description.lower() or "exchanged from" in description.lower():
        # For exchange transactions
        if is_income:
            # Income: All non-PLN currencies go to Card International (USD/EUR account)
            if currency == "PLN":
                account_relation_id = ACCOUNT_IDS["PLN"]
            elif currency == "USD":
                account_relation_id = ACCOUNT_IDS["SAVINGS"]
            else:
                # EUR, HUF, etc. all go to Card International
                account_relation_id = ACCOUNT_IDS["USD"]  # Card International (same as EUR)
        else:
            # Expense: Based on source currency
            if currency == "PLN":
                account_relation_id = ACCOUNT_IDS["PLN"]
            elif currency == "USD":
                account_relation_id = ACCOUNT_IDS["SAVINGS"]
            elif currency == "EUR":
                account_relation_id = ACCOUNT_IDS["EUR"]  # Card International
            else:
                # Other currencies go to Card International
                account_relation_id = ACCOUNT_IDS["USD"]  # Card International
    elif "mb:" in description.lower() or "vault" in description.lower() or "savings" in description.lower():
        account_relation_id = ACCOUNT_IDS["SAVINGS"]
    else:
        # Non-exchange transactions: explicit currency mapping
        if currency == "PLN":
            account_relation_id = ACCOUNT_IDS["PLN"]
        else:
            # EUR, USD, and all other currencies use Card International
            account_relation_id = ACCOUNT_IDS["USD"]  # Card International (includes EUR, USD, travel currencies)

    # if currency is anything other than usd, pln or eur, set category to travel
    if currency not in ["USD", "PLN", "EUR"]:
        category_name = "Travel"
        category_relation_id = CATEGORY_IDS.get(category_name)
    else:
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
    converted_amount = converter.convert_to_usd(Decimal(str(raw_amount)), currency, date_str)

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
        properties["To be Repaid?"] = {"select": {"name": "Not to be Repaid"}}
        properties["Year"] = {"select": {"name": str(date_obj.year)}}

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }

    # Enhanced logging with transaction ID and destination
    tx_id = tx["transaction_id"][:12]  # Show first 12 chars of transaction ID
    db_type = "Income" if is_income else "Expense"
    
    # Get account name for logging
    account_name = "Unknown"
    if account_relation_id == ACCOUNT_IDS["USD"]:  # Same as EUR - Card International
        account_name = "Card International"
    elif account_relation_id == ACCOUNT_IDS["PLN"]:
        account_name = "PLN"
    elif account_relation_id == ACCOUNT_IDS["SAVINGS"]:
        account_name = "Savings"
    else:
        account_name = "DEFAULT"
    
    response = requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload)

    if response.status_code == 200:
        print(f"✅ [{tx_id}] Added '{description}' to {db_type} DB | ${converted_amount} USD | {category_name} | {account_name} account")
    else:
        print(f"❌ [{tx_id}] Failed to add '{description}' to {db_type} DB — {response.status_code}")
        print(response.text)
