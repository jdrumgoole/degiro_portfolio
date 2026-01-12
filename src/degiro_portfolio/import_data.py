"""Import transaction data from Excel into SQLite database."""
import pandas as pd
from datetime import datetime
from collections import Counter
try:
    from src.degiro_portfolio.database import SessionLocal, init_db, Stock, Transaction
    from src.degiro_portfolio.ticker_resolver import get_ticker_for_stock
    from src.degiro_portfolio.config import Config, get_column
except ModuleNotFoundError:
    from database import SessionLocal, init_db, Stock, Transaction
    from ticker_resolver import get_ticker_for_stock
    from config import Config, get_column


def parse_date(date_str, time_str):
    """Parse date and time strings into datetime object."""
    # Format: DD-MM-YYYY and HH:MM
    datetime_str = f"{date_str} {time_str}"
    return datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")


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
            print(f"  Created stock: {product} (Native currency: {native_currency}, Ticker: {yahoo_ticker})")
        else:
            print(f"  Created stock: {product} (Native currency: {native_currency}, Ticker: NOT RESOLVED)")
            print(f"    WARNING: Could not automatically resolve Yahoo Finance ticker for ISIN {isin}")
            print(f"    Price fetching will not work until ticker is manually added to the database")

    elif stock and not stock.yahoo_ticker:
        # Stock exists but ticker wasn't resolved - try to resolve it now
        yahoo_ticker = get_ticker_for_stock(stock.isin, stock.name, stock.currency)
        if yahoo_ticker:
            stock.yahoo_ticker = yahoo_ticker
            session.flush()
            print(f"  Resolved ticker for {stock.name}: {yahoo_ticker}")

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

    print("Initializing database...")
    init_db()

    print(f"Reading {excel_file}...")
    df = pd.read_excel(excel_file)

    print(f"Found {len(df)} transactions\n")

    session = SessionLocal()
    try:
        imported = 0

        print("Creating stocks with native currencies...")

        for idx, row in df.iterrows():
            # Check if stock is in the ignore list
            isin = row[get_column('isin')]
            if isin in Config.IGNORED_STOCKS:
                print(f"  ⏭️  Skipping ignored stock: {row[get_column('product')]} (ISIN: {isin})")
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
                print(f"Processed {idx + 1} transactions...")

        session.commit()
        print(f"\n✅ Import complete!")
        print(f"   Imported: {imported} transactions\n")

        # Show summary with currencies
        print("="*80)
        print("Stocks in database:")
        print("="*80)
        stocks = session.query(Stock).all()
        for stock in stocks:
            trans_count = session.query(Transaction).filter_by(stock_id=stock.id).count()
            total_qty = session.query(Transaction).filter_by(stock_id=stock.id).with_entities(
                Transaction.quantity
            ).all()
            current_holding = sum(q[0] for q in total_qty)

            # Get currency breakdown for this stock
            transactions = session.query(Transaction).filter_by(stock_id=stock.id).all()
            currency_breakdown = Counter(t.currency for t in transactions)
            currency_str = ", ".join(f"{curr}: {count}" for curr, count in currency_breakdown.items())

            status = f"{current_holding} shares" if current_holding > 0 else "SOLD"
            print(f"  {stock.name}")
            print(f"    Native: {stock.currency} | Holdings: {status}")
            print(f"    Transactions: {trans_count} ({currency_str})")
            print()

    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import_transactions()
