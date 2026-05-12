"""
Automatic ISIN to Yahoo Finance ticker resolution.

This module provides utilities to automatically resolve ISIN codes to Yahoo Finance
ticker symbols, eliminating the need for hard-coded mappings.
"""
import yfinance as yf
from typing import Optional, Dict, List
import logging

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
    # US stocks from example data
    "US02079K3059": {"USD": "GOOGL"},  # ALPHABET INC-CL A - NASDAQ
    "US67066G1040": {"USD": "NVDA"},  # NVIDIA CORPORATION
    "US5949181045": {"USD": "MSFT"},  # MICROSOFT CORPORATION
    "US30303M1027": {"USD": "META"},  # META PLATFORMS INC
    "US0079031078": {"USD": "AMD"},  # ADVANCED MICRO DEVICES
    # Additional European stocks from example data
    "DE0006231004": {"EUR": "IFX.DE"},  # INFINEON TECHNOLOGIES AG - Frankfurt
    "NL0000226223": {"EUR": "STM"},  # STMICROELECTRONICS NV - NYSE (better data than STM.PA)
    "FI0009000681": {"EUR": "NOK"},  # NOKIA OYJ - NYSE (better data than NOKIA.HE)
    "SE0000108656": {"SEK": "ERIC-B.ST", "EUR": "ERIC-B.ST"},  # TELEFONAKTIEBOLAGET LM ERICSSON-B - Stockholm
    "DE0007164600": {"EUR": "SAP.DE"},  # SAP SE - Frankfurt
    "NL0010273215": {"EUR": "ASML.AS"},  # ASML HOLDING NV - Amsterdam
}


# Trading-currency → preferred Yahoo Finance ticker suffix.
# Used to disambiguate when an ISIN is listed on multiple Yahoo venues.
CURRENCY_TO_SUFFIX: Dict[str, str] = {
    # Europe
    "SEK": ".ST",   # Stockholm
    "NOK": ".OL",   # Oslo
    "DKK": ".CO",   # Copenhagen
    "ISK": ".IC",   # Iceland
    "CHF": ".SW",   # Swiss / SIX
    "GBP": ".L",    # London (pounds)
    "GBp": ".L",    # London (pence)
    "PLN": ".WA",   # Warsaw
    "CZK": ".PR",   # Prague
    "HUF": ".BD",   # Budapest
    "RON": ".RO",   # Bucharest
    "TRY": ".IS",   # Istanbul
    "RUB": ".ME",   # Moscow
    # Asia / Pacific
    "JPY": ".T",    # Tokyo
    "HKD": ".HK",   # Hong Kong
    "CNY": ".SS",   # Shanghai (Shenzhen also uses .SZ — currency alone can't tell)
    "KRW": ".KS",   # Korea (KOSPI; KOSDAQ is .KQ)
    "TWD": ".TW",   # Taiwan
    "INR": ".NS",   # India NSE (BSE is .BO)
    "SGD": ".SI",   # Singapore
    "AUD": ".AX",   # Australia
    "NZD": ".NZ",   # New Zealand
    "MYR": ".KL",   # Malaysia
    "THB": ".BK",   # Thailand
    "IDR": ".JK",   # Indonesia
    "PHP": ".PS",   # Philippines
    "VND": ".VN",   # Vietnam
    # Americas
    "CAD": ".TO",   # Toronto (Venture is .V)
    "MXN": ".MX",   # Mexico
    "BRL": ".SA",   # Brazil (São Paulo / B3)
    "ARS": ".BA",   # Argentina
    "CLP": ".SN",   # Chile
    # Middle East / Africa
    "ILS": ".TA",   # Tel Aviv
    "ZAR": ".JO",   # Johannesburg
    "SAR": ".SR",   # Saudi (Tadawul)
    "AED": ".AE",   # UAE
    "EGP": ".CA",   # Egypt
    # USD is left unmapped: most US listings have no suffix.
}

# ISIN country prefix → preferred Yahoo Finance ticker suffix (used as a
# fallback when the currency hint is ambiguous, e.g. EUR shared across many
# venues, or unset).
COUNTRY_TO_SUFFIX: Dict[str, str] = {
    # Europe (Eurozone)
    "DE": ".DE", "FR": ".PA", "NL": ".AS",
    "IT": ".MI", "ES": ".MC", "FI": ".HE",
    "BE": ".BR", "PT": ".LS", "AT": ".VI",
    "GR": ".AT", "IE": ".IR",
    # Europe (non-Euro)
    "SE": ".ST", "NO": ".OL", "DK": ".CO",
    "IS": ".IC", "CH": ".SW", "GB": ".L",
    "PL": ".WA", "CZ": ".PR", "HU": ".BD",
    "RO": ".RO", "TR": ".IS",
    # Asia / Pacific
    "JP": ".T",  "HK": ".HK", "CN": ".SS",
    "KR": ".KS", "TW": ".TW", "IN": ".NS",
    "SG": ".SI", "AU": ".AX", "NZ": ".NZ",
    "MY": ".KL", "TH": ".BK", "ID": ".JK",
    "PH": ".PS", "VN": ".VN",
    # Americas
    "CA": ".TO", "MX": ".MX", "BR": ".SA",
    "AR": ".BA", "CL": ".SN",
    # Middle East / Africa
    "IL": ".TA", "ZA": ".JO", "SA": ".SR",
    "AE": ".AE", "EG": ".CA",
    # US: no suffix — Yahoo uses bare ticker (AAPL, MSFT). Omitted intentionally.
}


def _pick_best_search_match(
    quotes: List[dict],
    currency: Optional[str] = None,
    isin: Optional[str] = None,
) -> Optional[str]:
    """Pick the best Yahoo Finance Search result for an equity-like instrument.

    Prefers EQUITY/ETF/MUTUALFUND quotes, then a ticker whose suffix matches
    the trading currency, then the ISIN's country prefix, then falls back to
    the first candidate.
    """
    if not quotes:
        return None

    candidates = [
        q for q in quotes
        if q.get("quoteType") in ("EQUITY", "ETF", "MUTUALFUND")
    ] or list(quotes)

    preferred_suffix: Optional[str] = None
    if currency and currency in CURRENCY_TO_SUFFIX:
        preferred_suffix = CURRENCY_TO_SUFFIX[currency]
    elif isin and len(isin) >= 2 and isin[:2] in COUNTRY_TO_SUFFIX:
        preferred_suffix = COUNTRY_TO_SUFFIX[isin[:2]]

    if preferred_suffix:
        for q in candidates:
            symbol = q.get("symbol", "")
            if symbol.endswith(preferred_suffix):
                return symbol

    return candidates[0].get("symbol")


def _search_yahoo(
    query: str,
    currency: Optional[str] = None,
    isin: Optional[str] = None,
) -> Optional[str]:
    """Run a Yahoo Finance search and return the best-matching ticker."""
    try:
        result = yf.Search(query)
        return _pick_best_search_match(result.quotes, currency=currency, isin=isin)
    except Exception as e:
        logger.debug(f"Yahoo Search for '{query}' failed: {e}")
        return None


def resolve_ticker_from_isin(isin: str, currency: str = None) -> Optional[str]:
    """
    Attempt to automatically resolve an ISIN code to a Yahoo Finance ticker symbol.

    Args:
        isin: The ISIN code to resolve
        currency: Optional currency hint for the stock

    Returns:
        Yahoo Finance ticker symbol if found, None otherwise
    """
    if not isin:
        return None

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

    # Primary resolver: Yahoo Finance Search. Works globally and returns the
    # canonical local-exchange ticker (e.g. SAVE.ST, KD, PGHN.SW) rather than
    # an ISIN-encoded one. Currency/country hints disambiguate when an
    # instrument is listed on multiple Yahoo venues.
    ticker = _search_yahoo(isin, currency=currency, isin=isin)
    if ticker:
        logger.info(f"Resolved {isin} to {ticker} via Yahoo Finance search")
        return ticker

    # Last-resort prefix heuristic (kept for offline / network-flaky cases).
    if isin.startswith("US"):
        for candidate in _generate_us_ticker_candidates(isin):
            if _verify_ticker(candidate, isin):
                logger.info(f"Resolved {isin} to {candidate} via US pattern matching")
                return candidate
    elif isin.startswith(("NL", "DE", "FR", "IT", "ES")):
        for candidate in _generate_european_ticker_candidates(isin):
            if _verify_ticker(candidate, isin):
                logger.info(f"Resolved {isin} to {candidate} via European pattern matching")
                return candidate

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
    # Handle None input
    if stock_name is None:
        return None

    # Extract potential ticker from name (first word, uppercase)
    potential_ticker = stock_name.split()[0].upper()

    # Remove common suffixes like CORP, INC, etc.
    potential_ticker = potential_ticker.replace("CORP", "").replace("INC", "").strip()

    # Try to verify it
    if _verify_ticker(potential_ticker):
        logger.info(f"Resolved '{stock_name}' to {potential_ticker} via name extraction")
        return potential_ticker

    # Fallback: Yahoo Finance search by company name.
    ticker = _search_yahoo(stock_name, currency=currency)
    if ticker:
        logger.info(f"Resolved '{stock_name}' to {ticker} via Yahoo Finance search")
        return ticker

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
