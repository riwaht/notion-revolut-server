import os
import json
from decimal import Decimal
from forex_python.converter import CurrencyRates, RatesNotAvailableError
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

    def convert_to_usd(self, amount: float, currency: str) -> float:
        try:
            rate = self.get_rate(currency, "USD")
        except Exception as e:
            print(f"⚠️ Error during conversion: {e}")
            rate = FALLBACK_RATES.get(currency, 1.0)
        return round(amount * rate, 2)


# Singleton for importing and reuse
converter = ExchangeRateConverter()