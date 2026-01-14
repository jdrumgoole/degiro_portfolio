# Getting Started

## Installation

Install the package from PyPI:

```bash
pip install degiro-portfolio
```

Or with uv:

```bash
uv pip install degiro-portfolio
```

## Quick Start

### 1. Start the Server

```bash
degiro-portfolio start
```

The server will start on http://localhost:8000

### 2. Open in Your Browser

Navigate to http://localhost:8000 in your web browser.

### 3. Upload Your Transaction Data

#### Exporting from DEGIRO

1. Log in to your DEGIRO account
2. Go to **Portfolio** → **Transactions**
3. Set your date range (e.g., "All time" or specific period)
4. Click **Export** and select **Excel** format
5. Save the file (typically named `Transactions.xlsx`)

#### Uploading to the Application

1. Click the **📤 Upload Transactions** button in the top-right corner of the application
2. Select your DEGIRO `Transactions.xlsx` file
3. Click **Upload**

The application will automatically:
- Import all transactions
- Fetch historical price data for your stocks
- Update live market prices
- Fetch market index data (S&P 500, Euro Stoxx 50) for comparison

**That's it!** Your portfolio is now ready to view with:
- Interactive price charts
- Transaction history
- Performance metrics
- Market index comparisons

### 4. Update Market Data

Click the **📈 Update Market Data** button to refresh live prices and latest market data.

## Supported Transaction Format

The application expects DEGIRO's standard Excel export format with columns:
- Date
- Time
- Product (stock name)
- ISIN
- Exchange
- Quantity
- Price
- Local value
- Value (EUR)
- Exchange rate
- Transaction and/or third

## Optional: Configure Data Provider

By default, the application uses **Twelve Data** for stock prices. You can configure alternative providers:

### Available Providers

1. **Twelve Data** (default) - Best for European stocks
2. **Yahoo Finance** - Free, excellent coverage, no API key required
3. **FMP (Financial Modeling Prep)** - Requires paid API key

### Configuration

Create a `.env` file in your working directory:

```bash
# Choose provider: 'twelvedata', 'yahoo', or 'fmp'
PRICE_DATA_PROVIDER=yahoo

# API keys (if using paid providers)
TWELVEDATA_API_KEY=your_key_here
FMP_API_KEY=your_key_here
```

**Note:** Yahoo Finance requires no configuration and provides excellent coverage for most stocks.

See [Data Providers](data-providers.md) for detailed information about each provider.

## Server Management

Start/stop the server using these commands:

```bash
degiro-portfolio start     # Start the server
degiro-portfolio stop      # Stop the server
degiro-portfolio restart   # Restart the server
degiro-portfolio status    # Check if server is running
```

## Next Steps

- **[Features](features.md)** - Explore all available features
- **[Data Providers](data-providers.md)** - Learn about price data sources
- **[API Reference](api-reference.md)** - API endpoint documentation
- **[Development](development.md)** - Contributing guidelines

## Troubleshooting

### No price data showing
- Make sure you clicked "Upload Transactions" - this triggers automatic price fetching
- Click "Update Market Data" to refresh prices
- Check your internet connection

### Stock not found
- Some stocks may not be available in all data providers
- Try switching to Yahoo Finance (no API key needed)
- Check that the ISIN in your transactions matches the stock listing

### Upload failed
- Verify you're using DEGIRO's Excel export format
- Check that the file is not corrupted
- Ensure the file contains valid transaction data
