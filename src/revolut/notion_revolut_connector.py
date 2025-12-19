import os
import json
import time
import urllib.parse
import webbrowser
import requests
from dotenv import load_dotenv
from src.notion.notion_utils import post_transaction_to_notion, check_and_update_rent_payment
from datetime import datetime, timezone

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) 
TOKENS_FILE = os.path.join(BASE_DIR, "data", "tokens.json")
TX_CACHE_FILE = os.path.join(BASE_DIR, "data", "logged_transactions.json")
# Cutoff timestamp for ignoring old transactions
CUTOFF_TIMESTAMP = datetime(2025, 8, 17, 14, 0, 0, tzinfo=timezone.utc)
REDIRECT_URI = os.getenv("TL_REDIRECT_URI")
CLIENT_ID = os.getenv("TL_CLIENT_ID")
CLIENT_SECRET = os.getenv("TL_CLIENT_SECRET")
AUTH_BASE = os.getenv("TL_AUTH_BASE", "https://auth.truelayer.com")
API_BASE = os.getenv("TL_API_BASE", "https://api.truelayer.com")

SCOPES = ["info", "accounts", "balance", "transactions", "offline_access"]

def load_logged_transactions():
    if os.path.exists(TX_CACHE_FILE):
        with open(TX_CACHE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_logged_transactions(tx_ids):
    with open(TX_CACHE_FILE, "w") as f:
        json.dump(list(tx_ids), f)

# Global variable to store auth code when running as standalone script
auth_code_storage = {"code": None}

def get_auth_code():
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "scope": " ".join(SCOPES),
        "redirect_uri": REDIRECT_URI,
        "providers": "pl-ob-revolut",
        "enable_mock": "false",
        "nonce": str(time.time()),
        "state": "xyz",
    }
    url = AUTH_BASE + "?" + urllib.parse.urlencode(params)
    print("🔗 Opening browser to authorize Revolut...")
    print(f"Please visit this URL if the browser doesn't open automatically: {url}")
    print("After authorization, the authorization code should be captured by your server.")
    print("If running standalone, please copy the 'code' parameter from the callback URL manually.")
    
    # Try to import from app to use shared storage, fallback to local storage
    try:
        from app import auth_code_storage as shared_storage
        storage = shared_storage
    except ImportError:
        storage = auth_code_storage
    
    webbrowser.open(url)
    
    # Wait for the code to be set by the callback
    timeout = 300  # 5 minutes timeout
    start_time = time.time()
    while storage["code"] is None:
        time.sleep(1)
        if time.time() - start_time > timeout:
            raise Exception("OAuth authorization timed out. Please try again.")
    
    code = storage["code"]
    storage["code"] = None  # Clear the code after use
    return code

def exchange_token(code):
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code": code,
    }
    r = requests.post(f"{AUTH_BASE}/connect/token", data=data)
    r.raise_for_status()
    token_data = r.json()
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f)
    return token_data["access_token"]

def refresh_access_token(refresh_token):
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    r = requests.post(f"{AUTH_BASE}/connect/token", data=data)
    r.raise_for_status()
    token_data = r.json()
    with open(TOKENS_FILE, "w") as f:
        json.dump(token_data, f)
    return token_data["access_token"]

def get_accounts(token):
    r = requests.get(API_BASE + "/data/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["results"]

def get_transactions(token, account_id):
    r = requests.get(API_BASE + f"/data/v1/accounts/{account_id}/transactions", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["results"]

def is_exchange_transaction(tx):
    return "exchanged to" in tx["description"].lower() or "exchanged from" in tx["description"].lower()


def main():
    token = None
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE) as f:
            token_data = json.load(f)
        refresh_token = token_data.get("refresh_token")
        try:
            token = refresh_access_token(refresh_token)
        except Exception as e:
            print("⚠️ Refresh failed, falling back to full auth:", e)

    if not token:
        code = get_auth_code()
        token = exchange_token(code)

    print("Authorized and got access token")

    logged_tx_ids = load_logged_transactions()
    new_logged_tx_ids = set()
    
    # Track sync results
    successful_transactions = 0
    failed_transactions = 0
    skipped_transactions = 0
    
    accounts = get_accounts(token)
    print(f"Found {len(accounts)} Revolut accounts")

    # Collect all transactions for rent payment detection
    all_transactions = []

    for account in accounts:
        print(f"\n📒 {account['display_name']} ({account['account_type']}) — {account['currency']}")
        txns = get_transactions(token, account["account_id"])
        print(f"💳 {len(txns)} transactions:")
        
        # Collect transactions for rent payment detection
        all_transactions.extend(txns)

        for tx in txns[:10]:
            tx_id = tx["transaction_id"]
            if tx_id in logged_tx_ids:
                tx_id_short = tx_id[:12]
                print(f"⏭️  [{tx_id_short}] Already logged {tx['description']} — skipping")
                skipped_transactions += 1
                continue

            tx_time = datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))
            if tx_time <= CUTOFF_TIMESTAMP:
                skipped_transactions += 1
                continue

            tx_id_short = tx["transaction_id"][:12]
            print(f"→ [{tx_id_short}] Logging {tx['description']} | {tx['amount']} {tx['currency']}")
            
            # Process each transaction as-is (no special exchange handling)
            is_income = tx["amount"] >= 0
            tx_type = "income" if is_income else "expense"
            
            if is_exchange_transaction(tx):
                print(f"  🔄 Exchange {tx_type} transaction: {tx['amount']} {tx['currency']}")
            else:
                print(f"  📝 Regular {tx_type} transaction")
            
            success = post_transaction_to_notion(tx, account, is_income=is_income)
            if success:
                successful_transactions += 1
            else:
                failed_transactions += 1
            
            new_logged_tx_ids.add(tx_id)

    # Save updated list
    all_logged_tx_ids = logged_tx_ids.union(new_logged_tx_ids)
    save_logged_transactions(all_logged_tx_ids)
    
    # Check for rent payments and update Notion Recurring database
    print("\n🏠 Checking for rent payments...")
    rent_result = check_and_update_rent_payment(all_transactions)
    print(f"  ✅ Matched: {rent_result['matched_payments']}")
    print(f"  📝 Updated pages: {rent_result['updated_pages']}")
    if rent_result['errors'] > 0:
        print(f"  ⚠️  Errors: {rent_result['errors']}")
    
    # Print comprehensive sync summary
    total_processed = successful_transactions + failed_transactions
    print("\n📊 Sync Summary:")
    print(f"  ✅ Successful: {successful_transactions}")
    print(f"  ❌ Failed: {failed_transactions}")
    print(f"  ⏭️  Skipped: {skipped_transactions}")
    print(f"  📝 Total Processed: {total_processed}")
    
    if failed_transactions > 0:
        print("  💡 Run POST /retry-failed to retry failed transactions")
    
    return {
        "successful": successful_transactions,
        "failed": failed_transactions,
        "skipped": skipped_transactions,
        "total_processed": total_processed,
        "rent_payments": rent_result
    }

if __name__ == "__main__":
    main()