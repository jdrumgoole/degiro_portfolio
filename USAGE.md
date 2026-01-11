# DEGIRO Portfolio - Usage Guide

## Starting and Managing the Server

### Using the CLI (Recommended)

The `degiro-portfolio` CLI provides the simplest way to manage the server:

```bash
# Start the server
./degiro-portfolio start

# Check if server is running
./degiro-portfolio status

# Stop the server
./degiro-portfolio stop

# Restart the server
./degiro-portfolio restart
```

### Using Invoke Tasks

Alternatively, you can use invoke tasks:

```bash
# Start the server
uv run invoke start

# Check status
uv run invoke status

# Stop the server
uv run invoke stop

# Restart the server
uv run invoke restart
```

## Data Management

### Import Transaction Data

```bash
# Import transactions from Excel file
uv run invoke import-data
```

This reads `Transactions.xlsx` and populates the SQLite database with:
- Stock metadata (name, ISIN, symbol, exchange)
- Transaction history (date, quantity, price, fees)

### Fetch Stock Prices

```bash
# Fetch historical prices for all holdings
uv run invoke fetch-prices
```

This fetches historical price data from Yahoo Finance for all stocks with current holdings.

### Fetch Market Indices

```bash
# Fetch market index data (S&P 500, Euro Stoxx 50)
uv run invoke fetch-indices
```

This fetches historical data for market indices used for performance comparison.

### Complete Setup

```bash
# Import data and fetch prices in one command
uv run invoke setup
```

## Viewing Database Information

```bash
# Show database statistics and current holdings
uv run invoke db-info
```

Output example:
```
📊 Database Information:
  Stocks: 21
  Transactions: 174
  Price records: 2773

  Current Holdings:
    SAAB AB: 63 shares
    AERCAP HOLDINGS N.V. O: 178 shares
    ASML HOLDING: 31 shares
    LEONARDO SPA: 147 shares
    AIRBUS GROUP: 88 shares
    RHEINMETALL AG: 43 shares
    SIGNATURE BANK: 43 shares
```

## Development

### Development Server with Auto-Reload

```bash
# Start server with auto-reload (automatically restarts on code changes)
uv run invoke dev
```

### View Server Logs

```bash
# Show last 50 lines of logs (default)
uv run invoke logs

# Show last 100 lines
uv run invoke logs --lines=100
```

## Maintenance

### Clean Generated Files

```bash
# Remove PID file, logs, and cache files
uv run invoke clean
```

This removes:
- `.degiro-portfolio.pid` (and legacy `.stockchart.pid`)
- `degiro-portfolio.log` (and legacy `stockchart.log`)
- Python cache files (`__pycache__`, `*.pyc`)

### Reset Everything

```bash
# Stop server and clean all data (including database)
uv run invoke reset
```

⚠️ **Warning**: This removes the database! You'll need to run `invoke setup` again.

## Common Workflows

### First Time Setup

```bash
# 1. Install dependencies
uv sync

# 2. Setup database and import data
uv run invoke setup

# 3. Start the server
./degiro-portfolio start

# 4. Open http://localhost:8000 in your browser
```

### Update Data

**Option 1: Web Interface (Recommended)**
```bash
# 1. Click the "📤 Upload Transactions" button in the web interface
# 2. Select your updated DEGIRO Excel export file
# 3. The page will automatically reload with new data
# 4. Click "📈 Update Market Data" to fetch latest prices
```

**Option 2: Command Line**
```bash
# 1. Update your Transactions.xlsx file with new transactions

# 2. Re-import the data
uv run invoke import-data

# 3. Fetch latest prices
uv run invoke fetch-prices

# 4. Restart the server to see updates
./degiro-portfolio restart
```

### Daily Use

```bash
# Start server
./degiro-portfolio start

# Check status anytime
./degiro-portfolio status

# When done, stop server
./degiro-portfolio stop
```

### Troubleshooting

```bash
# Check if server is running
./degiro-portfolio status

# View recent logs
uv run invoke logs

# If server won't start, clean and restart
uv run invoke clean
./degiro-portfolio start

# If database seems corrupted
uv run invoke reset
uv run invoke setup
./degiro-portfolio start
```

## Available Invoke Tasks

To see all available tasks:

```bash
uv run invoke --list
```

Output:
```
Available tasks:

  clean           Clean generated files.
  db-info         Show database information.
  dev             Start development server with auto-reload.
  fetch-indices   Fetch market index data (S&P 500, Euro Stoxx 50).
  fetch-prices    Fetch historical stock prices.
  format-code     Format code.
  help-tasks      Show available tasks.
  import-data     Import transaction data from Excel.
  install         Install dependencies.
  lint            Run linting checks.
  logs            Show server logs.
  reset           Reset everything (stop server, clean all data).
  restart         Restart the DEGIRO Portfolio server.
  setup           Complete setup: import data and fetch prices.
  start           Start the DEGIRO Portfolio server.
  status          Check server status.
  stop            Stop the DEGIRO Portfolio server.
  test            Run tests.
```

## Server Information

- **Default URL**: http://localhost:8000
- **Host**: 0.0.0.0 (accessible from network)
- **Port**: 8000
- **PID File**: `.degiro-portfolio.pid`
- **Log File**: `degiro-portfolio.log`
- **Database**: `stockchart.db`

## Tips

1. **Server must be running**: Make sure to start the server before accessing the web interface
2. **Check status first**: Use `./degiro-portfolio status` to check if server is running
3. **View logs for errors**: If something isn't working, check `uv run invoke logs`
4. **Update data regularly**: Use the "📈 Update Market Data" button in the web interface or run `invoke fetch-prices`
5. **Use dev mode for development**: When making code changes, use `invoke dev` for auto-reload
