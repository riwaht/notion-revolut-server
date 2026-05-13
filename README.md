# Revolut to Notion Sync

Automatically sync Revolut transactions to Notion with categorization and currency conversion.

Works with **Revolut Individual** (personal accounts). Not tested with Revolut Business.

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

Edit `.env` with your core settings:

```env
# Notion
NOTION_TOKEN=secret_xxx
EXPENSES_DB_ID=your_expenses_db_id
INCOME_DB_ID=your_income_db_id

# TrueLayer (truelayer.com)
# 1. Create application → 2. Copy client_id & client_secret
# 3. Make it live (not sandbox) → 4. Set redirect URI
TL_CLIENT_ID=xxx
TL_CLIENT_SECRET=xxx
TL_REDIRECT_URI=http://localhost:8000/callback
TL_PROVIDER=uk-ob-revolut  # or pl-ob-revolut, fr-ob-revolut, etc.
```

> **TrueLayer note**: When creating your app, select **Revolut Individual** (not Business). The free tier has rate limits; the Data API product may require contacting TrueLayer sales depending on your region.

### 5. Auto-Discover Notion IDs

Instead of manually copying 15+ category and account IDs, run the setup script:

```bash
python scripts/setup_notion.py
```

This queries your Notion databases, finds all Category and Account pages, and writes their IDs to `.env` automatically. You'll be prompted to assign accounts to PRIMARY/SECONDARY roles.

### 6. Run

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

### Categories

Transactions are categorized using this priority chain:

1. **Transfer keywords** — `exchanged to`, `vault`, `transfer` (hardcoded, highest priority)
2. **Keyword matching** — matches transaction description against `data/categories.json`
3. **Semantic similarity** — uses sentence embeddings to find the closest category (threshold: 0.2)
4. **Default** — falls back to "Other"

To add or modify categories:

1. Create the category page in your Notion Categories database
2. Re-run `python scripts/setup_notion.py` to pick up the new ID
3. Add keywords to `data/categories.json` under `expenses` or `income`

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

## Privacy & Data Handling

- All data is processed locally and sent only to **your own** Notion workspace
- No third-party analytics or telemetry
- OAuth tokens stored locally in `data/tokens.json` (gitignored)
- External services used:
  - **TrueLayer** — reads your bank transactions (OAuth-authorized)
  - **Notion API** — writes to your databases
  - **Frankfurter API** — public exchange rates (no auth required)
- No server-side database — all state is local JSON files

## License

MIT
