"""
Price data fetchers for different providers (Yahoo Finance, Twelve Data, etc.).
"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
import pandas as pd
import time
import threading

try:
    from .config import Config
except ImportError:
    from degiro_portfolio.config import Config


class YahooRateLimiter:
    """
    Rate limiter for Yahoo Finance API calls.

    Yahoo Finance has undocumented rate limits. This limiter:
    - Limits to ~20 requests per minute (conservative)
    - Adds delay between requests
    - Has cooldown after detecting rate limit errors
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.requests_per_minute = 20  # Conservative limit
        self.min_interval = 60.0 / self.requests_per_minute  # ~3 seconds between requests
        self.last_request_time = 0.0
        self.cooldown_until = 0.0
        self.request_lock = threading.Lock()

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        with self.request_lock:
            now = time.time()

            # Check if we're in cooldown period
            if now < self.cooldown_until:
                wait_time = self.cooldown_until - now
                print(f"  ⏳ Yahoo rate limit cooldown: waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                now = time.time()

            # Ensure minimum interval between requests
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)

            self.last_request_time = time.time()

    def report_rate_limit(self):
        """Called when a rate limit error is detected."""
        with self.request_lock:
            # Set cooldown for 60 seconds
            self.cooldown_until = time.time() + 60.0
            print("  ⚠️  Yahoo rate limit hit - cooling down for 60 seconds")


# Global rate limiter instance
yahoo_rate_limiter = YahooRateLimiter()


class PriceFetcher:
    """Base class for price data fetchers."""

    def fetch_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """
        Fetch historical prices for a ticker.

        Returns DataFrame with columns: Date (index), Open, High, Low, Close, Volume
        """
        raise NotImplementedError


class YahooFinanceFetcher(PriceFetcher):
    """Fetch prices from Yahoo Finance using yfinance with rate limiting."""

    def __init__(self):
        import yfinance as yf
        self.yf = yf

    def fetch_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch from Yahoo Finance with rate limiting."""
        # Wait for rate limiter
        yahoo_rate_limiter.wait_if_needed()

        try:
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
        except Exception as e:
            error_msg = str(e).lower()
            if 'rate' in error_msg or 'too many' in error_msg:
                yahoo_rate_limiter.report_rate_limit()
            raise


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
            SAAB-B.ST -> SAAB
            NVDA -> NVDA (no change for US stocks)
        """
        # Special mappings for stocks that use different symbols on FMP
        # FMP uses US ADR/OTC symbols for international stocks
        # NOTE: ADR mappings removed for SAAB, Leonardo, Rheinmetall because ADR prices
        # don't match actual stock prices. Yahoo Finance fallback handles these stocks.
        special_mappings = {
            'IFX': 'IFNNY',      # Infineon -> US ADR
            'ERIC-B': 'ERIC',    # Ericsson B-shares -> base symbol
            'NOKIA': 'NOK',      # Nokia ADR
            'STM': 'STM',        # STMicroelectronics ADR (already correct)
            # Removed: SAAB-B, SAAB, LDO, RHM (ADRs have wrong prices)
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

        # If no special mapping, also strip common share class suffixes (-A, -B, -C)
        # This handles cases like "XYZ-B" -> "XYZ" when there's no explicit mapping
        if '-' in base_ticker:
            parts = base_ticker.rsplit('-', 1)
            if len(parts) == 2 and parts[1] in ['A', 'B', 'C']:
                base_ticker = parts[0]

        # Return the base ticker
        return base_ticker

    def fetch_latest_quote(self, ticker: str) -> Optional[dict]:
        """
        Fetch latest available price for a single ticker using stable historical endpoint.

        Returns dict with: price, open, high, low, volume, change, change_percent, timestamp
        Returns None if fetch fails.

        Note: Uses the stable historical EOD endpoint which is accessible with standard FMP plan.
        Returns the most recent 2 days to calculate price changes.
        """
        try:
            fmp_ticker = self._normalize_ticker(ticker)

            # Use stable endpoint which works with paid plan
            url = f"{self.base_url}/stable/historical-price-eod/full"
            params = {
                'symbol': fmp_ticker,
                'apikey': self.api_key
            }

            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Check if we got valid data (stable endpoint returns list directly)
            if not data or len(data) == 0:
                return None

            # Get the most recent price (first item - data is sorted newest first)
            latest = data[0]

            # FMP returns these fields already
            change = latest.get('change', 0)
            change_percent = latest.get('changePercent', 0)

            # Extract relevant fields
            return {
                'ticker': ticker,  # Return original ticker format
                'price': latest.get('close'),
                'open': latest.get('open'),
                'high': latest.get('high'),
                'low': latest.get('low'),
                'volume': latest.get('volume'),
                'change': change,
                'change_percent': change_percent,
                'timestamp': latest.get('date'),
            }

        except Exception as e:
            print(f"  ❌ FMP quote error for {ticker}: {e}")
            return None

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

    def _normalize_ticker(self, ticker: str) -> str:
        """
        Convert Yahoo Finance ticker format to Twelve Data format.

        Twelve Data uses different ticker formats for European stocks.
        Note: Hyphens in share classes become dots (SAAB-B -> SAAB.B)

        Examples:
            SAAB-B.ST -> SAAB.B (Stockholm, dot notation)
            LDO.MI -> LDO (Milan/MTA)
            RHM.DE -> RHM (Frankfurt/XETR)
            ASML.AS -> ASML (Amsterdam/Euronext)
            AIR.PA -> AIR (Paris/Euronext)
            AER -> AER (US stocks, no change)
        """
        # Specific mappings for known stocks
        ticker_mappings = {
            'SAAB-B.ST': 'SAAB.B',     # Stockholm: convert hyphen to dot
            'LDO.MI': 'LDO',           # Milan: simple symbol
            'RHM.DE': 'RHM',           # Frankfurt: simple symbol
            'ASML.AS': 'ASML',         # Amsterdam: simple symbol
            'AIR.PA': 'AIR',           # Paris: simple symbol
        }

        # Check for specific mappings first
        if ticker in ticker_mappings:
            return ticker_mappings[ticker]

        # General rule: Remove exchange suffix and convert hyphens to dots for share classes
        exchange_suffixes = ['.ST', '.MI', '.DE', '.F', '.AS', '.PA', '.L', '.MC', '.HE']

        for suffix in exchange_suffixes:
            if ticker.endswith(suffix):
                base_ticker = ticker[:-len(suffix)]
                # Convert hyphens to dots (for share classes like A-shares, B-shares)
                base_ticker = base_ticker.replace('-', '.')
                return base_ticker

        # No exchange suffix, return as-is (US stocks)
        return ticker

    def fetch_latest_quote(self, ticker: str) -> Optional[dict]:
        """
        Fetch real-time quote from Twelve Data.

        Uses the price endpoint for real-time pricing during market hours,
        falls back to quote endpoint for end-of-day data.

        Returns dict with: ticker, price, open, high, low, volume, change, change_percent, timestamp
        """
        td_ticker = self._normalize_ticker(ticker)

        try:
            # First try the price endpoint for real-time data
            # This gives us the current market price during trading hours
            price_data = self.client.price(symbol=td_ticker)

            if price_data and hasattr(price_data, 'as_json'):
                price_json = price_data.as_json()
                current_price = float(price_json.get('price', 0))

                # Get additional details from quote endpoint
                quote = self.client.quote(symbol=td_ticker)

                if quote and hasattr(quote, 'as_json'):
                    quote_data = quote.as_json()

                    # Use real-time price but other data from quote
                    return {
                        'ticker': ticker,  # Return original ticker format
                        'price': current_price,  # Real-time price
                        'open': float(quote_data.get('open', 0)),
                        'high': float(quote_data.get('high', 0)),
                        'low': float(quote_data.get('low', 0)),
                        'volume': int(quote_data.get('volume', 0)),
                        'change': float(quote_data.get('change', 0)),
                        'change_percent': float(quote_data.get('percent_change', 0)),
                        'timestamp': quote_data.get('datetime', price_json.get('datetime', '')),
                    }

            # Fallback to quote endpoint only
            quote = self.client.quote(symbol=td_ticker)

            if not quote or not hasattr(quote, 'as_json'):
                return None

            data = quote.as_json()

            if not data:
                return None

            # Extract relevant fields
            return {
                'ticker': ticker,  # Return original ticker format
                'price': float(data.get('close', 0)),
                'open': float(data.get('open', 0)),
                'high': float(data.get('high', 0)),
                'low': float(data.get('low', 0)),
                'volume': int(data.get('volume', 0)),
                'change': float(data.get('change', 0)),
                'change_percent': float(data.get('percent_change', 0)),
                'timestamp': data.get('datetime', ''),
            }

        except Exception as e:
            error_msg = str(e)
            # Check for plan limitation error
            if "available starting with Pro" in error_msg or "upgrade" in error_msg.lower():
                print(f"  ⚠️  {td_ticker}: Real-time quote not available on current Twelve Data plan")
            elif "symbol" in error_msg.lower() and "invalid" in error_msg.lower():
                print(f"  ⚠️  {td_ticker}: Symbol not recognized by Twelve Data")
            else:
                print(f"  ❌ Twelve Data quote error for {td_ticker} (from {ticker}): {e}")
            return None

    def fetch_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch from Twelve Data API."""
        # Convert ticker to Twelve Data format
        td_ticker = self._normalize_ticker(ticker)

        # Twelve Data uses different date format
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')

        # Calculate number of days for outputsize
        days = (end_date - start_date).days
        outputsize = min(days + 10, 5000)  # Add buffer, max 5000

        try:
            # Fetch time series data
            ts = self.client.time_series(
                symbol=td_ticker,
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
            error_msg = str(e)
            # Check for plan limitation error
            if "available starting with Pro" in error_msg or "upgrade" in error_msg.lower():
                print(f"  ⚠️  {td_ticker}: Not available on current Twelve Data plan (requires Pro or higher)")
            elif "symbol" in error_msg.lower() and "invalid" in error_msg.lower():
                print(f"  ⚠️  {td_ticker}: Symbol not recognized by Twelve Data")
            else:
                print(f"  ❌ Twelve Data error for {td_ticker} (from {ticker}): {e}")
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
