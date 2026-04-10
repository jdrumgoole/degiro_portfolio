"""Import transaction data from Excel into SQLite database."""
import logging
import pandas as pd
from datetime import datetime
from collections import Counter
from dateutil.parser import parse as dateutil_parse

logger = logging.getLogger(__name__)
try:
    from .database import SessionLocal, init_db, Stock, Transaction, StockPrice
    from .ticker_resolver import get_ticker_for_stock
    from .config import Config, get_column
    from .fetch_prices import fetch_stock_prices
except ImportError:
    from degiro_portfolio.database import SessionLocal, init_db, Stock, Transaction, StockPrice
    from degiro_portfolio.ticker_resolver import get_ticker_for_stock
    from degiro_portfolio.config import Config, get_column
    from degiro_portfolio.fetch_prices import fetch_stock_prices


def parse_date(date_val, time_str):
    """Parse date and time values into a datetime object.

    Uses dateutil for robust parsing of any date format.
    DEGIRO exports use day-first format (DD-MM-YYYY), so dayfirst=True.

    Handles:
      - pandas Timestamp (auto-parsed by read_excel)
      - Any string date format (DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, etc.)
    """
    if isinstance(date_val, datetime):
        dt = date_val
        if isinstance(time_str, str) and ":" in time_str:
            parts = time_str.split(":")
            dt = dt.replace(hour=int(parts[0]), minute=int(parts[1]))
        return dt

    date_str = str(date_val)
    datetime_str = f"{date_str} {time_str}"
    return dateutil_parse(datetime_str, dayfirst=True)


def determine_native_currency(df, product):
    """Determine the native/primary currency for a stock based on transactions."""
    product_col = get_column('product')
    currency_col = get_column('currency')

    product_df = df[df[product_col] == product]

    # Count transactions by currency
    currency_counts = Counter(product_df[currency_col].values)

    # Get the most common currency
    if currency_counts:
        native_currency = currency_counts.most_common(1)[0][0]
        return native_currency

    return "EUR"  # Default fallback


def get_or_create_stock(session, df, product, isin, exchange):
    """Get existing stock or create new one with native currency and resolved ticker."""
    stock = session.query(Stock).filter_by(isin=isin).first()
    if not stock:
        # Determine native currency for this stock
        native_currency = determine_native_currency(df, product)

        # Extract a reasonable symbol from the product name
        symbol = product.split()[0].upper()

        # Attempt to resolve Yahoo Finance ticker automatically
        yahoo_ticker = get_ticker_for_stock(isin, product, native_currency)

        stock = Stock(
            symbol=symbol,
            name=product,
            isin=isin,
            exchange=exchange,
            currency=native_currency,
            yahoo_ticker=yahoo_ticker
        )
        session.add(stock)
        session.flush()

        if yahoo_ticker:
            logger.debug("Created stock: %s (currency: %s, ticker: %s)", product, native_currency, yahoo_ticker)
        else:
            logger.warning("Could not resolve ticker for %s (ISIN: %s)", product, isin)

    elif stock and not stock.yahoo_ticker:
        # Stock exists but ticker wasn't resolved - try to resolve it now
        yahoo_ticker = get_ticker_for_stock(stock.isin, stock.name, stock.currency)
        if yahoo_ticker:
            stock.yahoo_ticker = yahoo_ticker
            session.flush()
            logger.debug("Resolved ticker for %s: %s", stock.name, yahoo_ticker)

    return stock


def import_transactions(excel_file=None):
    """Import transactions from Excel file into database."""
    if excel_file is None:
        # Try to find Transactions.xlsx in project root
        import os
        current_dir = os.path.dirname(__file__)
        excel_file = os.path.join(current_dir, "..", "..", "Transactions.xlsx")
        if not os.path.exists(excel_file):
            excel_file = "Transactions.xlsx"  # Try current directory

    logger.debug("Initializing database...")
    init_db()

    logger.debug("Reading %s", excel_file)
    if str(excel_file).lower().endswith('.csv'):
        df = pd.read_csv(excel_file)
    else:
        df = pd.read_excel(excel_file)

    # Rename columns to canonical names (handles 14-col and 18-col formats)
    df = Config.normalize_degiro_columns(df)

    logger.info("Found %d transactions", len(df))

    session = SessionLocal()
    try:
        imported = 0

        logger.debug("Creating stocks with native currencies...")

        for idx, row in df.iterrows():
            # Check if stock is in the ignore list
            isin = row[get_column('isin')]
            if isin in Config.IGNORED_STOCKS:
                logger.debug("Skipping ignored stock: %s (ISIN: %s)", row[get_column('product')], isin)
                continue

            transaction_id = str(row[get_column('transaction_id')])
            transaction_currency = row[get_column('currency')]

            # Get or create stock
            stock = get_or_create_stock(
                session,
                df,
                row[get_column('product')],
                isin,
                row[get_column('exchange')]
            )

            # Parse date and time
            trans_date = parse_date(row[get_column('date')], row[get_column('time')])

            # Create transaction with currency
            transaction = Transaction(
                stock_id=stock.id,
                date=trans_date,
                time=row[get_column('time')],
                quantity=int(row[get_column('quantity')]),
                price=float(row[get_column('price')]),
                currency=transaction_currency,  # Store original currency
                value_eur=float(row[get_column('value_eur')]),
                total_eur=float(row[get_column('total_eur')]),
                venue=row[get_column('venue')],
                exchange_rate=float(row[get_column('exchange_rate')]) if pd.notna(row[get_column('exchange_rate')]) else None,
                fees_eur=float(row[get_column('fees_eur')]) if pd.notna(row[get_column('fees_eur')]) else 0.0,
                transaction_id=transaction_id
            )
            session.add(transaction)
            imported += 1

            if (idx + 1) % 50 == 0:
                logger.debug("Processed %d transactions...", idx + 1)

        session.commit()
        logger.info("Import complete: %d transactions", imported)

        # Fetch prices for all stocks with current holdings
        logger.debug("Fetching prices for current holdings...")
        stocks = session.query(Stock).all()
        total_prices = 0
        stocks_with_prices = 0

        for stock in stocks:
            # Check if stock has current holdings
            total_qty = session.query(Transaction).filter_by(stock_id=stock.id).with_entities(
                Transaction.quantity
            ).all()
            current_holding = sum(q[0] for q in total_qty)

            if current_holding > 0:
                # Only fetch if we haven't already fetched for this stock
                existing_prices = session.query(StockPrice).filter_by(stock_id=stock.id).count()
                if existing_prices == 0:
                    price_count = fetch_stock_prices(stock, session)
                    if price_count > 0:
                        total_prices += price_count
                        stocks_with_prices += 1

        if total_prices > 0:
            logger.info("Fetched %d price records for %d stocks", total_prices, stocks_with_prices)

        # Log summary
        stocks = session.query(Stock).all()
        for stock in stocks:
            trans_count = session.query(Transaction).filter_by(stock_id=stock.id).count()
            total_qty = session.query(Transaction).filter_by(stock_id=stock.id).with_entities(
                Transaction.quantity
            ).all()
            current_holding = sum(q[0] for q in total_qty)
            status = f"{current_holding} shares" if current_holding > 0 else "SOLD"
            logger.debug("%s: %s, %d transactions", stock.name, status, trans_count)

    except Exception as e:
        session.rollback()
        logger.error("Import error: %s", e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import_transactions()
