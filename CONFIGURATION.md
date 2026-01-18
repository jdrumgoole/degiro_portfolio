# Configuration System

## Overview

The DEGIRO Portfolio application uses a centralized configuration system that makes it easy to:
- Adapt to different broker export formats
- Customize server settings
- Configure data fetching behavior
- Support different market indices

All configuration is managed through `src/degiro_portfolio/config.py`.

## Configuration File

The configuration system is implemented in `src/degiro_portfolio/config.py` and provides:

### 1. Excel Column Mappings

The most important configuration is the Excel column mapping, which translates logical column names to actual column names in broker exports.

**Current mapping (DEGIRO format):**
```python
DEGIRO_COLUMNS = {
    # Transaction identification
    'date': 'Date',
    'time': 'Time',
    'transaction_id': 'Unnamed: 17',

    # Stock information
    'product': 'Product',
    'isin': 'ISIN',
    'exchange': 'Reference exchange',

    # Transaction details
    'quantity': 'Quantity',
    'price': 'Price ',  # NOTE: Trailing space in DEGIRO export!
    'currency': 'Unnamed: 8',  # NOTE: Unnamed column
    'venue': 'Venue',

    # Financial values (in EUR)
    'value_eur': 'Value EUR',
    'total_eur': 'Total EUR',
    'fees_eur': 'Transaction and/or third party fees EUR',
    'exchange_rate': 'Exchange rate',
}
```

**Usage in code:**
```python
from src.degiro_portfolio.config import get_column

# Instead of hard-coding:
currency = row['Unnamed: 8']

# Use:
currency = row[get_column('currency')]
```

### 2. Environment Variables

The following settings can be customized via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEGIRO_PORTFOLIO_DB` | `degiro_portfolio.db` | Database file path |
| `DEGIRO_PORTFOLIO_HOST` | `0.0.0.0` | Server bind address |
| `DEGIRO_PORTFOLIO_PORT` | `8000` | Server port |
| `INITIAL_FETCH_PERIOD` | `max` | How far back to fetch stock prices |
| `INDEX_FETCH_PERIOD` | `5y` | How far back to fetch index data |
| `UPDATE_FETCH_PERIOD` | `7d` | Update window for market data |

**Example:**
```bash
export DEGIRO_PORTFOLIO_PORT=9000
export DEGIRO_PORTFOLIO_DB=/path/to/my/database.db
uv run python -m src.degiro_portfolio.main
```

### 3. Market Indices

Configure which benchmark indices to track:

```python
INDICES = {
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50",
}
```

To add more indices, edit `config.py`:
```python
INDICES = {
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50",
    "^FTSE": "FTSE 100",  # Add this
    "^N225": "Nikkei 225",  # And this
}
```

### 4. Ignored Stocks

Exclude specific stocks from import (collapsed companies, delisted stocks, etc.):

```python
IGNORED_STOCKS = {
    'US82669G1040',  # Signature Bank (collapsed March 2023)
    # Add more ISINs here as needed
}
```

**How it works:**
- Transactions for ignored stocks are **skipped during import**
- Works for both CLI import (`invoke import-data`) and web upload
- Useful for excluding collapsed, delisted, or unwanted stocks
- Prevents cluttering your portfolio with defunct companies

**To add stocks to ignore:**
1. Find the ISIN code for the stock
2. Add it to the `IGNORED_STOCKS` set in `config.py`
3. Re-import your transactions

Example:
```python
IGNORED_STOCKS = {
    'US82669G1040',  # Signature Bank
    'US0378331005',  # Example: Another stock
}
```

## Supporting Other Brokers

The configuration system makes it easy to support transaction data from other brokers.

### Example: Interactive Brokers

1. **Create a new column mapping in `config.py`:**

```python
INTERACTIVE_BROKERS_COLUMNS = {
    'date': 'Date/Time',
    'time': 'Time',
    'transaction_id': 'Order ID',
    'product': 'Symbol',
    'isin': 'ISIN',
    'exchange': 'Exchange',
    'quantity': 'Quantity',
    'price': 'Price',
    'currency': 'Currency',
    'venue': 'Venue',
    'value_eur': 'Total (EUR)',
    'total_eur': 'Net Total (EUR)',
    'fees_eur': 'Commission (EUR)',
    'exchange_rate': 'FX Rate',
}
```

2. **Switch the active mapping:**

```python
# Change this line in config.py:
ACTIVE_COLUMN_MAPPING = INTERACTIVE_BROKERS_COLUMNS
```

3. **Import your Interactive Brokers transaction file:**

```bash
uv run invoke import-data --file=ib_transactions.xlsx
```

### Example: Trading 212

```python
TRADING_212_COLUMNS = {
    'date': 'Time',
    'time': 'Time',
    'transaction_id': 'ID',
    'product': 'Name',
    'isin': 'ISIN',
    'exchange': 'Exchange',
    'quantity': 'No. of shares',
    'price': 'Price / share',
    'currency': 'Currency (Price / share)',
    'venue': 'Exchange',
    'value_eur': 'Total (EUR)',
    'total_eur': 'Total (EUR)',
    'fees_eur': 'Charge amount (EUR)',
    'exchange_rate': 'FX',
}

ACTIVE_COLUMN_MAPPING = TRADING_212_COLUMNS
```

## Configuration API

### Config Class Methods

#### `Config.get_column(key: str) -> str`

Get the actual Excel column name for a logical column key.

```python
from src.degiro_portfolio.config import Config

# Returns 'Unnamed: 8' for DEGIRO format
currency_col = Config.get_column('currency')
```

#### `Config.validate_excel_columns(df_columns: list) -> tuple[bool, list]`

Validate that a DataFrame has all required columns.

```python
import pandas as pd
from src.degiro_portfolio.config import Config

df = pd.read_excel('transactions.xlsx')
is_valid, missing = Config.validate_excel_columns(df.columns.tolist())

if not is_valid:
    print(f"Missing columns: {missing}")
```

#### `Config.get_required_excel_columns() -> list`

Get list of actual Excel column names that are required.

```python
from src.degiro_portfolio.config import Config

required = Config.get_required_excel_columns()
# Returns: ['Date', 'Product', 'ISIN', 'Reference exchange', ...]
```

#### `Config.get_column_mapping_name() -> str`

Get the name of the active column mapping.

```python
from src.degiro_portfolio.config import Config

mapping = Config.get_column_mapping_name()
# Returns: 'DEGIRO' or 'CUSTOM'
```

## Convenience Functions

For simpler code, use the module-level convenience function:

```python
from src.degiro_portfolio.config import get_column

# This is shorthand for Config.get_column()
currency_col = get_column('currency')
```

## Required Columns

The following columns must be present in any transaction file:

- `date` - Transaction date
- `product` - Stock name/description
- `isin` - International Securities Identification Number
- `exchange` - Stock exchange
- `quantity` - Number of shares
- `price` - Price per share
- `currency` - Transaction currency
- `value_eur` - Value in EUR
- `total_eur` - Total in EUR

## Migration from Old System

If you were using an older version with hard-coded column names:

1. **No changes needed!** The configuration system is backward compatible with DEGIRO exports.

2. **Optional:** If you customized column names in the old code:
   - Move your customizations to `config.py`
   - Create a new column mapping
   - Set `ACTIVE_COLUMN_MAPPING` to your new mapping

## Best Practices

### 1. Never Hard-Code Column Names

❌ **Don't do this:**
```python
currency = row['Unnamed: 8']
product = row['Product']
```

✅ **Do this:**
```python
from src.degiro_portfolio.config import get_column

currency = row[get_column('currency')]
product = row[get_column('product')]
```

### 2. Validate Input Early

Always validate Excel files before processing:

```python
from src.degiro_portfolio.config import Config

df = pd.read_excel(file_path)
is_valid, missing = Config.validate_excel_columns(df.columns.tolist())

if not is_valid:
    raise ValueError(f"Missing columns: {missing}")
```

### 3. Use Environment Variables for Deployment

For production deployments, use environment variables instead of modifying `config.py`:

```bash
# .env file
DEGIRO_PORTFOLIO_DB=/var/data/portfolio.db
DEGIRO_PORTFOLIO_HOST=127.0.0.1
DEGIRO_PORTFOLIO_PORT=8080
```

## Troubleshooting

### "Missing required columns" Error

**Problem:** The Excel file doesn't have the expected columns.

**Solutions:**
1. Check that you're using a DEGIRO export file
2. Verify the export format hasn't changed
3. If using a different broker, create a custom column mapping

### "KeyError" when Reading Excel

**Problem:** Code is trying to access a column that doesn't exist.

**Solutions:**
1. Make sure you're using `get_column()` everywhere
2. Check that `DEGIRO_COLUMNS` mapping is correct
3. Verify the Excel file format

### Different Broker Format Not Working

**Problem:** Created a new column mapping but import fails.

**Solutions:**
1. Verify all required columns are mapped
2. Check for typos in column names
3. Use `Config.validate_excel_columns()` to debug
4. Ensure `ACTIVE_COLUMN_MAPPING` points to your new mapping

## Future Enhancements

Planned improvements to the configuration system:

1. **Runtime broker selection** - Choose broker format without editing code
2. **YAML/JSON config files** - External configuration files
3. **Web-based configuration** - Configure via web interface
4. **Auto-detection** - Automatically detect broker format from file structure

## See Also

- [TICKER_RESOLUTION.md](TICKER_RESOLUTION.md) - How ticker resolution works
- [CODE_REVIEW_HARDCODED_VALUES.md](CODE_REVIEW_HARDCODED_VALUES.md) - Review of hard-coded values
- [USAGE.md](USAGE.md) - General usage guide
