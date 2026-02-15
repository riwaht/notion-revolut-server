"""Tests for exchange rate utilities."""

import unittest
from decimal import Decimal
from unittest.mock import patch

from src.utils.exchange_utils import ExchangeRateConverter


class TestExchangeRateConverter(unittest.TestCase):

    def setUp(self):
        self.converter = ExchangeRateConverter()

    def test_same_currency_no_conversion(self):
        """No conversion needed when source equals base currency."""
        result = self.converter.convert_to_base(Decimal("100"), "USD", "2024-01-15")
        self.assertEqual(result, Decimal("100"))

    @patch("src.utils.exchange_utils.ExchangeRateConverter._api_request_with_retry")
    def test_conversion_with_api(self, mock_api):
        """Test conversion using API response."""
        mock_api.return_value = {"rates": {"USD": 1.1}}
        self.converter.cache.clear()

        result = self.converter.convert_to_base(Decimal("100"), "EUR", "2024-01-15")
        self.assertEqual(result, Decimal("110.00"))

    def test_conversion_uses_cache(self):
        """Test that cached rates are used."""
        self.converter.cache["EUR_USD_2024-01-15"] = "1.2"

        result = self.converter.convert_to_base(Decimal("100"), "EUR", "2024-01-15")
        self.assertEqual(result, Decimal("120.00"))


if __name__ == "__main__":
    unittest.main()
