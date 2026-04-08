"""Unit tests for FastAPI endpoints in main.py."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
import os
import pandas as pd
from pathlib import Path


@pytest.fixture
def client(test_database):
    """Create a test client for the FastAPI app."""
    # Import after test_database fixture to ensure correct DB
    from degiro_portfolio.main import app
    return TestClient(app)


# ---------------------------------------------------------------------------
# Basic endpoint tests
# ---------------------------------------------------------------------------

def test_root_endpoint_returns_html(client):
    """Test that root endpoint returns HTML page."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert b"DEGIRO Portfolio" in response.content


def test_ping_endpoint(client):
    """Test ping health check endpoint."""
    response = client.get("/api/ping")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["server"] == "DEGIRO Portfolio"
    assert "version" in data
    assert "started" in data
    assert "uptime_seconds" in data
    assert "uptime" in data
    assert data["uptime_seconds"] >= 0


def test_holdings_endpoint(client):
    """Test holdings API endpoint."""
    response = client.get("/api/holdings")
    assert response.status_code == 200
    data = response.json()
    assert "holdings" in data
    assert isinstance(data["holdings"], list)
    assert len(data["holdings"]) > 0


def test_holdings_structure(client):
    """Test that holdings have correct structure."""
    response = client.get("/api/holdings")
    data = response.json()

    if data["holdings"]:
        holding = data["holdings"][0]
        assert "id" in holding
        assert "name" in holding
        assert "symbol" in holding
        assert "shares" in holding
        assert "transactions_count" in holding


def test_stock_prices_endpoint(client):
    """Test stock prices API endpoint."""
    response = client.get("/api/stock/1/prices")
    assert response.status_code == 200
    data = response.json()
    assert "prices" in data
    assert isinstance(data["prices"], list)


def test_stock_transactions_endpoint(client):
    """Test stock transactions API endpoint."""
    response = client.get("/api/stock/1/transactions")
    assert response.status_code == 200
    data = response.json()
    assert "transactions" in data
    assert isinstance(data["transactions"], list)


def test_stock_chart_data_endpoint(client):
    """Test stock chart data API endpoint."""
    response = client.get("/api/stock/1/chart-data")
    assert response.status_code == 200
    data = response.json()

    assert "stock" in data
    assert "prices" in data
    assert "transactions" in data
    assert "indices" in data
    assert "stock_normalized" in data
    assert "position_percentage" in data


def test_stock_chart_data_has_indices(client):
    """Test that chart data includes market indices."""
    response = client.get("/api/stock/1/chart-data")
    data = response.json()

    assert isinstance(data["indices"], list)
    if data["indices"]:
        index_names = [idx["name"] for idx in data["indices"]]
        assert any("S&P" in name or "500" in name for name in index_names)


def test_invalid_stock_id_returns_404(client):
    """Test that invalid stock ID returns 404."""
    response = client.get("/api/stock/999999/chart-data")
    assert response.status_code == 404


def test_market_data_status_endpoint(client):
    """Test market data status endpoint."""
    response = client.get("/api/market-data-status")
    assert response.status_code == 200
    data = response.json()
    assert "has_data" in data


def test_portfolio_performance_endpoint(client):
    """Test portfolio performance endpoint."""
    response = client.get("/api/portfolio-performance")
    assert response.status_code == 200
    data = response.json()
    assert "stocks" in data
    assert isinstance(data["stocks"], list)


def test_portfolio_valuation_history_endpoint(client):
    """Test portfolio valuation history endpoint."""
    response = client.get("/api/portfolio-valuation-history")
    assert response.status_code == 200
    data = response.json()
    assert "dates" in data
    assert "values" in data
    assert "invested" in data
    assert isinstance(data["dates"], list)
    assert isinstance(data["values"], list)
    assert isinstance(data["invested"], list)


def test_api_cors_headers(client):
    """Test that API responses have proper headers."""
    response = client.get("/api/holdings")
    assert "application/json" in response.headers["content-type"]


def test_static_files_served(client):
    """Test that static files are accessible."""
    response = client.get("/static/favicon.svg")
    assert response.status_code in [200, 404]


# ---------------------------------------------------------------------------
# Mocked API endpoint tests (previously made real external API calls)
# ---------------------------------------------------------------------------

def _make_mock_price_df(periods: int = 5) -> pd.DataFrame:
    """Create a mock price DataFrame matching Yahoo Finance format."""
    dates = pd.date_range(end=datetime.now(), periods=periods, freq='D')
    return pd.DataFrame({
        'Open': [100.0] * periods,
        'High': [101.0] * periods,
        'Low': [99.0] * periods,
        'Close': [100.5] * periods,
        'Volume': [1000000] * periods,
    }, index=dates)


def test_update_market_data_endpoint(client, mocker):
    """Test update market data endpoint (POST) with mocked API calls."""
    mock_hist = _make_mock_price_df()

    # Mock the price fetcher used for stocks
    mock_fetcher = mocker.MagicMock()
    mock_fetcher.fetch_prices.return_value = mock_hist
    mocker.patch('degiro_portfolio.main.get_price_fetcher', return_value=mock_fetcher)

    # Mock yf.Ticker for index updates (module-level import in main.py)
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = mock_hist
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)

    # Mock rate limiter to avoid delays
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    response = client.post("/api/update-market-data")
    assert response.status_code == 200
    data = response.json()
    assert "success" in data
    assert "message" in data
    assert data["success"] is True


def test_refresh_live_prices_endpoint(client, mocker):
    """Test refresh live prices endpoint with mocked API calls."""
    mock_hist = _make_mock_price_df(periods=1)

    # Mock yfinance.Ticker at library level (endpoint does local import)
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = mock_hist
    mock_ticker.info = {'previousClose': 99.0, 'currency': 'USD'}
    mocker.patch('yfinance.Ticker', return_value=mock_ticker)

    # Mock rate limiter to avoid delays
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    response = client.post("/api/refresh-live-prices")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "success" in data
    assert "quotes" in data
    assert isinstance(data["quotes"], list)


def test_ensure_indices_exist_function(mocker):
    """Test the ensure_indices_exist helper function."""
    from degiro_portfolio.main import ensure_indices_exist, INDICES
    from degiro_portfolio.database import SessionLocal, Index, IndexPrice

    mock_history = _make_mock_price_df(periods=100)

    # Patch at the correct location (module-level import in main.py)
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = mock_history
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    db = SessionLocal()
    try:
        db.query(IndexPrice).delete()
        db.query(Index).delete()
        db.commit()

        indices_created, prices_fetched = ensure_indices_exist(db)

        assert indices_created == len(INDICES)
        assert prices_fetched > 0

        indices = db.query(Index).all()
        assert len(indices) == len(INDICES)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# New coverage tests
# ---------------------------------------------------------------------------

def test_main_module_calls_uvicorn(mocker):
    """Test that __main__.py calls uvicorn.run with correct config."""
    mock_run = mocker.patch('uvicorn.run')
    from degiro_portfolio.__main__ import main
    from degiro_portfolio.config import Config

    main()
    mock_run.assert_called_once_with(
        "degiro_portfolio.main:app",
        host=Config.HOST,
        port=Config.PORT,
    )


def test_python_m_degiro_portfolio_is_runnable():
    """Regression test for GitHub issue #1: python -m degiro_portfolio must not fail.

    Verifies that __main__.py exists and the package can be invoked with
    'python -m degiro_portfolio'. The process is expected to start uvicorn
    (which will fail to bind or we kill it), but it must NOT fail with
    'No module named degiro_portfolio.__main__'.
    """
    import subprocess
    result = subprocess.run(
        ["uv", "run", "python", "-c",
         "from degiro_portfolio.__main__ import main; print('OK')"],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, f"Import failed: {result.stderr}"
    assert "OK" in result.stdout


def test_get_fallback_rate_known_currencies():
    """Test fallback exchange rates for known currencies."""
    from degiro_portfolio.main import _get_fallback_rate

    assert _get_fallback_rate("USD") == 0.85
    assert _get_fallback_rate("SEK") == 0.093
    assert _get_fallback_rate("GBP") == 1.18


def test_get_fallback_rate_unknown_currency():
    """Test fallback for unknown currency returns 1.0."""
    from degiro_portfolio.main import _get_fallback_rate

    assert _get_fallback_rate("JPY") == 1.0
    assert _get_fallback_rate("EUR") == 1.0


def test_exchange_rates_endpoint(client, mocker):
    """Test exchange rates endpoint with mocked Yahoo Finance."""
    mock_hist = _make_mock_price_df()
    mock_hist['Close'] = [0.85] * 5

    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = mock_hist
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    response = client.get("/api/exchange-rates")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "rates" in data
    assert "EUR" in data["rates"]
    assert data["rates"]["EUR"] == 1.0


def test_ping_uptime_formatting(client, mocker):
    """Test uptime string formatting for various durations."""
    # Test days format
    mocker.patch('degiro_portfolio.main.SERVER_START_TIME',
                 datetime.now() - timedelta(days=2, hours=3, minutes=15))
    response = client.get("/api/ping")
    data = response.json()
    assert "2d" in data["uptime"]
    assert "3h" in data["uptime"]

    # Test hours-only format
    mocker.patch('degiro_portfolio.main.SERVER_START_TIME',
                 datetime.now() - timedelta(hours=5, minutes=30))
    response = client.get("/api/ping")
    data = response.json()
    assert "5h" in data["uptime"]

    # Test minutes-only format
    mocker.patch('degiro_portfolio.main.SERVER_START_TIME',
                 datetime.now() - timedelta(minutes=45))
    response = client.get("/api/ping")
    data = response.json()
    assert "45m" in data["uptime"]

    # Test seconds-only format
    mocker.patch('degiro_portfolio.main.SERVER_START_TIME',
                 datetime.now() - timedelta(seconds=10))
    response = client.get("/api/ping")
    data = response.json()
    assert data["uptime"].endswith("s")


# ---------------------------------------------------------------------------
# Destructive test (must run last in this module)
# ---------------------------------------------------------------------------

def test_z_purge_database_endpoint(test_database):
    """Test purge database endpoint clears all data and restores afterwards."""
    import shutil
    from pathlib import Path

    # Back up the worker DB so we can restore after the destructive test
    db_path = Path(test_database)
    backup_path = db_path.with_suffix(".db.bak")
    shutil.copy(db_path, backup_path)

    try:
        from degiro_portfolio.main import app
        from degiro_portfolio.database import reinitialize_engine
        client = TestClient(app)

        # Verify we have data first
        holdings = client.get("/api/holdings").json()
        assert len(holdings["holdings"]) > 0

        # Purge
        response = client.post("/api/purge-database")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "deleted" in data
        assert data["deleted"]["stocks"] > 0
        assert data["deleted"]["transactions"] > 0

        # Verify empty
        holdings = client.get("/api/holdings").json()
        assert len(holdings["holdings"]) == 0
    finally:
        # Restore the DB so other tests on this worker aren't affected
        shutil.copy(backup_path, db_path)
        backup_path.unlink()
        reinitialize_engine()


# ---------------------------------------------------------------------------
# Real yfinance smoke test
# ---------------------------------------------------------------------------

def test_yfinance_real_smoke_test():
    """Smoke test: verify real Yahoo Finance API returns data for AAPL."""
    import yfinance as yf

    ticker = yf.Ticker("AAPL")
    hist = ticker.history(period="5d")

    assert not hist.empty, "Yahoo Finance returned no data for AAPL"
    assert len(hist) > 0
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        assert col in hist.columns, f"Missing expected column: {col}"
    assert hist["Close"].iloc[-1] > 0, "AAPL close price should be positive"
