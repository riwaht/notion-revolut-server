"""Tests for category mapper."""

import unittest

from src.notion.category_mapper import categorize_transaction


class TestCategoryMapper(unittest.TestCase):

    def test_expense_keyword_match(self):
        self.assertEqual(categorize_transaction("McDonald's restaurant"), "Food")
        self.assertEqual(categorize_transaction("Uber ride"), "Transport")
        self.assertEqual(categorize_transaction("Amazon purchase"), "Shopping")
        self.assertEqual(categorize_transaction("Local gym membership"), "Entertainment")
        self.assertEqual(categorize_transaction("Netflix subscription"), "Entertainment")

    def test_income_keyword_match(self):
        self.assertEqual(categorize_transaction("Monthly salary", is_income=True), "Salary")
        self.assertEqual(categorize_transaction("Refund from store", is_income=True), "Refund")

    def test_transfer_detection(self):
        self.assertEqual(categorize_transaction("Exchanged to EUR"), "Transfer")
        self.assertEqual(categorize_transaction("Exchanged from USD"), "Transfer")
        self.assertEqual(categorize_transaction("Transfer to vault"), "Transfer")

    def test_semantic_fallback(self):
        # These rely on semantic similarity
        result = categorize_transaction("Late-night burger run")
        self.assertIn(result, ["Food", "Other"])

    def test_default_category(self):
        self.assertEqual(categorize_transaction(""), "Other")
        self.assertEqual(categorize_transaction(None), "Other")


if __name__ == "__main__":
    unittest.main()
