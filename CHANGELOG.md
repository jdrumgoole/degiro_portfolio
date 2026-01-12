# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
