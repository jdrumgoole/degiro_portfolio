# DEGIRO Portfolio Documentation

Welcome to DEGIRO Portfolio Tracker! This is a desktop application that helps you track and visualize your DEGIRO investment portfolio with beautiful charts and performance analytics.

```{toctree}
---
maxdepth: 2
caption: User Guide
---
getting-started
features
data-providers
advanced-setup
```

```{toctree}
---
maxdepth: 2
caption: For Developers
---
developer-appendix
```

## What Does This Application Do?

This application takes your DEGIRO transaction exports (the Excel files you download from DEGIRO) and creates an interactive dashboard where you can:

✅ **See all your stocks in one place** - View your current holdings with live prices
✅ **Track your gains and losses** - See how much money you've made or lost on each stock
✅ **View beautiful charts** - Interactive price charts showing your buy/sell transactions
✅ **Compare against market indices** - See how your stocks perform vs S&P 500 and Euro Stoxx 50
✅ **Monitor multiple currencies** - Automatic conversion to EUR for stocks in USD, SEK, GBP
✅ **Upload new transactions easily** - Just drag and drop your Excel file into the web interface

**Privacy First**: All data is stored securely on your own computer - nothing is sent to external servers (except to download stock prices).

## Quick Start

**For most users**, we recommend installing from PyPI:

```bash
pip install degiro-portfolio
degiro-portfolio start
```

Then open your browser to http://localhost:8000 and click "Upload Transactions" to get started!

See the [Getting Started](getting-started.md) guide for detailed installation instructions.

## Who Is This For?

- **DEGIRO Investors** who want to track their portfolio performance
- **Anyone** who wants beautiful, interactive charts of their investments
- **People** who prefer to keep their financial data on their own computer
- **Users** looking for more detailed analysis than DEGIRO's built-in tools

No programming knowledge required - just download, install, and use the web interface!

## Indices and Tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
