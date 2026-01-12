"""Pytest configuration and fixtures for DEGIRO Portfolio tests."""

import os
import shutil
import subprocess
import time
import signal
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page


# Test configuration - isolated from production
TEST_PORT = 8001
TEST_HOST = "127.0.0.1"
TEST_DB_DIR = Path(__file__).parent / ".test_data"
TEST_DB_PATH = TEST_DB_DIR / "test_portfolio.db"
EXAMPLE_DATA = "example_data.xlsx"


@pytest.fixture(scope="session", autouse=True)
def test_environment():
    """Set up isolated test environment before any tests run."""
    # Save original environment variables
    original_env = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "PORT": os.environ.get("PORT"),
    }

    # Create test data directory
    TEST_DB_DIR.mkdir(exist_ok=True)

    # Clean up any existing test data
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    # Clean up any leftover test files
    for backup in TEST_DB_DIR.glob("*.db*"):
        backup.unlink()

    yield

    # Restore original environment variables
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    # Clean up test data directory
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    # Remove test data directory if empty
    try:
        TEST_DB_DIR.rmdir()
    except OSError:
        pass  # Directory not empty or doesn't exist


@pytest.fixture(scope="session")
def test_database():
    """Create a test database with example data in isolated location."""
    # Set test database path
    test_db_absolute = str(TEST_DB_PATH.absolute())
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db_absolute}"

    print(f"\n📦 Creating test database: {test_db_absolute}")

    # Import the example data
    from degiro_portfolio.import_data import import_transactions
    import_transactions(EXAMPLE_DATA)

    # Fetch prices for the stocks
    from degiro_portfolio.fetch_prices import fetch_all_current_holdings
    fetch_all_current_holdings()

    # Fetch market indices
    from degiro_portfolio.fetch_indices import fetch_index_prices
    fetch_index_prices()

    print(f"✅ Test database created successfully")

    yield test_db_absolute


@pytest.fixture(scope="session")
def server_process(test_database):
    """Start dedicated FastAPI test server on isolated port."""
    # Ensure test server uses test database
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{test_database}"
    env["PORT"] = str(TEST_PORT)

    # Check if port is already in use
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((TEST_HOST, TEST_PORT))
    sock.close()

    if result == 0:
        raise Exception(
            f"Port {TEST_PORT} is already in use. Please stop any services using this port.\n"
            f"Run: lsof -ti:{TEST_PORT} | xargs kill -9"
        )

    print(f"\n🚀 Starting test server on {TEST_HOST}:{TEST_PORT}")

    # Start the server in a subprocess
    process = subprocess.Popen(
        [
            "uv", "run", "uvicorn",
            "degiro_portfolio.main:app",
            "--host", TEST_HOST,
            "--port", str(TEST_PORT),
            "--log-level", "warning"  # Reduce log noise during tests
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid  # Create new process group for clean shutdown
    )

    # Wait for server to be ready
    import httpx
    test_url = f"http://{TEST_HOST}:{TEST_PORT}"
    max_retries = 30

    for i in range(max_retries):
        try:
            response = httpx.get(f"{test_url}/api/holdings", timeout=1.0)
            if response.status_code == 200:
                print(f"✅ Test server ready at {test_url}")
                break
        except (httpx.ConnectError, httpx.ReadTimeout):
            if i == max_retries - 1:
                # Kill the process group
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                raise Exception(f"Test server failed to start on port {TEST_PORT}")
            time.sleep(0.5)

    yield test_url

    # Cleanup: Kill the process group to ensure all subprocesses are terminated
    print(f"\n🛑 Shutting down test server")
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        # Force kill if graceful shutdown fails
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass

    # Ensure port is freed
    time.sleep(0.5)


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
