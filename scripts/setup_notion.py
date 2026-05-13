"""
Auto-discover Notion database IDs and write them to .env.

Queries your Notion databases to find Category and Account relation IDs
so you don't have to copy-paste them manually.

Usage:
    python scripts/setup_notion.py

Prerequisites:
    - NOTION_TOKEN set in .env
    - EXPENSES_DB_ID and INCOME_DB_ID set in .env
"""

import os
import sys

import requests
from dotenv import load_dotenv, set_key

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(BASE_DIR, ".env")

load_dotenv(ENV_PATH)

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json",
}

# Expected category names (must match data/categories.json)
EXPENSE_CATEGORIES = [
    "Food", "Groceries", "Transport", "Shopping", "Health",
    "Entertainment", "Bills", "Travel", "Transfer", "Other",
]
INCOME_CATEGORIES = ["Salary", "Transfer", "Refund", "Other"]

# Env var mapping for categories
EXPENSE_ENV_KEYS = {
    "Food": "CATEGORY_FOOD_ID",
    "Groceries": "CATEGORY_GROCERIES_ID",
    "Transport": "CATEGORY_TRANSPORT_ID",
    "Shopping": "CATEGORY_SHOPPING_ID",
    "Health": "CATEGORY_HEALTH_ID",
    "Entertainment": "CATEGORY_ENTERTAINMENT_ID",
    "Bills": "CATEGORY_BILLS_ID",
    "Travel": "CATEGORY_TRAVEL_ID",
    "Transfer": "CATEGORY_TRANSFER_ID",
    "Other": "CATEGORY_OTHER_ID",
}

INCOME_ENV_KEYS = {
    "Salary": "CATEGORY_SALARY_ID",
    "Transfer": "CATEGORY_TRANSFER_ID",  # shared with expenses
    "Refund": "CATEGORY_REFUND_ID",
    "Other": "CATEGORY_OTHER_INCOME_ID",
}


def get_database_schema(db_id: str) -> dict | None:
    """Fetch database schema to find relation property targets."""
    url = f"https://api.notion.com/v1/databases/{db_id}"
    resp = requests.get(url, headers=HEADERS, timeout=15)
    if resp.status_code != 200:
        print(f"  Error fetching database {db_id}: {resp.status_code}")
        return None
    return resp.json()


def query_all_pages(db_id: str) -> list[dict]:
    """Query all pages from a Notion database (handles pagination)."""
    pages = []
    url = "https://api.notion.com/v1/databases/{}/query".format(db_id)
    payload = {"page_size": 100}

    while True:
        resp = requests.post(url, headers=HEADERS, json=payload, timeout=15)
        if resp.status_code != 200:
            print(f"  Error querying database {db_id}: {resp.status_code}")
            break
        data = resp.json()
        pages.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    return pages


def get_page_title(page: dict) -> str:
    """Extract the title text from a Notion page."""
    for prop in page.get("properties", {}).values():
        if prop.get("type") == "title":
            title_parts = prop.get("title", [])
            if title_parts:
                return title_parts[0].get("text", {}).get("content", "")
    return ""


def find_relation_db_id(schema: dict, property_name: str) -> str | None:
    """Find the target database ID for a relation property."""
    props = schema.get("properties", {})
    prop = props.get(property_name)
    if not prop or prop.get("type") != "relation":
        return None
    return prop.get("relation", {}).get("database_id")


def strip_dashes(uuid: str) -> str:
    """Remove dashes from a UUID to match Notion's format in URLs."""
    return uuid.replace("-", "")


def discover_categories(expenses_db_id: str) -> dict[str, str]:
    """Discover category IDs from the expenses database's Category relation."""
    print("\nDiscovering categories...")

    schema = get_database_schema(expenses_db_id)
    if not schema:
        return {}

    cat_db_id = find_relation_db_id(schema, "Category")
    if not cat_db_id:
        print("  Could not find 'Category' relation property in expenses database.")
        print("  Make sure your expenses database has a 'Category' relation column.")
        return {}

    print(f"  Found Category database: {cat_db_id[:12]}...")

    pages = query_all_pages(cat_db_id)
    categories = {}
    for page in pages:
        name = get_page_title(page)
        page_id = strip_dashes(page["id"])
        if name:
            categories[name] = page_id

    print(f"  Found {len(categories)} categories: {', '.join(sorted(categories.keys()))}")
    return categories


def discover_accounts(expenses_db_id: str) -> dict[str, str]:
    """Discover account IDs from the expenses database's Account relation."""
    print("\nDiscovering accounts...")

    schema = get_database_schema(expenses_db_id)
    if not schema:
        return {}

    acct_db_id = find_relation_db_id(schema, "Account")
    if not acct_db_id:
        print("  Could not find 'Account' relation property in expenses database.")
        print("  Make sure your expenses database has an 'Account' relation column.")
        return {}

    print(f"  Found Account database: {acct_db_id[:12]}...")

    pages = query_all_pages(acct_db_id)
    accounts = {}
    for page in pages:
        name = get_page_title(page)
        page_id = strip_dashes(page["id"])
        if name:
            accounts[name] = page_id

    if not accounts:
        print("  No accounts found.")
        return {}

    print(f"  Found {len(accounts)} accounts: {', '.join(sorted(accounts.keys()))}")

    # Let user assign accounts to roles
    assigned = {}
    account_names = sorted(accounts.keys())

    print("\n  Assign accounts to roles (enter the number, or press Enter to skip):")
    for role in ["PRIMARY", "SECONDARY"]:
        print(f"\n  {role} account:")
        for i, name in enumerate(account_names, 1):
            print(f"    {i}. {name}")
        print(f"    0. Skip")

        while True:
            choice = input(f"  Choice for {role}: ").strip()
            if choice == "" or choice == "0":
                break
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(account_names):
                    assigned[role] = accounts[account_names[idx]]
                    print(f"    -> {role} = {account_names[idx]}")
                    break
                else:
                    print("    Invalid number, try again.")
            except ValueError:
                print("    Enter a number.")

    return assigned


def write_to_env(categories: dict[str, str], accounts: dict[str, str]):
    """Write discovered IDs to .env file."""
    if not os.path.exists(ENV_PATH):
        print(f"\n.env file not found at {ENV_PATH}")
        print("Copy .env.example to .env first: cp .env.example .env")
        return

    updated = []

    # Write expense category IDs
    for cat_name, env_key in EXPENSE_ENV_KEYS.items():
        if cat_name in categories:
            set_key(ENV_PATH, env_key, categories[cat_name])
            updated.append(f"  {env_key} = {categories[cat_name][:12]}...")

    # Write income category IDs (some share env vars with expenses, like Transfer)
    for cat_name, env_key in INCOME_ENV_KEYS.items():
        if cat_name in categories and env_key not in [v for v in EXPENSE_ENV_KEYS.values() if categories.get(cat_name)]:
            set_key(ENV_PATH, env_key, categories[cat_name])
            updated.append(f"  {env_key} = {categories[cat_name][:12]}...")

    # Write account IDs
    account_env_keys = {
        "PRIMARY": "PRIMARY_ACCOUNT_ID",
        "SECONDARY": "SECONDARY_ACCOUNT_ID",
    }
    for role, env_key in account_env_keys.items():
        if role in accounts:
            set_key(ENV_PATH, env_key, accounts[role])
            updated.append(f"  {env_key} = {accounts[role][:12]}...")

    if updated:
        print(f"\nUpdated {len(updated)} values in .env:")
        for line in updated:
            print(line)
    else:
        print("\nNo values to update.")


def validate(categories: dict[str, str]):
    """Warn about expected categories that weren't found in Notion."""
    all_expected = set(EXPENSE_CATEGORIES + INCOME_CATEGORIES)
    found = set(categories.keys())
    missing = all_expected - found
    extra = found - all_expected

    if missing:
        print(f"\nWarning: These categories are expected but not found in Notion:")
        for name in sorted(missing):
            print(f"  - {name}")
        print("  Create them in your Categories database or update data/categories.json")

    if extra:
        print(f"\nNote: These categories exist in Notion but aren't mapped:")
        for name in sorted(extra):
            print(f"  - {name}")
        print("  Add them to data/categories.json and .env if you want to use them")


def main():
    print("Notion Setup - Auto-discover IDs")
    print("=" * 40)

    if not NOTION_TOKEN:
        print("Error: NOTION_TOKEN not set in .env")
        print("Get your token from: https://notion.so/my-integrations")
        sys.exit(1)

    expenses_db_id = os.getenv("EXPENSES_DB_ID", "")
    income_db_id = os.getenv("INCOME_DB_ID", "")

    if not expenses_db_id:
        print("Error: EXPENSES_DB_ID not set in .env")
        print("Copy the database ID from your Expenses database URL in Notion")
        sys.exit(1)

    if not income_db_id:
        print("Warning: INCOME_DB_ID not set in .env (income tracking won't work)")

    # Discover categories and accounts
    categories = discover_categories(expenses_db_id)
    accounts = discover_accounts(expenses_db_id)

    if not categories and not accounts:
        print("\nNo IDs discovered. Check that:")
        print("  1. Your NOTION_TOKEN has access to the databases")
        print("  2. Your EXPENSES_DB_ID is correct")
        print("  3. Your databases have 'Category' and 'Account' relation columns")
        sys.exit(1)

    # Validate against expected categories
    validate(categories)

    # Write to .env
    write_to_env(categories, accounts)

    print("\nDone! You can now run: python app.py")


if __name__ == "__main__":
    main()
