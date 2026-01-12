# DEGIRO Portfolio Test Suite

Comprehensive Playwright-based test suite for the DEGIRO Portfolio application.

## Overview

The test suite uses:
- **pytest** - Test framework
- **Playwright** - Browser automation for UI testing
- **httpx** - HTTP client for API testing

### Test Isolation

The test suite is **completely isolated** from the production application:

- **Dedicated Test Database**: `tests/.test_data/test_portfolio.db`
  - Created fresh for each test session
  - Automatically cleaned up after tests complete
  - Never interferes with production `degiro-portfolio.db`

- **Dedicated Test Server**: `http://127.0.0.1:8001`
  - Runs on port **8001** (production uses **8000**)
  - Started automatically during test session
  - Terminated automatically after tests complete

- **Isolated Environment Variables**:
  - `DATABASE_URL` set to test database path
  - Original environment restored after tests
  - No cross-contamination with production settings

**You can safely run tests while the production server is running!**

## Test Structure

```
tests/
├── conftest.py                      # Pytest fixtures and configuration
├── test_portfolio_overview.py       # Portfolio page UI tests
├── test_stock_charts.py            # Stock chart visualization tests
├── test_api_endpoints.py           # API endpoint tests
├── test_interactive_features.py    # Interactive UI feature tests
└── README.md                       # This file
```

## Running Tests

### Run All Tests

```bash
cd /Users/jdrumgoole/GIT/degiro-portfolio
uv run pytest tests/ -v
```

### Run Specific Test File

```bash
uv run pytest tests/test_portfolio_overview.py -v
```

### Run Single Test

```bash
uv run pytest tests/test_portfolio_overview.py::test_page_loads -v
```

### Run with Output

```bash
uv run pytest tests/ -v -s
```

## Test Fixtures

### `test_database`
- **Scope**: session
- **Purpose**: Creates a test database with example data
- **Data**: Uses `example_data.xlsx` (11 stocks, 28 transactions)
- **Cleanup**: Removes test database after session

### `server_process`
- **Scope**: session
- **Purpose**: Starts FastAPI server on port 8001 for testing
- **Dependencies**: Requires `test_database`
- **Cleanup**: Terminates server after session

### `browser`
- **Scope**: session
- **Purpose**: Creates Playwright Chromium browser instance
- **Mode**: Headless

### `context`
- **Scope**: function
- **Purpose**: Creates new browser context for each test
- **Viewport**: 1920x1080

### `page`
- **Scope**: function
- **Purpose**: Creates new page and navigates to app
- **Dependencies**: Uses `context` and `server_process`

### `expected_stocks`
- **Scope**: function
- **Purpose**: Provides expected stock data for validation
- **Data**: 11 stocks (5 US + 6 European)

## Test Coverage

### Portfolio Overview Tests (17 tests)
- Page loading and title
- Stock card display and information
- Latest prices and daily changes
- Ticker symbols and exchanges
- Clickable links (company names, tickers)
- Market data status
- Update button
- Portfolio summary
- Responsive design

### Stock Charts Tests (15 tests)
- Chart loading and rendering
- Multiple chart types
- Candlestick data
- Transaction markers
- Interactive features
- Axis labels
- Stock switching
- European stock support
- SEK currency support

### API Endpoint Tests (14 tests)
- Holdings endpoint
- Market data status
- Stock prices
- Transactions
- Chart data
- Portfolio performance
- Error handling
- Data validation

### Interactive Features Tests (19 tests)
- Button interactions
- Link behavior
- Stock selection
- Active states
- Visual feedback
- Price formatting
- Color coding
- Responsiveness

## Test Database

The test suite creates a temporary SQLite database (`test_portfolio.db`) with:
- 11 stocks from `example_data.xlsx`
- 28 transactions (14 US + 14 European)
- Historical price data fetched from Yahoo Finance
- Market index data (S&P 500, Euro Stoxx 50)

**Note**: Database creation includes real API calls to Yahoo Finance, which can take 30-60 seconds.

## Known Issues

1. **Slow Initial Run**: First test run fetches real price data (~30-60s)
2. **Ticker Resolution**: Some European stocks may not resolve tickers automatically
3. **Flaky Tests**: Network-dependent tests may occasionally timeout
4. **Display Issues**: Some tests expect specific UI elements that may vary

## Test Data

Example stocks included in test database:

**US Tech Stocks:**
- NVIDIA (NVDA) - 129 shares, 4 transactions
- Microsoft (MSFT) - 30 shares, 3 transactions
- Meta (META) - 68 shares, 2 transactions
- Alphabet (GOOGL) - 57 shares, 2 transactions
- AMD - 97 shares, 3 transactions

**European Tech Stocks:**
- ASML (Netherlands) - 33 shares, 3 transactions
- SAP (Germany) - 75 shares, 2 transactions
- Infineon (Germany) - 400 shares, 3 transactions
- Nokia (Finland) - 900 shares, 2 transactions
- Ericsson (Sweden) - 1400 shares, 2 transactions
- STMicroelectronics (France) - 240 shares, 2 transactions

## Debugging Tests

### View Browser Actions

Run tests in headed mode:
```bash
uv run pytest tests/ --headed
```

### Take Screenshots

Add to test:
```python
page.screenshot(path="debug.png")
```

### Print Page Content

Add to test:
```python
print(page.content())
```

### Slow Down Actions

```python
page.set_default_timeout(5000)  # 5 second timeout
```

## CI/CD Integration

For CI environments, ensure:
1. Playwright browsers are installed: `uv run playwright install chromium`
2. Set headless mode (default)
3. Handle network timeouts gracefully
4. Clean up test database after run

## Contributing

When adding new tests:
1. Use descriptive test names
2. Add docstrings explaining what is tested
3. Use appropriate fixtures
4. Clean up any test data
5. Update this README if adding new test categories
