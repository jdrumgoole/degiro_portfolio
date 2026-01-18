# Developer Appendix

This appendix contains technical documentation for developers who want to contribute to the project, understand the codebase, or integrate with the API.

**Note**: This section is for programmers and technical users. If you're just using the application, you don't need to read this.

---

## Table of Contents

1. [API Reference](#api-reference)
2. [Development Guide](#development-guide)
3. [Testing Guide](#testing-guide)
4. [Deployment Guide](#deployment-guide)

---

## API Reference

### Overview

The DEGIRO Portfolio application provides a RESTful API built with FastAPI. All endpoints return JSON data unless otherwise specified.

Base URL: `http://localhost:8000`

### Interactive Documentation

FastAPI provides interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

#### Portfolio Endpoints

##### GET /api/holdings

Get all current stock holdings with latest prices and exchange rates.

**Response:**
```json
{
  "success": true,
  "holdings": [
    {
      "id": 1,
      "name": "NVIDIA Corporation",
      "symbol": "NVDA",
      "isin": "US67066G1040",
      "currency": "USD",
      "total_quantity": 129.0,
      "latest_price": 140.15,
      "position_value_eur": 15234.50,
      "daily_change_percent": 2.34,
      "transaction_count": 4,
      "exchange": "NASDAQ"
    }
  ]
}
```

##### GET /api/portfolio-performance

Get portfolio-wide performance metrics.

**Response:**
```json
{
  "total_value": 125000.50,
  "total_cost": 100000.00,
  "total_gain_loss": 25000.50,
  "gain_loss_percent": 25.0
}
```

##### GET /api/exchange-rates

Get current exchange rates for currency conversion.

**Response:**
```json
{
  "success": true,
  "rates": {
    "USD": 1.09,
    "SEK": 0.093,
    "GBP": 1.27
  }
}
```

#### Stock Endpoints

##### GET /api/stock/{stock_id}/prices

Get historical price data for a specific stock.

**Parameters:**
- `stock_id` (path): Stock ID

**Response:**
```json
[
  {
    "date": "2024-01-15",
    "open": 138.50,
    "high": 141.20,
    "low": 137.80,
    "close": 140.15,
    "volume": 45234567
  }
]
```

##### GET /api/stock/{stock_id}/transactions

Get transaction history for a specific stock.

**Parameters:**
- `stock_id` (path): Stock ID

**Response:**
```json
[
  {
    "id": 1,
    "date": "2024-01-15",
    "quantity": 50.0,
    "price": 135.00,
    "fees": 2.50,
    "transaction_type": "Buy",
    "currency": "USD"
  }
]
```

##### GET /api/stock/{stock_id}/chart-data

Get combined data for chart visualization including prices, transactions, position percentage, and tranches.

**Parameters:**
- `stock_id` (path): Stock ID

**Response:**
```json
{
  "prices": [...],
  "transactions": [...],
  "position_percentage": [...],
  "tranches": [...]
}
```

#### Market Data Endpoints

##### GET /api/market-data-status

Get the most recent market data update timestamp.

**Response:**
```json
{
  "last_update": "2024-01-15T16:00:00",
  "status": "up_to_date"
}
```

##### POST /api/update-market-data

Fetch latest market data for all stocks and indices.

**Request:** No body required

**Response:**
```json
{
  "status": "success",
  "stocks_updated": 10,
  "indices_updated": 2
}
```

#### Upload Endpoints

##### POST /api/upload-transactions

Upload a new transaction Excel file.

**Request:**
- Content-Type: `multipart/form-data`
- Body: Form data with file field

**Response:**
```json
{
  "status": "success",
  "stocks_imported": 5,
  "transactions_imported": 23
}
```

##### POST /api/purge-database

Delete all data from the database (stocks, transactions, prices, indices).

**WARNING**: This is a destructive operation that cannot be undone.

**Request:** No body required

**Response:**
```json
{
  "success": true,
  "message": "Database purged successfully",
  "deleted": {
    "stocks": 10,
    "transactions": 45,
    "stock_prices": 2300,
    "indices": 2,
    "index_prices": 1200
  }
}
```

#### Index Endpoints

##### GET /api/indices

Get all market indices.

**Response:**
```json
[
  {
    "id": 1,
    "symbol": "^GSPC",
    "name": "S&P 500"
  },
  {
    "id": 2,
    "symbol": "^STOXX50E",
    "name": "Euro Stoxx 50"
  }
]
```

##### GET /api/index/{index_id}/prices

Get historical price data for a market index.

**Parameters:**
- `index_id` (path): Index ID

**Response:**
```json
[
  {
    "date": "2024-01-15",
    "close": 4850.25
  }
]
```

### Error Responses

All endpoints may return error responses in the following format:

```json
{
  "detail": "Error message description"
}
```

Common HTTP status codes:
- `200 OK`: Success
- `400 Bad Request`: Invalid parameters
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

### Python Client Example

```python
import httpx

# Get all holdings
response = httpx.get("http://localhost:8000/api/holdings")
holdings = response.json()

# Get stock prices
stock_id = 1
response = httpx.get(f"http://localhost:8000/api/stock/{stock_id}/prices")
prices = response.json()

# Update market data
response = httpx.post("http://localhost:8000/api/update-market-data")
result = response.json()

# Upload transactions
with open("Transactions.xlsx", "rb") as f:
    files = {"file": f}
    response = httpx.post("http://localhost:8000/api/upload-transactions", files=files)
    result = response.json()
```

### Rate Limiting

Currently, there are no rate limits on the API. However, be mindful of:

- Yahoo Finance rate limits when fetching prices
- Database performance with large datasets
- Concurrent request handling

---

## Development Guide

### Development Environment

#### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Git

#### Setup Development Environment

```bash
# Clone the repository
git clone <repository-url>
cd degiro_portfolio

# Install dependencies including dev dependencies
uv sync

# Install Playwright browsers for testing
uv run playwright install chromium --with-deps
```

### Project Structure

```
degiro_portfolio/
├── src/degiro_portfolio/      # Main application code
│   ├── __init__.py
│   ├── config.py             # Configuration management
│   ├── database.py           # Database models and configuration
│   ├── import_data.py        # Transaction import logic
│   ├── fetch_prices.py       # Price fetching logic
│   ├── fetch_indices.py      # Index data fetching
│   ├── price_fetchers.py     # Price data provider implementations
│   ├── ticker_resolver.py    # ISIN to ticker resolution
│   ├── main.py               # FastAPI application
│   └── static/
│       └── index.html        # Frontend interface
├── tests/                    # Test suite
│   ├── conftest.py          # Pytest fixtures
│   ├── test_*.py            # Test files
│   └── README.md
├── docs/                    # Sphinx documentation
├── .github/                 # GitHub Actions workflows
├── tasks.py                 # Invoke tasks
├── degiro_portfolio         # CLI script
└── pyproject.toml          # Project configuration
```

### Development Workflow

#### Starting Development Server

The development server includes auto-reload for rapid iteration:

```bash
uv run invoke dev
```

This starts uvicorn with `--reload` flag, which automatically restarts when code changes.

#### Making Changes

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**

3. **Run tests**:
   ```bash
   uv run invoke test
   ```

4. **Commit changes**:
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

### Invoke Tasks

Common development tasks:

```bash
# Server Management
uv run invoke start          # Start the server
uv run invoke stop           # Stop the server
uv run invoke restart        # Restart the server
uv run invoke status         # Check server status
uv run invoke dev            # Start development server with auto-reload
uv run invoke logs           # Show server logs

# Data Management
uv run invoke setup          # Import data and fetch prices
uv run invoke import-data    # Import transactions from Excel
uv run invoke fetch-prices   # Fetch latest stock prices
uv run invoke fetch-indices  # Fetch market index data
uv run invoke db-info        # Show database information

# Testing
uv run invoke test           # Run all tests
uv run invoke test-cov       # Run tests with coverage report
uv run invoke test-cov-html  # Generate HTML coverage report
uv run invoke test-unit      # Run only unit tests (fast)
uv run invoke test-integration  # Run browser integration tests

# Utilities
uv run invoke clean          # Clean generated files
uv run invoke --list         # Show all available tasks
```

### Code Style

#### Python

- Follow PEP 8 guidelines
- Use type hints where appropriate
- Write docstrings for functions and classes
- Use Ruff for linting and formatting

#### JavaScript

- Use modern ES6+ syntax
- Keep vanilla JavaScript (no frameworks)
- Comment complex logic
- Use meaningful variable names

### Database Development

#### Models

Database models are defined in `src/degiro_portfolio/database.py` using SQLAlchemy ORM.

Key models:
- `Stock`: Stock metadata (symbol, name, ISIN, exchange, currency)
- `Transaction`: Transaction history (date, quantity, price, fees, type, currency)
- `StockPrice`: Historical OHLCV data
- `Index`: Market index metadata
- `IndexPrice`: Index historical prices

#### Making Schema Changes

1. Modify models in `database.py`
2. Delete existing database: `uv run invoke clean`
3. Restart server to recreate schema
4. Re-import data: `uv run invoke setup`

**Note**: For production, implement proper database migrations using Alembic.

### Adding New Features

#### Backend (FastAPI)

1. Add new route in `main.py`:
   ```python
   @app.get("/api/new-endpoint")
   async def new_endpoint(db: Session = Depends(get_db)):
       # Implementation
       return {"data": "value"}
   ```

2. Add database queries if needed
3. Write tests in `tests/test_api_endpoints.py` or create new test file

#### Frontend

1. Modify `static/index.html`
2. Add JavaScript functions for new features
3. Update UI elements
4. Write Playwright tests in `tests/`

### Debugging

#### Server Logs

```bash
# View logs
uv run invoke logs

# Follow logs in real-time
tail -f server.log
```

#### Database Inspection

```bash
# Show database info
uv run invoke db-info

# SQLite command line
sqlite3 degiro_portfolio.db

# Example queries
.tables
.schema stocks
SELECT * FROM stocks LIMIT 5;
```

#### Development Mode

Run with debug logging:

```python
# In main.py, set debug mode
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Ensure all tests pass
6. Update documentation
7. Submit a pull request

### Release Process

**IMPORTANT**: Before making any release:
1. Ensure ALL tests pass (100% pass rate required)
2. Run full test suite: `uv run pytest -v`
3. Check test coverage: `uv run invoke test-cov`

When making a release:

1. Update version in `pyproject.toml`
2. Update documentation and changelog
3. Run full test suite and ensure 100% pass
4. Commit changes: `git commit -m "Release vX.Y.Z"`
5. Create git tag: `git tag vX.Y.Z`
6. Push changes: `git push origin main`
7. Push tag: `git push origin vX.Y.Z`
8. GitHub Actions will automatically:
   - Run full test suite again
   - Build the package
   - Publish to PyPI (if tests pass)
   - Create GitHub Release

**Never release with failing tests!**

---

## Testing Guide

### Test Suite Overview

The DEGIRO Portfolio application includes a comprehensive test suite using Pytest and Playwright for end-to-end testing.

**Current Coverage**: 125 tests with 70% code coverage

### Test Structure

```
tests/
├── conftest.py                      # Pytest fixtures and configuration
├── test_portfolio_overview.py      # Portfolio UI tests (17 tests)
├── test_stock_charts.py            # Chart visualization tests (15 tests)
├── test_api_endpoints.py           # API endpoint tests (14 tests)
├── test_interactive_features.py    # User interaction tests (19 tests)
├── test_price_fetchers_unit.py     # Price fetcher unit tests
├── test_ticker_resolver_unit.py    # Ticker resolver unit tests
├── test_zzz_purge_database.py      # Database purge tests (runs last)
└── README.md                       # Testing documentation
```

### Running Tests

#### All Tests

```bash
# Run complete test suite
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with visible output (print statements)
uv run pytest -v -s
```

#### Specific Test Files

```bash
# Portfolio overview tests
uv run pytest tests/test_portfolio_overview.py -v

# Stock chart tests
uv run pytest tests/test_stock_charts.py -v

# API endpoint tests
uv run pytest tests/test_api_endpoints.py -v

# Unit tests only (fast)
uv run invoke test-unit
```

#### Specific Tests

```bash
# Run a specific test by name
uv run pytest tests/test_portfolio_overview.py::test_portfolio_displays_holdings -v

# Run tests matching a pattern
uv run pytest -k "test_stock" -v
```

### Test Categories

#### Portfolio Overview Tests (17 tests)

Tests for the main portfolio dashboard:
- Holdings display
- Stock cards
- Price information with currency conversion
- Daily change indicators
- Market data status
- Overall layout and UI

**Example:**
```python
def test_portfolio_displays_holdings(page: Page):
    """Test that portfolio displays all holdings"""
    page.goto("http://localhost:8001")
    page.wait_for_selector(".stock-card", timeout=10000)
    assert page.locator(".stock-card").count() > 0
```

#### Stock Chart Tests (15 tests)

Tests for chart visualizations:
- Candlestick charts
- Transaction markers
- Position percentage charts
- Investment tranche tracking
- Market index comparison
- Chart interactivity

#### API Endpoint Tests (14 tests)

Tests for all API endpoints:
- Holdings endpoint with exchange rates
- Stock prices endpoint
- Transaction history endpoint
- Chart data endpoint
- Market data endpoints
- Upload functionality
- Purge database functionality
- Error handling

#### Interactive Feature Tests (19 tests)

Tests for user interactions:
- Chart navigation
- Tab switching
- Market data updates
- File uploads
- Button clicks
- Responsive behavior
- Error handling

#### Unit Tests (55+ tests)

Tests for core modules:
- Price fetcher implementations (Yahoo, FMP, TwelveData)
- Ticker resolution from ISIN
- Configuration management
- Data processing logic

### Test Fixtures

#### Application Fixtures

Defined in `conftest.py`:

##### `server_process`
Starts an isolated test server on port 8001 with a separate test database.

```python
@pytest.fixture(scope="session")
def server_process():
    """Start test server with isolated database"""
    # Setup and teardown handled automatically
```

##### `page`
Provides a Playwright page instance for browser automation.

```python
def test_example(page: Page):
    page.goto("http://localhost:8001")
    # Interact with page
```

### Test Database

Tests use an isolated test database to avoid affecting production data:

- **Test DB**: `test-degiro_portfolio.db`
- **Test Port**: 8001 (production uses 8000)
- **Automatic Cleanup**: Database is deleted after tests

The test database is seeded with example data including:
- Multiple stocks (NVDA, MSFT, META, GOOGL, AMD, SAP, ASML, etc.)
- Transaction history
- Historical prices
- Market indices (S&P 500, Euro Stoxx 50)

### Writing New Tests

#### Portfolio UI Test

```python
def test_new_ui_feature(page: Page):
    """Test description"""
    # Navigate to page
    page.goto("http://localhost:8001")

    # Wait for page to load
    page.wait_for_selector(".stock-card", timeout=10000)

    # Perform actions
    page.locator("#some-button").click()

    # Assert expectations
    assert page.locator("#result").is_visible()
    assert page.locator("#result").text_content() == "Expected"
```

#### API Test

```python
def test_new_api_endpoint(page: Page):
    """Test API endpoint"""
    # Make request using Playwright's request API
    response = page.request.get("http://localhost:8001/api/new-endpoint")

    # Assert response
    assert response.ok
    data = response.json()
    assert "expected_field" in data
```

#### Unit Test

```python
def test_price_fetcher():
    """Test price fetcher logic"""
    from degiro_portfolio.price_fetchers import YahooFinanceFetcher

    fetcher = YahooFinanceFetcher()
    prices = fetcher.fetch_prices("AAPL", "2024-01-01", "2024-01-31")

    assert len(prices) > 0
    assert all("close" in p for p in prices)
```

### Test Best Practices

#### 1. Isolation
- Each test should be independent
- Don't rely on test execution order
- Use fixtures for setup and teardown

#### 2. Clear Naming
```python
# Good
def test_portfolio_displays_stock_cards():
    pass

# Bad
def test_stuff():
    pass
```

#### 3. Arrange-Act-Assert
```python
def test_example(page: Page):
    # Arrange - setup
    page.goto("http://localhost:8001")
    page.wait_for_selector(".stock-card")

    # Act - perform action
    page.locator("#button").click()

    # Assert - verify result
    assert page.locator("#result").is_visible()
```

#### 4. Wait for Elements
```python
# Always wait for dynamic content
page.wait_for_selector("#element", state="visible", timeout=10000)

# Or use timeout in assertions
assert page.locator("#element").is_visible(timeout=10000)
```

#### 5. Meaningful Assertions
```python
# Good - specific assertion with context
assert page.locator(".stock-card").count() == 10, \
    "Should display all 10 test stocks"

# Bad - vague assertion
assert page.locator(".stock-card").count() > 0
```

### Continuous Integration

Tests run automatically on GitHub Actions:
- On every push to main
- On every pull request
- Before publishing releases

**CI must pass with 100% test success before release.**

See `.github/workflows/ci.yml` for CI configuration.

### Debugging Tests

#### Run Single Test with Output
```bash
uv run pytest tests/test_file.py::test_name -v -s
```

#### Playwright Inspector
```bash
PWDEBUG=1 uv run pytest tests/test_file.py::test_name
```

This opens a visual debugger where you can step through browser interactions.

#### Screenshots on Failure
Playwright automatically captures screenshots on test failures in `test-results/` directory.

#### Server Logs
Test server logs are available in `test-server.log` during test execution.

### Test Coverage

Run with coverage report:

```bash
# Terminal coverage report
uv run invoke test-cov

# HTML coverage report (opens in browser)
uv run invoke test-cov-html
```

Current coverage: **70%** across all modules.

---

## Deployment Guide

### Publishing to PyPI

The DEGIRO Portfolio package is automatically published to PyPI using GitHub Actions when you create a release tag.

### Automated Publishing Process

#### Prerequisites

**Option 1: PyPI Trusted Publishing** (Recommended):
1. Go to https://pypi.org/manage/account/publishing/
2. Add a new publisher:
   - **PyPI Project Name**: `degiro_portfolio`
   - **Owner**: Your GitHub username
   - **Repository**: `degiro_portfolio`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`

**Option 2: API Token**:
1. Create token at https://pypi.org/manage/account/token/
2. Add to GitHub Secrets as `PYPI_API_TOKEN`

#### Release Process

1. **Update Version**:
   ```bash
   # Edit pyproject.toml
   version = "0.3.2"
   ```

2. **Run ALL Tests**:
   ```bash
   uv run pytest -v
   ```
   **CRITICAL**: All 125 tests must pass. Never release with failing tests.

3. **Commit Changes**:
   ```bash
   git add .
   git commit -m "Release v0.3.2"
   ```

4. **Create and Push Tag**:
   ```bash
   git tag v0.3.2
   git push origin main
   git push origin v0.3.2
   ```

5. **GitHub Actions Will**:
   - Run full test suite (must pass 100%)
   - Build the package
   - Publish to PyPI (only if tests pass)
   - Create GitHub Release with artifacts

### Manual Publishing

If you need to publish manually:

```bash
# Build the package
uv build

# Publish to PyPI (requires PyPI credentials)
uv publish

# Or use twine
uv pip install twine
twine upload dist/*
```

### Installation from PyPI

Once published, users can install via:

```bash
pip install degiro_portfolio

# Or with uv
uv pip install degiro_portfolio
```

### Docker Deployment

Create a `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY . .

# Install dependencies
RUN uv sync

# Expose port
EXPOSE 8000

# Start server
CMD ["./degiro_portfolio", "start"]
```

Build and run:

```bash
# Build image
docker build -t degiro_portfolio .

# Run container
docker run -p 8000:8000 -v $(pwd)/data:/app/data degiro_portfolio
```

### Production Deployment Considerations

#### Process Manager

Use a process manager to keep the server running:

```bash
# systemd service example
[Unit]
Description=DEGIRO Portfolio Tracker
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/degiro_portfolio
ExecStart=/path/to/degiro_portfolio start
Restart=always

[Install]
WantedBy=multi-user.target
```

#### Reverse Proxy

nginx configuration example:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

#### SSL/TLS

```bash
# Using certbot
sudo certbot --nginx -d your-domain.com
```

#### Environment Variables

Create `.env` file:

```bash
DATABASE_URL=sqlite:///path/to/degiro_portfolio.db
HOST=0.0.0.0
PORT=8000
PRICE_DATA_PROVIDER=yahoo
```

### Database Considerations

#### SQLite (Default)

- Suitable for personal use
- Single file database
- No setup required
- Backup: just copy `degiro_portfolio.db`

```bash
# Backup
cp degiro_portfolio.db degiro_portfolio-backup-$(date +%Y%m%d).db

# Automated daily backup (cron)
0 2 * * * cp /path/to/degiro_portfolio.db /backups/degiro-$(date +\%Y\%m\%d).db
```

#### PostgreSQL (Multi-user)

For multi-user deployments:

```python
# Update database.py
import os
from sqlalchemy import create_engine

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost/degiro"
)

engine = create_engine(DATABASE_URL)
```

### Monitoring

#### Health Check Endpoint

Add to `main.py`:

```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }
```

#### Logging

Configure logging for production:

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
```

### Security Considerations

1. **Authentication**: Add authentication for production use
2. **HTTPS**: Always use HTTPS in production
3. **Secrets**: Use environment variables for sensitive data
4. **Updates**: Keep dependencies updated (`uv sync --upgrade`)
5. **Firewall**: Restrict access to necessary ports

### Performance Optimization

#### Database Indexes

Add indexes for frequently queried fields in `database.py`:

```python
class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    symbol = Column(String, index=True)  # Add index
    isin = Column(String, unique=True, index=True)  # Add index
```

#### Caching

Consider caching for:
- Stock prices (update periodically)
- Market indices
- Exchange rates (cache for 1 hour)
- Chart data (cache for 5 minutes)

### Troubleshooting

#### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>

# Or use the CLI
./degiro_portfolio stop
```

#### Database Locked

```bash
# Stop server
./degiro_portfolio stop

# Check for stale connections
fuser degiro_portfolio.db

# Restart
./degiro_portfolio start
```

#### Memory Issues

```bash
# Check memory usage
ps aux | grep degiro_portfolio

# Monitor in real-time
top -p $(pgrep -f degiro_portfolio)
```

### Support

For deployment issues:
- Check [GitHub Issues](https://github.com/jdrumgoole/degiro_portfolio/issues)
- Review application logs: `./degiro_portfolio logs`
- Verify configuration in `.env`
- Test in development environment first
- Ensure all tests pass before deploying

---

## Additional Resources

### Project Links

- **GitHub Repository**: https://github.com/jdrumgoole/degiro_portfolio
- **PyPI Package**: https://pypi.org/project/degiro_portfolio/
- **Documentation**: https://degiro_portfolio.readthedocs.io/

### Technology Documentation

- **FastAPI**: https://fastapi.tiangolo.com/
- **SQLAlchemy**: https://www.sqlalchemy.org/
- **Playwright**: https://playwright.dev/python/
- **Pytest**: https://docs.pytest.org/
- **uv**: https://github.com/astral-sh/uv

### Contributing

We welcome contributions! Please:
1. Read the development guide above
2. Ensure all tests pass
3. Follow code style guidelines
4. Update documentation
5. Submit a pull request

Thank you for contributing to DEGIRO Portfolio Tracker!
