import os
import json
import requests
from decimal import Decimal
from datetime import datetime
from collections import defaultdict

# Path to cache file
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CACHE_FILE = os.path.join(BASE_DIR, "data", "exchange_rates_cache.json")

# Default fallback rates if API fails
FALLBACK_RATES = {
    "PLN": 0.25,
    "EUR": 1.1,
    "USD": 1.0,
    "GBP": 1.27,
    "CHF": 1.14,
    "AED": 0.27,
    "CAD": 0.74,
    "TRY": 0.03,
    "HUF": 0.00295,  # Hungarian Forint (339 HUF = 1 USD)
}

class ExchangeRateConverter:
    def __init__(self):
        self.currency_rates = CurrencyRates(force_decimal=True)
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    self.cache = json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load exchange rate cache: {e}")
                self.cache = {}

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save exchange rate cache: {e}")

    def get_rate(self, from_currency: str, to_currency: str = "USD") -> float:
        key = f"{from_currency}_{to_currency}"
        if key in self.cache:
            return float(self.cache[key])

        try:
            rate = self.currency_rates.get_rate(from_currency, to_currency)
            self.cache[key] = float(rate)
            self._save_cache()
            print(f"✅ Fetched {from_currency} → {to_currency}: {rate}")
            return float(rate)
        except RatesNotAvailableError:
            fallback = FALLBACK_RATES.get(from_currency, 1.0)
            print(f"⚠️ Falling back to default rate for {from_currency}: {fallback}")
            return fallback

    def convert(self, amount: float, from_currency: str, to_currency: str = "USD") -> float:
        rate = self.get_rate(from_currency, to_currency)
        return round(float(Decimal(amount) * Decimal(rate)), 2)

    def convert_to_usd(self, amount: Decimal, currency: str, date: str) -> Decimal:
        """
        Convert amount from given currency to USD using historical rate on given date (YYYY-MM-DD).
        Falls back to same amount if API fails.
        """
        if currency == "USD":
            return amount

        try:
            today = datetime.utcnow().date()
            requested_date = min(datetime.strptime(date, "%Y-%m-%d").date(), today)
            url = f"https://api.frankfurter.app/{requested_date.isoformat()}"
            resp = requests.get(url, params={"from": currency, "to": "USD"}, timeout=10)
            data = resp.json()

            if "rates" in data and "USD" in data["rates"]:
                rate = Decimal(str(data["rates"]["USD"]))
                converted = (amount * rate).quantize(Decimal("0.01"))
                print(f"[INFO] Converted {amount} {currency} to {converted} USD @ {rate}")
                return converted
            else:
                print(f"[ERROR] USD rate not in response: {data}")
        except Exception as e:
            print(f"[ERROR] Currency conversion failed: {e}")
            # Keep fallback rates as an exception
            if currency in FALLBACK_RATES:
                fallback_rate = Decimal(str(FALLBACK_RATES[currency]))
                converted = (amount * fallback_rate).quantize(Decimal("0.01"))
                print(f"[FALLBACK] Using fallback rate for {currency}: {fallback_rate}")
                return converted

        return amount


# Singleton for importing and reuse
converter = ExchangeRateConverter()