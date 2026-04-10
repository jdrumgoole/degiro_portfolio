"""End-to-end test: upload degiro.csv and validate displayed holdings.

This test uploads a real DEGIRO CSV export (18-column format) via the API
and verifies that the holdings shown on screen match the CSV data.

Uses a dedicated empty database so that only the CSV data is present.
"""

import os
import subprocess
import socket
import tempfile
import time
import platform

import httpx
import pandas as pd
import pytest
from pathlib import Path
from playwright.sync_api import Browser, BrowserContext

from degiro_portfolio.config import Config
from degiro_portfolio.database import init_db, reinitialize_engine

IS_WINDOWS = platform.system() == "Windows"
CSV_PATH = Path(__file__).parent / "degiro.csv"
TEST_HOST = "127.0.0.1"
CSV_TEST_PORT = 8005


def _compute_expected_holdings() -> dict:
    """Parse degiro.csv and compute expected held stocks."""
    df = pd.read_csv(CSV_PATH)
    df = Config.normalize_degiro_columns(df)

    grouped = df.groupby(["Product", "ISIN"]).agg(
        net_qty=("Quantity", "sum"),
        txn_count=("Quantity", "count"),
    ).reset_index()

    holdings = {}
    for _, row in grouped.iterrows():
        isin = row["ISIN"]
        net_qty = int(row["net_qty"])

        if net_qty <= 0:
            continue
        if isin in Config.IGNORED_STOCKS:
            continue

        holdings[row["Product"]] = {
            "isin": isin,
            "shares": net_qty,
            "transactions": int(row["txn_count"]),
        }

    return holdings


EXPECTED_HOLDINGS = _compute_expected_holdings()


def _kill_process_tree(process):
    """Kill a process and all its children."""
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True)
        else:
            os.killpg(os.getpgid(process.pid), 9)
    except (ProcessLookupError, OSError):
        pass


@pytest.fixture(scope="module")
def csv_server():
    """Start a server with an empty database for CSV upload testing."""
    tmp_db = tempfile.NamedTemporaryFile(
        suffix=".db", prefix="csv_test_", delete=False
    )
    tmp_db.close()
    db_path = tmp_db.name
    db_url = f"sqlite:///{os.path.abspath(db_path)}"

    # Initialize empty schema
    orig_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    reinitialize_engine()
    init_db()

    # Check port is free
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((TEST_HOST, CSV_TEST_PORT))
    sock.close()
    if result == 0:
        pytest.skip(f"Port {CSV_TEST_PORT} is in use")

    # Start server with the empty database
    env = os.environ.copy()
    env["DATABASE_URL"] = db_url

    popen_kwargs = dict(env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if IS_WINDOWS:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["preexec_fn"] = os.setsid

    process = subprocess.Popen(
        [
            "uv", "run", "uvicorn",
            "degiro_portfolio.main:app",
            "--host", TEST_HOST,
            "--port", str(CSV_TEST_PORT),
            "--log-level", "warning",
        ],
        **popen_kwargs,
    )

    base_url = f"http://{TEST_HOST}:{CSV_TEST_PORT}"

    for i in range(20):
        try:
            resp = httpx.get(f"{base_url}/api/ping", timeout=0.5)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == 19:
                _kill_process_tree(process)
                pytest.fail(f"CSV test server failed to start on {CSV_TEST_PORT}")
            time.sleep(0.25)

    # Upload the CSV via the API (faster than UI — avoids browser timeouts)
    with open(CSV_PATH, "rb") as f:
        resp = httpx.post(
            f"{base_url}/api/upload-transactions",
            files={"file": ("degiro.csv", f, "text/csv")},
            timeout=120.0,
        )
    assert resp.status_code == 200, f"CSV upload failed: {resp.text}"
    result = resp.json()
    assert result["success"], f"CSV upload not successful: {result}"

    yield base_url

    _kill_process_tree(process)
    time.sleep(0.5)

    # Restore original DATABASE_URL
    if orig_url is not None:
        os.environ["DATABASE_URL"] = orig_url
    else:
        os.environ.pop("DATABASE_URL", None)
    reinitialize_engine()

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="module")
def csv_context(browser: Browser, csv_server):
    """Browser context that mocks external API calls."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
    )

    def mock_api_response(route):
        route.fulfill(
            status=200,
            content_type="application/json",
            body='{"updated": 0, "quotes": [], "errors": []}',
        )

    context.route("**/api/refresh-live-prices", mock_api_response)
    context.route("**/api/update-market-data", mock_api_response)
    yield context
    context.close()


@pytest.fixture(scope="module")
def csv_page(csv_context, csv_server):
    """Page navigated to the server after CSV has been uploaded."""
    page = csv_context.new_page()
    page.goto(csv_server, timeout=10000)
    page.wait_for_selector(".stock-card", timeout=15000)
    yield page
    page.close()


def test_csv_upload_shows_correct_stock_count(csv_page):
    """Uploading the CSV should show exactly the expected number of held stocks."""
    cards = csv_page.locator(".stock-card")
    assert cards.count() == len(EXPECTED_HOLDINGS), (
        f"Expected {len(EXPECTED_HOLDINGS)} stock cards, got {cards.count()}"
    )


def test_csv_upload_shows_all_stock_names(csv_page):
    """Every expected stock name should appear on screen."""
    page_text = csv_page.locator("#holdings-container").inner_text()
    for name in EXPECTED_HOLDINGS:
        assert name in page_text, f"Stock '{name}' not found on page"


def test_csv_upload_shows_correct_share_counts(csv_page):
    """Each stock card should display the correct number of shares."""
    for name, expected in EXPECTED_HOLDINGS.items():
        card = csv_page.locator(f".stock-card:has-text('{name}')")
        card_text = card.inner_text()
        expected_text = f"{expected['shares']} shares"
        assert expected_text in card_text, (
            f"{name}: expected '{expected_text}' in card, got: {card_text}"
        )


def test_csv_upload_shows_correct_transaction_counts(csv_page):
    """Each stock card should display the correct number of transactions."""
    for name, expected in EXPECTED_HOLDINGS.items():
        card = csv_page.locator(f".stock-card:has-text('{name}')")
        card_text = card.inner_text()
        count = expected["transactions"]
        expected_text = f"{count} transaction" if count == 1 else f"{count} transactions"
        assert expected_text in card_text, (
            f"{name}: expected '{expected_text}' in card, got: {card_text}"
        )


def test_csv_upload_ignored_stocks_not_shown(csv_page):
    """Stocks in IGNORED_STOCKS should not appear on screen."""
    page_text = csv_page.locator("#holdings-container").inner_text()
    assert "SIGNATURE BANK" not in page_text, (
        "SIGNATURE BANK should be ignored but appears on screen"
    )


def test_csv_upload_holdings_api_matches(csv_page, csv_server):
    """The /api/holdings response should match the expected holdings."""
    response = httpx.get(f"{csv_server}/api/holdings")
    assert response.status_code == 200

    data = response.json()
    holdings = data["holdings"]

    api_names = {h["name"] for h in holdings}
    expected_names = set(EXPECTED_HOLDINGS.keys())
    assert api_names == expected_names, (
        f"API holdings mismatch.\n"
        f"  Expected: {expected_names}\n"
        f"  Got: {api_names}"
    )

    for h in holdings:
        expected = EXPECTED_HOLDINGS[h["name"]]
        assert h["shares"] == expected["shares"], (
            f"{h['name']}: expected {expected['shares']} shares, got {h['shares']}"
        )
        assert h["transactions_count"] == expected["transactions"], (
            f"{h['name']}: expected {expected['transactions']} txns, "
            f"got {h['transactions_count']}"
        )


def test_csv_upload_chart_data_loads_for_each_stock(csv_server):
    """The /api/stock/<id>/chart-data endpoint should return valid data for each held stock."""
    holdings_resp = httpx.get(f"{csv_server}/api/holdings")
    assert holdings_resp.status_code == 200
    holdings = holdings_resp.json()["holdings"]

    for h in holdings:
        resp = httpx.get(f"{csv_server}/api/stock/{h['id']}/chart-data")
        assert resp.status_code == 200, (
            f"Chart data failed for {h['name']} (id={h['id']}): {resp.text}"
        )
        data = resp.json()
        # Should have transactions (we know all held stocks have transactions)
        assert "transactions" in data, f"No transactions key for {h['name']}"
        assert len(data["transactions"]) > 0, f"No transactions for {h['name']}"


def test_csv_upload_stock_transactions_api(csv_server):
    """The /api/stock/<id>/transactions endpoint should return correct transaction data."""
    holdings_resp = httpx.get(f"{csv_server}/api/holdings")
    holdings = holdings_resp.json()["holdings"]

    for h in holdings:
        resp = httpx.get(f"{csv_server}/api/stock/{h['id']}/transactions")
        assert resp.status_code == 200, (
            f"Transactions API failed for {h['name']}: {resp.text}"
        )
        data = resp.json()
        expected = EXPECTED_HOLDINGS[h["name"]]
        assert len(data["transactions"]) == expected["transactions"], (
            f"{h['name']}: API returned {len(data['transactions'])} transactions, "
            f"expected {expected['transactions']}"
        )


def test_csv_upload_portfolio_performance_api(csv_server):
    """The /api/portfolio-performance endpoint should not error."""
    resp = httpx.get(f"{csv_server}/api/portfolio-performance")
    assert resp.status_code == 200, f"Portfolio performance failed: {resp.text}"


def test_csv_upload_portfolio_valuation_history_api(csv_server):
    """The /api/portfolio-valuation-history endpoint should not error."""
    resp = httpx.get(f"{csv_server}/api/portfolio-valuation-history")
    assert resp.status_code == 200, f"Valuation history failed: {resp.text}"


def test_csv_upload_market_data_status_api(csv_server):
    """The /api/market-data-status endpoint should not error."""
    resp = httpx.get(f"{csv_server}/api/market-data-status")
    assert resp.status_code == 200, f"Market data status failed: {resp.text}"


def test_csv_upload_stock_prices_api(csv_server):
    """The /api/stock/<id>/prices endpoint should return data for held stocks."""
    holdings_resp = httpx.get(f"{csv_server}/api/holdings")
    holdings = holdings_resp.json()["holdings"]

    for h in holdings:
        resp = httpx.get(f"{csv_server}/api/stock/{h['id']}/prices")
        assert resp.status_code == 200, (
            f"Prices API failed for {h['name']}: {resp.text}"
        )


def test_csv_upload_clicking_stock_card_no_js_errors(csv_page):
    """Clicking each stock card should not produce JavaScript errors."""
    # Collect JS errors during this test
    js_errors = []
    csv_page.on("pageerror", lambda err: js_errors.append(str(err)))

    cards = csv_page.locator(".stock-card")
    count = cards.count()

    for i in range(count):
        card = cards.nth(i)
        stock_name = card.locator(".stock-name").inner_text()
        card.click()
        # Wait for chart area to update
        csv_page.wait_for_timeout(2000)

        assert len(js_errors) == 0, (
            f"JavaScript error after clicking '{stock_name}': {js_errors}"
        )


def test_csv_upload_chart_renders_for_each_stock(csv_page):
    """Clicking each stock card should render chart data without error banners."""
    console_errors = []
    csv_page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

    cards = csv_page.locator(".stock-card")
    count = cards.count()

    for i in range(count):
        console_errors.clear()
        card = cards.nth(i)
        stock_name = card.locator(".stock-name").inner_text()
        card.click()

        # Wait for chart data to load
        csv_page.wait_for_timeout(3000)

        # Check for error banner in page
        error_banner = csv_page.locator(".error-message")
        if error_banner.count() > 0:
            error_text = error_banner.first.inner_text()
            assert "Failed to load" not in error_text, (
                f"Chart error for '{stock_name}': {error_text}. "
                f"Console errors: {console_errors}"
            )


def test_csv_upload_no_error_banner_on_page_load(csv_page):
    """The page should not show any error banners after CSV import."""
    csv_page.reload()
    csv_page.wait_for_selector(".stock-card", timeout=15000)
    csv_page.wait_for_timeout(1000)

    # Check for visible error banners (not HTML source which contains error handler code)
    error_banner = csv_page.locator(".error-message")
    if error_banner.count() > 0 and error_banner.first.is_visible():
        error_text = error_banner.first.inner_text()
        assert False, f"Error banner visible on page load: {error_text}"
