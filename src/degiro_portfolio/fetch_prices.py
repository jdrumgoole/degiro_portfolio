"""Fetch historical stock price data for current holdings."""
import yfinance as yf
from datetime import datetime, timedelta
try:
    from src.degiro_portfolio.database import SessionLocal, Stock, StockPrice, Transaction
except ModuleNotFoundError:
    from database import SessionLocal, Stock, StockPrice, Transaction
from sqlalchemy import func

# Manual mapping of ISIN to Yahoo Finance ticker symbols
# Format: ISIN -> {currency: ticker}
ISIN_TO_TICKER = {
    "SE0021921269": {"SEK": "SAAB-B.ST", "EUR": "SAAB-B.ST"},  # SAAB AB - Stockholm (SEK)
    "NL0000687663": {"USD": "AER"},  # AERCAP HOLDINGS
    "NL0010273215": {"EUR": "ASML"},  # ASML HOLDING
    "IT0003856405": {"EUR": "LDO.MI"},  # LEONARDO SPA
    "NL0000235190": {"EUR": "AIR.PA"},  # AIRBUS GROUP
    "DE0007030009": {"EUR": "RHM.DE"},  # RHEINMETALL AG
    "US82669G1040": {"USD": "SBNY"},  # SIGNATURE BANK (delisted)
}

def get_ticker_for_stock(stock):
    """Get Yahoo Finance ticker for a stock in its native currency."""
    isin_map = ISIN_TO_TICKER.get(stock.isin)
    if not isin_map:
        print(f"Warning: No ticker mapping for {stock.name} ({stock.isin})")
        return None

    # Get ticker for the stock's native currency
    ticker = isin_map.get(stock.currency)
    if not ticker and isinstance(isin_map, dict):
        # Fallback to first available ticker
        ticker = list(isin_map.values())[0]
    elif isinstance(isin_map, str):
        # Old format compatibility
        ticker = isin_map

    return ticker

def fetch_stock_prices(stock, session, start_date=None, end_date=None):
    """Fetch historical prices for a stock."""
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

    print(f"Fetching prices for {stock.name} ({ticker_symbol}) in {stock.currency}")
    print(f"  Period: {start_date} to {end_date}")

    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(start=start_date, end=end_date)

        if hist.empty:
            print(f"  ❌ No price data available")
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
                open=float(row['Open']),
                high=float(row['High']),
                low=float(row['Low']),
                close=float(row['Close']),
                volume=int(row['Volume']),
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
