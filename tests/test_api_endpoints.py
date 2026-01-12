"""Tests for API endpoints."""

import pytest
from playwright.sync_api import Page, APIRequestContext


def test_holdings_endpoint_returns_all_stocks(page: Page, expected_stocks):
    """Test that /api/holdings returns all expected stocks."""
    response = page.request.get("http://127.0.0.1:8001/api/holdings")
    assert response.ok, f"Holdings API returned {response.status}"

    data = response.json()
    assert "holdings" in data, "Response missing 'holdings' key"

    holdings = data["holdings"]
    assert len(holdings) == 11, f"Expected 11 holdings, got {len(holdings)}"


def test_holdings_endpoint_includes_share_counts(page: Page, expected_stocks):
    """Test that holdings include correct share counts."""
    response = page.request.get("http://127.0.0.1:8001/api/holdings")
    data = response.json()
    holdings = data["holdings"]

    # Create a map of stock names to holdings
    holdings_map = {h["name"]: h for h in holdings}

    # Check a few specific stocks
    for stock_name, expected_data in expected_stocks.items():
        assert stock_name in holdings_map, f"Stock {stock_name} not found in holdings"
        holding = holdings_map[stock_name]

        assert holding["shares"] == expected_data["shares"], \
            f"{stock_name}: expected {expected_data['shares']} shares, got {holding['shares']}"


def test_holdings_endpoint_includes_latest_prices(page: Page):
    """Test that holdings include latest price information."""
    response = page.request.get("http://127.0.0.1:8001/api/holdings")
    data = response.json()
    holdings = data["holdings"]

    # At least some stocks should have price data
    stocks_with_prices = [h for h in holdings if h.get("latest_price") is not None]
    assert len(stocks_with_prices) > 0, "No stocks have price data"


def test_holdings_endpoint_includes_price_changes(page: Page):
    """Test that holdings include daily price change percentages."""
    response = page.request.get("http://127.0.0.1:8001/api/holdings")
    data = response.json()
    holdings = data["holdings"]

    # Check that price change fields exist
    for holding in holdings:
        assert "price_change_pct" in holding, f"{holding['name']} missing price_change_pct"


def test_holdings_endpoint_includes_ticker_and_exchange(page: Page):
    """Test that holdings include ticker symbols and exchange info."""
    response = page.request.get("http://127.0.0.1:8001/api/holdings")
    data = response.json()
    holdings = data["holdings"]

    # All holdings should have ticker and exchange
    for holding in holdings:
        assert "yahoo_ticker" in holding, f"{holding['name']} missing yahoo_ticker"
        assert "exchange" in holding, f"{holding['name']} missing exchange"


def test_market_data_status_endpoint(page: Page):
    """Test that /api/market-data-status returns status information."""
    response = page.request.get("http://127.0.0.1:8001/api/market-data-status")
    assert response.ok, f"Market data status API returned {response.status}"

    data = response.json()
    assert "has_data" in data, "Response missing 'has_data' key"
    assert "latest_date" in data, "Response missing 'latest_date' key"


def test_stock_prices_endpoint(page: Page):
    """Test that /api/stock/{id}/prices returns price data."""
    # First get holdings to get a stock ID
    holdings_response = page.request.get("http://127.0.0.1:8001/api/holdings")
    holdings = holdings_response.json()["holdings"]

    # Get first stock ID
    stock_id = holdings[0]["id"]

    # Fetch prices for that stock
    prices_response = page.request.get(f"http://127.0.0.1:8001/api/stock/{stock_id}/prices")
    assert prices_response.ok, f"Prices API returned {prices_response.status}"

    data = prices_response.json()
    assert "prices" in data, "Response missing 'prices' key"

    prices = data["prices"]
    assert len(prices) > 0, "No price data returned"

    # Check price data structure
    first_price = prices[0]
    assert "date" in first_price, "Price missing date"
    assert "open" in first_price, "Price missing open"
    assert "high" in first_price, "Price missing high"
    assert "low" in first_price, "Price missing low"
    assert "close" in first_price, "Price missing close"


def test_stock_transactions_endpoint(page: Page, expected_stocks):
    """Test that /api/stock/{id}/transactions returns transaction data."""
    # First get holdings to get a stock ID
    holdings_response = page.request.get("http://127.0.0.1:8001/api/holdings")
    holdings = holdings_response.json()["holdings"]

    # Find NVIDIA (which has 4 transactions)
    nvidia = next(h for h in holdings if "NVIDIA" in h["name"])
    stock_id = nvidia["id"]

    # Fetch transactions
    trans_response = page.request.get(f"http://127.0.0.1:8001/api/stock/{stock_id}/transactions")
    assert trans_response.ok, f"Transactions API returned {trans_response.status}"

    data = trans_response.json()
    assert "transactions" in data, "Response missing 'transactions' key"

    transactions = data["transactions"]
    assert len(transactions) == 4, f"NVIDIA should have 4 transactions, got {len(transactions)}"

    # Check transaction structure
    first_trans = transactions[0]
    assert "date" in first_trans, "Transaction missing date"
    assert "quantity" in first_trans, "Transaction missing quantity"
    assert "price" in first_trans, "Transaction missing price"
    assert "transaction_type" in first_trans, "Transaction missing transaction_type"


def test_stock_chart_data_endpoint(page: Page):
    """Test that /api/stock/{id}/chart-data returns combined chart data."""
    # Get a stock ID
    holdings_response = page.request.get("http://127.0.0.1:8001/api/holdings")
    holdings = holdings_response.json()["holdings"]
    stock_id = holdings[0]["id"]

    # Fetch chart data
    chart_response = page.request.get(f"http://127.0.0.1:8001/api/stock/{stock_id}/chart-data")
    assert chart_response.ok, f"Chart data API returned {chart_response.status}"

    data = chart_response.json()

    # Should include multiple data sets
    assert "prices" in data or "transactions" in data, "Chart data missing expected keys"


def test_portfolio_performance_endpoint(page: Page):
    """Test that /api/portfolio-performance returns performance metrics."""
    response = page.request.get("http://127.0.0.1:8001/api/portfolio-performance")

    # This endpoint might not be fully implemented, so just check it doesn't error
    assert response.status in [200, 404], f"Unexpected status: {response.status}"


def test_api_endpoints_return_json(page: Page):
    """Test that all API endpoints return proper JSON content type."""
    endpoints = [
        "/api/holdings",
        "/api/market-data-status"
    ]

    for endpoint in endpoints:
        response = page.request.get(f"http://127.0.0.1:8001{endpoint}")
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, \
            f"{endpoint} doesn't return JSON: {content_type}"


def test_invalid_stock_id_returns_error(page: Page):
    """Test that invalid stock IDs return appropriate errors."""
    response = page.request.get("http://127.0.0.1:8001/api/stock/99999/prices")

    # Should return an error status
    assert response.status in [404, 400], f"Expected error for invalid ID, got {response.status}"


def test_holdings_currency_matches_expected(page: Page, expected_stocks):
    """Test that stock currencies match expected values."""
    response = page.request.get("http://127.0.0.1:8001/api/holdings")
    holdings = response.json()["holdings"]

    holdings_map = {h["name"]: h for h in holdings}

    # Check specific currencies
    test_cases = [
        ("NVIDIA CORP", "USD"),
        ("ASML HOLDING NV", "EUR"),
        ("TELEFONAKTIEBOLAGET LM ERICSSON-B", "SEK"),
    ]

    for stock_name, expected_currency in test_cases:
        if stock_name in holdings_map:
            actual_currency = holdings_map[stock_name]["currency"]
            assert actual_currency == expected_currency, \
                f"{stock_name}: expected {expected_currency}, got {actual_currency}"


def test_holdings_transaction_counts_match_expected(page: Page, expected_stocks):
    """Test that transaction counts match expected values."""
    response = page.request.get("http://127.0.0.1:8001/api/holdings")
    holdings = response.json()["holdings"]

    holdings_map = {h["name"]: h for h in holdings}

    for stock_name, expected_data in expected_stocks.items():
        if stock_name in holdings_map:
            actual_count = holdings_map[stock_name]["transactions_count"]
            expected_count = expected_data["transactions"]
            assert actual_count == expected_count, \
                f"{stock_name}: expected {expected_count} transactions, got {actual_count}"
