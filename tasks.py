"""
Invoke tasks for DEGIRO Portfolio application.

Usage:
    Production Server:
        invoke start         - Start the application
        invoke stop          - Stop the application
        invoke restart       - Restart the application
        invoke status        - Check application status

    Data Management:
        invoke import-data   - Import transactions from Excel, fetch prices, and fetch indices (default: Transactions.xlsx)
        invoke load-demo     - Load demo data (example_data.xlsx), fetch prices, and fetch indices
        invoke fetch-prices  - Fetch latest stock prices
        invoke fetch-indices - Fetch market index data (S&P 500, Euro Stoxx 50)
        invoke setup         - Complete setup (same as import-data)
        invoke demo-setup    - Complete demo setup (same as load-demo)
        invoke purge-data    - Purge all portfolio data (stops server, removes database, restarts server)

    Test Server (Port 8001):
        invoke test-full-setup       - Set up test database and start test server on port 8001
        invoke test-server-start     - Start test server (--port 8001, --database degiro_portfolio-test.db)
        invoke test-server-stop      - Stop test server (--port 8001)
        invoke test-server-restart   - Restart test server
        invoke test-server-status    - Check test server status
        invoke setup-test-db         - Set up test database with example data

    Testing:
        invoke test              - Run all tests
        invoke test-cov          - Run tests with coverage report
        invoke test-cov-html     - Run tests with HTML coverage report
        invoke test-unit         - Run only unit tests (fast)
        invoke test-integration  - Run integration tests (browser tests)

    Development:
        invoke dev           - Start development server with auto-reload

    Cleanup:
        invoke prodclean     - Clean production files (includes production database)
        invoke testclean     - Clean test database and test server files
"""
from invoke import task
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent


@task
def start(c):
    """Start the DEGIRO Portfolio server."""
    c.run("./degiro_portfolio start", pty=True)


@task
def stop(c):
    """Stop the Stock Chart server."""
    c.run("./degiro_portfolio stop", pty=True)


@task
def restart(c):
    """Restart the Stock Chart server."""
    c.run("./degiro_portfolio restart", pty=True)


@task
def status(c):
    """Check server status."""
    c.run("./degiro_portfolio status", pty=True)


@task
def import_data(c, file=None):
    """Import transaction data from Excel, fetch prices, and fetch indices."""
    print("📥 Importing transaction data...")
    if file:
        c.run(f"uv run python -c \"from src.degiro_portfolio.import_data import import_transactions; import_transactions('{file}')\"", pty=True)
    else:
        c.run("uv run python src/degiro_portfolio/import_data.py", pty=True)
    print()
    fetch_prices(c)
    print()
    fetch_indices(c)


@task
def load_demo(c):
    """Load demo data (example_data.xlsx), fetch prices, and fetch indices."""
    print("📥 Loading demo data...")
    c.run("uv run python -c \"from src.degiro_portfolio.import_data import import_transactions; import_transactions('example_data.xlsx')\"", pty=True)
    print()
    fetch_prices(c)
    print()
    fetch_indices(c)


@task
def fetch_prices(c):
    """Fetch historical stock prices."""
    print("📈 Fetching stock prices...")
    c.run("uv run python src/degiro_portfolio/fetch_prices.py", pty=True)


@task
def fetch_indices(c):
    """Fetch historical index data (S&P 500, Euro Stoxx 50)."""
    print("📊 Fetching market index data...")
    c.run("uv run python src/degiro_portfolio/fetch_indices.py", pty=True)


@task
def setup(c):
    """Complete setup: import data, fetch prices, and fetch indices."""
    print("🔧 Setting up DEGIRO Portfolio application...\n")
    import_data(c)
    print("\n✅ Setup complete! Run 'invoke start' to launch the application.")


@task
def demo_setup(c):
    """Complete demo setup: load demo data, fetch prices, and fetch indices."""
    print("🔧 Setting up DEGIRO Portfolio with demo data...\n")
    load_demo(c)
    print("\n✅ Demo setup complete! Run 'invoke start' to launch the application.")


@task
def purge_data(c):
    """Purge all portfolio data (removes database only) and restart server."""
    print("⚠️  WARNING: This will delete all portfolio data (stocks, transactions, prices)")
    print("   Database file will be removed: degiro_portfolio.db")

    response = input("\n   Are you sure you want to continue? (yes/no): ")

    if response.lower() in ['yes', 'y']:
        # Stop the server first
        print("\n🛑 Stopping server...")
        try:
            stop(c)
        except Exception as e:
            print(f"   Note: Server may not have been running ({e})")

        # Purge the database files
        db_files = [
            "degiro_portfolio.db",
            "stockchart.db",  # Legacy database name
        ]

        removed = False
        for file in db_files:
            file_path = PROJECT_ROOT / file
            if file_path.exists():
                file_path.unlink()
                print(f"   ✓ Removed: {file}")
                removed = True

        if removed:
            print("\n✅ Data purged successfully")
            print("   Run 'invoke load-demo' or 'invoke import-data' to reload data")
            print("   (Indices will be fetched automatically)")
        else:
            print("\n   No database files found")

        # Start the server
        print("\n🚀 Starting server...")
        try:
            start(c)
        except Exception as e:
            print(f"   Error starting server: {e}")
            print("   You may need to run 'invoke start' manually")
    else:
        print("\n   Cancelled - no data was deleted")


@task
def prodclean(c):
    """Clean production files (includes production database)."""
    print("🧹 Cleaning production files...")

    files_to_remove = [
        ".degiro_portfolio.pid",
        "degiro_portfolio.log",
        "degiro_portfolio.db",
        "stockchart.db",  # Legacy database name
        ".stockchart.pid",  # Legacy PID file
        "stockchart.log",   # Legacy log file
        "examine_data.py"
    ]

    for file in files_to_remove:
        file_path = PROJECT_ROOT / file
        if file_path.exists():
            file_path.unlink()
            print(f"   Removed: {file}")

    # Clean pycache
    c.run("find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true")
    c.run("find . -name '*.pyc' -delete 2>/dev/null || true")

    print("✅ Production cleanup complete")


@task
def testclean(c):
    """Clean test database and test server files."""
    print("🧹 Cleaning test files...")

    files_to_remove = [
        "degiro_portfolio-test.db",
        ".degiro_portfolio-test.pid",
        "degiro_portfolio-test.log",
    ]

    for file in files_to_remove:
        file_path = PROJECT_ROOT / file
        if file_path.exists():
            file_path.unlink()
            print(f"   Removed: {file}")

    print("✅ Test cleanup complete")


@task
def test(c):
    """Run tests."""
    print("🧪 Running tests...")
    c.run("uv run pytest", pty=True)


@task
def test_cov(c):
    """Run tests with coverage report."""
    print("🧪 Running tests with coverage...")
    c.run("uv run pytest --cov=src/degiro_portfolio --cov-report=term-missing", pty=True)


@task
def test_cov_html(c):
    """Run tests with HTML coverage report."""
    print("🧪 Running tests with HTML coverage report...")
    c.run("uv run pytest --cov=src/degiro_portfolio --cov-report=html", pty=True)
    print("\n✅ Coverage report generated in htmlcov/index.html")
    print("   Open htmlcov/index.html in your browser to view detailed coverage")


@task
def test_unit(c):
    """Run only unit tests (fast)."""
    print("🧪 Running unit tests...")
    c.run("uv run pytest tests/test_*_unit.py -v", pty=True)


@task
def test_integration(c):
    """Run integration tests (slower, uses browser)."""
    print("🧪 Running integration tests...")
    c.run("uv run pytest tests/test_portfolio_overview.py tests/test_stock_charts.py tests/test_interactive_features.py -v", pty=True)


@task
def lint(c):
    """Run linting checks."""
    print("🔍 Running linting checks...")
    c.run("uv run ruff check src/", pty=True)


@task
def format_code(c):
    """Format code."""
    print("✨ Formatting code...")
    c.run("uv run ruff format src/", pty=True)


@task(pre=[stop, prodclean])
def reset(c):
    """Reset production environment (stop server, clean all production data)."""
    print("\n⚠️  All production data has been cleaned. Run 'invoke setup' to reinitialize.")


@task
def logs(c, lines=50):
    """Show server logs."""
    log_file = PROJECT_ROOT / "degiro_portfolio.log"
    # Fall back to old log file name for backwards compatibility
    if not log_file.exists():
        log_file = PROJECT_ROOT / "stockchart.log"

    if log_file.exists():
        c.run(f"tail -n {lines} {log_file}", pty=True)
    else:
        print("No log file found. Server may not be running.")


@task
def db_info(c):
    """Show database information."""
    print("📊 Database Information:")
    c.run("""uv run python -c "
from src.degiro_portfolio.database import SessionLocal, Stock, Transaction, StockPrice, Index, IndexPrice
from sqlalchemy import func

session = SessionLocal()

# Stocks
stock_count = session.query(Stock).count()
print(f'  Stocks: {stock_count}')

# Transactions
trans_count = session.query(Transaction).count()
print(f'  Transactions: {trans_count}')

# Prices
price_count = session.query(StockPrice).count()
print(f'  Price records: {price_count}')

# Indices
index_count = session.query(Index).count()
print(f'  Indices: {index_count}')
indices = session.query(Index).all()
for index in indices:
    index_price_count = session.query(IndexPrice).filter_by(index_id=index.id).count()
    print(f'    {index.name}: {index_price_count} price records')

# Current holdings
print('\\n  Current Holdings:')
stocks = session.query(Stock).all()
for stock in stocks:
    total_qty = session.query(func.sum(Transaction.quantity)).filter_by(stock_id=stock.id).scalar() or 0
    if total_qty > 0:
        print(f'    {stock.name}: {total_qty} shares')

session.close()
"
""", pty=True)


@task
def dev(c):
    """Start development server with auto-reload."""
    print("🔧 Starting development server with auto-reload...")
    c.run("cd src/degiro_portfolio && uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000", pty=True)


@task
def install(c):
    """Install dependencies."""
    print("📦 Installing dependencies...")
    c.run("uv sync", pty=True)
    print("✅ Dependencies installed")


@task
def build_docs(c):
    """Build Sphinx documentation."""
    print("📚 Building documentation...")
    c.run("cd docs && uv run sphinx-build -b html . _build/html", pty=True)
    print("✅ Documentation built in docs/_build/html/")
    print("   Open docs/_build/html/index.html to view")


@task
def clean_docs(c):
    """Clean built documentation."""
    print("🧹 Cleaning documentation build...")
    c.run("rm -rf docs/_build", pty=True)
    print("✅ Documentation build cleaned")


@task
def serve_docs(c):
    """Serve documentation locally."""
    print("📖 Serving documentation on http://localhost:8080")
    c.run("cd docs/_build/html && python -m http.server 8080", pty=True)


@task
def help_tasks(c):
    """Show available tasks."""
    c.run("invoke --list")


# ============================================================================
# Test Server Management
# ============================================================================

@task
def test_server_start(c, port=8001, database="degiro_portfolio-test.db"):
    """Start test server on specified port with test database."""
    c.run(f"uv run python test_server.py start --port {port} --database {database}", pty=True)


@task
def test_server_stop(c, port=8001):
    """Stop test server on specified port."""
    c.run(f"uv run python test_server.py stop --port {port}", pty=True)


@task
def test_server_restart(c, port=8001, database="degiro_portfolio-test.db"):
    """Restart test server on specified port."""
    c.run(f"uv run python test_server.py restart --port {port} --database {database}", pty=True)


@task
def test_server_status(c, port=8001):
    """Check test server status."""
    c.run(f"uv run python test_server.py status --port {port}", pty=True)


@task
def setup_test_db(c, database="degiro_portfolio-test.db"):
    """Set up test database with example data."""
    db_path = f"$(pwd)/{database}"

    # Remove old database
    c.run(f"rm -f {database}")

    print("📥 Importing example data...")
    c.run(f"""DATABASE_URL="sqlite:///{db_path}" uv run python -c "
from src.degiro_portfolio.import_data import import_transactions
import_transactions('example_data.xlsx')
"
""", pty=True)

    print("\n📊 Fetching market indices...")
    c.run(f"""DATABASE_URL="sqlite:///{db_path}" uv run python -c "
from src.degiro_portfolio.fetch_indices import fetch_index_prices
fetch_index_prices()
"
""", pty=True)

    print("\n📈 Fetching stock prices...")
    c.run(f"""DATABASE_URL="sqlite:///{db_path}" uv run python -c "
from src.degiro_portfolio.fetch_prices import fetch_all_current_holdings
fetch_all_current_holdings()
"
""", pty=True)

    print(f"\n✅ Test database created: {database}")


@task
def test_full_setup(c, port=8001):
    """Complete test setup: create database, load data, and start server."""
    print("🔧 Setting up test environment...\n")

    # Set up test database
    setup_test_db(c)

    print("\n🚀 Starting test server...")
    test_server_start(c, port=port)

    print(f"\n✅ Test environment ready!")
    print(f"   URL: http://localhost:{port}")
    print(f"   Database: degiro_portfolio-test.db")
