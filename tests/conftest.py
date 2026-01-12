"""Pytest configuration and fixtures for DEGIRO Portfolio tests."""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page


# Test database path
TEST_DB = "test_portfolio.db"
EXAMPLE_DATA = "example_data.xlsx"


@pytest.fixture(scope="session")
def test_database():
    """Create a test database with example data."""
    # Remove existing test database if it exists
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

    # Also remove any test database backups
    import glob
    for backup in glob.glob(f"{TEST_DB}*"):
        try:
            os.remove(backup)
        except:
            pass

    # Set environment variable for test database
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

    # Import the example data
    from degiro_portfolio.import_data import import_transactions
    import_transactions(EXAMPLE_DATA)

    # Fetch prices for the stocks
    from degiro_portfolio.fetch_prices import fetch_all_current_holdings
    fetch_all_current_holdings()

    # Fetch market indices
    from degiro_portfolio.fetch_indices import fetch_index_prices
    fetch_index_prices()

    yield TEST_DB

    # Cleanup
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.fixture(scope="session")
def server_process(test_database):
    """Start the FastAPI server for testing."""
    # Start the server in a subprocess
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{test_database}"

    process = subprocess.Popen(
        ["uv", "run", "uvicorn", "degiro_portfolio.main:app", "--host", "127.0.0.1", "--port", "8001"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to be ready
    import httpx
    max_retries = 30
    for i in range(max_retries):
        try:
            response = httpx.get("http://127.0.0.1:8001/api/holdings", timeout=1.0)
            if response.status_code == 200:
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == max_retries - 1:
                process.kill()
                raise Exception("Server failed to start")
            time.sleep(0.5)

    yield "http://127.0.0.1:8001"

    # Cleanup
    process.terminate()
    process.wait(timeout=5)


@pytest.fixture(scope="session")
def browser(playwright):
    """Create a browser instance for the test session."""
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture
def context(browser: Browser):
    """Create a new browser context for each test."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        locale="en-US"
    )
    yield context
    context.close()


@pytest.fixture
def page(context: BrowserContext, server_process):
    """Create a new page for each test."""
    page = context.new_page()
    page.goto(server_process)
    yield page
    page.close()


@pytest.fixture
def expected_stocks():
    """Expected stock data from example_data.xlsx."""
    return {
        "NVIDIA CORP": {
            "shares": 129,
            "transactions": 4,
            "currency": "USD",
            "ticker": "NVDA"
        },
        "MICROSOFT CORP": {
            "shares": 30,
            "transactions": 3,
            "currency": "USD",
            "ticker": "MSFT"
        },
        "META PLATFORMS INC": {
            "shares": 68,
            "transactions": 2,
            "currency": "USD",
            "ticker": "META"
        },
        "ALPHABET INC-CL A": {
            "shares": 57,
            "transactions": 2,
            "currency": "USD",
            "ticker": "GOOGL"
        },
        "ADVANCED MICRO DEVICES": {
            "shares": 97,
            "transactions": 3,
            "currency": "USD",
            "ticker": "AMD"
        },
        "ASML HOLDING NV": {
            "shares": 33,
            "transactions": 3,
            "currency": "EUR",
            "ticker": "ASML.AS"
        },
        "SAP SE": {
            "shares": 75,
            "transactions": 2,
            "currency": "EUR",
            "ticker": "SAP.DE"
        },
        "INFINEON TECHNOLOGIES AG": {
            "shares": 400,
            "transactions": 3,
            "currency": "EUR",
            "ticker": "IFX.DE"
        },
        "NOKIA OYJ": {
            "shares": 900,
            "transactions": 2,
            "currency": "EUR",
            "ticker": "NOKIA.HE"
        },
        "TELEFONAKTIEBOLAGET LM ERICSSON-B": {
            "shares": 1400,
            "transactions": 2,
            "currency": "SEK",
            "ticker": "ERIC-B.ST"
        },
        "STMICROELECTRONICS NV": {
            "shares": 240,
            "transactions": 2,
            "currency": "EUR",
            "ticker": "STM.PA"
        }
    }
