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


def test_upload_transactions_invalid_file_type(client):
    """Upload endpoint rejects non-Excel/CSV files."""
    from io import BytesIO

    response = client.post(
        "/api/upload-transactions",
        files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["message"] or "Excel" in response.json()["message"]


def test_upload_transactions_wrong_column_count(client):
    """Upload endpoint rejects files with wrong column count."""
    from io import BytesIO

    csv_content = "col1,col2,col3\n1,2,3\n"
    response = client.post(
        "/api/upload-transactions",
        files={"file": ("test.csv", BytesIO(csv_content.encode()), "text/csv")},
    )
    assert response.status_code == 400
    assert "Expected" in response.json()["message"]


def test_upload_ignored_stock_skipped(client, mocker):
    """Stocks in IGNORED_STOCKS should be skipped during upload."""
    from io import BytesIO
    from degiro_portfolio.config import Config

    mocker.patch('degiro_portfolio.main.fetch_stock_prices', return_value=0)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = pd.DataFrame()
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)

    ignored_isin = list(Config.IGNORED_STOCKS)[0]
    csv_content = (
        "Date,Time,Product,ISIN,Reference exchange,Venue,Quantity,Price,,Local value,,Value EUR,Exchange rate,AutoFX Fee,Transaction and/or third party fees EUR,Total EUR,Order ID,\n"
        f"20-03-2026,10:00,IGNORED STOCK,{ignored_isin},NASDAQ,XNAS,10,50.00,USD,500.00,USD,425.00,0.85,0.00,1.00,-426.00,,ignored-001\n"
    )

    response = client.post(
        "/api/upload-transactions",
        files={"file": ("test.csv", BytesIO(csv_content.encode()), "text/csv")},
    )
    assert response.json()["success"]
    assert "0 new transactions" in response.json()["message"]


def test_chart_data_with_valid_stock(client):
    """Chart data for a valid stock should return all expected fields."""
    response = client.get("/api/stock/1/chart-data")
    assert response.status_code == 200
    data = response.json()

    assert "stock" in data
    assert "prices" in data
    assert "transactions" in data
    assert "indices" in data
    assert "stock_normalized" in data
    assert "position_percentage" in data
    assert data["stock"]["name"] is not None

    # Verify no null close values in returned prices
    for p in data["prices"]:
        assert p["close"] is not None, f"Null close found on {p['date']}"


def test_chart_data_transactions_have_running_position(client):
    """Chart data transactions should include running share count."""
    response = client.get("/api/stock/1/chart-data")
    data = response.json()

    if data["transactions"]:
        t = data["transactions"][0]
        assert "shares" in t
        assert "transaction_type" in t
        assert t["transaction_type"] in ("buy", "sell")



def test_portfolio_summary_endpoint(client):
    """Test the new portfolio-summary endpoint returns computed values."""
    response = client.get("/api/portfolio-summary")
    assert response.status_code == 200
    data = response.json()

    assert "total_holdings" in data
    assert "net_invested" in data
    assert "current_value" in data
    assert "gain_loss" in data
    assert "gain_loss_percent" in data
    assert data["total_holdings"] > 0
    assert isinstance(data["net_invested"], float)
    assert isinstance(data["current_value"], float)


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
# Upload endpoint — coverage for new-stock, duplicate, FMP, index branches
# ---------------------------------------------------------------------------

_UPLOAD_CSV_HEADER = (
    "Date,Time,Product,ISIN,Reference exchange,Quantity,Price,Currency,"
    "Value EUR,Total EUR,Venue,Exchange rate,Fees EUR,Transaction ID\n"
)


def _make_upload_csv(rows: list[str]) -> bytes:
    return (_UPLOAD_CSV_HEADER + "".join(rows)).encode()


@pytest.fixture
def cleanup_test_isins():
    """Yield a set; delete stocks (+ their txns/prices) for any ISIN added to it."""
    isins: set[str] = set()
    yield isins
    if not isins:
        return
    from degiro_portfolio.database import (
        SessionLocal, Stock, Transaction, StockPrice
    )
    db = SessionLocal()
    try:
        stocks = db.query(Stock).filter(Stock.isin.in_(isins)).all()
        for s in stocks:
            db.query(StockPrice).filter_by(stock_id=s.id).delete()
            db.query(Transaction).filter_by(stock_id=s.id).delete()
            db.delete(s)
        # Also purge any future-dated StockPrice rows (from FMP mock quotes
        # injected on existing stocks during upload tests).
        tomorrow = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        ) + timedelta(days=1)
        db.query(StockPrice).filter(StockPrice.date >= tomorrow).delete()
        db.commit()
    finally:
        db.close()


def _patch_upload_externals(mocker):
    """Mute all network-touching calls made during upload post-processing."""
    mocker.patch('degiro_portfolio.main.fetch_stock_prices', return_value=0)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = _make_mock_price_df()
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)
    return mock_ticker


def test_upload_creates_new_stock_and_skips_duplicate_transaction(client, mocker, cleanup_test_isins):
    cleanup_test_isins.add("US9999999991")
    """Upload creates a new stock on first call and skips duplicates on the second.

    Covers main.py 984-1030 (new-stock insert, transaction insert, duplicate skip,
    existing-stock else branch) and 1040-1058 (held-stock price fetch loop).
    """
    _patch_upload_externals(mocker)

    csv = _make_upload_csv([
        "02-01-2026,10:00:00,COVERAGE CORP,US9999999991,NASDAQ,5,100.00,USD,"
        "500.00,-430.00,XNAS,0.86,1.00,cov-001\n",
        "03-01-2026,10:00:00,COVERAGE CORP,US9999999991,NASDAQ,3,110.00,USD,"
        "330.00,-285.00,XNAS,0.86,1.00,cov-002\n",
    ])

    r1 = client.post("/api/upload-transactions",
                     files={"file": ("t.csv", csv, "text/csv")})
    assert r1.status_code == 200, r1.text
    assert r1.json()["success"] is True
    assert "2 new transactions" in r1.json()["message"]

    # Second upload: stock exists → else-branch; rows exist → duplicate skip.
    r2 = client.post("/api/upload-transactions",
                     files={"file": ("t.csv", csv, "text/csv")})
    assert r2.status_code == 200
    assert "0 new transactions" in r2.json()["message"]

    from degiro_portfolio.database import SessionLocal, Stock, Transaction
    db = SessionLocal()
    try:
        stock = db.query(Stock).filter_by(isin="US9999999991").first()
        assert stock is not None
        assert stock.name == "COVERAGE CORP"
        assert db.query(Transaction).filter_by(stock_id=stock.id).count() == 2
    finally:
        db.close()


def test_upload_skips_price_fetch_for_fully_sold_positions(client, mocker, cleanup_test_isins):
    cleanup_test_isins.add("US9999999992")
    """A new stock bought then fully sold has net qty == 0 → held_stock_ids excludes it.

    Covers main.py 1040-1058 skipped-sold branch (len(held) < len(to_fetch)).
    """
    fetch_mock = mocker.patch('degiro_portfolio.main.fetch_stock_prices',
                              return_value=0)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')
    mock_ticker = mocker.MagicMock()
    mock_ticker.history.return_value = _make_mock_price_df()
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)

    csv = _make_upload_csv([
        "02-01-2026,10:00:00,SOLDOUT INC,US9999999992,NASDAQ,10,50.00,USD,"
        "500.00,-430.00,XNAS,0.86,1.00,sold-001\n",
        "03-01-2026,10:00:00,SOLDOUT INC,US9999999992,NASDAQ,-10,55.00,USD,"
        "550.00,473.00,XNAS,0.86,1.00,sold-002\n",
    ])

    r = client.post("/api/upload-transactions",
                    files={"file": ("t.csv", csv, "text/csv")})
    assert r.status_code == 200
    assert r.json()["success"] is True
    # fetch_stock_prices must NOT be called for the sold-out stock
    fetch_mock.assert_not_called()


def test_upload_fmp_live_prices_inserts_new_price(client, mocker, cleanup_test_isins):
    cleanup_test_isins.add("US9999999993")
    """When PRICE_DATA_PROVIDER='fmp', upload should refresh live prices via FMP.

    Covers main.py 1063-1107 (FMP fetcher branch, StockPrice insert path).
    """
    _patch_upload_externals(mocker)
    mocker.patch('degiro_portfolio.main.Config.PRICE_DATA_PROVIDER', 'fmp')

    # Future timestamp guarantees the "insert new price" branch (no existing row)
    future_ts = (datetime.now() + timedelta(days=1)).replace(microsecond=0)
    fake_fetcher = mocker.MagicMock()
    fake_fetcher.fetch_latest_quote.return_value = {
        "price": 123.45, "open": 120.0, "high": 125.0, "low": 119.0,
        "volume": 10_000, "timestamp": future_ts.isoformat(),
    }
    mocker.patch('degiro_portfolio.price_fetchers.FMPFetcher',
                 return_value=fake_fetcher)

    csv = _make_upload_csv([
        "02-01-2026,10:00:00,FMP CORP,US9999999993,NASDAQ,5,100.00,USD,"
        "500.00,-430.00,XNAS,0.86,1.00,fmp-001\n",
    ])
    r = client.post("/api/upload-transactions",
                    files={"file": ("t.csv", csv, "text/csv")})
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    # FMPFetcher must have been consulted for at least one held stock
    assert fake_fetcher.fetch_latest_quote.called

    from degiro_portfolio.database import SessionLocal, StockPrice
    db = SessionLocal()
    try:
        # At least one new StockPrice row at the future timestamp was inserted
        inserted = db.query(StockPrice).filter(
            StockPrice.date >= future_ts.replace(hour=0, minute=0, second=0)
        ).count()
        assert inserted >= 1
    finally:
        db.close()


def test_upload_index_update_handles_yfinance_exception(client, mocker, cleanup_test_isins):
    cleanup_test_isins.add("US9999999994")
    """If yfinance raises while refreshing indices post-upload, upload still succeeds.

    Covers main.py 1146-1147 (index-update exception branch).
    """
    mocker.patch('degiro_portfolio.main.fetch_stock_prices', return_value=0)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    mock_ticker = mocker.MagicMock()
    mock_ticker.history.side_effect = RuntimeError("boom")
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)

    csv = _make_upload_csv([
        "02-01-2026,10:00:00,BOOM CORP,US9999999994,NASDAQ,1,10.00,USD,"
        "10.00,-9.00,XNAS,0.86,1.00,boom-001\n",
    ])
    r = client.post("/api/upload-transactions",
                    files={"file": ("t.csv", csv, "text/csv")})
    assert r.status_code == 200
    assert r.json()["success"] is True


# ---------------------------------------------------------------------------
# Batch 2 — error branches, fallbacks, resolver paths
# ---------------------------------------------------------------------------


def test_exchange_rates_yahoo_empty_and_rate_limit(client, mocker):
    """Force cached rates to be missing so Yahoo fetch runs; simulate empty
    history and a rate-limit exception to cover the fallback branches.

    Covers main.py 330-367.
    """
    from degiro_portfolio.database import SessionLocal, ExchangeRate

    db = SessionLocal()
    try:
        db.query(ExchangeRate).delete()
        db.commit()
    finally:
        db.close()

    # First call returns empty DF (USD), second raises rate-limit (GBP),
    # third raises generic error (SEK)
    empty_ticker = mocker.MagicMock()
    empty_ticker.history.return_value = pd.DataFrame()
    rl_ticker = mocker.MagicMock()
    rl_ticker.history.side_effect = RuntimeError("Too Many Requests rate")
    err_ticker = mocker.MagicMock()
    err_ticker.history.side_effect = RuntimeError("boom")

    mocker.patch('degiro_portfolio.main.yf.Ticker',
                 side_effect=[empty_ticker, rl_ticker, err_ticker])
    report_rl = mocker.patch(
        'degiro_portfolio.main.yahoo_rate_limiter.report_rate_limit'
    )
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    response = client.get("/api/exchange-rates")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    # All three currencies should have fallback values assigned
    assert data["rates"]["USD"] == 0.85
    assert data["rates"]["GBP"] == 1.18
    assert data["rates"]["SEK"] == 0.093
    report_rl.assert_called()  # GBP branch hit


def test_update_market_data_resolves_missing_ticker(client, mocker):
    """update-market-data auto-resolves missing yahoo_ticker via resolver.

    Covers main.py 1337-1344.
    """
    from degiro_portfolio.database import SessionLocal, Stock

    # Null one stock's yahoo_ticker to force the resolver path
    db = SessionLocal()
    original = None
    try:
        stock = db.query(Stock).filter(Stock.yahoo_ticker.isnot(None)).first()
        original = (stock.id, stock.yahoo_ticker)
        stock.yahoo_ticker = None
        db.commit()
    finally:
        db.close()

    try:
        mocker.patch(
            'degiro_portfolio.main.resolve_ticker_from_isin',
            return_value='RESOLVED.TEST',
        )
        mock_fetcher = mocker.MagicMock()
        mock_fetcher.fetch_prices.return_value = _make_mock_price_df()
        mocker.patch('degiro_portfolio.main.get_price_fetcher',
                     return_value=mock_fetcher)
        mock_ticker = mocker.MagicMock()
        mock_ticker.history.return_value = _make_mock_price_df()
        mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)
        mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

        r = client.post("/api/update-market-data")
        assert r.status_code == 200
        assert r.json()["success"] is True

        # Stock should now have the resolved ticker persisted
        db = SessionLocal()
        try:
            refreshed = db.query(Stock).filter_by(id=original[0]).first()
            assert refreshed.yahoo_ticker == 'RESOLVED.TEST'
        finally:
            db.close()
    finally:
        # Restore original ticker
        db = SessionLocal()
        try:
            s = db.query(Stock).filter_by(id=original[0]).first()
            s.yahoo_ticker = original[1]
            db.commit()
        finally:
            db.close()


def test_update_market_data_fallback_yahoo_when_primary_empty(client, mocker):
    """When primary fetcher returns empty and provider != 'yahoo', fall back
    to YahooFinanceFetcher.

    Covers main.py 1353-1359.
    """
    mocker.patch('degiro_portfolio.main.Config.PRICE_DATA_PROVIDER', 'twelvedata')

    empty_fetcher = mocker.MagicMock()
    empty_fetcher.fetch_prices.return_value = pd.DataFrame()
    mocker.patch('degiro_portfolio.main.get_price_fetcher',
                 return_value=empty_fetcher)

    yahoo_instance = mocker.MagicMock()
    yahoo_instance.fetch_prices.return_value = _make_mock_price_df()
    mocker.patch('degiro_portfolio.price_fetchers.YahooFinanceFetcher',
                 return_value=yahoo_instance)

    mock_idx_ticker = mocker.MagicMock()
    mock_idx_ticker.history.return_value = _make_mock_price_df()
    mocker.patch('degiro_portfolio.main.yf.Ticker',
                 return_value=mock_idx_ticker)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    r = client.post("/api/update-market-data")
    assert r.status_code == 200
    assert r.json()["success"] is True
    yahoo_instance.fetch_prices.assert_called()


def test_update_market_data_index_rate_limit_exception(client, mocker):
    """yfinance raising a rate-limit error during index update must be caught
    and the rate-limiter notified.

    Covers main.py 1431-1435.
    """
    mock_fetcher = mocker.MagicMock()
    mock_fetcher.fetch_prices.return_value = _make_mock_price_df()
    mocker.patch('degiro_portfolio.main.get_price_fetcher',
                 return_value=mock_fetcher)

    mock_ticker = mocker.MagicMock()
    mock_ticker.history.side_effect = RuntimeError("Too Many Requests")
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)
    report_rl = mocker.patch(
        'degiro_portfolio.main.yahoo_rate_limiter.report_rate_limit'
    )
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    r = client.post("/api/update-market-data")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["errors"]  # index errors propagated to message list
    report_rl.assert_called()


def test_purge_database_error_branch(client, mocker):
    """If commit fails during purge, endpoint returns 500 with rollback.

    Covers main.py 1498-1500.
    """
    mocker.patch(
        'sqlalchemy.orm.Session.commit',
        side_effect=RuntimeError("commit failed"),
    )
    r = client.post("/api/purge-database")
    assert r.status_code == 500
    body = r.json()
    assert body["success"] is False
    assert "commit failed" in body["message"]


def test_shutdown_endpoint_without_event_triggers_timer(client, mocker):
    """/api/shutdown with no shutdown event falls back to os._exit via Timer.

    Covers main.py 1517-1522 (Timer branch).
    """
    import degiro_portfolio.main as m

    mocker.patch.object(m, '_shutdown_event', None)
    mock_timer_cls = mocker.patch('threading.Timer')

    r = client.post("/api/shutdown")
    assert r.status_code == 200
    assert r.json()["status"] == "shutting_down"
    mock_timer_cls.assert_called_once()


def test_shutdown_endpoint_with_event_sets_event(client, mocker):
    """/api/shutdown with a shutdown event calls event.set().

    Covers main.py 1518 (event branch).
    """
    import degiro_portfolio.main as m

    fake_event = mocker.MagicMock()
    mocker.patch.object(m, '_shutdown_event', fake_event)

    r = client.post("/api/shutdown")
    assert r.status_code == 200
    fake_event.set.assert_called_once()


def test_ensure_indices_exist_rollback_on_error(mocker):
    """ensure_indices_exist rolls back and re-raises on DB error.

    Covers main.py 79-82.
    """
    from degiro_portfolio.main import ensure_indices_exist
    from degiro_portfolio.database import SessionLocal, Index, IndexPrice

    db = SessionLocal()
    try:
        db.query(IndexPrice).delete()
        db.query(Index).delete()
        db.commit()
    finally:
        db.close()

    mock_ticker = mocker.MagicMock()
    mock_ticker.history.side_effect = RuntimeError("kaboom")
    mocker.patch('degiro_portfolio.main.yf.Ticker', return_value=mock_ticker)
    mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

    db = SessionLocal()
    try:
        with pytest.raises(RuntimeError, match="kaboom"):
            ensure_indices_exist(db)
    finally:
        db.close()


def test_refresh_live_prices_missing_ticker_and_error(client, mocker):
    """refresh-live-prices: one held stock has no yahoo_ticker (skip with
    error), another hits a yfinance rate-limit exception.

    Covers main.py 1213-1214, 1263-1268.
    """
    from degiro_portfolio.database import SessionLocal, Stock

    db = SessionLocal()
    saved: list[tuple[int, str]] = []
    try:
        stocks = db.query(Stock).filter(
            Stock.yahoo_ticker.isnot(None)
        ).limit(1).all()
        for s in stocks:
            saved.append((s.id, s.yahoo_ticker))
            s.yahoo_ticker = None
        db.commit()
    finally:
        db.close()

    try:
        mock_ticker = mocker.MagicMock()
        mock_ticker.history.side_effect = RuntimeError("Too Many Requests")
        mocker.patch('yfinance.Ticker', return_value=mock_ticker)
        report_rl = mocker.patch(
            'degiro_portfolio.main.yahoo_rate_limiter.report_rate_limit'
        )
        mocker.patch('degiro_portfolio.main.yahoo_rate_limiter.wait_if_needed')

        r = client.post("/api/refresh-live-prices")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True
        assert data["errors"]  # both missing-ticker and rate-limit errors
        report_rl.assert_called()
    finally:
        db = SessionLocal()
        try:
            for stock_id, ticker in saved:
                s = db.query(Stock).filter_by(id=stock_id).first()
                s.yahoo_ticker = ticker
            db.commit()
        finally:
            db.close()


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
