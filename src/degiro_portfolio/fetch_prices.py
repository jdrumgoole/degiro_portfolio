"""Fetch historical stock price data for current holdings."""
import yfinance as yf
import pandas as pd
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

# Stocks that should always use Yahoo Finance instead of other providers
# (due to incorrect data from other providers)
YAHOO_FINANCE_OVERRIDE = [
    'AIR.PA',   # Airbus - Twelve Data returns incorrect price
    'ASML.AS',  # ASML - Twelve Data normalizes to US ticker with different prices
]

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

    # Check if this stock is in the Yahoo Finance override list
    if ticker_symbol in YAHOO_FINANCE_OVERRIDE:
        provider = 'yahoo'
        print(f"Fetching prices for {stock.name} ({ticker_symbol}) in {stock.currency} [Provider: {provider} - FORCED OVERRIDE]")
        print(f"  Reason: Other providers return incorrect data for this stock")
    else:
        provider = Config.PRICE_DATA_PROVIDER
        print(f"Fetching prices for {stock.name} ({ticker_symbol}) in {stock.currency} [Provider: {provider}]")

    print(f"  Period: {start_date.date()} to {end_date.date()}")

    # Track which provider actually provided the data
    actual_provider = provider

    try:
        # Get the appropriate price fetcher (use overridden provider if set)
        fetcher = get_price_fetcher(provider)
        hist = fetcher.fetch_prices(ticker_symbol, start_date, end_date)

        # Check if we should fall back to Yahoo Finance
        should_fallback = False
        if hist.empty:
            should_fallback = True
        elif provider != 'yahoo' and not hist.empty:
            # Check if we're missing today's data
            today = datetime.now().date()
            latest_date = hist.index[-1].date() if hasattr(hist.index[-1], 'date') else hist.index[-1].to_pydatetime().date()
            if latest_date < today:
                should_fallback = True

        # If primary provider returns no data or missing today's data, fall back to Yahoo Finance
        # CRITICAL: Use original ticker (ticker_symbol), not FMP-normalized ticker
        if should_fallback and provider != 'yahoo':
            if hist.empty:
                print(f"  ⚠️  No data from {provider}, trying Yahoo Finance as fallback...")
            else:
                print(f"  ⚠️  {provider} missing today's data (latest: {latest_date}), trying Yahoo Finance as fallback...")

            try:
                from .price_fetchers import YahooFinanceFetcher
            except ImportError:
                from degiro_portfolio.price_fetchers import YahooFinanceFetcher
            yahoo_fetcher = YahooFinanceFetcher()
            # Use ticker_symbol directly (e.g., SAAB-B.ST, not SAABY)
            yahoo_hist = yahoo_fetcher.fetch_prices(ticker_symbol, start_date, end_date)
            if not yahoo_hist.empty:
                # Normalize timezones before merging
                if not hist.empty:
                    # Convert both to timezone-naive for comparison
                    if hasattr(hist.index, 'tz') and hist.index.tz is not None:
                        hist.index = hist.index.tz_localize(None)
                    if hasattr(yahoo_hist.index, 'tz') and yahoo_hist.index.tz is not None:
                        yahoo_hist.index = yahoo_hist.index.tz_localize(None)

                    # Combine: Yahoo data for newer dates, Twelve Data for existing
                    latest_twelve_date = hist.index[-1]
                    yahoo_new = yahoo_hist[yahoo_hist.index > latest_twelve_date]
                    if not yahoo_new.empty:
                        hist = pd.concat([hist, yahoo_new])
                else:
                    hist = yahoo_hist
                    # Ensure timezone-naive
                    if hasattr(hist.index, 'tz') and hist.index.tz is not None:
                        hist.index = hist.index.tz_localize(None)

                print(f"  ✓ Using Yahoo Finance data")
                actual_provider = 'yahoo'  # Track that we fell back to Yahoo

        if hist.empty:
            print(f"  ❌ No price data available from any provider")
            return 0

        # Detect the actual trading currency from the exchange
        # This is important because stock.currency is from DEGIRO transactions (may be EUR),
        # but the actual price data is in the native exchange currency (e.g., SEK for Stockholm)
        actual_currency = stock.currency  # Default to DEGIRO's currency

        # Try to get actual currency from ticker info
        try:
            import yfinance as yf
            ticker_info = yf.Ticker(ticker_symbol)
            exchange_currency = ticker_info.info.get('currency')
            if exchange_currency:
                actual_currency = exchange_currency
                if actual_currency != stock.currency:
                    print(f"  ℹ️  Price currency: {actual_currency} (DEGIRO uses {stock.currency})")
        except Exception:
            pass  # If we can't get currency info, use stock.currency

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
                currency=actual_currency  # Store prices in actual exchange currency
            )
            session.add(price)
            count += 1

        session.commit()

        # Update the stock's data provider field (even if no new records added)
        if stock.data_provider != actual_provider:
            stock.data_provider = actual_provider
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
