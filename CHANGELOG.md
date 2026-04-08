# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.9] - 2026-04-08

### Changed
- **Default Price Provider**: Switched from Twelve Data to Yahoo Finance as the default price data provider in `.env` — Yahoo requires no API key and provides better European stock coverage
- **Parallel Test Workers**: Reduced pytest-xdist workers from 4 to 2 for optimal performance with fewer server startup overhead

### Fixed
- **Ticker Resolver Crash**: Fixed `AttributeError` in `resolve_ticker_from_isin()` when ISIN is `None`
- **Playwright Test Timeouts**: Fixed all playwright tests timing out because the page's JavaScript called `/api/refresh-live-prices` on load, blocking the single-threaded test server with external API calls for 30+ seconds. Resolved by intercepting blocking API endpoints at the browser context level
- **Test DB Teardown Race**: Fixed workers deleting the shared master test database while other workers were still using it — only the controller now cleans up shared files

### Testing
- **Performance**: Test suite runtime reduced from ~97s to ~62s (36% faster)
- **Database Caching**: Master test database is now cached between runs using SHA-256 hash of input files — only rebuilt when source code or test data changes
- **Mocked API Tests**: Three slow unit tests (`test_update_market_data_endpoint`, `test_refresh_live_prices_endpoint`, `test_ensure_indices_exist_function`) now mock external API calls instead of hitting Yahoo Finance for all 11 stocks
- **New Tests** (7 added, 133 total):
  - `__main__.py` CLI entry point (0% → 86% coverage)
  - `_get_fallback_rate()` exchange rate fallbacks
  - `GET /api/exchange-rates` endpoint
  - `POST /api/purge-database` endpoint via TestClient
  - Uptime string formatting branches
  - Real yfinance smoke test (single AAPL call verifies API integration)
- **Regression Tests for Issue #1**: 8 tests covering `python -m degiro_portfolio` execution, Dutch column auto-detection, English column whitespace handling, and column validation
- **Coverage**: 70% across all modules (141 tests total)
- **Skipped Real API Calls**: Test database creation no longer fetches real stock prices — uses mock data exclusively, eliminating Twelve Data rate limit errors during tests

## [0.3.0] - 2026-01-15

### Added
- **Auto-Refreshing Stock Charts**: Stock price charts now automatically refresh every minute to show the latest data
- **Portfolio Valuation Timeline Extension**: Portfolio Total Value Over Time chart now always extends to today's date, not just the last price update
- **Latest Date Annotation**: Portfolio valuation chart displays the most recent date in the top-right corner for easy reference
- **Automatic Market Index Loading**: Market indices (S&P 500, Euro Stoxx 50) are now automatically fetched when uploading transactions
- **Comprehensive Test Suite**: Added 55+ unit tests across core modules (fetch_prices, fetch_indices, price_fetchers, ticker_resolver, main API endpoints)
- **Test Coverage Reporting**: New invoke tasks for coverage reports (`test-cov`, `test-cov-html`)
- **Test Organization**: Separated unit tests (`test-unit`) from integration tests (`test-integration`) for faster feedback

### Changed
- **Transaction Marker Positioning**: Buy/sell markers now align with candlestick high/low prices instead of transaction prices, fixing alignment issues caused by stock splits
- **Chart Refresh Interval Management**: Each stock chart properly clears previous refresh intervals when switching stocks

### Fixed
- **Portfolio Chart End Date**: Fixed issue where portfolio valuation chart would stop at the last price update instead of extending to today
- **Transaction Marker Alignment**: Fixed misalignment of transaction markers on stocks with splits (e.g., ASML) by positioning markers at actual candlestick prices
- **Chart Auto-Refresh**: Properly manages refresh intervals to prevent memory leaks and duplicate refreshes

### Testing
- **Test Coverage**: Achieved 70% code coverage (116 passing tests)
- **Unit Test Coverage**:
  - main.py: API endpoints and server functionality
  - fetch_indices.py: Market index data fetching
  - fetch_prices.py: Stock price data fetching
  - price_fetchers.py: Price provider implementations
  - ticker_resolver.py: ISIN to ticker mapping
- **Integration Test Coverage**: All browser-based UI tests passing

### Documentation
- Updated README.md with new features (auto-refresh, test coverage, new invoke tasks)
- Enhanced testing section with coverage information and test organization
- Added changelog entry for version 0.3.0

## [0.2.0] - 2026-01-12

### Added
- **Live Price Updates on Stock Cards**: Stock cards now display the latest closing price with daily percentage change (green ▲ for gains, red ▼ for losses)
- **Market Data Status Display**: Shows the most recent market data update date below the "Update Market Data" button
- **Clickable Company Names**: Company names link to Google search for investor relations information
- **Clickable Ticker Symbols**: Yahoo Finance ticker symbols link directly to corresponding Google Finance pages
- **Exchange Information**: Each stock card now displays the exchange where the stock is traded
- **New API Endpoint**: `GET /api/market-data-status` returns the latest market data update date
- **Enhanced Holdings API**: `/api/holdings` now includes latest_price, price_change_pct, and price_date for each stock

### Changed
- **Compact UI Design**: Reduced font sizes throughout the application for more efficient use of screen space
  - Smaller headers, buttons, labels, and values
  - Tighter spacing and padding
  - More stocks visible without scrolling
- **Uniform Transaction Markers**: Buy/sell markers on charts are now consistent size (14px) instead of varying by quantity
- **Improved Marker Visibility**: Transaction markers have better opacity (0.9) and cleaner borders for easier identification
- **Currency-Aware Charts**: Transaction markers only display when currency matches price data currency, preventing misaligned markers
- **Portfolio Summary Condensed**: More compact layout with smaller fonts and reduced padding
- **Update Market Data**: Now only fetches prices for currently held stocks (ignores sold positions)

### Fixed
- **SAAB Currency Correction**: Fixed SAAB AB currency from EUR to SEK to match Stockholm Exchange pricing
- **ASML Ticker Correction**: Updated ASML ticker from "ASML" (NASDAQ/USD) to "ASML.AS" (Amsterdam/EUR) to match transaction currency
- **Transaction Marker Alignment**: Fixed "floating markers" issue where markers appeared detached from price chart due to currency mismatches
- **Upload Error Handling**: Fixed date/time parsing for DEGIRO transaction files with separate Date and Time columns
- **Auto-refresh Clarity**: Improved upload status messages to clearly indicate automatic page refresh after data updates
- **Active Stock Highlight**: Changed from hard-to-read blue gradient to light green background for better text contrast

### Documentation
- Updated README.md with new features and enhanced feature descriptions
- Created CHANGELOG.md to track version history
- Updated API endpoint documentation
- Added notes about clickable links and compact design

### Example Data
- Extended example_data.xlsx to include European Tech Stocks alongside US AI stocks:
  - ASML (Netherlands) - Semiconductor equipment
  - SAP (Germany) - Enterprise software
  - Infineon (Germany) - Semiconductors
  - Nokia (Finland) - Telecommunications
  - Ericsson (Sweden) - Telecommunications
  - STMicroelectronics (France) - Semiconductors
- Total example transactions increased from 14 to 28
- Demonstrates multi-currency support (EUR, USD, SEK) and multi-exchange functionality

## [0.1.0] - 2025-01-XX

### Initial Release
- DEGIRO transaction import from Excel
- Historical stock price fetching via Yahoo Finance
- Interactive candlestick charts with transaction markers
- Investment tranche tracking
- Position value percentage charts
- Market index comparison (S&P 500, Euro Stoxx 50)
- Multi-currency support (EUR, USD, SEK)
- Web-based portfolio viewer
- Upload transactions via web interface
- One-click market data updates
