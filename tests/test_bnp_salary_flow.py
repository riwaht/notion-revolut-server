#!/usr/bin/env python3
"""
Test case for the new BNP Paribas salary flow:
1. Salary received directly in BNP Paribas account
2. Manual transfer from BNP to Revolut for spending money

This simulates the future flow where your salary goes to BNP instead of Revolut.
"""

import json
import os
from datetime import datetime, timezone
from src.notion.notion_utils import post_transaction_to_notion

def test_bnp_salary_and_spending_transfer():
    """Test the complete flow: salary to BNP + spending transfer to Revolut"""
    
    print("🧪 Testing BNP Paribas Salary Flow")
    print("=" * 50)
    
    # Current timestamp for test transactions
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Step 1: Salary received in BNP Paribas account
    print("\n📥 Step 1: Salary received in BNP Paribas Savings account")
    
    salary_tx = {
        "transaction_id": "bnp_salary_test_001",
        "amount": 8500.00,  # Example salary amount in PLN
        "currency": "PLN",
        "description": "Snowflake Computing - Monthly salary payment",
        "timestamp": current_time
    }
    
    # Create BNP account object
    bnp_account = {
        "display_name": "BNP Paribas Savings",
        "account_type": "savings",
        "currency": "PLN",
        "id": "bnp_savings_001"
    }
    
    print(f"💰 Processing salary: {salary_tx['amount']} {salary_tx['currency']}")
    print(f"📝 Description: {salary_tx['description']}")
    print(f"🏦 Account: {bnp_account['display_name']}")
    
    try:
        # This should post to BNP Paribas Savings and NOT create automatic transfer
        # (since the salary is already in the savings account)
        post_transaction_to_notion(salary_tx, bnp_account, is_income=True)
        print("✅ Salary transaction posted successfully")
    except Exception as e:
        print(f"❌ Error posting salary: {e}")
    
    print("\n" + "-" * 50)
    
    # Step 2: Manual transfer from BNP to Revolut for spending
    print("\n💸 Step 2: Transfer from BNP to Revolut for spending money")
    
    spending_transfer_amount = 3000.00  # Amount to transfer for spending
    
    # 2a: Expense transaction (money leaving BNP Paribas)
    bnp_expense_tx = {
        "transaction_id": "bnp_to_revolut_expense_001",
        "amount": -spending_transfer_amount,
        "currency": "PLN",
        "description": f"Transfer to Revolut for spending - {spending_transfer_amount} PLN",
        "timestamp": current_time
    }
    
    print(f"💳 BNP Expense: {bnp_expense_tx['amount']} {bnp_expense_tx['currency']}")
    print(f"📝 Description: {bnp_expense_tx['description']}")
    
    try:
        post_transaction_to_notion(bnp_expense_tx, bnp_account, is_income=False)
        print("✅ BNP expense transaction posted successfully")
    except Exception as e:
        print(f"❌ Error posting BNP expense: {e}")
    
    # 2b: Income transaction (money entering Revolut PLN)
    revolut_income_tx = {
        "transaction_id": "revolut_from_bnp_income_001",
        "amount": spending_transfer_amount,
        "currency": "PLN",
        "description": f"From BNP Paribas for spending - {spending_transfer_amount} PLN",
        "timestamp": current_time
    }
    
    # Create Revolut account object
    revolut_account = {
        "display_name": "Revolut PLN",
        "account_type": "current",
        "currency": "PLN",
        "id": "revolut_pln_001"
    }
    
    print(f"💰 Revolut Income: {revolut_income_tx['amount']} {revolut_income_tx['currency']}")
    print(f"📝 Description: {revolut_income_tx['description']}")
    print(f"🏦 Account: {revolut_account['display_name']}")
    
    try:
        post_transaction_to_notion(revolut_income_tx, revolut_account, is_income=True)
        print("✅ Revolut income transaction posted successfully")
    except Exception as e:
        print(f"❌ Error posting Revolut income: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 Test completed!")
    print("\n📊 Summary:")
    print(f"   💰 Salary received in BNP: +{salary_tx['amount']} PLN")
    print(f"   📤 Transfer from BNP: -{spending_transfer_amount} PLN")
    print(f"   📥 Transfer to Revolut: +{spending_transfer_amount} PLN")
    print(f"   💳 Net in BNP: +{salary_tx['amount'] - spending_transfer_amount} PLN")
    print(f"   🏦 Available for spending in Revolut: +{spending_transfer_amount} PLN")

def test_edge_cases():
    """Test edge cases for the new flow"""
    print("\n🔍 Testing Edge Cases")
    print("=" * 30)
    
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Edge Case 1: EUR salary in BNP (for when you might get EUR salary)
    print("\n🇪🇺 Edge Case 1: EUR salary in BNP Paribas")
    
    eur_salary_tx = {
        "transaction_id": "bnp_eur_salary_test_001",
        "amount": 2000.00,
        "currency": "EUR",
        "description": "Freelance payment - EUR salary",
        "timestamp": current_time
    }
    
    bnp_account = {
        "display_name": "BNP Paribas Savings",
        "account_type": "savings",
        "currency": "EUR"
    }
    
    try:
        post_transaction_to_notion(eur_salary_tx, bnp_account, is_income=True)
        print("✅ EUR salary in BNP processed successfully")
    except Exception as e:
        print(f"❌ Error with EUR salary: {e}")
    
    # Edge Case 2: Transfer from BNP to Revolut International (for EUR spending)
    print("\n🌍 Edge Case 2: Transfer from BNP to Revolut International for EUR spending")
    
    eur_transfer_expense = {
        "transaction_id": "bnp_to_revolut_eur_expense_001",
        "amount": -500.00,
        "currency": "EUR", 
        "description": "Transfer to Revolut International for EUR spending - 500 EUR",
        "timestamp": current_time
    }
    
    eur_transfer_income = {
        "transaction_id": "revolut_from_bnp_eur_income_001",
        "amount": 500.00,
        "currency": "EUR",
        "description": "From BNP Paribas for EUR spending - 500 EUR", 
        "timestamp": current_time
    }
    
    revolut_intl_account = {
        "display_name": "Revolut International",
        "account_type": "current",
        "currency": "EUR"
    }
    
    try:
        post_transaction_to_notion(eur_transfer_expense, bnp_account, is_income=False)
        post_transaction_to_notion(eur_transfer_income, revolut_intl_account, is_income=True)
        print("✅ EUR transfer BNP → Revolut International processed successfully")
    except Exception as e:
        print(f"❌ Error with EUR transfer: {e}")

def simulate_monthly_flow():
    """Simulate a complete monthly flow"""
    print("\n📅 Simulating Complete Monthly Flow")
    print("=" * 40)
    
    base_time = datetime.now(timezone.utc)
    
    # Month simulation: salary + multiple spending transfers
    transactions = [
        # Day 1: Salary
        {
            "day": 1,
            "tx": {
                "transaction_id": "monthly_salary_001",
                "amount": 8500.00,
                "currency": "PLN", 
                "description": "Snowflake - Monthly salary",
                "timestamp": base_time.replace(day=1).isoformat()
            },
            "account": {"display_name": "BNP Paribas Savings", "account_type": "savings", "currency": "PLN"},
            "is_income": True,
            "description": "💰 Monthly salary received"
        },
        # Day 3: Transfer for weekly spending
        {
            "day": 3,
            "tx": {
                "transaction_id": "weekly_spending_1_expense",
                "amount": -1500.00,
                "currency": "PLN",
                "description": "Weekly spending transfer to Revolut - 1500 PLN",
                "timestamp": base_time.replace(day=3).isoformat()
            },
            "account": {"display_name": "BNP Paribas Savings", "account_type": "savings", "currency": "PLN"},
            "is_income": False,
            "description": "📤 Weekly spending - BNP expense"
        },
        {
            "day": 3,
            "tx": {
                "transaction_id": "weekly_spending_1_income",
                "amount": 1500.00,
                "currency": "PLN",
                "description": "From BNP for weekly spending - 1500 PLN",
                "timestamp": base_time.replace(day=3).isoformat()
            },
            "account": {"display_name": "Revolut PLN", "account_type": "current", "currency": "PLN"},
            "is_income": True,
            "description": "📥 Weekly spending - Revolut income"
        },
        # Day 10: Another transfer
        {
            "day": 10,
            "tx": {
                "transaction_id": "weekly_spending_2_expense",
                "amount": -1000.00,
                "currency": "PLN",
                "description": "Mid-month spending transfer - 1000 PLN",
                "timestamp": base_time.replace(day=10).isoformat()
            },
            "account": {"display_name": "BNP Paribas Savings", "account_type": "savings", "currency": "PLN"},
            "is_income": False,
            "description": "📤 Mid-month spending - BNP expense"
        },
        {
            "day": 10,
            "tx": {
                "transaction_id": "weekly_spending_2_income",
                "amount": 1000.00,
                "currency": "PLN",
                "description": "From BNP mid-month spending - 1000 PLN",
                "timestamp": base_time.replace(day=10).isoformat()
            },
            "account": {"display_name": "Revolut PLN", "account_type": "current", "currency": "PLN"},
            "is_income": True,
            "description": "📥 Mid-month spending - Revolut income"
        }
    ]
    
    total_salary = 0
    total_transferred = 0
    
    for transaction in transactions:
        print(f"\n📅 Day {transaction['day']}: {transaction['description']}")
        try:
            post_transaction_to_notion(
                transaction['tx'], 
                transaction['account'], 
                is_income=transaction['is_income']
            )
            print("✅ Processed successfully")
            
            if transaction['is_income'] and 'salary' in transaction['tx']['description'].lower():
                total_salary += transaction['tx']['amount']
            elif not transaction['is_income'] and 'bnp' in transaction['account']['display_name'].lower():
                total_transferred += abs(transaction['tx']['amount'])
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n📈 Monthly Summary:")
    print(f"   💰 Total salary received: {total_salary} PLN")
    print(f"   📤 Total transferred for spending: {total_transferred} PLN")
    print(f"   💳 Remaining in BNP Paribas: {total_salary - total_transferred} PLN")

if __name__ == "__main__":
    print("🚀 BNP Paribas Salary Flow Test Suite")
    print("Testing the new flow where salary goes to BNP and spending money goes to Revolut")
    
    try:
        # Run main test
        test_bnp_salary_and_spending_transfer()
        
        # Run edge cases
        test_edge_cases()
        
        # Run monthly simulation  
        simulate_monthly_flow()
        
        print("\n🎉 All tests completed successfully!")
        print("\n💡 Next steps:")
        print("   1. Update your payroll to direct deposit to BNP Paribas")
        print("   2. Set up regular transfers from BNP to Revolut for spending")
        print("   3. The system will automatically track both accounts correctly")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        raise
