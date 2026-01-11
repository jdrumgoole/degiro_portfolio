# Code Review: Hard-Coded Values

## Summary

This document identifies hard-coded values in the codebase that could be made configurable for better flexibility and maintainability.

---

## 🔴 Critical Hard-Coded Values (Should Fix)

### 1. **DEGIRO-Specific Excel Column Names**

**Location:** `src/degiro_portfolio/import_data.py`, `src/degiro_portfolio/main.py`

**Hard-coded values:**
```python
'Unnamed: 8'  # Currency column
'Unnamed: 17'  # Transaction ID column
'Price '  # Note the trailing space!
'Reference exchange'
'Transaction and/or third party fees EUR'
'Value (EUR)'
'Total (EUR)'
```

**Issue:** These column names are specific to DEGIRO's export format. If DEGIRO changes their export format or if someone wants to use data from another broker, the entire import process breaks.

**Recommendation:** Create a column mapping configuration:

```python
# config.py
EXCEL_COLUMN_MAPPING = {
    'date': 'Date',
    'time': 'Time',
    'product': 'Product',
    'isin': 'ISIN',
    'exchange': 'Reference exchange',
    'quantity': 'Quantity',
    'price': 'Price ',  # Note the space
    'currency': 'Unnamed: 8',
    'value_eur': 'Value (EUR)',
    'total_eur': 'Total (EUR)',
    'venue': 'Venue',
    'exchange_rate': 'Exchange rate',
    'fees_eur': 'Transaction and/or third party fees EUR',
    'transaction_id': 'Unnamed: 17'
}
```

**Priority:** HIGH - This is the biggest barrier to supporting other brokers

---

### 2. **Market Indices Selection**

**Location:** `src/degiro_portfolio/fetch_indices.py`

**Hard-coded values:**
```python
INDICES = {
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50"
}
```

**Issue:** Users might want different benchmark indices based on their geography or investment strategy.

**Recommendation:** Make indices configurable via config file or allow users to select which indices to track.

```python
# config.py
DEFAULT_INDICES = {
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50",
    # Optional indices users can enable:
    # "^FTSE": "FTSE 100",
    # "^N225": "Nikkei 225",
    # "^DJI": "Dow Jones Industrial Average",
}
```

**Priority:** MEDIUM

---

### 3. **Database File Path**

**Location:** `src/degiro_portfolio/database.py`

**Hard-coded value:**
```python
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "stockchart.db")
```

**Issues:**
- Still uses old name "stockchart.db" instead of "degiro-portfolio.db"
- Path is hard-coded
- Can't easily use a different database location

**Recommendation:**
```python
# Use environment variable with fallback
DB_PATH = os.environ.get(
    'DEGIRO_PORTFOLIO_DB',
    os.path.join(os.path.dirname(__file__), "..", "..", "degiro-portfolio.db")
)
```

**Priority:** MEDIUM (also rename to match project name)

---

## 🟡 Moderate Hard-Coded Values (Consider Fixing)

### 4. **Server Configuration**

**Location:** `degiro-portfolio` CLI script, `tasks.py`, `src/degiro_portfolio/main.py`

**Hard-coded values:**
```python
HOST = "0.0.0.0"
PORT = 8000
```

**Issue:** Users might want to run on a different port or bind to a specific interface.

**Recommendation:** Use environment variables:
```python
HOST = os.environ.get('DEGIRO_PORTFOLIO_HOST', '0.0.0.0')
PORT = int(os.environ.get('DEGIRO_PORTFOLIO_PORT', '8000'))
```

**Priority:** LOW (current defaults are sensible)

---

### 5. **Historical Data Fetch Periods**

**Location:** Multiple files

**Hard-coded values:**
```python
period="5y"  # In fetch_indices.py - 5 years of index data
period="7d"  # In main.py update endpoint - 7 days for updates
```

**Issue:** Users might want more or less historical data based on their needs and API rate limits.

**Recommendation:**
```python
# config.py
INITIAL_PRICE_FETCH_PERIOD = "max"  # Get all available history
INDEX_FETCH_PERIOD = "5y"
UPDATE_FETCH_PERIOD = "7d"
```

**Priority:** LOW (current values work well)

---

### 6. **Default Transaction File Name**

**Location:** `src/degiro_portfolio/import_data.py`

**Hard-coded value:**
```python
excel_file = "Transactions.xlsx"
```

**Issue:** Users might have their file named differently.

**Current behavior:** Actually acceptable - file path is a parameter, and this is just a fallback.

**Priority:** VERY LOW (already has good fallback behavior)

---

## 🟢 Acceptable Hard-Coded Values (No Action Needed)

### 7. **File Extensions**

**Location:** Multiple files

**Values:**
```python
'.xlsx', '.xls'  # Excel file extensions
'.db'  # SQLite database extension
```

**Justification:** These are standard file extensions and shouldn't change.

---

### 8. **Application Title and Version**

**Location:** `src/degiro_portfolio/main.py`

**Value:**
```python
app = FastAPI(title="Stock Price Visualizer", version="0.1.0")
```

**Issue:** Title could be updated to "DEGIRO Portfolio" for consistency.

**Priority:** LOW (cosmetic)

---

## 📋 Recommended Actions

### Immediate (Before Next Release)

1. **Rename database file** from `stockchart.db` to `degiro-portfolio.db`
2. **Update application title** from "Stock Price Visualizer" to "DEGIRO Portfolio"

### Short-term (Next Major Version)

3. **Create configuration system** for Excel column mappings
4. **Make indices configurable**
5. **Add environment variable support** for database path, host, and port

### Long-term (Future Enhancement)

6. **Support multiple broker formats** by allowing different column mapping configs
7. **Allow user-selectable indices** via web interface
8. **Configuration file** (e.g., `config.yaml`) for all settings

---

## Implementation Example: Configuration System

```python
# src/degiro_portfolio/config.py
"""
Configuration management for DEGIRO Portfolio application.
"""
import os
from pathlib import Path

class Config:
    """Application configuration."""

    # Paths
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DB_PATH = os.environ.get(
        'DEGIRO_PORTFOLIO_DB',
        str(PROJECT_ROOT / 'degiro-portfolio.db')
    )
    DEFAULT_TRANSACTIONS_FILE = PROJECT_ROOT / 'Transactions.xlsx'

    # Server
    HOST = os.environ.get('DEGIRO_PORTFOLIO_HOST', '0.0.0.0')
    PORT = int(os.environ.get('DEGIRO_PORTFOLIO_PORT', '8000'))

    # Data fetching
    INITIAL_FETCH_PERIOD = os.environ.get('INITIAL_FETCH_PERIOD', 'max')
    INDEX_FETCH_PERIOD = os.environ.get('INDEX_FETCH_PERIOD', '5y')
    UPDATE_FETCH_PERIOD = os.environ.get('UPDATE_FETCH_PERIOD', '7d')

    # Market indices
    INDICES = {
        "^GSPC": "S&P 500",
        "^STOXX50E": "Euro Stoxx 50",
    }

    # Excel column mappings for DEGIRO format
    DEGIRO_COLUMNS = {
        'date': 'Date',
        'time': 'Time',
        'product': 'Product',
        'isin': 'ISIN',
        'exchange': 'Reference exchange',
        'quantity': 'Quantity',
        'price': 'Price ',  # Note: trailing space in DEGIRO export
        'currency': 'Unnamed: 8',
        'value_eur': 'Value (EUR)',
        'total_eur': 'Total (EUR)',
        'venue': 'Venue',
        'exchange_rate': 'Exchange rate',
        'fees_eur': 'Transaction and/or third party fees EUR',
        'transaction_id': 'Unnamed: 17'
    }

    @classmethod
    def get_column(cls, key):
        """Get mapped column name for a key."""
        return cls.DEGIRO_COLUMNS.get(key, key)
```

Then use it throughout the codebase:
```python
from src.degiro_portfolio.config import Config

# Instead of hard-coding
row['Unnamed: 8']

# Use
row[Config.get_column('currency')]
```

---

## Conclusion

The most critical issue is the **hard-coded DEGIRO column names**, which makes the application tightly coupled to DEGIRO's specific export format. Implementing a configuration system would make the application:

- ✅ More maintainable
- ✅ Easier to adapt to format changes
- ✅ Potentially support other brokers
- ✅ More professional and production-ready

The ticker resolution system you requested we fix was actually the second most critical hard-coded dependency, which we've now addressed successfully.
