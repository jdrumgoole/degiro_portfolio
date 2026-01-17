"""Unit tests for price_fetchers.py module."""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import pandas as pd


def test_get_price_fetcher_returns_twelvedata():
    """Test that get_price_fetcher returns TwelveDataFetcher when configured."""
    from degiro_portfolio.price_fetchers import get_price_fetcher, TwelveDataFetcher
    from degiro_portfolio.config import Config

    # Mock API key and set provider to twelvedata
    original_key = Config.TWELVEDATA_API_KEY
    original_provider = Config.PRICE_DATA_PROVIDER
    Config.TWELVEDATA_API_KEY = 'test_key_for_ci'
    Config.PRICE_DATA_PROVIDER = 'twelvedata'

    try:
        fetcher = get_price_fetcher()
        assert isinstance(fetcher, TwelveDataFetcher)
    finally:
        # Restore originals
        Config.TWELVEDATA_API_KEY = original_key
        Config.PRICE_DATA_PROVIDER = original_provider


def test_get_price_fetcher_returns_fmp_when_configured():
    """Test that get_price_fetcher returns FMPFetcher when configured."""
    from degiro_portfolio.price_fetchers import get_price_fetcher, FMPFetcher
    from degiro_portfolio.config import Config

    # Save original values and patch Config directly
    original_provider = Config.PRICE_DATA_PROVIDER
    original_key = Config.FMP_API_KEY
    Config.FMP_API_KEY = 'test_key_for_ci'

    try:
        # Set to FMP
        Config.PRICE_DATA_PROVIDER = 'fmp'

        fetcher = get_price_fetcher()
        assert isinstance(fetcher, FMPFetcher)

    finally:
        # Restore originals
        Config.PRICE_DATA_PROVIDER = original_provider
        Config.FMP_API_KEY = original_key


def test_get_price_fetcher_returns_yahoo_when_configured():
    """Test that get_price_fetcher returns YahooFinanceFetcher when configured."""
    from degiro_portfolio.price_fetchers import get_price_fetcher, YahooFinanceFetcher
    from degiro_portfolio.config import Config

    original = Config.PRICE_DATA_PROVIDER

    try:
        Config.PRICE_DATA_PROVIDER = 'yahoo'
        fetcher = get_price_fetcher()
        assert isinstance(fetcher, YahooFinanceFetcher)
    finally:
        Config.PRICE_DATA_PROVIDER = original


def test_twelvedata_fetcher_normalize_ticker():
    """Test TwelveDataFetcher ticker normalization."""
    from degiro_portfolio.price_fetchers import TwelveDataFetcher
    from degiro_portfolio.config import Config

    # Mock API key for test by patching Config directly
    original_key = Config.TWELVEDATA_API_KEY
    Config.TWELVEDATA_API_KEY = 'test_key_for_ci'

    try:
        fetcher = TwelveDataFetcher()

        # Test various ticker formats
        assert fetcher._normalize_ticker("AAPL") == "AAPL"
        assert fetcher._normalize_ticker("ASML.AS") == "ASML"
        assert fetcher._normalize_ticker("SAP.DE") == "SAP"
        assert fetcher._normalize_ticker("SAAB-B.ST") == "SAAB.B"
        assert fetcher._normalize_ticker("LDO.MI") == "LDO"
        assert fetcher._normalize_ticker("RHM.DE") == "RHM"
    finally:
        # Restore original
        Config.TWELVEDATA_API_KEY = original_key


def test_twelvedata_fetcher_fetch_prices():
    """Test TwelveDataFetcher.fetch_prices."""
    from degiro_portfolio.price_fetchers import TwelveDataFetcher

    with patch.object(TwelveDataFetcher, '__init__', lambda self, api_key=None: None):
        fetcher = TwelveDataFetcher()

        # Mock the client
        mock_client = MagicMock()
        mock_ts = MagicMock()

        # Create mock DataFrame response
        dates = pd.date_range(start='2024-01-01', periods=5, freq='D')
        mock_df = pd.DataFrame({
            'open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'high': [105.0, 106.0, 107.0, 108.0, 109.0],
            'low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'close': [103.0, 104.0, 105.0, 106.0, 107.0],
            'volume': [1000000, 1100000, 1200000, 1300000, 1400000]
        }, index=dates)

        mock_ts.as_pandas.return_value = mock_df
        mock_client.time_series.return_value = mock_ts
        fetcher.client = mock_client

        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 5)

        result = fetcher.fetch_prices("AAPL", start_date, end_date)

        # Should return DataFrame with correct structure
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 5
        assert 'open' in result.columns
        assert 'high' in result.columns
        assert 'low' in result.columns
        assert 'close' in result.columns
        assert 'volume' in result.columns


def test_yahoo_fetcher_fetch_prices():
    """Test YahooFinanceFetcher.fetch_prices."""
    from degiro_portfolio.price_fetchers import YahooFinanceFetcher

    with patch('yfinance.Ticker') as mock_ticker_class:
        # Mock ticker and history
        mock_ticker = MagicMock()
        dates = pd.date_range(start='2024-01-01', periods=10, freq='D')
        mock_hist = pd.DataFrame({
            'Open': [100 + i for i in range(10)],
            'High': [105 + i for i in range(10)],
            'Low': [99 + i for i in range(10)],
            'Close': [103 + i for i in range(10)],
            'Volume': [1000000] * 10
        }, index=dates)
        mock_ticker.history.return_value = mock_hist
        mock_ticker_class.return_value = mock_ticker

        fetcher = YahooFinanceFetcher()
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 10)

        result = fetcher.fetch_prices("AAPL", start_date, end_date)

        # Should return DataFrame with data
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 10
        assert 'open' in result.columns
        assert 'close' in result.columns


@patch('requests.Session.get')
def test_fmp_fetcher_fetch_latest_quote(mock_get):
    """Test FMPFetcher.fetch_latest_quote."""
    from degiro_portfolio.price_fetchers import FMPFetcher
    from degiro_portfolio.config import Config

    # Skip if no API key configured
    if not Config.FMP_API_KEY:
        pytest.skip("FMP API key not configured")

    # Mock successful quote response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{
        'date': '2024-01-15',
        'close': 150.25,
        'open': 149.00,
        'high': 151.00,
        'low': 148.00,
        'volume': 50000000,
        'change': 1.75,
        'changePercent': 1.18
    }]
    mock_get.return_value = mock_response

    fetcher = FMPFetcher()
    result = fetcher.fetch_latest_quote("AAPL")

    # Should return quote data
    assert isinstance(result, dict)
    assert 'price' in result
    assert 'change_percent' in result
    assert result['price'] == 150.25


def test_price_fetcher_base_class():
    """Test PriceFetcher base class."""
    from degiro_portfolio.price_fetchers import PriceFetcher

    fetcher = PriceFetcher()

    # Base class methods should raise NotImplementedError
    with pytest.raises(NotImplementedError):
        fetcher.fetch_prices("AAPL", datetime.now(), datetime.now())


def test_yahoo_finance_fetcher_handles_empty_data():
    """Test YahooFinanceFetcher handles empty data gracefully."""
    from degiro_portfolio.price_fetchers import YahooFinanceFetcher

    with patch('yfinance.Ticker') as mock_ticker_class:
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()  # Empty DataFrame
        mock_ticker_class.return_value = mock_ticker

        fetcher = YahooFinanceFetcher()
        result = fetcher.fetch_prices("INVALID", datetime.now(), datetime.now())

        # Should return empty DataFrame
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


def test_twelvedata_fetcher_handles_exceptions():
    """Test TwelveDataFetcher handles exceptions gracefully."""
    from degiro_portfolio.price_fetchers import TwelveDataFetcher

    with patch.object(TwelveDataFetcher, '__init__', lambda self, api_key=None: None):
        fetcher = TwelveDataFetcher()

        # Mock client that raises exception
        mock_client = MagicMock()
        mock_client.time_series.side_effect = Exception("API Error")
        fetcher.client = mock_client

        result = fetcher.fetch_prices("AAPL", datetime.now(), datetime.now())

        # Should return empty DataFrame
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


def test_get_price_fetcher_with_invalid_provider():
    """Test get_price_fetcher with invalid provider raises ValueError."""
    from degiro_portfolio.price_fetchers import get_price_fetcher

    # Invalid provider should raise ValueError
    with pytest.raises(ValueError, match="Unknown price data provider"):
        get_price_fetcher('invalid_provider')
