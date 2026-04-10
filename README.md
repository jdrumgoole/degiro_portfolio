# DEGIRO Portfolio Tracker

A desktop application that helps you track and visualize your DEGIRO investment portfolio with beautiful charts and performance metrics.

[![Documentation](https://readthedocs.org/projects/degiro-portfolio/badge/?version=latest)](https://degiro-portfolio.readthedocs.io/en/latest/) [![PyPI](https://img.shields.io/pypi/v/degiro_portfolio)](https://pypi.org/project/degiro_portfolio/)

**[Full Documentation](https://degiro-portfolio.readthedocs.io/)** | **[Release Notes](https://degiro-portfolio.readthedocs.io/en/latest/release-notes.html)**

![Portfolio Dashboard](https://raw.githubusercontent.com/jdrumgoole/degiro_portfolio/main/screenshots/portfolio-overview.png)
*Your portfolio at a glance with live prices and performance charts*

## What Does This Do?

This application takes your DEGIRO transaction exports (the Excel files you download from DEGIRO) and creates an interactive dashboard where you can:

- **See all your stocks in one place** - View your current holdings with live prices
- **Track your gains and losses** - See how much money you've made or lost on each stock
- **View beautiful charts** - Interactive price charts showing your buy/sell transactions
- **Compare against market indices** - See how your stocks perform vs S&P 500 and Euro Stoxx 50
- **Monitor multiple currencies** - Automatic conversion to EUR for stocks in USD, SEK, GBP
- **Upload new transactions easily** - Just click and upload your Excel file

All data is stored securely on your own computer - nothing is sent to external servers.

## Screenshots

### Portfolio Dashboard
![Portfolio Dashboard](https://raw.githubusercontent.com/jdrumgoole/degiro_portfolio/main/screenshots/dashboard-with-buttons.png)
*Main dashboard showing portfolio summary, action buttons, and stock holdings*

### Individual Stock View
![Stock Detail - NVIDIA](https://raw.githubusercontent.com/jdrumgoole/degiro_portfolio/main/screenshots/stock-detail-nvidia.png)
*Detailed charts showing NVIDIA price history, buy transactions, position value %, and market comparison*

## Quick Start

### 1. Install

```bash
pip install degiro_portfolio
```

You need Python 3.10 or newer ([download here](https://www.python.org/downloads/)).

### 2. Launch

```bash
python -m degiro_portfolio --desktop
```

The application opens in a native window. No browser needed - the server starts and stops automatically with the window.

### 3. Upload Your Transactions

1. Export your transactions from [DEGIRO](https://trader.degiro.nl/trader/#/transactions) (Transactions -> Export as CSV or Excel)
2. Click **Upload Transactions** in the app
3. Select your file (.csv or .xlsx)

The app automatically downloads stock prices and displays your portfolio.

## Alternative: Web Server Mode

If you prefer to use a browser, you can run the application as a web server:

```bash
pip install degiro_portfolio
python -m degiro_portfolio
```

Then open `http://localhost:8000` in your browser.

**Mac/Linux** also supports the CLI:
```bash
degiro_portfolio start    # Start the server
degiro_portfolio stop     # Stop the server
degiro_portfolio status   # Check if running
```

**Windows**: Use `python -m degiro_portfolio` for all commands.

## Using the Application

### Uploading Transactions

1. **Export from DEGIRO:**
   - Log in at [trader.degiro.nl/trader/#/transactions](https://trader.degiro.nl/trader/#/transactions)
   - Set your date range and click **Export**
   - Choose CSV or Excel format
   - All DEGIRO languages are supported (English, Dutch, German, etc.)

2. **Upload to the Application:**
   - Click the **Upload Transactions** button
   - Select your DEGIRO file (.csv or .xlsx)
   - Wait for the upload to complete

### Updating Stock Prices

Click the **Update Market Data** button to refresh all stock prices. Prices are fetched from Yahoo Finance (free, no API key needed).

### Clearing All Data

Click **Purge All Data** to start fresh. This permanently deletes all stored data.

## Understanding Your Portfolio

### Stock Cards
Each stock shows:
- **Company name** - Click to search for investor relations info
- **Number of shares** you own
- **Current price** with daily change
- **Position value** in EUR
- **Ticker symbol** - Click to view on Google Finance

### Charts
Click any stock card to see:
1. **Price Chart** - Historical prices with your buy/sell transactions marked
2. **Position Value %** - Shows if you're profitable (above 100% = profit)
3. **Investment Tranches** - Performance of each individual purchase
4. **Market Comparison** - How your stock compares to S&P 500 and Euro Stoxx 50

## Features

- Native desktop app with embedded web view (Mac, Windows, Linux)
- Import DEGIRO transaction exports (English and Dutch)
- Automatic historical price downloads via Yahoo Finance
- Live exchange rate conversion (EUR, USD, SEK, GBP)
- Interactive candlestick charts with transaction markers
- Portfolio performance tracking
- Market index comparison (S&P 500, Euro Stoxx 50)
- Multi-currency support with automatic conversion
- One-click market data updates

## Data Privacy

All your financial data stays on your computer:
- Data stored locally in `degiro_portfolio.db`
- Only connects to internet for stock prices
- Does NOT send your transaction data anywhere
- Does NOT require creating an account

## Troubleshooting

### The app won't start
- Make sure Python 3.10+ is installed: `python --version`
- On Windows: use `python -m degiro_portfolio --desktop`
- If port 8000 is busy: `python -m degiro_portfolio --desktop --port 8001`

### My stocks don't show prices
- Click "Update Market Data"
- Check your internet connection

### The upload fails
- Make sure you're uploading a DEGIRO transaction export (.csv or .xlsx)
- All DEGIRO languages are supported

## Getting Help

- **[Full Documentation](https://degiro-portfolio.readthedocs.io/)** — installation, features, advanced setup
- **[Release Notes](https://degiro-portfolio.readthedocs.io/en/latest/release-notes.html)** — what's new in each version
- **[GitHub Issues](https://github.com/jdrumgoole/degiro_portfolio/issues)** — report bugs or request features

## License

See LICENSE file for details.
