import requests
import json
import os
import time
from decimal import Decimal
from datetime import datetime

# Cache file for exchange rates
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
EXCHANGE_CACHE_FILE = os.path.join(BASE_DIR, "data", "exchange_rates_cache.json")

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

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1  # seconds

class ExchangeRateConverter:
    def __init__(self):
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """Load exchange rate cache from file"""
        if os.path.exists(EXCHANGE_CACHE_FILE):
            try:
                with open(EXCHANGE_CACHE_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                print("[WARNING] Could not load exchange rate cache, starting fresh")
        return {}
    
    def _save_cache(self):
        """Save exchange rate cache to file"""
        try:
            os.makedirs(os.path.dirname(EXCHANGE_CACHE_FILE), exist_ok=True)
            with open(EXCHANGE_CACHE_FILE, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except IOError as e:
            print(f"[WARNING] Could not save exchange rate cache: {e}")
    
    def _get_cache_key(self, currency: str, date: str) -> str:
        """Generate cache key for currency and date"""
        return f"{currency}_{date}"
    
    def _api_request_with_retry(self, url: str, params: dict, timeout: int = 10) -> dict:
        """Make API request with exponential backoff retry"""
        last_exception = None
        
        for attempt in range(MAX_RETRIES):
            try:
                print(f"[INFO] API request attempt {attempt + 1}/{MAX_RETRIES}: {url}")
                resp = requests.get(url, params=params, timeout=timeout)
                resp.raise_for_status()  # Raises HTTPError for bad status codes
                return resp.json()
                
            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    print(f"[RETRY] Timeout error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(delay)
                else:
                    print(f"[ERROR] Max retries exceeded for timeout: {e}")
                    
            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = BASE_DELAY * (2 ** attempt)
                    print(f"[RETRY] Connection error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(delay)
                else:
                    print(f"[ERROR] Max retries exceeded for connection error: {e}")
                    
            except requests.exceptions.HTTPError as e:
                last_exception = e
                print(f"[ERROR] HTTP error (status {e.response.status_code}): {e}")
                if e.response.status_code >= 500:  # Server error, retry
                    if attempt < MAX_RETRIES - 1:
                        delay = BASE_DELAY * (2 ** attempt)
                        print(f"[RETRY] Server error, retrying in {delay}s (attempt {attempt + 1}/{MAX_RETRIES})")
                        time.sleep(delay)
                    else:
                        print(f"[ERROR] Max retries exceeded for server error")
                else:  # Client error, don't retry
                    break
                    
            except requests.exceptions.RequestException as e:
                last_exception = e
                print(f"[ERROR] Request exception: {e}")
                break
                
            except Exception as e:
                last_exception = e
                print(f"[ERROR] Unexpected error: {e}")
                break
        
        # If we get here, all retries failed
        raise last_exception if last_exception else Exception("API request failed after retries")

    def convert_to_usd(self, amount: Decimal, currency: str, date: str) -> Decimal:
        """
        Convert amount from given currency to USD using historical rate on given date (YYYY-MM-DD).
        Uses cache first, then API with retry, then fallback rates.
        """
        if currency == "USD":
            return amount

        # Check cache first
        cache_key = self._get_cache_key(currency, date)
        if cache_key in self.cache:
            cached_rate = Decimal(str(self.cache[cache_key]))
            converted = (amount * cached_rate).quantize(Decimal("0.01"))
            print(f"[CACHE] Converted {amount} {currency} to {converted} USD @ {cached_rate} (cached)")
            return converted

        # Try API with retry mechanism
        try:
            today = datetime.utcnow().date()
            requested_date = min(datetime.strptime(date, "%Y-%m-%d").date(), today)
            url = f"https://api.frankfurter.app/{requested_date.isoformat()}"
            
            data = self._api_request_with_retry(url, {"from": currency, "to": "USD"})

            if "rates" in data and "USD" in data["rates"]:
                rate = Decimal(str(data["rates"]["USD"]))
                converted = (amount * rate).quantize(Decimal("0.01"))
                
                # Update cache with new rate
                self.cache[cache_key] = str(rate)
                self._save_cache()
                
                # Also update fallback rate for this currency
                FALLBACK_RATES[currency] = float(rate)
                print(f"[SUCCESS] Converted {amount} {currency} to {converted} USD @ {rate} (updated cache & fallback)")
                return converted
            else:
                print(f"[ERROR] USD rate not in response: {data}")
                
        except Exception as e:
            print(f"[ERROR] Currency conversion API failed after retries: {e}")
            
        # Fallback to cached rate or default fallback
        if currency in FALLBACK_RATES:
            fallback_rate = Decimal(str(FALLBACK_RATES[currency]))
            converted = (amount * fallback_rate).quantize(Decimal("0.01"))
            print(f"[FALLBACK] Using fallback rate for {currency}: {fallback_rate}")
            return converted

        # Last resort - return original amount
        print(f"[WARNING] No conversion rate available for {currency}, using original amount")
        return amount


# Singleton for importing and reuse
converter = ExchangeRateConverter()