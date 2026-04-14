"""End-to-end test: upload Dutch 18-column DEGIRO Excel and validate holdings.

Regression test for Dutch DEGIRO exports which use different column names
(Datum, Koers, Aantal, etc.) but the same positional format.
"""

import os
import subprocess
import socket
import tempfile
import time
import platform

import httpx
import pytest
from pathlib import Path
from playwright.sync_api import Browser, BrowserContext

from degiro_portfolio.config import Config

IS_WINDOWS = platform.system() == "Windows"
DUTCH_FILE = Path(__file__).parent / "degiro_dutch.xlsx"
TEST_HOST = "127.0.0.1"
DUTCH_TEST_PORT = 8006


def _kill_process_tree(process):
    try:
        if IS_WINDOWS:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                           capture_output=True)
        else:
            os.killpg(os.getpgid(process.pid), 9)
    except (ProcessLookupError, OSError):
        pass


@pytest.fixture(scope="module")
def dutch_server():
    """Start a server with an empty database for Dutch Excel upload testing."""
    from sqlalchemy import create_engine
    from degiro_portfolio.database import Base

    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", prefix="dutch_test_", delete=False)
    tmp_db.close()
    db_path = tmp_db.name
    db_url = f"sqlite:///{os.path.abspath(db_path)}"

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    engine.dispose()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((TEST_HOST, DUTCH_TEST_PORT))
    sock.close()
    if result == 0:
        pytest.skip(f"Port {DUTCH_TEST_PORT} is in use")

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url

    popen_kwargs = dict(env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if IS_WINDOWS:
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["preexec_fn"] = os.setsid

    process = subprocess.Popen(
        ["uv", "run", "uvicorn", "degiro_portfolio.main:app",
         "--host", TEST_HOST, "--port", str(DUTCH_TEST_PORT), "--log-level", "warning"],
        **popen_kwargs,
    )

    base_url = f"http://{TEST_HOST}:{DUTCH_TEST_PORT}"

    for i in range(40):
        try:
            resp = httpx.get(f"{base_url}/api/ping", timeout=1.0)
            if resp.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == 39:
                _kill_process_tree(process)
                pytest.fail(f"Dutch test server failed to start on {DUTCH_TEST_PORT}")
            time.sleep(0.25)

    # Upload the Dutch Excel via API
    with open(DUTCH_FILE, "rb") as f:
        resp = httpx.post(
            f"{base_url}/api/upload-transactions",
            files={"file": ("degiro_dutch.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            timeout=120.0,
        )
    assert resp.status_code == 200, f"Dutch upload failed: {resp.text}"
    result = resp.json()
    assert result["success"], f"Dutch upload not successful: {result}"

    yield base_url

    _kill_process_tree(process)
    time.sleep(0.5)

    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture(scope="module")
def dutch_context(browser: Browser, dutch_server):
    context = browser.new_context(viewport={"width": 1920, "height": 1080}, locale="en-US")

    def mock_api(route):
        route.fulfill(status=200, content_type="application/json",
                      body='{"updated": 0, "quotes": [], "errors": []}')

    context.route("**/api/refresh-live-prices", mock_api)
    context.route("**/api/update-market-data", mock_api)
    yield context
    context.close()


@pytest.fixture(scope="module")
def dutch_page(dutch_context, dutch_server):
    page = dutch_context.new_page()
    page.goto(dutch_server, timeout=30000, wait_until="domcontentloaded")
    page.wait_for_selector(".stock-card", timeout=15000)
    yield page
    page.close()


def test_dutch_upload_creates_stock(dutch_server):
    """Dutch Excel upload should create 1 stock (ALPHABET INC CLASS C)."""
    resp = httpx.get(f"{dutch_server}/api/holdings")
    assert resp.status_code == 200
    holdings = resp.json()["holdings"]
    assert len(holdings) == 1
    assert holdings[0]["name"] == "ALPHABET INC CLASS C"
    assert holdings[0]["shares"] == 4


def test_dutch_upload_stock_card_displayed(dutch_page):
    """The Dutch-imported stock should appear on screen."""
    cards = dutch_page.locator(".stock-card")
    assert cards.count() == 1
    card_text = cards.first.inner_text()
    assert "ALPHABET INC CLASS C" in card_text
    assert "4 shares" in card_text


def test_dutch_upload_chart_data_loads(dutch_server):
    """Chart data should load without errors for the Dutch-imported stock."""
    holdings = httpx.get(f"{dutch_server}/api/holdings").json()["holdings"]
    stock_id = holdings[0]["id"]

    resp = httpx.get(f"{dutch_server}/api/stock/{stock_id}/chart-data")
    assert resp.status_code == 200, f"Chart data failed: {resp.text}"

    data = resp.json()
    assert data["stock"]["name"] == "ALPHABET INC CLASS C"
    assert len(data["transactions"]) == 1


def test_dutch_upload_no_js_errors(dutch_page):
    """Clicking the stock card should not produce JavaScript errors."""
    js_errors = []
    dutch_page.on("pageerror", lambda err: js_errors.append(str(err)))

    dutch_page.locator(".stock-card").first.click()
    dutch_page.wait_for_timeout(2000)

    assert len(js_errors) == 0, f"JS errors: {js_errors}"
