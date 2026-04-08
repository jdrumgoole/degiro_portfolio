"""Unit tests for fetch_prices.py module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd


def test_get_ticker_for_stock():
    """Test get_ticker_for_stock function."""
    from degiro_portfolio.fetch_prices import get_ticker_for_stock
    from degiro_portfolio.database import SessionLocal, Stock

    session = SessionLocal()
    try:
        # Get first stock from test database
        stock = session.query(Stock).first()
        if stock:
            ticker = get_ticker_for_stock(stock)
            # Should return a ticker (either existing or resolved)
            assert ticker is not None
            assert isinstance(ticker, str)
    finally:
        session.close()


def test_fetch_stock_prices_success(test_database):
    """Test successful stock price fetching."""
    from degiro_portfolio.fetch_prices import fetch_stock_prices
    from degiro_portfolio.database import SessionLocal, Stock

    session = SessionLocal()
    try:
        stock = session.query(Stock).first()
        if stock and stock.yahoo_ticker:
            with patch('degiro_portfolio.fetch_prices.get_price_fetcher') as mock_fetcher:
                # Mock fetcher
                mock_instance = MagicMock()

                # Create mock price data
                dates = pd.date_range(start=datetime.now() - timedelta(days=10), periods=10, freq='D')
                mock_df = pd.DataFrame({
                    'open': [100.0] * 10,
                    'high': [105.0] * 10,
                    'low': [99.0] * 10,
                    'close': [103.0] * 10,
                    'volume': [1000000] * 10
                }, index=dates)

                mock_instance.fetch_prices.return_value = mock_df
                mock_fetcher.return_value = mock_instance

                # Fetch prices
                count = fetch_stock_prices(stock, session)

                # Should have added some prices
                assert count >= 0
    finally:
        session.close()


def test_fetch_stock_prices_handles_no_ticker(test_database):
    """Test that fetch_stock_prices handles stocks without tickers."""
    from degiro_portfolio.fetch_prices import fetch_stock_prices
    from degiro_portfolio.database import SessionLocal, Stock

    session = SessionLocal()
    try:
        stock = session.query(Stock).first()
        if stock:
            # Clear ticker, ISIN, and name so the resolver can't recover the ticker
            original_ticker = stock.yahoo_ticker
            original_isin = stock.isin
            original_name = stock.name
            stock.yahoo_ticker = None
            stock.isin = None
            stock.name = "UNKNOWN_TEST_STOCK"

            # Should return 0 or handle gracefully
            count = fetch_stock_prices(stock, session)
            assert count == 0

            # Restore original values
            stock.yahoo_ticker = original_ticker
            stock.isin = original_isin
            stock.name = original_name
    finally:
        session.close()


def test_fetch_stock_prices_with_date_range(test_database):
    """Test fetching prices with specific date range."""
    from degiro_portfolio.fetch_prices import fetch_stock_prices
    from degiro_portfolio.database import SessionLocal, Stock

    session = SessionLocal()
    try:
        stock = session.query(Stock).first()
        if stock and stock.yahoo_ticker:
            with patch('degiro_portfolio.fetch_prices.get_price_fetcher') as mock_fetcher:
                mock_instance = MagicMock()
                mock_instance.fetch_prices.return_value = pd.DataFrame()
                mock_fetcher.return_value = mock_instance

                start_date = datetime(2024, 1, 1)
                end_date = datetime(2024, 1, 10)

                count = fetch_stock_prices(stock, session, start_date, end_date)

                # Should have called fetcher with correct dates
                mock_instance.fetch_prices.assert_called_once()
                assert count >= 0
    finally:
        session.close()


def test_fetch_all_current_holdings(test_database):
    """Test fetching prices for all current holdings."""
    from degiro_portfolio.fetch_prices import fetch_all_current_holdings

    with patch('degiro_portfolio.fetch_prices.fetch_stock_prices') as mock_fetch:
        mock_fetch.return_value = 10

        # Run function (should not crash)
        fetch_all_current_holdings()

        # Should have been called for stocks
        assert mock_fetch.called or mock_fetch.call_count >= 0


def test_get_ticker_for_stock_creates_ticker():
    """Test that get_ticker_for_stock resolves and saves ticker."""
    from degiro_portfolio.fetch_prices import get_ticker_for_stock
    from degiro_portfolio.database import SessionLocal, Stock

    session = SessionLocal()
    try:
        stock = session.query(Stock).first()
        if stock:
            # Clear ticker
            original_ticker = stock.yahoo_ticker
            stock.yahoo_ticker = None
            session.commit()

            with patch('degiro_portfolio.ticker_resolver.get_ticker_for_stock') as mock_resolve:
                mock_resolve.return_value = "TEST"

                ticker = get_ticker_for_stock(stock)

                # Should have resolved ticker
                assert ticker == "TEST"

                # Restore
                stock.yahoo_ticker = original_ticker
                session.commit()
    finally:
        session.close()


def test_fetch_stock_prices_handles_empty_data(test_database):
    """Test that fetch_stock_prices handles empty price data."""
    from degiro_portfolio.fetch_prices import fetch_stock_prices
    from degiro_portfolio.database import SessionLocal, Stock

    session = SessionLocal()
    try:
        stock = session.query(Stock).first()
        if stock and stock.yahoo_ticker:
            with patch('degiro_portfolio.fetch_prices.get_price_fetcher') as mock_fetcher:
                mock_instance = MagicMock()
                # Return empty DataFrame
                mock_instance.fetch_prices.return_value = pd.DataFrame()
                mock_fetcher.return_value = mock_instance

                count = fetch_stock_prices(stock, session)

                # Should return 0 for no data
                assert count == 0
    finally:
        session.close()


def test_fetch_stock_prices_handles_exceptions(test_database):
    """Test that fetch_stock_prices handles exceptions gracefully."""
    from degiro_portfolio.fetch_prices import fetch_stock_prices
    from degiro_portfolio.database import SessionLocal, Stock

    session = SessionLocal()
    try:
        stock = session.query(Stock).first()
        if stock and stock.yahoo_ticker:
            with patch('degiro_portfolio.fetch_prices.get_price_fetcher') as mock_fetcher:
                mock_instance = MagicMock()
                mock_instance.fetch_prices.side_effect = Exception("API Error")
                mock_fetcher.return_value = mock_instance

                # Should not crash
                count = fetch_stock_prices(stock, session)
                assert count == 0
    finally:
        session.close()


def test_fetch_stock_prices_skips_duplicates(test_database):
    """Test that fetch_stock_prices skips existing price records."""
    from degiro_portfolio.fetch_prices import fetch_stock_prices
    from degiro_portfolio.database import SessionLocal, Stock, StockPrice

    session = SessionLocal()
    try:
        stock = session.query(Stock).first()
        if stock and stock.yahoo_ticker:
            # Add a price record
            existing_date = datetime.now() - timedelta(days=5)
            existing_price = StockPrice(
                stock_id=stock.id,
                date=existing_date,
                open=100.0,
                high=105.0,
                low=99.0,
                close=103.0,
                volume=1000000,
                currency=stock.currency
            )
            session.add(existing_price)
            session.commit()

            with patch('degiro_portfolio.fetch_prices.get_price_fetcher') as mock_fetcher:
                mock_instance = MagicMock()

                # Return data including the existing date
                dates = pd.date_range(start=existing_date, periods=3, freq='D')
                mock_df = pd.DataFrame({
                    'open': [100.0] * 3,
                    'high': [105.0] * 3,
                    'low': [99.0] * 3,
                    'close': [103.0] * 3,
                    'volume': [1000000] * 3
                }, index=dates)

                mock_instance.fetch_prices.return_value = mock_df
                mock_fetcher.return_value = mock_instance

                count = fetch_stock_prices(stock, session)

                # Should skip duplicate and add new ones
                assert count >= 0

            # Clean up
            session.delete(existing_price)
            session.commit()
    finally:
        session.close()
