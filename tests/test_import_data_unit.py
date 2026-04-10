"""Unit tests for import_data.py — parse_date, determine_native_currency."""

from datetime import datetime

import pandas as pd
import pytest

from degiro_portfolio.import_data import parse_date, determine_native_currency
from degiro_portfolio.config import Config


def test_parse_date_string_dd_mm_yyyy():
    """parse_date handles DD-MM-YYYY string format."""
    result = parse_date("15-03-2026", "09:30")
    assert result == datetime(2026, 3, 15, 9, 30)


def test_parse_date_string_dd_slash_mm_yyyy():
    """parse_date handles DD/MM/YYYY string format."""
    result = parse_date("15/03/2026", "14:00")
    assert result == datetime(2026, 3, 15, 14, 0)


def test_parse_date_string_yyyy_mm_dd():
    """parse_date handles YYYY-MM-DD string format."""
    result = parse_date("2026-03-15", "08:45")
    assert result == datetime(2026, 3, 15, 8, 45)


def test_parse_date_pandas_timestamp():
    """parse_date handles pandas Timestamp (auto-parsed by read_excel)."""
    ts = pd.Timestamp("2026-03-15")
    result = parse_date(ts, "10:15")
    assert result.year == 2026
    assert result.month == 3
    assert result.day == 15
    assert result.hour == 10
    assert result.minute == 15


def test_parse_date_pandas_timestamp_no_time():
    """parse_date handles pandas Timestamp with non-time string."""
    ts = pd.Timestamp("2026-03-15")
    result = parse_date(ts, "nan")
    assert result.year == 2026
    assert result.hour == 0


def test_parse_date_iso_format():
    """parse_date handles ISO 8601 format."""
    result = parse_date("2026-03-15T00:00:00", "09:30")
    assert result.year == 2026
    assert result.month == 3


def test_parse_date_day_month_ambiguity():
    """parse_date uses dayfirst=True for DEGIRO (DD-MM, not MM-DD)."""
    result = parse_date("03-04-2026", "10:00")
    assert result.day == 3
    assert result.month == 4


def test_parse_date_invalid_format_raises():
    """parse_date raises for completely unparseable strings."""
    with pytest.raises(Exception):
        parse_date("not-a-date", "09:00")


def test_determine_native_currency_most_common():
    """determine_native_currency returns the most frequent currency."""
    df = pd.DataFrame({
        'Product': ['SAAB', 'SAAB', 'SAAB', 'SAAB'],
        'Currency': ['EUR', 'EUR', 'EUR', 'SEK'],
    })
    # Ensure active mapping points to canonical names
    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS
    result = determine_native_currency(df, 'SAAB')
    assert result == 'EUR'


def test_determine_native_currency_single_currency():
    """determine_native_currency works with a single currency."""
    df = pd.DataFrame({
        'Product': ['NVDA', 'NVDA'],
        'Currency': ['USD', 'USD'],
    })
    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS
    result = determine_native_currency(df, 'NVDA')
    assert result == 'USD'


def test_determine_native_currency_no_transactions_defaults_eur():
    """determine_native_currency returns EUR when no transactions found."""
    df = pd.DataFrame({
        'Product': ['OTHER'],
        'Currency': ['USD'],
    })
    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS
    result = determine_native_currency(df, 'NONEXISTENT')
    assert result == 'EUR'


def _run_import_test(tmp_path, csv_content, expected_stocks, expected_txns,
                     check_fn=None):
    """Helper to run an import test with an isolated database."""
    import os
    from unittest.mock import patch
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from degiro_portfolio.database import Base, Stock, Transaction

    # Create isolated engine — don't touch the shared one
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    csv_path = tmp_path / "test.csv"
    csv_path.write_text(csv_content)

    # Patch SessionLocal and init_db in import_data to use our isolated engine
    with patch('degiro_portfolio.import_data.SessionLocal', TestSession), \
         patch('degiro_portfolio.import_data.init_db'), \
         patch('degiro_portfolio.import_data.fetch_stock_prices', return_value=0), \
         patch('degiro_portfolio.import_data.get_ticker_for_stock', return_value='TEST'):
        from degiro_portfolio.import_data import import_transactions
        import_transactions(str(csv_path))

    session = TestSession()
    try:
        stocks = session.query(Stock).all()
        assert len(stocks) == expected_stocks, (
            f"Expected {expected_stocks} stocks, got {len(stocks)}: "
            f"{[s.name for s in stocks]}"
        )
        txns = session.query(Transaction).all()
        assert len(txns) == expected_txns, (
            f"Expected {expected_txns} transactions, got {len(txns)}"
        )
        if check_fn:
            check_fn(stocks, txns, session)
    finally:
        session.close()
    engine.dispose()


def test_import_transactions_csv_in_process(tmp_path):
    """Test import_transactions with a CSV file in-process (coverage-tracked)."""
    csv = (
        "Date,Time,Product,ISIN,Reference exchange,Venue,Quantity,Price,,Local value,,Value EUR,Exchange rate,AutoFX Fee,Transaction and/or third party fees EUR,Total EUR,Order ID,\n"
        "15-03-2026,09:00,IMPORT TEST CO,US1111111111,NASDAQ,XNAS,10,50.00,USD,500.00,USD,425.00,0.85,0.00,1.00,-426.00,,import-001\n"
        "16-03-2026,10:00,IMPORT TEST CO,US1111111111,NASDAQ,XNAS,5,55.00,USD,275.00,USD,233.75,0.85,0.00,0.50,-234.25,,import-002\n"
    )

    def check(stocks, txns, session):
        assert stocks[0].name == "IMPORT TEST CO"
        assert stocks[0].isin == "US1111111111"
        assert txns[0].quantity == 10
        assert txns[1].quantity == 5

    _run_import_test(tmp_path, csv, expected_stocks=1, expected_txns=2, check_fn=check)


def test_import_transactions_excel_in_process(tmp_path):
    """Test import_transactions with an Excel file in-process."""
    from unittest.mock import patch
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from degiro_portfolio.database import Base, Stock, Transaction

    db_path = tmp_path / "test_xl.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)

    df = pd.DataFrame([
        ['15-03-2026', '09:00', 'EXCEL STOCK', 'US2222222222', 'NASDAQ',
         10, 100.0, 'USD', 850.0, -851.0, 'XNAS', 0.85, 1.0, 'xl-001'],
    ], columns=[
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Quantity', 'Price', 'Currency', 'Value EUR', 'Total EUR',
        'Venue', 'Exchange rate', 'Fees EUR', 'Transaction ID'
    ])
    xlsx_path = tmp_path / "test.xlsx"
    df.to_excel(str(xlsx_path), index=False)

    with patch('degiro_portfolio.import_data.SessionLocal', TestSession), \
         patch('degiro_portfolio.import_data.init_db'), \
         patch('degiro_portfolio.import_data.fetch_stock_prices', return_value=0), \
         patch('degiro_portfolio.import_data.get_ticker_for_stock', return_value='XLTEST'):
        from degiro_portfolio.import_data import import_transactions
        import_transactions(str(xlsx_path))

    session = TestSession()
    try:
        assert len(session.query(Stock).all()) == 1
        assert session.query(Stock).first().name == "EXCEL STOCK"
        assert len(session.query(Transaction).all()) == 1
    finally:
        session.close()
    engine.dispose()


def test_import_skips_ignored_stocks(tmp_path):
    """import_transactions should skip stocks in IGNORED_STOCKS."""
    ignored_isin = list(Config.IGNORED_STOCKS)[0]
    csv = (
        "Date,Time,Product,ISIN,Reference exchange,Venue,Quantity,Price,,Local value,,Value EUR,Exchange rate,AutoFX Fee,Transaction and/or third party fees EUR,Total EUR,Order ID,\n"
        f"15-03-2026,09:00,SIGNATURE BANK,{ignored_isin},NASDAQ,XNAS,10,50.00,USD,500.00,USD,425.00,0.85,0.00,1.00,-426.00,,sig-001\n"
    )
    _run_import_test(tmp_path, csv, expected_stocks=0, expected_txns=0)


def test_import_multiple_stocks_from_csv(tmp_path):
    """Import CSV with multiple different stocks creates separate Stock records."""
    csv = (
        "Date,Time,Product,ISIN,Reference exchange,Venue,Quantity,Price,,Local value,,Value EUR,Exchange rate,AutoFX Fee,Transaction and/or third party fees EUR,Total EUR,Order ID,\n"
        "15-03-2026,09:00,ALPHA INC,US1111111111,NASDAQ,XNAS,10,50.00,USD,500.00,USD,425.00,0.85,0.00,1.00,-426.00,,multi-001\n"
        "16-03-2026,10:00,BETA CORP,US2222222222,NASDAQ,XNAS,20,75.00,USD,1500.00,USD,1275.00,0.85,0.00,1.50,-1276.50,,multi-002\n"
    )

    def check(stocks, txns, session):
        names = {s.name for s in stocks}
        assert names == {"ALPHA INC", "BETA CORP"}

    _run_import_test(tmp_path, csv, expected_stocks=2, expected_txns=2, check_fn=check)
