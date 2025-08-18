import unittest
from src.notion.category_mapper import categorize_transaction

class TestCategoryMapper(unittest.TestCase):
    
    def test_expense_keyword_match(self):
        self.assertEqual(categorize_transaction("McDonald's"), "Food")
        self.assertEqual(categorize_transaction("PKP Intercity train"), "Transport")
        self.assertEqual(categorize_transaction("Zabka groceries"), "Necessities")
        self.assertEqual(categorize_transaction("Calypso gym membership"), "Gym")
        self.assertEqual(categorize_transaction("Netflix monthly subscription"), "Subscription")

    def test_income_keyword_match(self):
        self.assertEqual(categorize_transaction("Snowflake salary", is_income=True), "Salary")
        self.assertEqual(categorize_transaction("Twisto refund", is_income=True), "Repaid")
        self.assertEqual(categorize_transaction("Interest from Revolut Vault", is_income=True), "Savings")
        self.assertEqual(categorize_transaction("From dad", is_income=True), "Parents")

    def test_expense_semantic_only(self):
        # These are intentionally vague, not in keyword list
        self.assertEqual(categorize_transaction("Late-night burger run"), "Food")
        self.assertEqual(categorize_transaction("Ticket for a metal concert"), "Free Time")
        self.assertEqual(categorize_transaction("Zakopane ski rental cabin"), "Travel")

    def test_income_semantic_only(self):
        self.assertEqual(categorize_transaction("Work bonus from company", is_income=True), "Salary")
        self.assertEqual(categorize_transaction("Sent back my money", is_income=True), "Repaid")
        self.assertEqual(categorize_transaction("Deposit from dad", is_income=True), "Parents")

    def test_default_category(self):
        self.assertEqual(categorize_transaction("Some unknown thing here"), "Others")
        self.assertEqual(categorize_transaction("", is_income=True), "Others")
        self.assertEqual(categorize_transaction(None, is_income=True), "Others")

if __name__ == "__main__":
    unittest.main()
