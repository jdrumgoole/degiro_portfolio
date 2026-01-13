"""Fetch historical stock price data for current holdings."""
import yfinance as yf
from datetime import datetime, timedelta
try:
    from .database import SessionLocal, Stock, StockPrice, Transaction
    from .config import Config
    from .price_fetchers import get_price_fetcher
except ImportError:
    from degiro_portfolio.database import SessionLocal, Stock, StockPrice, Transaction
    from degiro_portfolio.config import Config
    from degiro_portfolio.price_fetchers import get_price_fetcher
from sqlalchemy import func

# NOTE: Hard-coded ticker mappings have been replaced by automatic resolution
# via ticker_resolver.py. Tickers are now stored in the database and resolved
# automatically during import. See ticker_resolver.py for manual fallback mappings.

def get_ticker_for_stock(stock):
    """
    Get Yahoo Finance ticker for a stock.

    Uses the ticker stored in the database (resolved during import).
    If no ticker is stored, attempts to resolve it now.
    """
    # Use stored ticker if available
    if stock.yahoo_ticker:
        return stock.yahoo_ticker

    # If no ticker stored, try to resolve it now
    print(f"  ⚠️  No ticker found for {stock.name} ({stock.isin}), attempting to resolve...")

    try:
        from .ticker_resolver import get_ticker_for_stock as resolve_ticker
    except ImportError:
        from degiro_portfolio.ticker_resolver import get_ticker_for_stock as resolve_ticker

    ticker = resolve_ticker(stock.isin, stock.name, stock.currency)

    if ticker:
        # Store the resolved ticker in the database for future use
        stock.yahoo_ticker = ticker
        print(f"  ✓ Resolved and stored ticker: {ticker}")
        return ticker
    else:
        print(f"  ✗ Could not resolve ticker for {stock.name}")
        print(f"     You may need to manually add the ticker to the database or")
        print(f"     add a manual mapping in src/degiro_portfolio/ticker_resolver.py")
        return None

def fetch_stock_prices(stock, session, start_date=None, end_date=None):
    """Fetch historical prices for a stock using configured data provider."""
    ticker_symbol = get_ticker_for_stock(stock)
    if not ticker_symbol:
        return 0

    # If no start date provided, use the earliest transaction date
    if not start_date:
        earliest_trans = session.query(func.min(Transaction.date)).filter_by(
            stock_id=stock.id
        ).scalar()
        if earliest_trans:
            start_date = earliest_trans.date()
        else:
            start_date = datetime.now().date() - timedelta(days=365)

    if not end_date:
        end_date = datetime.now().date()

    # Convert dates to datetime for fetcher
    if not isinstance(start_date, datetime):
        start_date = datetime.combine(start_date, datetime.min.time())
    if not isinstance(end_date, datetime):
        end_date = datetime.combine(end_date, datetime.max.time())

    provider = Config.PRICE_DATA_PROVIDER
    print(f"Fetching prices for {stock.name} ({ticker_symbol}) in {stock.currency} [Provider: {provider}]")
    print(f"  Period: {start_date.date()} to {end_date.date()}")

    try:
        # Get the appropriate price fetcher
        fetcher = get_price_fetcher()
        hist = fetcher.fetch_prices(ticker_symbol, start_date, end_date)

        # If primary provider returns no data, fall back to Yahoo Finance
        # CRITICAL: Use original ticker (ticker_symbol), not FMP-normalized ticker
        if hist.empty and provider != 'yahoo':
            print(f"  ⚠️  No data from {provider}, trying Yahoo Finance as fallback...")
            try:
                from .price_fetchers import YahooFinanceFetcher
            except ImportError:
                from degiro_portfolio.price_fetchers import YahooFinanceFetcher
            yahoo_fetcher = YahooFinanceFetcher()
            # Use ticker_symbol directly (e.g., SAAB-B.ST, not SAABY)
            hist = yahoo_fetcher.fetch_prices(ticker_symbol, start_date, end_date)
            if not hist.empty:
                print(f"  ✓ Using Yahoo Finance data")

        if hist.empty:
            print(f"  ❌ No price data available from any provider")
            return 0

        count = 0
        for date, row in hist.iterrows():
            # Check if price already exists for this date
            existing = session.query(StockPrice).filter_by(
                stock_id=stock.id,
                date=date
            ).first()

            if existing:
                continue

            price = StockPrice(
                stock_id=stock.id,
                date=date,
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=int(row['volume']),
                currency=stock.currency  # Store prices in native currency
            )
            session.add(price)
            count += 1

        session.commit()
        print(f"  ✅ Added {count} price records\n")
        return count

    except Exception as e:
        print(f"  ❌ Error fetching prices: {e}\n")
        session.rollback()
        return 0

def fetch_all_current_holdings():
    """Fetch prices for all stocks with current holdings."""
    session = SessionLocal()
    try:
        # Get all stocks
        stocks = session.query(Stock).all()

        # Filter to only stocks with current holdings
        current_holdings = []
        for stock in stocks:
            total_qty = session.query(func.sum(Transaction.quantity)).filter_by(
                stock_id=stock.id
            ).scalar() or 0

            if total_qty > 0:
                current_holdings.append(stock)
                print(f"Found holding: {stock.name} - {total_qty} shares (Currency: {stock.currency})")

        print(f"\n{'='*80}")
        print(f"Fetching prices for {len(current_holdings)} stocks")
        print(f"{'='*80}\n")

        total_records = 0
        for stock in current_holdings:
            records = fetch_stock_prices(stock, session)
            total_records += records

        print(f"{'='*80}")
        print(f"✅ Fetch complete! Added {total_records} total price records")
        print(f"{'='*80}")

    finally:
        session.close()

if __name__ == "__main__":
    fetch_all_current_holdings()
