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
    "INTERNATIONAL": "245364a1215e8082ba70c1831590fc89",  # Card International (USD/EUR/other currencies)
    "SAVINGS": "24e364a1215e80778100e822ec199a0a",
    "DEFAULT": "12e364a1215e808daed4e333e7f3efd1",
}

# Automatic savings transfer amount (PLN)
AUTO_SAVINGS_AMOUNT = 2000


def is_salary_transaction(description: str) -> bool:
    """Check if transaction is a salary payment"""
    salary_keywords = ["salary", "paycheck", "wage", "employer", "snowflake", "payment from", "payroll", "stipend", "bonus"]
    return any(keyword in description.lower() for keyword in salary_keywords)


def parse_exchange_currencies(description: str):
    """
    Parse exchange transaction description to extract source and destination currencies.
    Returns tuple of (source_currency, destination_currency) or (None, None) if not parseable.
    
    Expected formats:
    - "Exchanged to EUR"
    - "Exchanged from PLN to EUR"
    - "PLN exchanged to EUR"
    """
    desc_lower = description.lower()
    
    # Try to find patterns like "exchanged to EUR", "exchanged from PLN to EUR", etc.
    import re
    
    # Pattern 1: "Exchanged from PLN to EUR"
    match = re.search(r'exchanged from ([A-Z]{3}) to ([A-Z]{3})', description, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).upper()
    
    # Pattern 2: "PLN exchanged to EUR" 
    match = re.search(r'([A-Z]{3}) exchanged to ([A-Z]{3})', description, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2).upper()
        
    # Pattern 3: "Exchanged to EUR" (need to infer source currency from tx context)
    match = re.search(r'exchanged to ([A-Z]{3})', description, re.IGNORECASE)
    if match:
        destination = match.group(1).upper()
        # We'll return None for source and let the caller handle it
        return None, destination
        
    # Pattern 4: "Exchanged from PLN"
    match = re.search(r'exchanged from ([A-Z]{3})', description, re.IGNORECASE)
    if match:
        source = match.group(1).upper()
        return source, None
    
    return None, None


def create_automatic_savings_transfer(original_tx, account):
    """Create automatic transfer from PLN to Savings when salary is received"""
    if original_tx["currency"] != "PLN":
        return  # Only transfer from PLN transactions
    
    date_obj = datetime.fromisoformat(original_tx["timestamp"].replace("Z", "+00:00"))
    date_str = date_obj.date().isoformat()
    
    print(f"💰 Creating automatic savings transfer of {AUTO_SAVINGS_AMOUNT} PLN")
    
    # Create expense transaction (money leaving PLN account)
    expense_tx = {
        "amount": -AUTO_SAVINGS_AMOUNT,
        "currency": "PLN",
        "description": f"Auto transfer to savings - {AUTO_SAVINGS_AMOUNT} PLN",
        "timestamp": original_tx["timestamp"],
        "transaction_id": f"auto_savings_expense_{original_tx['transaction_id']}"
    }
    
    # Create income transaction (money entering Savings account)  
    income_tx = {
        "amount": AUTO_SAVINGS_AMOUNT,
        "currency": "PLN",
        "description": f"Auto transfer from PLN - {AUTO_SAVINGS_AMOUNT} PLN",
        "timestamp": original_tx["timestamp"],
        "transaction_id": f"auto_savings_income_{original_tx['transaction_id']}"
    }
    
    # Post the expense (PLN account loses money)
    post_transaction_to_notion_internal(expense_tx, account, is_income=False, force_account="PLN")
    
    # Post the income (Savings account gains money)
    post_transaction_to_notion_internal(income_tx, account, is_income=True, force_account="SAVINGS")


def post_transaction_to_notion_internal(tx, account, is_income=None, force_account=None):
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

    # Determine account relation - handle exchange transactions specially
    if force_account:
        account_relation_id = ACCOUNT_IDS[force_account]
    elif "vault" in description.lower():
        account_relation_id = ACCOUNT_IDS["SAVINGS"]
    elif "exchanged" in description.lower():
        # Special handling for exchange transactions
        source_currency, dest_currency = parse_exchange_currencies(description)
        
        # Determine which currency to use for account assignment
        if is_income:
            # For income (money received), use destination currency
            # If we can parse destination currency, use it; otherwise fall back to tx currency
            account_currency = dest_currency if dest_currency else currency
        else:
            # For expense (money sent), use source currency
            # If we can parse source currency, use it; otherwise fall back to tx currency
            account_currency = source_currency if source_currency else currency
        
        # Now assign account based on the determined currency
        if account_currency == "PLN":
            account_relation_id = ACCOUNT_IDS["PLN"]
        else:
            # All non-PLN currencies (EUR, USD, HUF, etc.) go to Card International
            account_relation_id = ACCOUNT_IDS["INTERNATIONAL"]
    elif currency == "PLN":
        account_relation_id = ACCOUNT_IDS["PLN"]
    else:
        # All non-PLN currencies (EUR, USD, HUF, etc.) go to Card International
        account_relation_id = ACCOUNT_IDS["INTERNATIONAL"]

    # Special cases and category determination
    if currency not in ["USD", "PLN"]:
        # Non-major currencies (HUF, GBP, etc.) default to travel
        category_name = "Travel"
        category_relation_id = CATEGORY_IDS.get(category_name)
    else:
        # Normal category determination for PLN, USD, EUR
        category_name = categorize_transaction(description, is_income=is_income)
        category_relation_id = (
            INCOME_CATEGORY_IDS.get(category_name)
            if is_income else CATEGORY_IDS.get(category_name)
        )

    # Convert timestamp to ISO 8601 date
    date_obj = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    date_str = date_obj.date().isoformat()

    # Convert to USD for consistent tracking
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
    if account_relation_id == ACCOUNT_IDS["INTERNATIONAL"]:
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


def post_transaction_to_notion(tx, account, is_income=None):
    """
    Main function to post transactions to Notion.
    Handles automatic savings transfer when salary is received.
    """
    # First post the original transaction
    post_transaction_to_notion_internal(tx, account, is_income)
    
    # Check if this is a salary transaction and create automatic transfer
    # Auto-detect income if not specified
    detected_income = is_income if is_income is not None else tx["amount"] >= 0
    
    if detected_income and is_salary_transaction(tx["description"]) and tx["currency"] == "PLN":
        create_automatic_savings_transfer(tx, account)
