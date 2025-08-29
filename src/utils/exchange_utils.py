import requests
from decimal import Decimal
from datetime import datetime

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
        pass

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