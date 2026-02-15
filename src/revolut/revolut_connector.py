"""
Revolut connector using TrueLayer API for OAuth and transaction fetching.
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOKENS_FILE = os.path.join(BASE_DIR, "data", "tokens.json")
TX_CACHE_FILE = os.path.join(BASE_DIR, "data", "logged_transactions.json")


class RevolutConnector:
    """Revolut connector via TrueLayer API."""

    def __init__(self):
        self.client_id = os.getenv("TL_CLIENT_ID")
        self.client_secret = os.getenv("TL_CLIENT_SECRET")
        self.redirect_uri = os.getenv("TL_REDIRECT_URI")
        self.provider = os.getenv("TL_PROVIDER", "uk-ob-revolut")
        self.auth_base = os.getenv("TL_AUTH_BASE", "https://auth.truelayer.com")
        self.api_base = os.getenv("TL_API_BASE", "https://api.truelayer.com")
        self.scopes = ["info", "accounts", "balance", "transactions", "offline_access"]
        self.cutoff_timestamp = self._get_cutoff_timestamp()

        if not all([self.client_id, self.client_secret, self.redirect_uri]):
            raise ValueError("Missing TrueLayer credentials in environment variables")

    def _get_cutoff_timestamp(self) -> datetime:
        """Get cutoff timestamp from environment or default."""
        cutoff_str = os.getenv("CUTOFF_DATE", "2024-01-01")
        try:
            cutoff = datetime.strptime(cutoff_str, "%Y-%m-%d")
            return cutoff.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime(2024, 1, 1, tzinfo=timezone.utc)

    def get_auth_url(self, state: str = "xyz") -> str:
        """Generate OAuth authorization URL."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "scope": " ".join(self.scopes),
            "redirect_uri": self.redirect_uri,
            "providers": self.provider,
            "enable_mock": "false",
            "nonce": str(time.time()),
            "state": state,
        }
        return f"{self.auth_base}?{urlencode(params)}"

    def exchange_token(self, code: str) -> str:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": code,
        }
        response = requests.post(f"{self.auth_base}/connect/token", data=data)
        response.raise_for_status()
        token_data = response.json()

        os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
        with open(TOKENS_FILE, "w") as f:
            json.dump(token_data, f)

        return token_data["access_token"]

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """Load tokens from file."""
        if os.path.exists(TOKENS_FILE):
            try:
                with open(TOKENS_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return None
        return None

    def save_tokens(self, token_data: Dict[str, Any]):
        """Save tokens to file."""
        os.makedirs(os.path.dirname(TOKENS_FILE), exist_ok=True)
        with open(TOKENS_FILE, "w") as f:
            json.dump(token_data, f)

    def refresh_access_token(self, refresh_token: str) -> str:
        """Refresh access token."""
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
        }
        response = requests.post(f"{self.auth_base}/connect/token", data=data)
        response.raise_for_status()
        token_data = response.json()
        self.save_tokens(token_data)
        return token_data["access_token"]

    def get_valid_token(self) -> Optional[str]:
        """Get a valid access token, refreshing if needed."""
        token_data = self.load_tokens()
        if not token_data:
            return None

        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            return None

        try:
            return self.refresh_access_token(refresh_token)
        except Exception as e:
            print(f"Token refresh failed: {e}")
            return None

    def get_accounts(self, token: str) -> List[Dict[str, Any]]:
        """Fetch all accounts."""
        response = requests.get(
            f"{self.api_base}/data/v1/accounts",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def get_transactions(self, token: str, account_id: str) -> List[Dict[str, Any]]:
        """Fetch transactions for an account."""
        response = requests.get(
            f"{self.api_base}/data/v1/accounts/{account_id}/transactions",
            headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json().get("results", [])

    def load_logged_transactions(self) -> set:
        """Load already logged transaction IDs."""
        if os.path.exists(TX_CACHE_FILE):
            try:
                with open(TX_CACHE_FILE, "r") as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, IOError):
                return set()
        return set()

    def save_logged_transactions(self, tx_ids: set):
        """Save logged transaction IDs."""
        os.makedirs(os.path.dirname(TX_CACHE_FILE), exist_ok=True)
        with open(TX_CACHE_FILE, "w") as f:
            json.dump(list(tx_ids), f)

    def sync_transactions(self) -> Dict[str, Any]:
        """Sync transactions to Notion."""
        from src.notion.notion_utils import ACCOUNT_IDS, post_transaction_to_notion

        token = self.get_valid_token()
        if not token:
            raise ValueError("Not authenticated. Please complete OAuth flow first.")

        print("Authenticated with Revolut")

        logged_tx_ids = self.load_logged_transactions()
        new_logged_tx_ids = set()

        successful = 0
        failed = 0
        skipped = 0

        accounts = self.get_accounts(token)
        print(f"Found {len(accounts)} accounts")

        for account in accounts:
            account_name = account.get("display_name", "Unknown")
            currency = account.get("currency", "Unknown")
            print(f"\nAccount: {account_name} ({currency})")

            # Use PRIMARY account by default
            notion_account_id = ACCOUNT_IDS.get("PRIMARY", "")

            txns = self.get_transactions(token, account["account_id"])
            print(f"  {len(txns)} transactions")

            for tx in txns:
                tx_id = tx["transaction_id"]

                if tx_id in logged_tx_ids:
                    skipped += 1
                    continue

                tx_time = datetime.fromisoformat(tx["timestamp"].replace("Z", "+00:00"))
                if tx_time <= self.cutoff_timestamp:
                    skipped += 1
                    continue

                is_income = tx["amount"] >= 0

                success = post_transaction_to_notion(
                    tx, account, is_income=is_income, force_account_id=notion_account_id
                )

                if success:
                    successful += 1
                else:
                    failed += 1

                new_logged_tx_ids.add(tx_id)

        all_logged = logged_tx_ids.union(new_logged_tx_ids)
        self.save_logged_transactions(all_logged)

        print(f"\nSync complete: {successful} added, {failed} failed, {skipped} skipped")

        return {
            "successful": successful,
            "failed": failed,
            "skipped": skipped,
        }
