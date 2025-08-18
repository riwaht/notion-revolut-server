import unittest
from unittest.mock import patch
from src.utils.exchange_utils import ExchangeRateConverter, FALLBACK_RATES
from forex_python.converter import RatesNotAvailableError

class TestExchangeRateConverter(unittest.TestCase):
    def setUp(self):
        self.converter = ExchangeRateConverter()

    @patch("src.utils.exchange_utils.CurrencyRates.get_rate")
    def test_get_rate_caches_result(self, mock_get_rate):
        mock_get_rate.return_value = 4.5
        rate = self.converter.get_rate("PLN", "USD")
        self.assertEqual(rate, 4.5)
        self.assertIn("PLN_USD", self.converter.cache)
        self.assertEqual(self.converter.cache["PLN_USD"], 4.5)

    @patch("src.utils.exchange_utils.CurrencyRates.get_rate", side_effect=RatesNotAvailableError("No internet"))
    def test_get_rate_fallback(self, mock_get_rate):
        self.converter.cache.clear()  # Ensure no cache is used
        rate = self.converter.get_rate("PLN", "USD")
        expected = FALLBACK_RATES["PLN"]
        self.assertEqual(rate, expected)

    @patch("src.utils.exchange_utils.ExchangeRateConverter.get_rate", side_effect=Exception("No internet"))
    def test_convert_to_usd_fallback(self, mock_get_rate):
        fallback = FALLBACK_RATES.get("EUR", 1.0)
        result = self.converter.convert_to_usd(100, "EUR")
        self.assertEqual(result, round(100 * fallback, 2))

    def test_direct_usd_conversion(self):
        result = self.converter.convert_to_usd(100, "USD")
        self.assertEqual(result, 100.0)
