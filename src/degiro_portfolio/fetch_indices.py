"""Fetch historical index data for benchmarking."""
import sys
from datetime import datetime
import yfinance as yf

try:
    from src.degiro_portfolio.database import SessionLocal, init_db, Index, IndexPrice
except ModuleNotFoundError:
    from database import SessionLocal, init_db, Index, IndexPrice


INDICES = {
    "^GSPC": "S&P 500",
    "^STOXX50E": "Euro Stoxx 50"
}


def fetch_index_prices():
    """Fetch historical prices for market indices."""
    # Initialize database to create tables if they don't exist
    init_db()

    session = SessionLocal()
    try:
        for symbol, name in INDICES.items():
            print(f"\nFetching data for {name} ({symbol})...")

            # Check if index already exists
            index = session.query(Index).filter_by(symbol=symbol).first()
            if not index:
                index = Index(symbol=symbol, name=name)
                session.add(index)
                session.commit()
                print(f"  Created index: {name}")
            else:
                print(f"  Index exists: {name}")

            # Delete existing prices to refresh data
            existing_count = session.query(IndexPrice).filter_by(index_id=index.id).count()
            if existing_count > 0:
                session.query(IndexPrice).filter_by(index_id=index.id).delete()
                print(f"  Deleted {existing_count} existing price records")

            # Fetch historical data (5 years)
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5y")

            if hist.empty:
                print(f"  ⚠️  No data available for {symbol}")
                continue

            # Store prices
            price_count = 0
            for date, row in hist.iterrows():
                price = IndexPrice(
                    index_id=index.id,
                    date=date.to_pydatetime(),
                    close=float(row['Close'])
                )
                session.add(price)
                price_count += 1

            session.commit()
            print(f"  ✅ Stored {price_count} price records")
            print(f"  Date range: {hist.index[0].date()} to {hist.index[-1].date()}")

        print("\n✅ All index data fetched successfully")

    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    fetch_index_prices()
