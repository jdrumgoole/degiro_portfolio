# Automatic Ticker Resolution

## Overview

The DEGIRO Portfolio application now automatically resolves ISIN codes to Yahoo Finance ticker symbols, eliminating the need for manual code updates when importing new stocks.

## How It Works

### 1. During Import

When you import transaction data (`example_data.xlsx` or your own `Transactions.xlsx`):

1. The import script (`import_data.py`) extracts stock information including ISIN and currency
2. For each new stock, the ticker resolver (`ticker_resolver.py`) attempts to automatically determine the Yahoo Finance ticker symbol
3. The resolved ticker is stored in the database (`yahoo_ticker` column in the `stocks` table)
4. Future imports of the same stock reuse the stored ticker

### 2. During Price Fetching

When fetching historical prices (`fetch_prices.py`):

1. The script reads the `yahoo_ticker` from the database for each stock
2. If no ticker is found, it attempts automatic resolution on-the-fly
3. Successfully resolved tickers are saved to the database for future use

### 3. Resolution Strategy

The ticker resolver tries multiple strategies in order:

1. **Manual Mapping** - Checks a small fallback list for stocks with known resolution issues
2. **ISIN-based Resolution** - Attempts to derive the ticker from the ISIN code pattern
3. **Name-based Resolution** - Extracts potential ticker from the stock name

## Adding Manual Mappings

While the system aims to resolve tickers automatically, some stocks may require manual mapping. To add a manual mapping:

1. Open `src/degiro_portfolio/ticker_resolver.py`
2. Add an entry to the `MANUAL_TICKER_MAPPING` dictionary:

```python
MANUAL_TICKER_MAPPING: Dict[str, Dict[str, str]] = {
    # ... existing mappings ...

    # Your new stock
    "YOUR_ISIN_CODE": {"CURRENCY": "TICKER_SYMBOL"},

    # Example:
    "GB0005405286": {"GBP": "HSBA.L"},  # HSBC Holdings - London
}
```

## Database Schema

The `stocks` table includes:
- `symbol` - Original symbol extracted from transaction data
- `name` - Full company name
- `isin` - ISIN code (unique identifier)
- `exchange` - Exchange from transaction data
- `currency` - Native trading currency
- **`yahoo_ticker`** - Resolved Yahoo Finance ticker symbol (nullable)

## Viewing Resolved Tickers

To see which tickers have been resolved for your stocks:

```bash
uv run invoke db-info
```

Or query the database directly:

```python
from src.degiro_portfolio.database import SessionLocal, Stock

session = SessionLocal()
stocks = session.query(Stock).all()

for stock in stocks:
    print(f"{stock.name:30} | ISIN: {stock.isin:12} | Ticker: {stock.yahoo_ticker or 'NOT RESOLVED'}")
```

## Manually Setting a Ticker

If automatic resolution fails, you can manually set the ticker in the database:

```python
from src.degiro_portfolio.database import SessionLocal, Stock

session = SessionLocal()

# Find the stock by ISIN
stock = session.query(Stock).filter_by(isin="YOUR_ISIN").first()

if stock:
    stock.yahoo_ticker = "TICKER_SYMBOL"
    session.commit()
    print(f"Updated {stock.name} ticker to {stock.yahoo_ticker}")
```

## Benefits

✅ **No Code Changes Required** - Upload any DEGIRO transaction file without modifying code
✅ **Automatic** - Tickers are resolved and stored during import
✅ **Persistent** - Once resolved, tickers are cached in the database
✅ **Fallback Support** - Manual mappings available for edge cases
✅ **Transparent** - Clear error messages when resolution fails

## Troubleshooting

### "No ticker resolved for Stock Name"

This means automatic resolution failed. Options:

1. Add a manual mapping to `MANUAL_TICKER_MAPPING` in `ticker_resolver.py`
2. Manually set the ticker in the database (see above)
3. Check if the stock trades on Yahoo Finance at all

### "Could not fetch prices for Stock Name"

Even with a resolved ticker, price fetching may fail if:
- The stock is delisted
- Yahoo Finance doesn't have data for this ticker
- The ticker symbol is incorrect

Try verifying the ticker manually at https://finance.yahoo.com

## Migration from Old System

If you were using an older version with hard-coded `ISIN_TO_TICKER` mappings:

1. Delete your old database: `rm degiro_portfolio.db`
2. Re-import your transactions: `uv run invoke import-data`
3. Fetch prices: `uv run invoke fetch-prices`

The new system will automatically resolve and store tickers for all your stocks.
