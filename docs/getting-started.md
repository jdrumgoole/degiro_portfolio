# Getting Started

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Install Dependencies

```bash
uv sync
```

This will install all required dependencies including:
- FastAPI for the web framework
- Pandas for data processing
- yfinance for stock price data
- SQLAlchemy for database management
- Plotly for interactive charts

## Initial Setup

### 1. Configure Data Provider (Optional)

By default, the application uses Yahoo Finance (free, no setup required). For better reliability and coverage, you can configure FMP or Twelve Data:

```bash
# Create .env file
cp .env.example .env

# Edit .env and set your provider
# PRICE_DATA_PROVIDER=fmp
# FMP_API_KEY=your_api_key_here
```

See [Data Providers](data-providers.md) for detailed configuration options.

### 2. Import Transaction Data

You have two options for importing data:

#### Option A: Use Your Own Data

```bash
uv run invoke import-data
```

This will look for `Transactions.xlsx` in the project root. Make sure your Excel file follows the DEGIRO export format.

#### Option B: Use Example Data

```bash
uv run invoke load-demo
```

This imports the included `example_data.xlsx` with sample AI and European tech stocks.

### 3. Fetch Stock Prices

After importing transactions, fetch historical price data:

```bash
uv run invoke fetch-prices
```

This will download historical OHLCV (Open, High, Low, Close, Volume) data for all stocks in your portfolio using your configured data provider.

### 4. Fetch Market Indices

Get market index data for comparison:

```bash
uv run invoke fetch-indices
```

This fetches data for:
- S&P 500 (^GSPC)
- Euro Stoxx 50 (^STOXX50E)

### 5. Start the Server

```bash
./degiro-portfolio start
```

Or using invoke:

```bash
uv run invoke start
```

### 6. Access the Application

Open your browser and navigate to:

```
http://localhost:8000
```

## CLI Commands

The `degiro-portfolio` script provides easy server management:

```bash
./degiro-portfolio start    # Start the server
./degiro-portfolio stop     # Stop the server
./degiro-portfolio restart  # Restart the server
./degiro-portfolio status   # Check server status
```

## Complete Setup (One Command)

For a complete setup in one command:

```bash
# With your own data
uv run invoke setup

# With demo data
uv run invoke demo-setup
```

These commands will:
1. Import transaction data
2. Fetch stock prices
3. Fetch market indices

## Next Steps

- Read about [Features](features.md) to understand what you can do
- Check the [API Reference](api-reference.md) for endpoint documentation
- See [Development](development.md) for contributing guidelines
