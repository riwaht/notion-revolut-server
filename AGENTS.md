# Agent Instructions

Guidelines for AI assistants working on this codebase.

## Project Overview

This is a FastAPI server that syncs Revolut transactions to Notion via TrueLayer API. It auto-categorizes transactions using keyword matching + semantic similarity, converts currencies, and handles retries for failed transactions.

## Architecture

```
app.py                           → FastAPI endpoints
src/revolut/revolut_connector.py → TrueLayer OAuth & transaction fetching
src/notion/notion_utils.py       → Notion API client, posts transactions
src/notion/category_mapper.py    → Categorization (keywords + embeddings)
src/utils/exchange_utils.py      → Currency conversion via Frankfurter API
data/categories.json             → Category keywords (editable)
```

## Key Flows

### OAuth Flow
1. User visits `GET /auth` → gets TrueLayer auth URL
2. User authorizes in browser → redirected to `GET /callback` with code
3. User calls `POST /auth/exchange` → exchanges code for tokens
4. Tokens saved to `data/tokens.json`

### Sync Flow
1. `POST /sync` triggers `RevolutConnector.sync_transactions()`
2. Refreshes access token using saved refresh token
3. Fetches all accounts and transactions from TrueLayer
4. For each transaction: categorize → convert currency → post to Notion
5. Failed transactions logged to `data/failed_transactions.json` for retry

## Setup Checklist

1. Copy `.env.example` to `.env`
2. Get Notion integration token from notion.so/my-integrations
3. Copy the Notion template and get database/relation IDs
4. Create TrueLayer app, go live, get credentials
5. Run `pip install -r requirements.txt`
6. Run `python app.py`

## Common Issues

### "Not authenticated" error
- Tokens expired or missing. Complete OAuth flow: `GET /auth` → authorize → `POST /auth/exchange`

### Transactions not appearing in Notion
- Check database IDs in `.env` are correct (32-char IDs from Notion URLs)
- Check category/account relation IDs match your Notion setup
- Check `data/failed_transactions.json` for errors

### Category mapping wrong
- Edit `data/categories.json` to add keywords
- Semantic fallback uses averaged embeddings with 0.2 threshold

### Currency conversion failing
- Frankfurter API might be down; falls back to hardcoded rates
- Check `data/exchange_rates_cache.json` for cached rates

### TrueLayer errors
- Ensure app is "live" not "sandbox"
- Check redirect URI matches exactly
- Check provider code matches your country (e.g., `uk-ob-revolut`)

## Testing

```bash
python -m pytest tests/
```

## Adding Features

### New category
1. Add to `data/categories.json` under expenses or income
2. Add env var `CATEGORY_X_ID` to `.env.example` and `.env`
3. Add to `EXPENSE_CATEGORY_IDS` or `INCOME_CATEGORY_IDS` in `notion_utils.py`

### New Notion field
1. Add property to `properties` dict in `post_transaction_to_notion_internal()`
2. Match Notion's expected format (title, number, select, relation, etc.)

### LLM categorization
Replace `categorize_transaction()` in `category_mapper.py` with an LLM call. Mistral has a free tier.

## Environment Variables

Required:
- `NOTION_TOKEN` - Notion integration token
- `EXPENSES_DB_ID`, `INCOME_DB_ID` - Database IDs
- `PRIMARY_ACCOUNT_ID` - Account relation ID
- `CATEGORY_*_ID` - Category relation IDs
- `TL_CLIENT_ID`, `TL_CLIENT_SECRET`, `TL_REDIRECT_URI` - TrueLayer credentials
- `TL_PROVIDER` - TrueLayer provider code

Optional:
- `CUTOFF_DATE` - Ignore transactions before this date (YYYY-MM-DD)
- `BASE_CURRENCY` - Target currency for conversion (default: USD)
