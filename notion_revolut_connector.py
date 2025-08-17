
import os
import json
import time
import urllib.parse
import http.server
import socketserver
import webbrowser
import requests
from dotenv import load_dotenv
load_dotenv()

# Load your TrueLayer credentials from env vars
CLIENT_ID = os.getenv("TL_CLIENT_ID")
CLIENT_SECRET = os.getenv("TL_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TL_REDIRECT_URI")
AUTH_BASE = os.getenv("TL_AUTH_BASE")
API_BASE = os.getenv("TL_API_BASE")

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

    # Save the tokens
    with open("tokens.json", "w") as f:
        json.dump(token_data, f, indent=2)

    return token_data["access_token"]

def refresh_access_token(refresh_token):
    data = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
    }
    r = requests.post(f"{AUTH_BASE}/connect/token", data=data)
    print("♻️ Refresh token response:", r.status_code)
    print("Body:", r.text)
    r.raise_for_status()
    token_data = r.json()

    # Overwrite old tokens
    with open("tokens.json", "w") as f:
        json.dump(token_data, f, indent=2)

    return token_data["access_token"]

def get_accounts(token):
    r = requests.get(API_BASE + "/data/v1/accounts", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["results"]

def get_transactions(token, account_id):
    r = requests.get(API_BASE + f"/data/v1/accounts/{account_id}/transactions", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["results"]

def main():
    token = None

    # Try loading saved token first
    if os.path.exists("tokens.json"):
        with open("tokens.json") as f:
            token_data = json.load(f)
        refresh_token = token_data.get("refresh_token")
        try:
            token = refresh_access_token(refresh_token)
        except Exception as e:
            print("⚠️ Refresh failed, falling back to full auth:", e)

    # Fallback to full auth if needed
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
        for tx in txns[:5]:
            print(f"- {tx['timestamp']} | {tx['description']} | {tx['amount']} {tx['currency']}")

if __name__ == "__main__":
    main()
