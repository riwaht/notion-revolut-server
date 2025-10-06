# notion_utils.py

import json
import os
import requests
import time
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
    "Travel": "12e364a1215e8083a389c6dbf7ef8dac",
    "Free Time": "12e364a1215e818e98d0e8abcdadf58c",
    "Necessities": "156364a1215e80dcbebddd89ba57b4ab",
    "Others": "12e364a1215e81999522f7421e1947f0",
    "Transaction": "156364a1215e80e380e6c328a7e5d2e4"
}

INCOME_CATEGORY_IDS = {
    "Salary": "12e364a1215e81e9814ce231403b1207",
    "Parents" : "12e364a1215e81ba8da4c0100297cdda",
    "Repaid": "136364a1215e80fab733eb38739b9a1d",
    "Transaction": "25a364a1215e800fad15f09941aa5e19",
    "Others": "12e364a1215e81acbb77f4e668d148d2",
}

ACCOUNT_IDS = {
    "PLN": "24e364a1215e80faba4ec73df82d4aac",
    "INTERNATIONAL": "245364a1215e8082ba70c1831590fc89",  # Card International (USD/EUR/other currencies)
    "DEFAULT": "12e364a1215e808daed4e333e7f3efd1",
}

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1  # seconds
FAILED_TRANSACTIONS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "failed_transactions.json")

def is_temporary_error(status_code: int) -> bool:
    """Check if an HTTP status code indicates a temporary error that should be retried"""
    return status_code in [429, 500, 502, 503, 504]


def is_permanent_error(status_code: int) -> bool:
    """Check if an HTTP status code indicates a permanent error that should not be retried"""
    return status_code in [400, 401, 403, 404, 422]


def log_failed_transaction(tx, account, is_income, error_info):
    """Log a failed transaction to file for later retry"""
    try:
        os.makedirs(os.path.dirname(FAILED_TRANSACTIONS_FILE), exist_ok=True)
        
        failed_tx = {
            "transaction": tx,
            "account": account,
            "is_income": is_income,
            "error": error_info,
            "timestamp": datetime.now().isoformat(),
            "retry_count": 0
        }
        
        # Load existing failed transactions
        failed_txs = []
        if os.path.exists(FAILED_TRANSACTIONS_FILE):
            try:
                with open(FAILED_TRANSACTIONS_FILE, 'r') as f:
                    failed_txs = json.load(f)
            except (json.JSONDecodeError, IOError):
                failed_txs = []
        
        # Add new failed transaction
        failed_txs.append(failed_tx)
        
        # Save back to file
        with open(FAILED_TRANSACTIONS_FILE, 'w') as f:
            json.dump(failed_txs, f, indent=2)
            
        print(f"💾 Logged failed transaction {tx['transaction_id'][:12]} to retry queue")
        
    except Exception as e:
        print(f"⚠️  Failed to log failed transaction: {e}")


def retry_with_backoff(func, *args, **kwargs):
    """Execute a function with exponential backoff retry logic"""
    last_exception = None
    
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.Timeout as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"🔄 Timeout error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            else:
                print(f"❌ Max retries exceeded for timeout error: {e}")
                break
        except requests.exceptions.ConnectionError as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY * (2 ** attempt)
                print(f"🔄 Connection error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
            else:
                print(f"❌ Max retries exceeded for connection error: {e}")
                break
        except requests.exceptions.RequestException as e:
            last_exception = e
            print(f"❌ Request exception (not retryable): {e}")
            break
        except Exception as e:
            last_exception = e
            print(f"❌ Unexpected error: {e}")
            break
    
    # If we get here, all retries failed
    raise last_exception


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


def post_transaction_to_notion_internal(tx, account, is_income=None, force_account=None, override_usd_amount=None):
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

    # Convert to USD for consistent tracking with fallback
    if override_usd_amount is not None:
        # Use the provided USD amount (for exchange transactions to maintain balance)
        converted_amount = float(override_usd_amount)
        print(f"[INFO] Using override USD amount: {converted_amount}")
    else:
        # Normal currency conversion
        try:
            converted_amount = converter.convert_to_usd(Decimal(str(raw_amount)), currency, date_str)
        except Exception as e:
            print(f"⚠️  [{tx_id}] Currency conversion failed: {e}, using raw amount")
            converted_amount = float(raw_amount)  # Fallback to raw amount

    # Build Notion properties with graceful degradation
    properties = {
        "Name": {"title": [{"text": {"content": description}}]},
        "Amount": {"number": converted_amount},
        "Date": {"date": {"start": date_str}},
    }
    
    # Add optional properties with fallbacks
    if account_relation_id:
        properties["Account"] = {"relation": [{"id": account_relation_id}]}
    else:
        print(f"⚠️  [{tx_id}] No account relation ID found, skipping account field")
    
    if category_relation_id:
        properties["Category"] = {"relation": [{"id": category_relation_id}]}
    else:
        print(f"⚠️  [{tx_id}] No category relation ID found for '{category_name}', skipping category field")

    # Add expense-specific fields with error handling
    if not is_income:
        try:
            properties["Month"] = {"select": {"name": date_obj.strftime("%B")}}
            properties["To be Repaid?"] = {"select": {"name": "Not to be Repaid"}}
            properties["Year"] = {"select": {"name": str(date_obj.year)}}
        except Exception as e:
            print(f"⚠️  [{tx_id}] Error setting expense fields: {e}, continuing without them")

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
    else:
        account_name = "DEFAULT"
    
    def make_notion_request():
        """Inner function to make the actual API request with timeout"""
        return requests.post(
            "https://api.notion.com/v1/pages", 
            headers=HEADERS, 
            json=payload, 
            timeout=30  # 30 second timeout
        )

    try:
        # Use retry mechanism for the API call
        response = retry_with_backoff(make_notion_request)
        
        if response.status_code == 200:
            print(f"✅ [{tx_id}] Added '{description}' to {db_type} DB | ${converted_amount} USD | {category_name} | {account_name} account")
            return True
        elif is_temporary_error(response.status_code):
            # Rate limiting or temporary server error
            error_info = {
                "status_code": response.status_code,
                "error_type": "temporary",
                "response_text": response.text[:500],  # Limit error text length
                "attempt_time": datetime.now().isoformat()
            }
            print(f"⏳ [{tx_id}] Temporary error ({response.status_code}), will retry later")
            log_failed_transaction(tx, account, is_income, error_info)
            return False
        elif is_permanent_error(response.status_code):
            # Client error - don't retry, but log for manual review
            error_info = {
                "status_code": response.status_code,
                "error_type": "permanent", 
                "response_text": response.text[:500],
                "attempt_time": datetime.now().isoformat()
            }
            print(f"🚫 [{tx_id}] Permanent error ({response.status_code}), manual review needed")
            print(f"Error details: {response.text[:200]}...")
            log_failed_transaction(tx, account, is_income, error_info)
            return False
        else:
            # Unknown error
            error_info = {
                "status_code": response.status_code,
                "error_type": "unknown",
                "response_text": response.text[:500],
                "attempt_time": datetime.now().isoformat()
            }
            print(f"❓ [{tx_id}] Unknown error ({response.status_code}), logging for review")
            log_failed_transaction(tx, account, is_income, error_info)
            return False
            
    except requests.exceptions.Timeout:
        error_info = {
            "error_type": "timeout",
            "message": "Request timed out after retries",
            "attempt_time": datetime.now().isoformat()
        }
        print(f"⏰ [{tx_id}] Request timed out after {MAX_RETRIES} attempts")
        log_failed_transaction(tx, account, is_income, error_info)
        return False
        
    except requests.exceptions.ConnectionError:
        error_info = {
            "error_type": "connection",
            "message": "Connection failed after retries",
            "attempt_time": datetime.now().isoformat()
        }
        print(f"🌐 [{tx_id}] Connection failed after {MAX_RETRIES} attempts")
        log_failed_transaction(tx, account, is_income, error_info)
        return False
        
    except Exception as e:
        error_info = {
            "error_type": "exception",
            "message": str(e),
            "attempt_time": datetime.now().isoformat()
        }
        print(f"💥 [{tx_id}] Unexpected error: {e}")
        log_failed_transaction(tx, account, is_income, error_info)
        return False


def retry_failed_transactions():
    """Retry all failed transactions from the failed transactions file"""
    if not os.path.exists(FAILED_TRANSACTIONS_FILE):
        print("📁 No failed transactions file found")
        return
    
    try:
        with open(FAILED_TRANSACTIONS_FILE, 'r') as f:
            failed_txs = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Error reading failed transactions file: {e}")
        return
    
    if not failed_txs:
        print("📁 No failed transactions to retry")
        return
    
    print(f"🔄 Found {len(failed_txs)} failed transactions to retry")
    
    successful_retries = []
    still_failed = []
    
    for failed_tx in failed_txs:
        # Skip permanent errors unless they're older than a day (for manual review)
        if failed_tx.get("error", {}).get("error_type") == "permanent":
            still_failed.append(failed_tx)
            continue
            
        tx = failed_tx["transaction"]
        account = failed_tx["account"] 
        is_income = failed_tx["is_income"]
        
        print(f"🔁 Retrying transaction {tx['transaction_id'][:12]}...")
        
        success = post_transaction_to_notion_internal(tx, account, is_income)
        
        if success:
            successful_retries.append(failed_tx)
            print(f"✅ Successfully retried {tx['transaction_id'][:12]}")
        else:
            # Update retry count
            failed_tx["retry_count"] = failed_tx.get("retry_count", 0) + 1
            failed_tx["last_retry"] = datetime.now().isoformat()
            still_failed.append(failed_tx)
    
    # Update the failed transactions file with only the ones that still failed
    try:
        with open(FAILED_TRANSACTIONS_FILE, 'w') as f:
            json.dump(still_failed, f, indent=2)
        
        print(f"📊 Retry summary: {len(successful_retries)} succeeded, {len(still_failed)} still failed")
        
    except IOError as e:
        print(f"⚠️  Error updating failed transactions file: {e}")


def post_transaction_to_notion(tx, account, is_income=None, override_usd_amount=None):
    """
    Main function to post transactions to Notion with graceful error handling.
    Returns True if successful, False if failed.
    
    Args:
        tx: Transaction data
        account: Account data
        is_income: Whether this is an income transaction
        override_usd_amount: Optional USD amount to use instead of automatic conversion
    """
    try:
        return post_transaction_to_notion_internal(tx, account, is_income, override_usd_amount=override_usd_amount)
    except Exception as e:
        tx_id = tx.get("transaction_id", "unknown")[:12]
        print(f"💥 [{tx_id}] Critical error in transaction posting: {e}")
        
        # Log the critical failure
        error_info = {
            "error_type": "critical",
            "message": str(e),
            "attempt_time": datetime.now().isoformat()
        }
        log_failed_transaction(tx, account, is_income, error_info)
        return False
