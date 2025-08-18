import os
import json
from datetime import datetime
from forex_python.converter import CurrencyRates, RatesNotAvailableError
from collections import defaultdict

CACHE_FILE = "data/exchange_rates_cache.json"
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
        self.currency_rates = CurrencyRates()
        self.cache = defaultdict(dict)
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r") as f:
                raw = json.load(f)
                for currency, rate in raw.items():
                    self.cache[currency] = rate

    def _save_cache(self):
        with open(CACHE_FILE, "w") as f:
            json.dump(self.cache, f, indent=2)

    def get_rate_to_usd(self, currency: str) -> float:
        if currency == "USD":
            return 1.0

        if currency in self.cache:
            return float(self.cache[currency])

        try:
            rate = self.currency_rates.get_rate(currency, "USD")
            self.cache[currency] = rate
            self._save_cache()
            print(f"✅ Fetched {currency} → USD: {rate}")
            return rate
        except RatesNotAvailableError:
            fallback = FALLBACK_RATES.get(currency)
            print(f"⚠️ Falling back to default rate for {currency}: {fallback}")
            return fallback if fallback is not None else 1.0

    def convert_to_usd(self, amount: float, currency: str) -> float:
        rate = self.get_rate_to_usd(currency)
        return round(amount * rate, 2)


# Singleton for reuse
converter = ExchangeRateConverter()
