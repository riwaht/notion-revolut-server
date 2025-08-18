# Revolut → Notion Sync

**Automatically sync your Revolut transactions to Notion with smart categorization and currency conversion!**

This tool connects your Revolut account to Notion, automatically categorizing transactions, converting currencies, and organizing your financial data beautifully.

---

## What It Does

- **Smart Categorization**: Automatically classifies expenses, income, and transfers
- **Multi-Currency Support**: Converts all transactions to USD with real-time exchange rates
- **Cross-Account Sync**: Fetches transactions from ALL your Revolut accounts
- **Dual Database Support**: Separate tracking for expenses and income in Notion
- **OAuth2 Security**: Secure authentication with automatic token refresh
- **Offline Fallback**: Works even when exchange rate APIs are down

---

## Your Notion, Your Way

**Important**: This tool is designed around my specific Notion setup (separate expenses and income databases), but it's easily adaptable to yours!

You can:
- **Use a Single Database**: Combine expenses and income into one database with a "Type" field
- **Different Field Names**: Modify the field mappings to match your database properties
- **Custom Categories**: Add more categorization logic for your specific needs

The code is modular and well-documented, making it easy to customize.

---

## Quick Setup

### 1. **Get Started**
```bash
git clone https://github.com/riwaht/notion-revolut-server.git
cd notion-revolut-server
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 2. **Configure Environment**
Create a `.env` file:
```env
NOTION_TOKEN=your_notion_integration_token
EXPENSES_DB_ID=your_expenses_database_id
INCOME_DB_ID=your_income_database_id
CUTOFF_DATE=2024-01-01  # Optional: only sync transactions after this date
```

### 3. **Set Up Notion**
1. Create integration at [notion.so/my-integrations](https://notion.so/my-integrations)
2. Share your databases with the integration
3. Copy database IDs from the URLs

### 4. **Authenticate & Run**
```bash
python app.py
```

Follow the prompts to complete OAuth2 authentication. Your tokens will be saved automatically.

---

## Usage

### **Manual Sync**
```bash
python app.py
```

### **API Endpoints**
- **GET `/`**: Check server status
- **POST `/sync`**: Trigger manual sync

### **Automated Scheduling**
I run this daily at 9 AM using Make. You can use:
- Cron jobs (Linux/Mac)
- Task Scheduler (Windows)
- Cloud platforms (Make, Zapier, n8n)
- GitHub Actions

---

## Project Structure

```
revolut_server/
├── app.py                          # FastAPI server
├── src/
│   ├── revolut/notion_revolut_connector.py  # Main sync logic
│   ├── notion/                     # Notion API operations
│   └── utils/exchange_utils.py     # Currency conversion
├── data/                           # Cached data
└── tests/                          # Unit tests
```

---

## Testing

```bash
python -m unittest discover -s tests -p "test_*.py"
```

---

## **Data Flow**
1. **Authentication** → Revolut OAuth2 flow
2. **Transaction Fetch** → Get all transactions from Revolut API
3. **Categorization** → Analyze and classify each transaction
4. **Currency Conversion** → Convert to USD using cached rates
5. **Notion Sync** → Create database entries with mapped properties

### **Key Features**
- **Modular Design**: Each component handles a specific responsibility
- **Error Handling**: Graceful failure recovery at each step
- **Caching**: Exchange rates and tokens are cached locally
- **Configurable**: Easy to adapt for different Notion structures

---

## Customization

The modular design makes it easy to:
- **Adapt to your Notion structure** (single database, different fields)
- **Add new features** (webhooks, analytics, notifications)
- **Extend categorization** logic for your needs

---

## Contributing

Found a bug? Want to add a feature? Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

---

## Contact

Have questions or need help setting this up? Feel free to reach out!

- **GitHub Issues**: [Create an issue](https://github.com/riwaht/notion-revolut-server/issues) for bugs or feature requests
- **Email**: Gmail[mailto:riwa.hoteit@gmail.com]
- **LinkedIn**: LinkedIn(https://www.linkedin.com/in/riwa-hoteit-7236b6204/)

---

**Ready to transform your financial tracking? Let's sync!**

