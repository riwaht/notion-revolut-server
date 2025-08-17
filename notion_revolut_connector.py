import os
import json
import time
import urllib.parse
import http.server
import socketserver
import webbrowser
import requests
from dotenv import load_dotenv
from notion_utils import post_transaction_to_notion
from datetime import datetime, timezone

load_dotenv()

REDIRECT_URI = os.getenv("TL_REDIRECT_URI")
CLIENT_ID = os.getenv("TL_CLIENT_ID")
CLIENT_SECRET = os.getenv("TL_CLIENT_SECRET")
AUTH_BASE = os.getenv("TL_AUTH_BASE", "https://auth.truelayer.com")
API_BASE = os.getenv("TL_API_BASE", "https://api.truelayer.com")

SCOPES = ["info", "accounts", "balance", "transactions", "offline_access"]

class Handler(http.server.SimpleHTTPRequestHandler):
    code = None
    def do_GET(self):
        if self.path.startswith("/callback"):
            qs = urllib.parse.urlparse(self.path).query
            Handler.code = urllib.parse.parse_qs(qs).get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"You can close this tab.")
        else:
            self.send_response(404)
            self.end_headers()

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
    with socketserver.TCPServer(("", 3000), Handler) as httpd:
        webbrowser.open(url)
        while Handler.code is None:
            httpd.handle_request()
    return Handler.code

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

    with open("tokens.json", "w") as f:
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
    with open("tokens.json", "w") as f:
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
    CUTOFF_TIMESTAMP = datetime(2025, 8, 17, 14, 0, 0, tzinfo=timezone.utc)

    if os.path.exists("tokens.json"):
        with open("tokens.json") as f:
            token_data = json.load(f)
        refresh_token = token_data.get("refresh_token")
        try:
            token = refresh_access_token(refresh_token)
        except Exception as e:
            print("⚠️ Refresh failed, falling back to full auth:", e)

    if not token:
        code = get_auth_code()
        token = exchange_token(code)

    print("✅ Authorized and got access token")

    accounts = get_accounts(token)
    print(f"✅ Found {len(accounts)} Revolut accounts")

    for account in accounts:
        print(f"\n📒 {account['display_name']} ({account['account_type']}) — {account['currency']}")
        txns = get_transactions(token, account["account_id"])
        print(f"💳 {len(txns)} transactions:")

        for tx in txns[:10]:
            tx_time = datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))
            if tx_time <= CUTOFF_TIMESTAMP:
                continue  # Skip this transaction

            print(f"- {tx['timestamp']} | {tx['description']} | {tx['amount']} {tx['currency']}")

            if is_exchange_transaction(tx):
                if tx['amount'] > 0:
                    post_transaction_to_notion(tx, account, is_income=True)
                else:
                    post_transaction_to_notion(tx, account, is_income=False)
            elif tx['amount'] < 0:
                post_transaction_to_notion(tx, account, is_income=False)
            else:
                post_transaction_to_notion(tx, account, is_income=True)

if __name__ == "__main__":
    main()