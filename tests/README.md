# DEGIRO Portfolio Test Suite

Comprehensive test suite using Pytest, Playwright, and FastAPI TestClient.

## Overview

The test suite uses:
- **pytest** with **pytest-xdist** — parallel test execution (2 workers)
- **Playwright** — browser automation for UI/integration tests
- **FastAPI TestClient** — in-process API testing for unit tests
- **pytest-mock** — mocking external API calls (Yahoo Finance, Twelve Data)

### Key Design Decisions

- **No real API calls during tests** (except one yfinance smoke test for AAPL)
- **Master test DB is cached** between runs — only rebuilt when source files change
- **Each xdist worker** gets its own database copy and server port
- **Blocking API endpoints** (`/api/refresh-live-prices`, `/api/update-market-data`) are intercepted at the Playwright browser context level to prevent server hangs

## Test Isolation

The test suite is **completely isolated** from the production application:

- **Dedicated Test Databases**: `tests/.test_data/test_portfolio_gw0.db`, `gw1.db`, etc.
  - Copied from a cached master database for each worker
  - Automatically cleaned up after tests complete
  - Never interferes with production `degiro_portfolio.db`

- **Dedicated Test Servers**: `http://127.0.0.1:8001`, `:8002`, etc.
  - One per xdist worker
  - Started/terminated automatically

- **Isolated Environment Variables**:
  - `DATABASE_URL` set to worker-specific test database
  - Original environment restored after tests

**You can safely run tests while the production server is running!**

## Test Structure

```
tests/
├── conftest.py                      # Fixtures, DB caching, server lifecycle
├── test_main_unit.py               # FastAPI endpoint unit tests (26 tests)
├── test_fetch_prices_unit.py       # Price fetching unit tests
├── test_fetch_indices_unit.py      # Index fetching unit tests
├── test_price_fetchers_unit.py     # Price fetcher provider tests
├── test_ticker_resolver_unit.py    # Ticker resolver unit tests
├── test_portfolio_overview.py      # Portfolio UI tests (Playwright)
├── test_stock_charts.py            # Chart visualization tests (Playwright)
├── test_api_endpoints.py           # API endpoint tests (Playwright)
├── test_interactive_features.py    # Interactive UI tests (Playwright)
├── test_zzz_purge_database.py      # Database purge tests (Playwright, runs last)
└── README.md                       # This file
```

## Running Tests

```bash
# Run complete test suite (parallel, 2 workers)
uv run python -m pytest

# Run with verbose output
uv run python -m pytest -v

# Run a single test file
uv run python -m pytest tests/test_main_unit.py -v

# Run a single test
uv run python -m pytest tests/test_main_unit.py::test_ping_endpoint -v

# Run with coverage
uv run python -m pytest --cov=degiro_portfolio --cov-report=term-missing

# Force rebuild of cached test database
rm -rf tests/.test_data/ && uv run python -m pytest
```

## Test Database Caching

The master test database (`tests/.test_data/master_test_portfolio.db`) is cached between runs:

1. On first run, conftest.py imports `example_data.xlsx`, resolves tickers, and adds 180 days of mock price data
2. A SHA-256 hash of all input files is stored alongside the DB
3. On subsequent runs, if the hash matches, the cached DB is reused (prints "Using cached master test database")
4. If any input file changes (conftest.py, example_data.xlsx, ticker_resolver.py, config.py, import_data.py, database.py), the DB is rebuilt

**Input files that trigger rebuild:**
- `tests/conftest.py`
- `example_data.xlsx`
- `src/degiro_portfolio/ticker_resolver.py`
- `src/degiro_portfolio/config.py`
- `src/degiro_portfolio/import_data.py`
- `src/degiro_portfolio/database.py`

## Test Fixtures

### `test_database` (session-scoped)
Creates worker-specific test database from cached master. Reinitializes the SQLAlchemy engine.

### `server_process` (session-scoped)
Starts a uvicorn subprocess on a worker-specific port (8001+). Waits for `/api/ping` to return 200.

### `context` (module-scoped)
Playwright browser context with route interception for blocking API endpoints.

### `page` (function-scoped)
Navigates to the test server and waits for `.stock-card` elements to load.

### `client` (function-scoped, test_main_unit.py)
FastAPI TestClient for in-process API testing without a real server.

## Test Data

11 stocks from `example_data.xlsx`:

**US Tech Stocks:**
- NVIDIA (NVDA) — 129 shares, 4 transactions
- Microsoft (MSFT) — 30 shares, 3 transactions
- Meta (META) — 68 shares, 2 transactions
- Alphabet (GOOGL) — 57 shares, 2 transactions
- AMD — 97 shares, 3 transactions

**European Tech Stocks:**
- ASML (Netherlands) — 33 shares, 3 transactions
- SAP (Germany) — 75 shares, 2 transactions
- Infineon (Germany) — 400 shares, 3 transactions
- Nokia (Finland) — 900 shares, 2 transactions
- Ericsson (Sweden) — 1400 shares, 2 transactions
- STMicroelectronics (France) — 240 shares, 2 transactions

## Debugging

```bash
# Run single test with output
uv run python -m pytest tests/test_file.py::test_name -v -s

# Playwright visual debugger
PWDEBUG=1 uv run python -m pytest tests/test_file.py::test_name

# Show slowest tests
uv run python -m pytest --durations=10
```
