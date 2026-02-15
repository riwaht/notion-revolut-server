"""
Notion API utilities for posting transactions and managing failed transaction retries.
"""

import json
import os
import time
from datetime import datetime
from decimal import Decimal

import requests
from dotenv import load_dotenv

from src.notion.category_mapper import categorize_transaction
from src.utils.exchange_utils import converter

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

DB_IDS = {
    "expenses": os.getenv("EXPENSES_DB_ID", ""),
    "income": os.getenv("INCOME_DB_ID", ""),
}

# Account IDs from environment variables
ACCOUNT_IDS = {
    "PRIMARY": os.getenv("PRIMARY_ACCOUNT_ID", ""),
    "SECONDARY": os.getenv("SECONDARY_ACCOUNT_ID", ""),
}

# Category IDs from environment variables
EXPENSE_CATEGORY_IDS = {
    "Food": os.getenv("CATEGORY_FOOD_ID", ""),
    "Groceries": os.getenv("CATEGORY_GROCERIES_ID", ""),
    "Transport": os.getenv("CATEGORY_TRANSPORT_ID", ""),
    "Shopping": os.getenv("CATEGORY_SHOPPING_ID", ""),
    "Health": os.getenv("CATEGORY_HEALTH_ID", ""),
    "Entertainment": os.getenv("CATEGORY_ENTERTAINMENT_ID", ""),
    "Bills": os.getenv("CATEGORY_BILLS_ID", ""),
    "Travel": os.getenv("CATEGORY_TRAVEL_ID", ""),
    "Transfer": os.getenv("CATEGORY_TRANSFER_ID", ""),
    "Other": os.getenv("CATEGORY_OTHER_ID", ""),
}

INCOME_CATEGORY_IDS = {
    "Salary": os.getenv("CATEGORY_SALARY_ID", ""),
    "Transfer": os.getenv("CATEGORY_TRANSFER_ID", ""),
    "Refund": os.getenv("CATEGORY_REFUND_ID", ""),
    "Other": os.getenv("CATEGORY_OTHER_INCOME_ID", ""),
}

# Base currency for conversion
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "USD")

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FAILED_TRANSACTIONS_FILE = os.path.join(BASE_DIR, "data", "failed_transactions.json")


def is_temporary_error(status_code: int) -> bool:
    """Check if status code indicates a temporary error that should be retried."""
    return status_code in [429, 500, 502, 503, 504]


def is_permanent_error(status_code: int) -> bool:
    """Check if status code indicates a permanent error that should not be retried."""
    return status_code in [400, 401, 403, 404, 422]


def log_failed_transaction(tx, account, is_income, error_info):
    """Log a failed transaction to file for later retry."""
    try:
        os.makedirs(os.path.dirname(FAILED_TRANSACTIONS_FILE), exist_ok=True)

        failed_tx = {
            "transaction": tx,
            "account": account,
            "is_income": is_income,
            "error": error_info,
            "timestamp": datetime.now().isoformat(),
            "retry_count": 0,
        }

        failed_txs = []
        if os.path.exists(FAILED_TRANSACTIONS_FILE):
            try:
                with open(FAILED_TRANSACTIONS_FILE, "r") as f:
                    failed_txs = json.load(f)
            except (json.JSONDecodeError, IOError):
                failed_txs = []

        failed_txs.append(failed_tx)

        with open(FAILED_TRANSACTIONS_FILE, "w") as f:
            json.dump(failed_txs, f, indent=2)

        print(f"Logged failed transaction {tx['transaction_id'][:12]} to retry queue")

    except Exception as e:
        print(f"Failed to log failed transaction: {e}")


def retry_with_backoff(func, *args, **kwargs):
    """Execute a function with exponential backoff retry logic."""
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"Timeout error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            else:
                print(f"Max retries exceeded for timeout error: {e}")
                break
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"Connection error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            else:
                print(f"Max retries exceeded for connection error: {e}")
                break
        except requests.exceptions.RequestException as e:
            last_exception = e
            print(f"Request exception (not retryable): {e}")
            break
        except Exception as e:
            last_exception = e
            print(f"Unexpected error: {e}")
            break

    raise last_exception


def post_transaction_to_notion_internal(tx, account, is_income=None, force_account_id=None, override_amount=None):
    """Internal function to post transaction to Notion."""
    raw_amount = abs(tx["amount"])
    currency = tx["currency"]
    description = tx["description"]
    timestamp = tx["timestamp"]
    tx_id = tx["transaction_id"][:12]

    # Auto-detect income vs expense
    if is_income is None:
        if "exchanged to" in description.lower():
            is_income = tx["amount"] > 0
        else:
            is_income = tx["amount"] >= 0

    db_id = DB_IDS["income"] if is_income else DB_IDS["expenses"]

    # Determine account relation
    if force_account_id:
        account_relation_id = force_account_id
    else:
        account_relation_id = ACCOUNT_IDS.get("PRIMARY", "")

    # Convert timestamp to date
    date_obj = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    date_str = date_obj.date().isoformat()

    # Category determination
    category_name = categorize_transaction(description, is_income=is_income)
    category_ids = INCOME_CATEGORY_IDS if is_income else EXPENSE_CATEGORY_IDS
    category_relation_id = category_ids.get(category_name, category_ids.get("Other", ""))

    # Convert to base currency
    if override_amount is not None:
        converted_amount = float(override_amount)
    else:
        try:
            converted_amount = converter.convert_to_base(Decimal(str(raw_amount)), currency, date_str)
        except Exception as e:
            print(f"[{tx_id}] Currency conversion failed: {e}, using raw amount")
            converted_amount = float(raw_amount)

    if isinstance(converted_amount, Decimal):
        converted_amount = float(converted_amount)

    # Build Notion properties
    properties = {
        "Name": {"title": [{"text": {"content": description}}]},
        "Amount": {"number": converted_amount},
        "Date": {"date": {"start": date_str}},
    }

    if account_relation_id:
        properties["Account"] = {"relation": [{"id": account_relation_id}]}

    if category_relation_id:
        properties["Category"] = {"relation": [{"id": category_relation_id}]}

    # Add expense-specific fields (customize these based on your Notion setup)
    if not is_income:
        try:
            properties["Month"] = {"select": {"name": date_obj.strftime("%B")}}
            properties["Year"] = {"select": {"name": str(date_obj.year)}}
        except Exception as e:
            print(f"[{tx_id}] Error setting expense fields: {e}")

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
    }

    db_type = "Income" if is_income else "Expense"

    def make_notion_request():
        return requests.post("https://api.notion.com/v1/pages", headers=HEADERS, json=payload, timeout=30)

    try:
        response = retry_with_backoff(make_notion_request)

        if response.status_code == 200:
            print(f"[{tx_id}] Added '{description}' to {db_type} | {converted_amount} {BASE_CURRENCY} | {category_name}")
            return True
        elif is_temporary_error(response.status_code):
            error_info = {
                "status_code": response.status_code,
                "error_type": "temporary",
                "response_text": response.text[:500],
                "attempt_time": datetime.now().isoformat(),
            }
            print(f"[{tx_id}] Temporary error ({response.status_code}), will retry later")
            log_failed_transaction(tx, account, is_income, error_info)
            return False
        elif is_permanent_error(response.status_code):
            error_info = {
                "status_code": response.status_code,
                "error_type": "permanent",
                "response_text": response.text[:500],
                "attempt_time": datetime.now().isoformat(),
            }
            print(f"[{tx_id}] Permanent error ({response.status_code}), manual review needed")
            log_failed_transaction(tx, account, is_income, error_info)
            return False
        else:
            error_info = {
                "status_code": response.status_code,
                "error_type": "unknown",
                "response_text": response.text[:500],
                "attempt_time": datetime.now().isoformat(),
            }
            print(f"[{tx_id}] Unknown error ({response.status_code})")
            log_failed_transaction(tx, account, is_income, error_info)
            return False

    except requests.exceptions.Timeout:
        error_info = {
            "error_type": "timeout",
            "message": "Request timed out after retries",
            "attempt_time": datetime.now().isoformat(),
        }
        print(f"[{tx_id}] Request timed out after {MAX_RETRIES} attempts")
        log_failed_transaction(tx, account, is_income, error_info)
        return False

    except requests.exceptions.ConnectionError:
        error_info = {
            "error_type": "connection",
            "message": "Connection failed after retries",
            "attempt_time": datetime.now().isoformat(),
        }
        print(f"[{tx_id}] Connection failed after {MAX_RETRIES} attempts")
        log_failed_transaction(tx, account, is_income, error_info)
        return False

    except Exception as e:
        error_info = {
            "error_type": "exception",
            "message": str(e),
            "attempt_time": datetime.now().isoformat(),
        }
        print(f"[{tx_id}] Unexpected error: {e}")
        log_failed_transaction(tx, account, is_income, error_info)
        return False


def retry_failed_transactions():
    """Retry all failed transactions from the queue."""
    if not os.path.exists(FAILED_TRANSACTIONS_FILE):
        print("No failed transactions file found")
        return

    try:
        with open(FAILED_TRANSACTIONS_FILE, "r") as f:
            failed_txs = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading failed transactions file: {e}")
        return

    if not failed_txs:
        print("No failed transactions to retry")
        return

    print(f"Found {len(failed_txs)} failed transactions to retry")

    successful_retries = []
    still_failed = []

    for failed_tx in failed_txs:
        if failed_tx.get("error", {}).get("error_type") == "permanent":
            still_failed.append(failed_tx)
            continue

        tx = failed_tx["transaction"]
        account = failed_tx["account"]
        is_income = failed_tx["is_income"]

        print(f"Retrying transaction {tx['transaction_id'][:12]}...")

        success = post_transaction_to_notion_internal(tx, account, is_income)

        if success:
            successful_retries.append(failed_tx)
        else:
            failed_tx["retry_count"] = failed_tx.get("retry_count", 0) + 1
            failed_tx["last_retry"] = datetime.now().isoformat()
            still_failed.append(failed_tx)

    try:
        with open(FAILED_TRANSACTIONS_FILE, "w") as f:
            json.dump(still_failed, f, indent=2)

        print(f"Retry summary: {len(successful_retries)} succeeded, {len(still_failed)} still failed")

    except IOError as e:
        print(f"Error updating failed transactions file: {e}")


def post_transaction_to_notion(tx, account, is_income=None, force_account_id=None, override_amount=None):
    """
    Main function to post transactions to Notion with error handling.

    Args:
        tx: Transaction data
        account: Account data
        is_income: Whether this is an income transaction
        force_account_id: Notion account ID to use
        override_amount: Optional amount to use instead of automatic conversion

    Returns:
        True if successful, False if failed
    """
    try:
        return post_transaction_to_notion_internal(
            tx, account, is_income, force_account_id=force_account_id, override_amount=override_amount
        )
    except Exception as e:
        tx_id = tx.get("transaction_id", "unknown")[:12]
        print(f"[{tx_id}] Critical error in transaction posting: {e}")

        error_info = {
            "error_type": "critical",
            "message": str(e),
            "attempt_time": datetime.now().isoformat(),
        }
        log_failed_transaction(tx, account, is_income, error_info)
        return False
