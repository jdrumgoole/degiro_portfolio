"""Import transaction data from Excel into SQLite database."""
import pandas as pd
from datetime import datetime
from collections import Counter
try:
    from src.degiro_portfolio.database import SessionLocal, init_db, Stock, Transaction
except ModuleNotFoundError:
    from database import SessionLocal, init_db, Stock, Transaction


def parse_date(date_str, time_str):
    """Parse date and time strings into datetime object."""
    # Format: DD-MM-YYYY and HH:MM
    datetime_str = f"{date_str} {time_str}"
    return datetime.strptime(datetime_str, "%d-%m-%Y %H:%M")


def determine_native_currency(df, product):
    """Determine the native/primary currency for a stock based on transactions."""
    product_df = df[df['Product'] == product]

    # Count transactions by currency
    currency_counts = Counter(product_df['Unnamed: 8'].values)

    # Get the most common currency
    if currency_counts:
        native_currency = currency_counts.most_common(1)[0][0]
        return native_currency

    return "EUR"  # Default fallback


def get_or_create_stock(session, df, product, isin, exchange):
    """Get existing stock or create new one with native currency."""
    stock = session.query(Stock).filter_by(isin=isin).first()
    if not stock:
        # Determine native currency for this stock
        native_currency = determine_native_currency(df, product)

        # Extract a reasonable symbol from the product name
        symbol = product.split()[0].upper()

        stock = Stock(
            symbol=symbol,
            name=product,
            isin=isin,
            exchange=exchange,
            currency=native_currency
        )
        session.add(stock)
        session.flush()

        print(f"  Created stock: {product} (Native currency: {native_currency})")

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
            transaction_id = str(row['Unnamed: 17'])
            transaction_currency = row['Unnamed: 8']  # Currency column

            # Get or create stock
            stock = get_or_create_stock(
                session,
                df,
                row['Product'],
                row['ISIN'],
                row['Reference exchange']
            )

            # Parse date and time
            trans_date = parse_date(row['Date'], row['Time'])

            # Create transaction with currency
            transaction = Transaction(
                stock_id=stock.id,
                date=trans_date,
                time=row['Time'],
                quantity=int(row['Quantity']),
                price=float(row['Price ']),  # Note the space in column name
                currency=transaction_currency,  # Store original currency
                value_eur=float(row['Value EUR']),
                total_eur=float(row['Total EUR']),
                venue=row['Venue'],
                exchange_rate=float(row['Exchange rate']) if pd.notna(row['Exchange rate']) else None,
                fees_eur=float(row['Transaction and/or third party fees EUR']) if pd.notna(row['Transaction and/or third party fees EUR']) else 0.0,
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
