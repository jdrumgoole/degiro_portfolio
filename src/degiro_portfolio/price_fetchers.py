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


class FMPFetcher(PriceFetcher):
    """Fetch prices from Financial Modeling Prep API using REST API."""

    def __init__(self, api_key: Optional[str] = None):
        import requests

        self.api_key = api_key or Config.FMP_API_KEY
        if not self.api_key:
            raise ValueError(
                "FMP API key required. Get key at https://site.financialmodelingprep.com/ "
                "and set FMP_API_KEY environment variable or pass to constructor."
            )

        self.session = requests.Session()
        self.base_url = "https://financialmodelingprep.com"

    def _normalize_ticker(self, ticker: str) -> str:
        """
        Normalize Yahoo Finance ticker to FMP format.

        FMP uses US-traded symbols (ADRs) or simplified tickers for international stocks.
        Examples:
            SAP.DE -> SAP
            ASML.AS -> ASML
            IFX.DE -> IFNNY (Infineon ADR)
            ERIC-B.ST -> ERIC
            NVDA -> NVDA (no change for US stocks)
        """
        # Special mappings for stocks that use different symbols on FMP
        special_mappings = {
            'IFX': 'IFNNY',      # Infineon -> US ADR
            'ERIC-B': 'ERIC',    # Ericsson B-shares -> base symbol
            'NOKIA': 'NOK',      # Nokia ADR
            'STM': 'STM',        # STMicroelectronics ADR (already correct)
        }

        # Common European exchange suffixes to remove
        exchange_suffixes = [
            '.DE',  # Germany (Frankfurt, XETRA)
            '.F',   # Germany (Frankfurt)
            '.AS',  # Amsterdam
            '.PA',  # Paris
            '.MI',  # Milan
            '.MC',  # Madrid
            '.ST',  # Stockholm
            '.HE',  # Helsinki
            '.L',   # London
        ]

        # First, remove exchange suffix if present
        base_ticker = ticker
        for suffix in exchange_suffixes:
            if ticker.endswith(suffix):
                base_ticker = ticker[:-len(suffix)]
                break

        # Then check if we have a special mapping
        if base_ticker in special_mappings:
            return special_mappings[base_ticker]

        # Return the base ticker
        return base_ticker

    def fetch_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch from FMP REST API."""
        try:
            # FMP uses base ticker symbols without exchange suffixes
            # Convert Yahoo-style tickers (e.g., SAP.DE, ASML.AS) to FMP format (SAP, ASML)
            fmp_ticker = self._normalize_ticker(ticker)

            # FMP historical price endpoint (fetches full history)
            # Note: The stable endpoint provides full historical data
            url = f"{self.base_url}/stable/historical-price-eod/full"
            params = {
                'symbol': fmp_ticker,
                'apikey': self.api_key
            }

            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()

            # Check if we got valid data
            # FMP stable endpoint returns a list directly, not a dict with 'historical' key
            if not data:
                return pd.DataFrame()

            # Convert to DataFrame (data is already a list of records)
            df = pd.DataFrame(data)

            if df.empty:
                return pd.DataFrame()

            # Convert date column to datetime and set as index
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')

            # Sort by date (oldest first)
            df = df.sort_index()

            # Standardize column names to lowercase
            df.columns = [col.lower() for col in df.columns]

            # Filter to requested date range
            df = df[(df.index >= start_date) & (df.index <= end_date)]

            # Ensure we have the required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                print(f"  ⚠️  FMP data missing required columns for {ticker}")
                return pd.DataFrame()

            return df[required_cols]

        except Exception as e:
            print(f"  ❌ FMP error for {ticker}: {e}")
            return pd.DataFrame()


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
        provider: 'yahoo', 'twelvedata', 'fmp', or None (uses Config.PRICE_DATA_PROVIDER)

    Returns:
        PriceFetcher instance
    """
    provider = provider or Config.PRICE_DATA_PROVIDER

    if provider == 'fmp':
        return FMPFetcher()
    elif provider == 'twelvedata':
        return TwelveDataFetcher()
    elif provider == 'yahoo':
        return YahooFinanceFetcher()
    else:
        raise ValueError(f"Unknown price data provider: {provider}. Use 'yahoo', 'twelvedata', or 'fmp'")
