"""
Price data fetchers for different providers (Yahoo Finance, Twelve Data, etc.).
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import pandas as pd

try:
    from .config import Config
except ImportError:
    from degiro_portfolio.config import Config


class PriceFetcher:
    """Base class for price data fetchers."""

    def fetch_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch historical prices for a ticker.

        Returns DataFrame with columns: Date (index), Open, High, Low, Close, Volume
        """
        raise NotImplementedError


class YahooFinanceFetcher(PriceFetcher):
    """Fetch prices from Yahoo Finance using yfinance."""

    def __init__(self):
        import yfinance as yf
        self.yf = yf

    def fetch_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch from Yahoo Finance."""
        ticker_obj = self.yf.Ticker(ticker)
        hist = ticker_obj.history(start=start_date, end=end_date)

        if hist.empty:
            return pd.DataFrame()

        # Rename columns to match our standard format
        hist = hist.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })

        return hist[['open', 'high', 'low', 'close', 'volume']]


class TwelveDataFetcher(PriceFetcher):
    """Fetch prices from Twelve Data API."""

    def __init__(self, api_key: Optional[str] = None):
        from twelvedata import TDClient

        self.api_key = api_key or Config.TWELVEDATA_API_KEY
        if not self.api_key:
            raise ValueError(
                "Twelve Data API key required. Get free key at https://twelvedata.com/ "
                "and set TWELVEDATA_API_KEY environment variable or pass to constructor."
            )

        self.client = TDClient(apikey=self.api_key)

    def fetch_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch from Twelve Data API."""
        # Twelve Data uses different date format
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        # Calculate number of days for outputsize
        days = (end_date - start_date).days
        outputsize = min(days + 10, 5000)  # Add buffer, max 5000

        try:
            # Fetch time series data
            ts = self.client.time_series(
                symbol=ticker,
                interval="1day",
                outputsize=outputsize,
                start_date=start_str,
                end_date=end_str
            )

            df = ts.as_pandas()

            if df is None or df.empty:
                return pd.DataFrame()

            # Twelve Data returns columns: open, high, low, close, volume
            # Already in the format we need!
            df.index = pd.to_datetime(df.index)

            # Convert columns to lowercase if needed
            df.columns = [col.lower() for col in df.columns]

            # Filter to date range (Twelve Data sometimes returns extra data)
            df = df[(df.index >= start_date) & (df.index <= end_date)]

            return df[['open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            print(f"  ❌ Twelve Data error for {ticker}: {e}")
            return pd.DataFrame()


def get_price_fetcher(provider: Optional[str] = None) -> PriceFetcher:
    """
    Get price fetcher instance based on configuration or provider name.

    Args:
        provider: 'yahoo', 'twelvedata', or None (uses Config.PRICE_DATA_PROVIDER)

    Returns:
        PriceFetcher instance
    """
    provider = provider or Config.PRICE_DATA_PROVIDER

    if provider == 'twelvedata':
        return TwelveDataFetcher()
    elif provider == 'yahoo':
        return YahooFinanceFetcher()
    else:
        raise ValueError(f"Unknown price data provider: {provider}. Use 'yahoo' or 'twelvedata'")
