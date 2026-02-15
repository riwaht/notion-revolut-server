"""
Currency conversion utilities using the Frankfurter API with caching and fallback rates.
"""

import json
import os
import time
from datetime import datetime
from decimal import Decimal

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXCHANGE_CACHE_FILE = os.path.join(BASE_DIR, "data", "exchange_rates_cache.json")

# Base currency for conversion (configurable via environment)
BASE_CURRENCY = os.getenv("BASE_CURRENCY", "USD")

# Default fallback rates (to BASE_CURRENCY)
FALLBACK_RATES = {
    "USD": 1.0,
    "EUR": 1.1,
    "GBP": 1.27,
    "CHF": 1.14,
    "CAD": 0.74,
    "AUD": 0.65,
    "JPY": 0.0067,
    "CNY": 0.14,
    "INR": 0.012,
    "MXN": 0.058,
    "BRL": 0.20,
}

MAX_RETRIES = 3
BASE_DELAY = 1


class ExchangeRateConverter:
    """Currency converter with caching and retry logic."""

    def __init__(self):
        self.cache = self._load_cache()
        self.base_currency = BASE_CURRENCY

    def _load_cache(self):
        """Load exchange rate cache from file."""
        if os.path.exists(EXCHANGE_CACHE_FILE):
            try:
                with open(EXCHANGE_CACHE_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {}

    def _save_cache(self):
        """Save exchange rate cache to file."""
        try:
            os.makedirs(os.path.dirname(EXCHANGE_CACHE_FILE), exist_ok=True)
            with open(EXCHANGE_CACHE_FILE, "w") as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"Could not save exchange rate cache: {e}")

    def _get_cache_key(self, from_currency: str, to_currency: str, date: str) -> str:
        """Generate cache key for currency pair and date."""
        return f"{from_currency}_{to_currency}_{date}"

    def _api_request_with_retry(self, url: str, params: dict, timeout: int = 10) -> dict:
        """Make API request with exponential backoff retry."""
        last_exception = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    time.sleep(delay)

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    time.sleep(delay)

            except requests.exceptions.HTTPError as e:
                last_exception = e
                if e.response.status_code >= 500 and attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    time.sleep(delay)
                else:
                    break

            except requests.exceptions.RequestException as e:
                last_exception = e
                break

        raise last_exception if last_exception else Exception("API request failed")

    def convert_to_base(self, amount: Decimal, currency: str, date: str) -> Decimal:
        """
        Convert amount to base currency using historical rate.

        Args:
            amount: Amount to convert
            currency: Source currency code
            date: Date for historical rate (YYYY-MM-DD)

        Returns:
            Converted amount in base currency
        """
        if currency == self.base_currency:
            return amount

        cache_key = self._get_cache_key(currency, self.base_currency, date)
        if cache_key in self.cache:
            cached_rate = Decimal(str(self.cache[cache_key]))
            return (amount * cached_rate).quantize(Decimal("0.01"))

        try:
            today = datetime.utcnow().date()
            requested_date = min(datetime.strptime(date, "%Y-%m-%d").date(), today)
            url = f"https://api.frankfurter.app/{requested_date.isoformat()}"

            data = self._api_request_with_retry(url, {"from": currency, "to": self.base_currency})

            if "rates" in data and self.base_currency in data["rates"]:
                rate = Decimal(str(data["rates"][self.base_currency]))
                converted = (amount * rate).quantize(Decimal("0.01"))

                self.cache[cache_key] = str(rate)
                self._save_cache()

                return converted

        except Exception as e:
            print(f"Currency conversion failed: {e}")

        # Fallback
        if currency in FALLBACK_RATES:
            fallback_rate = Decimal(str(FALLBACK_RATES[currency]))
            return (amount * fallback_rate).quantize(Decimal("0.01"))

        return amount


converter = ExchangeRateConverter()
