# Revolut to Notion Sync

Automatically sync Revolut transactions to Notion with categorization and currency conversion.

> **Not a developer?** Don't worry, I built this repo to be easy to work with using AI tools like Claude Code or Cursor. Just open the project and ask for help! There's an `AGENTS.md` file that gives AI all the context it needs to guide you through setup and troubleshooting.

## Features

- Auto-categorization (keyword matching + semantic similarity)
- Currency conversion via Frankfurter API
- Multi-account support via TrueLayer
- Failed transaction retry queue

## Quick Start

### 1. Copy the Notion Template

Duplicate the budget tracker template to your workspace:

**[Get the Template](https://www.notion.com/templates/budget-tracker-automated)**

This gives you pre-configured databases for Expenses, Income, Accounts, and Categories.

### 2. Get Your Database IDs

For each database (Expenses, Income, Accounts, Categories), open it in Notion and copy the ID from the URL:

```
https://notion.so/Your-Database-NAME?v=...
                  ^^^^^^^^^^^^^^^^
                  This is your database ID (32 characters)
```

### 3. Get Relation IDs

For Account and Category relations, open each page and copy the ID from the URL:

```
https://notion.so/Category-Name-abc123...
                                ^^^^^^
                                This is the relation ID
```

### 4. Install & Configure

```bash
git clone <repo-url>
cd notion-revolut-server
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your IDs:

```env
# Notion
NOTION_TOKEN=secret_xxx
EXPENSES_DB_ID=your_expenses_db_id
INCOME_DB_ID=your_income_db_id

# Account relation IDs (from your Accounts database)
PRIMARY_ACCOUNT_ID=your_main_account_id

# Category relation IDs (from your Categories database)
CATEGORY_FOOD_ID=xxx
CATEGORY_TRANSPORT_ID=xxx
# ... add all your categories

# TrueLayer (truelayer.com)
# 1. Create application → 2. Copy client_id & client_secret
# 3. Make it live (not sandbox) → 4. Set redirect URI
TL_CLIENT_ID=xxx
TL_CLIENT_SECRET=xxx
TL_REDIRECT_URI=http://localhost:8000/callback
TL_PROVIDER=uk-ob-revolut  # or pl-ob-revolut, fr-ob-revolut, etc.
```

### 5. Run

```bash
python app.py
```

First time: visit `GET /auth`, complete OAuth, then `POST /auth/exchange`.

Sync: `POST /sync`

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth` | GET | Get OAuth URL |
| `/auth/exchange` | POST | Exchange auth code |
| `/sync` | POST | Sync transactions |
| `/retry-failed` | POST | Retry failed |

## Customization

**Categories**: Edit `data/categories.json` to add keywords for your categories.

**LLM Integration**: For smarter categorization, modify `src/notion/category_mapper.py` to call an LLM API (Mistral offers a free tier ;)).

**Notion Fields**: Adjust `src/notion/notion_utils.py` to match your database schema.

## Project Structure

```
├── app.py                    # FastAPI server
├── src/
│   ├── revolut/              # TrueLayer OAuth & sync
│   ├── notion/               # Notion API & categorization
│   └── utils/                # Currency conversion
├── data/
│   ├── categories.json              # Category keywords
│   └── exchange_rates_cache.json    # Caches rates, e.g. EUR_USD_2024-01-15: 1.08
└── tests/
```

## Hosting

I host this on DigitalOcean App Platform (free tier via GitHub integration) with a cron job that calls `POST /sync` daily.

## License

MIT
