"""
Invoke tasks for DEGIRO Portfolio application.

Usage:
    invoke start         - Start the application
    invoke stop          - Stop the application
    invoke restart       - Restart the application
    invoke status        - Check application status
    invoke import-data   - Import transactions from Excel
    invoke fetch-prices  - Fetch latest stock prices
    invoke fetch-indices - Fetch market index data (S&P 500, Euro Stoxx 50)
    invoke setup         - Complete setup (import + fetch)
    invoke clean         - Clean generated files
    invoke test          - Run tests
"""
from invoke import task
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent


@task
def start(c):
    """Start the DEGIRO Portfolio server."""
    c.run("./degiro-portfolio start", pty=True)


@task
def stop(c):
    """Stop the Stock Chart server."""
    c.run("./degiro-portfolio stop", pty=True)


@task
def restart(c):
    """Restart the Stock Chart server."""
    c.run("./degiro-portfolio restart", pty=True)


@task
def status(c):
    """Check server status."""
    c.run("./degiro-portfolio status", pty=True)


@task
def import_data(c):
    """Import transaction data from Excel."""
    print("📥 Importing transaction data...")
    c.run("uv run python src/degiro_portfolio/import_data.py", pty=True)


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
    """Complete setup: import data and fetch prices."""
    print("🔧 Setting up DEGIRO Portfolio application...\n")
    import_data(c)
    print()
    fetch_prices(c)
    print()
    fetch_indices(c)
    print("\n✅ Setup complete! Run 'invoke start' to launch the application.")


@task
def clean(c):
    """Clean generated files."""
    print("🧹 Cleaning generated files...")

    files_to_remove = [
        ".degiro-portfolio.pid",
        "degiro-portfolio.log",
        "stockchart.db",  # Keep for backwards compatibility
        ".stockchart.pid",  # Keep for backwards compatibility
        "stockchart.log",   # Keep for backwards compatibility
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

    print("✅ Cleanup complete")


@task
def test(c):
    """Run tests."""
    print("🧪 Running tests...")
    c.run("uv run pytest", pty=True)


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


@task(pre=[stop, clean])
def reset(c):
    """Reset everything (stop server, clean all data)."""
    print("\n⚠️  All data has been cleaned. Run 'invoke setup' to reinitialize.")


@task
def logs(c, lines=50):
    """Show server logs."""
    log_file = PROJECT_ROOT / "degiro-portfolio.log"
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
def help_tasks(c):
    """Show available tasks."""
    c.run("invoke --list")
