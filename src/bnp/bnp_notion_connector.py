import os
import json
import time
import requests
from dotenv import load_dotenv
from src.notion.notion_utils import post_transaction_to_notion
from datetime import datetime, timezone

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__))) 
BNP_TOKENS_FILE = os.path.join(BASE_DIR, "data", "bnp_tokens.json")
BNP_TX_CACHE_FILE = os.path.join(BASE_DIR, "data", "bnp_logged_transactions.json")

# Cutoff timestamp for ignoring old transactions
CUTOFF_TIMESTAMP = datetime(2025, 8, 17, 14, 0, 0, tzinfo=timezone.utc)

# BNP Paribas API configuration
BNP_CLIENT_ID = os.getenv("BNP_CLIENT_ID")
BNP_CLIENT_SECRET = os.getenv("BNP_CLIENT_SECRET")
BNP_API_BASE = os.getenv("BNP_API_BASE", "https://apistore.bnpparibas.com")
BNP_AUTH_BASE = os.getenv("BNP_AUTH_BASE", "https://auth.bnpparibas.com")
BNP_REDIRECT_URI = os.getenv("BNP_REDIRECT_URI")

# Store auth code when running as standalone script
bnp_auth_code_storage = {"code": None}

def load_bnp_logged_transactions():
    """Load previously logged BNP transaction IDs to avoid duplicates"""
    if os.path.exists(BNP_TX_CACHE_FILE):
        with open(BNP_TX_CACHE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_bnp_logged_transactions(tx_ids):
    """Save logged transaction IDs to file"""
    with open(BNP_TX_CACHE_FILE, "w") as f:
        json.dump(list(tx_ids), f)

def get_bnp_auth_code():
    """Get OAuth authorization code for BNP Paribas API"""
    # This will need to be adapted based on BNP Paribas OAuth flow
    # For now, creating a placeholder structure similar to TrueLayer
    
    # The actual parameters will depend on BNP Paribas API documentation
    params = {
        "response_type": "code",
        "client_id": BNP_CLIENT_ID,
        "redirect_uri": BNP_REDIRECT_URI,
        "scope": "account:read transaction:read",  # Placeholder scope
        "state": "bnp_state_" + str(time.time()),
    }
    
    # Construct authorization URL (structure may vary)
    auth_url = f"{BNP_AUTH_BASE}/oauth/authorize"
    url_params = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{auth_url}?{url_params}"
    
    print("🔗 Opening browser to authorize BNP Paribas...")
    print(f"Please visit this URL: {url}")
    print("After authorization, copy the 'code' parameter from the callback URL.")
    
    # Try to import from app to use shared storage
    try:
        from app import bnp_auth_code_storage as shared_storage
        storage = shared_storage
    except ImportError:
        storage = bnp_auth_code_storage
    
    # For now, manual input - this can be improved with web server integration
    code = input("Enter the authorization code: ").strip()
    return code

def exchange_bnp_token(code):
    """Exchange authorization code for access token"""
    data = {
        "grant_type": "authorization_code",
        "client_id": BNP_CLIENT_ID,
        "client_secret": BNP_CLIENT_SECRET,
        "redirect_uri": BNP_REDIRECT_URI,
        "code": code,
    }
    
    # This endpoint structure is placeholder - adapt based on actual BNP API
    token_url = f"{BNP_AUTH_BASE}/oauth/token"
    r = requests.post(token_url, data=data)
    r.raise_for_status()
    
    token_data = r.json()
    with open(BNP_TOKENS_FILE, "w") as f:
        json.dump(token_data, f)
    return token_data["access_token"]

def refresh_bnp_access_token(refresh_token):
    """Refresh BNP access token using refresh token"""
    data = {
        "grant_type": "refresh_token",
        "client_id": BNP_CLIENT_ID,
        "client_secret": BNP_CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    
    token_url = f"{BNP_AUTH_BASE}/oauth/token"
    r = requests.post(token_url, data=data)
    r.raise_for_status()
    
    token_data = r.json()
    with open(BNP_TOKENS_FILE, "w") as f:
        json.dump(token_data, f)
    return token_data["access_token"]

def get_bnp_accounts(token):
    """Get BNP Paribas accounts"""
    headers = {"Authorization": f"Bearer {token}"}
    # This endpoint is placeholder - adapt based on actual BNP API
    r = requests.get(f"{BNP_API_BASE}/accounts", headers=headers)
    r.raise_for_status()
    return r.json().get("accounts", [])

def get_bnp_transactions(token, account_id):
    """Get transactions for a specific BNP account"""
    headers = {"Authorization": f"Bearer {token}"}
    # This endpoint is placeholder - adapt based on actual BNP API
    r = requests.get(f"{BNP_API_BASE}/accounts/{account_id}/transactions", headers=headers)
    r.raise_for_status()
    return r.json().get("transactions", [])

def normalize_bnp_transaction(tx):
    """Normalize BNP transaction format to match expected structure"""
    # This function will need to be adapted based on actual BNP API response format
    # For now, creating a structure that matches what notion_utils expects
    
    return {
        "transaction_id": tx.get("id", tx.get("transactionId")),
        "amount": float(tx.get("amount", {}).get("value", 0)),
        "currency": tx.get("amount", {}).get("currency", "EUR"),
        "description": tx.get("description", tx.get("reference", "BNP Transaction")),
        "timestamp": tx.get("bookingDate", tx.get("valueDate", datetime.now().isoformat())),
    }

def detect_transaction_source_destination(tx):
    """Detect if transaction is coming from/going to BNP Paribas savings account"""
    description = tx.get("description", "").lower()
    
    # Keywords that indicate money going TO savings (BNP Paribas)
    to_savings_keywords = [
        "transfer to savings", "to bnp", "savings transfer", 
        "auto transfer to savings", "deposit to savings"
    ]
    
    # Keywords that indicate money coming FROM savings (BNP Paribas)
    from_savings_keywords = [
        "transfer from savings", "from bnp", "savings withdrawal",
        "from savings account", "withdrawal from savings"
    ]
    
    if any(keyword in description for keyword in to_savings_keywords):
        return "to_savings"
    elif any(keyword in description for keyword in from_savings_keywords):
        return "from_savings" 
    else:
        return "internal_savings"  # Transaction within BNP Paribas savings account

def main():
    """Main function to sync BNP Paribas transactions with Notion"""
    print("🏦 Starting BNP Paribas sync...")
    
    token = None
    if os.path.exists(BNP_TOKENS_FILE):
        with open(BNP_TOKENS_FILE) as f:
            token_data = json.load(f)
        refresh_token = token_data.get("refresh_token")
        try:
            token = refresh_bnp_access_token(refresh_token)
        except Exception as e:
            print("⚠️ BNP token refresh failed, falling back to full auth:", e)

    if not token:
        code = get_bnp_auth_code()
        token = exchange_bnp_token(code)

    print("✅ BNP Paribas authorized and got access token")

    logged_tx_ids = load_bnp_logged_transactions()
    new_logged_tx_ids = set()

    accounts = get_bnp_accounts(token)
    print(f"Found {len(accounts)} BNP Paribas accounts")

    for account in accounts:
        # Focus only on savings account - adapt the account identification logic
        account_name = account.get("name", account.get("displayName", ""))
        account_type = account.get("type", account.get("accountType", ""))
        
        print(f"\n💰 {account_name} ({account_type}) — {account.get('currency', 'EUR')}")
        
        try:
            txns = get_bnp_transactions(token, account.get("id", account.get("accountId")))
            print(f"💳 {len(txns)} transactions found")

            for tx in txns[:10]:  # Process latest 10 transactions
                normalized_tx = normalize_bnp_transaction(tx)
                tx_id = normalized_tx["transaction_id"]
                
                if tx_id in logged_tx_ids:
                    tx_id_short = tx_id[:12]
                    print(f"⏭️  [{tx_id_short}] Already logged {normalized_tx['description']} — skipping")
                    continue

                tx_time = datetime.fromisoformat(normalized_tx["timestamp"].replace("Z", "+00:00"))
                if tx_time <= CUTOFF_TIMESTAMP:
                    continue

                tx_id_short = tx_id[:12]
                source_dest = detect_transaction_source_destination(normalized_tx)
                
                print(f"→ [{tx_id_short}] Logging BNP {normalized_tx['description']} | {normalized_tx['amount']} {normalized_tx['currency']} | {source_dest}")
                
                # Post transaction to Notion - it will be marked as savings account
                is_income = normalized_tx["amount"] >= 0
                tx_type = "income" if is_income else "expense"
                print(f"  📝 BNP Savings {tx_type} transaction")
                
                # Create a BNP account object similar to Revolut format
                bnp_account = {
                    "display_name": "BNP Paribas Savings",
                    "account_type": "savings", 
                    "currency": normalized_tx["currency"]
                }
                
                post_transaction_to_notion(normalized_tx, bnp_account, is_income=is_income)
                new_logged_tx_ids.add(tx_id)

        except Exception as e:
            print(f"❌ Error processing account {account_name}: {e}")
            continue

    # Save updated list
    all_logged_tx_ids = logged_tx_ids.union(new_logged_tx_ids)
    save_bnp_logged_transactions(all_logged_tx_ids)
    print("✅ BNP Paribas sync completed")

if __name__ == "__main__":
    main()
