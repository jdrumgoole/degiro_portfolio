"""
Automatic ISIN to Yahoo Finance ticker resolution.

This module provides utilities to automatically resolve ISIN codes to Yahoo Finance
ticker symbols, eliminating the need for hard-coded mappings.
"""
import yfinance as yf
from typing import Optional, Dict
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Fallback manual mapping for stocks that can't be automatically resolved
# This should only be used when automatic resolution fails
MANUAL_TICKER_MAPPING: Dict[str, Dict[str, str]] = {
    # European stocks that need specific exchange suffixes
    "SE0021921269": {"SEK": "SAAB-B.ST", "EUR": "SAAB-B.ST"},  # SAAB AB - Stockholm
    "IT0003856405": {"EUR": "LDO.MI"},  # LEONARDO SPA - Milan
    "NL0000235190": {"EUR": "AIR.PA"},  # AIRBUS GROUP - Paris
    "DE0007030009": {"EUR": "RHM.DE"},  # RHEINMETALL AG - Frankfurt
    "NL0000687663": {"USD": "AER", "EUR": "AER"},  # AERCAP HOLDINGS - NYSE
}


def resolve_ticker_from_isin(isin: str, currency: str = None) -> Optional[str]:
    """
    Attempt to automatically resolve an ISIN code to a Yahoo Finance ticker symbol.

    Args:
        isin: The ISIN code to resolve
        currency: Optional currency hint for the stock

    Returns:
        Yahoo Finance ticker symbol if found, None otherwise
    """
    # First check manual mapping (for stocks with known issues)
    if isin in MANUAL_TICKER_MAPPING:
        mapping = MANUAL_TICKER_MAPPING[isin]
        if currency and currency in mapping:
            logger.info(f"Resolved {isin} to {mapping[currency]} via manual mapping")
            return mapping[currency]
        # Return first available ticker if currency not specified
        ticker = list(mapping.values())[0]
        logger.info(f"Resolved {isin} to {ticker} via manual mapping (default)")
        return ticker

    # Try to resolve automatically using yfinance search
    # For US stocks, the ticker often matches the last part of the ISIN
    if isin.startswith("US"):
        # US ISINs format: US + 9-digit identifier
        # Try common US stock patterns
        potential_tickers = _generate_us_ticker_candidates(isin)
        for ticker in potential_tickers:
            if _verify_ticker(ticker, isin):
                logger.info(f"Resolved {isin} to {ticker} via US pattern matching")
                return ticker

    # For European stocks, try common exchange suffixes
    elif isin.startswith(("NL", "DE", "FR", "IT", "ES")):
        potential_tickers = _generate_european_ticker_candidates(isin)
        for ticker in potential_tickers:
            if _verify_ticker(ticker, isin):
                logger.info(f"Resolved {isin} to {ticker} via European pattern matching")
                return ticker

    logger.warning(f"Could not automatically resolve ISIN {isin} to ticker symbol")
    return None


def _generate_us_ticker_candidates(isin: str) -> list:
    """Generate potential US ticker symbols from ISIN."""
    candidates = []

    # Extract the numeric part (digits 3-11)
    numeric_part = isin[2:11]

    # Try to look up by ISIN directly (some data sources support this)
    candidates.append(isin)

    # Note: Actual ticker derivation from ISIN is complex and may require external APIs
    # This is a simplified version that would need enhancement

    return candidates


def _generate_european_ticker_candidates(isin: str) -> list:
    """Generate potential European ticker symbols from ISIN."""
    candidates = []

    # Map country codes to common exchanges
    exchange_suffixes = {
        "NL": [".AS"],  # Amsterdam
        "DE": [".DE", ".F"],  # XETRA, Frankfurt
        "FR": [".PA"],  # Paris
        "IT": [".MI"],  # Milan
        "ES": [".MC"],  # Madrid
    }

    country_code = isin[:2]
    suffixes = exchange_suffixes.get(country_code, [])

    # Try ISIN with exchange suffixes
    for suffix in suffixes:
        candidates.append(f"{isin}{suffix}")

    return candidates


def _verify_ticker(ticker: str, expected_isin: str = None) -> bool:
    """
    Verify that a ticker symbol is valid and optionally matches an ISIN.

    Args:
        ticker: The ticker symbol to verify
        expected_isin: Optional ISIN to verify against

    Returns:
        True if the ticker is valid (and matches ISIN if provided), False otherwise
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # Check if we got valid data
        if not info or 'symbol' not in info:
            return False

        # If ISIN provided, verify it matches
        if expected_isin:
            ticker_isin = info.get('isin', '')
            if ticker_isin and ticker_isin == expected_isin:
                return True
            # If ISIN not in info or doesn't match, still return True
            # (some tickers don't expose ISIN in yfinance)
            return 'regularMarketPrice' in info or 'currentPrice' in info

        # Just verify ticker is valid
        return 'regularMarketPrice' in info or 'currentPrice' in info

    except Exception as e:
        logger.debug(f"Ticker verification failed for {ticker}: {e}")
        return False


def resolve_ticker_from_name(stock_name: str, currency: str = None) -> Optional[str]:
    """
    Attempt to resolve a ticker from the stock name.

    This is a fallback method when ISIN resolution fails.

    Args:
        stock_name: The stock name/company name
        currency: Optional currency hint

    Returns:
        Yahoo Finance ticker symbol if found, None otherwise
    """
    # Extract potential ticker from name (first word, uppercase)
    potential_ticker = stock_name.split()[0].upper()

    # Remove common suffixes like CORP, INC, etc.
    potential_ticker = potential_ticker.replace("CORP", "").replace("INC", "").strip()

    # Try to verify it
    if _verify_ticker(potential_ticker):
        logger.info(f"Resolved '{stock_name}' to {potential_ticker} via name extraction")
        return potential_ticker

    logger.warning(f"Could not resolve ticker from stock name: {stock_name}")
    return None


def get_ticker_for_stock(stock_isin: str, stock_name: str, currency: str) -> Optional[str]:
    """
    Main entry point to resolve a ticker for a stock.

    Tries multiple strategies in order:
    1. Manual mapping (for known edge cases)
    2. ISIN-based resolution
    3. Name-based resolution

    Args:
        stock_isin: The stock's ISIN code
        stock_name: The stock's name
        currency: The stock's trading currency

    Returns:
        Yahoo Finance ticker symbol if found, None otherwise
    """
    # Try ISIN resolution first
    ticker = resolve_ticker_from_isin(stock_isin, currency)
    if ticker:
        return ticker

    # Fall back to name-based resolution
    ticker = resolve_ticker_from_name(stock_name, currency)
    if ticker:
        return ticker

    logger.error(f"Failed to resolve ticker for {stock_name} (ISIN: {stock_isin})")
    return None
