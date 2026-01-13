# DEGIRO Portfolio Documentation

Welcome to the DEGIRO Portfolio documentation. This application helps you track and visualize your DEGIRO portfolio with interactive charts and performance analytics.

```{toctree}
---
maxdepth: 2
caption: Contents
---
getting-started
data-providers
features
api-reference
development
testing
deployment
```

## Overview

DEGIRO Portfolio is a web application built with FastAPI that allows you to:

- Import DEGIRO transaction exports from Excel
- Track portfolio performance with real-time data
- Visualize stock prices with interactive charts
- Compare performance against market indices
- Manage your portfolio through a clean web interface

## Quick Start

```bash
# Install dependencies
uv sync

# Setup database and import data
uv run invoke setup

# Start the server
./degiro-portfolio start

# Open browser to http://localhost:8000
```

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite
- **Data Processing**: Pandas, SQLAlchemy
- **Stock Data**: Yahoo Finance (yfinance)
- **Frontend**: Vanilla JavaScript with Plotly.js
- **Package Management**: uv

## Indices and Tables

- {ref}`genindex`
- {ref}`modindex`
- {ref}`search`
