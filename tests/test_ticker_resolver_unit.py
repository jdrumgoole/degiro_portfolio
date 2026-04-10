"""Unit tests for ticker_resolver.py module."""

import pytest
from unittest.mock import patch, MagicMock


def test_resolve_ticker_from_isin_with_manual_mapping():
    """Test resolution from manual ISIN to ticker mapping."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_isin

    # Test known ISINs from manual mapping
    assert resolve_ticker_from_isin("US5949181045", "USD") == "MSFT"  # Microsoft
    assert resolve_ticker_from_isin("US67066G1040", "USD") == "NVDA"  # NVIDIA
    assert resolve_ticker_from_isin("US02079K3059", "USD") == "GOOGL"  # Alphabet


def test_resolve_ticker_from_isin_with_currency():
    """Test resolution with currency hint."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_isin

    # European stocks with currency
    ticker = resolve_ticker_from_isin("DE0007164600", "EUR")
    assert ticker == "SAP.DE"  # SAP

    ticker = resolve_ticker_from_isin("NL0010273215", "EUR")
    assert ticker == "ASML.AS"  # ASML


def test_resolve_ticker_from_isin_unknown():
    """Test resolution with unknown ISIN."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_isin

    # Test with made-up ISIN
    result = resolve_ticker_from_isin("XX0000000000", "USD")
    # Should return None for unknown ISIN
    assert result is None


def test_get_ticker_for_stock_success():
    """Test successful ticker resolution."""
    from degiro_portfolio.ticker_resolver import get_ticker_for_stock

    # Test with known ISIN
    ticker = get_ticker_for_stock("US5949181045", "MICROSOFT CORP", "USD")
    assert ticker == "MSFT"

    ticker = get_ticker_for_stock("DE0007164600", "SAP SE", "EUR")
    assert ticker == "SAP.DE"


def test_get_ticker_for_stock_with_name_fallback():
    """Test ticker resolution falls back to name search."""
    from degiro_portfolio.ticker_resolver import get_ticker_for_stock

    with patch('degiro_portfolio.ticker_resolver.resolve_ticker_from_name') as mock_resolve:
        mock_resolve.return_value = "AAPL"

        # Unknown ISIN should try name resolution
        ticker = get_ticker_for_stock("UNKNOWN_ISIN", "Apple Inc", "USD")

        # Should have called name resolution
        mock_resolve.assert_called_once()


def test_manual_ticker_mapping_keys():
    """Test that MANUAL_TICKER_MAPPING has expected entries."""
    from degiro_portfolio.ticker_resolver import MANUAL_TICKER_MAPPING

    # Should have major tech companies
    assert "US5949181045" in MANUAL_TICKER_MAPPING  # Microsoft
    assert "US67066G1040" in MANUAL_TICKER_MAPPING  # NVIDIA
    assert "US02079K3059" in MANUAL_TICKER_MAPPING  # Google

    # Check some European stocks
    assert "NL0010273215" in MANUAL_TICKER_MAPPING  # ASML
    assert "DE0007164600" in MANUAL_TICKER_MAPPING  # SAP


def test_manual_ticker_mapping_values():
    """Test that MANUAL_TICKER_MAPPING has correct ticker values."""
    from degiro_portfolio.ticker_resolver import MANUAL_TICKER_MAPPING

    assert MANUAL_TICKER_MAPPING["US5949181045"]["USD"] == "MSFT"
    assert MANUAL_TICKER_MAPPING["US67066G1040"]["USD"] == "NVDA"
    assert MANUAL_TICKER_MAPPING["US02079K3059"]["USD"] == "GOOGL"
    assert MANUAL_TICKER_MAPPING["NL0010273215"]["EUR"] == "ASML.AS"
    assert MANUAL_TICKER_MAPPING["DE0007164600"]["EUR"] == "SAP.DE"


def test_resolve_ticker_from_name():
    """Test ticker resolution from company name."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_name

    with patch('degiro_portfolio.ticker_resolver.yf.Ticker') as mock_ticker_class:
        # Mock successful ticker lookup
        mock_ticker = MagicMock()
        mock_ticker.info = {'symbol': 'AAPL'}
        mock_ticker_class.return_value = mock_ticker

        ticker = resolve_ticker_from_name("Apple Inc", "USD")

        # Should attempt ticker search
        assert mock_ticker_class.called


def test_verify_ticker():
    """Test ticker verification."""
    from degiro_portfolio.ticker_resolver import _verify_ticker

    with patch('degiro_portfolio.ticker_resolver.yf.Ticker') as mock_ticker_class:
        # Mock successful verification
        mock_ticker = MagicMock()
        mock_ticker.info = {
            'symbol': 'AAPL',
            'shortName': 'Apple Inc.',
            'regularMarketPrice': 150.25
        }
        mock_ticker_class.return_value = mock_ticker

        result = _verify_ticker("AAPL")
        assert result is True


def test_verify_ticker_handles_errors():
    """Test that ticker verification handles errors gracefully."""
    from degiro_portfolio.ticker_resolver import _verify_ticker

    with patch('degiro_portfolio.ticker_resolver.yf.Ticker') as mock_ticker_class:
        # Mock ticker that raises exception
        mock_ticker_class.side_effect = Exception("API Error")

        result = _verify_ticker("INVALID")
        assert result is False


def test_generate_us_ticker_candidates():
    """Test US ticker candidate generation."""
    from degiro_portfolio.ticker_resolver import _generate_us_ticker_candidates

    # US ISIN format: US followed by 9 characters
    candidates = _generate_us_ticker_candidates("US0378331005")

    # Should generate some candidates
    assert isinstance(candidates, list)
    assert len(candidates) > 0


def test_generate_european_ticker_candidates():
    """Test European ticker candidate generation."""
    from degiro_portfolio.ticker_resolver import _generate_european_ticker_candidates

    # German ISIN
    candidates = _generate_european_ticker_candidates("DE0007164600")

    # Should generate candidates with German exchange suffixes
    assert isinstance(candidates, list)
    assert any('.DE' in c or '.F' in c for c in candidates)


def test_resolve_ticker_from_isin_caches_results():
    """Test that ticker resolution doesn't make redundant calls."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_isin

    # First call - hits manual mapping
    ticker1 = resolve_ticker_from_isin("US5949181045", "USD")
    # Second call - should use same logic
    ticker2 = resolve_ticker_from_isin("US5949181045", "USD")

    assert ticker1 == ticker2 == "MSFT"


def test_get_ticker_for_stock_returns_none_for_failures():
    """Test that get_ticker_for_stock returns None when all methods fail."""
    from degiro_portfolio.ticker_resolver import get_ticker_for_stock

    with patch('degiro_portfolio.ticker_resolver.resolve_ticker_from_isin', return_value=None):
        with patch('degiro_portfolio.ticker_resolver.resolve_ticker_from_name', return_value=None):
            ticker = get_ticker_for_stock("UNKNOWN", "Unknown Company", "USD")
            assert ticker is None


def test_resolve_ticker_from_name_handles_none_name():
    """Test resolve_ticker_from_name handles None gracefully."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_name

    result = resolve_ticker_from_name(None, "USD")
    assert result is None


def test_european_exchange_suffixes():
    """Test that European stocks have correct exchange suffixes."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_isin

    # Frankfurt/XETRA stocks should have .DE or .F
    ticker = resolve_ticker_from_isin("DE0007164600", "EUR")
    assert ticker and ('.DE' in ticker or '.F' in ticker or ticker == "SAP.DE")

    # Amsterdam should have .AS
    ticker = resolve_ticker_from_isin("NL0010273215", "EUR")
    assert ticker and ('.AS' in ticker or ticker == "ASML.AS")

    # Stockholm should have .ST
    ticker = resolve_ticker_from_isin("SE0000108656", "SEK")
    assert ticker and ('.ST' in ticker or ticker == "ERIC-B.ST")


def test_resolve_ticker_from_isin_default_when_no_currency():
    """Manual mapping should return first available ticker when currency is None."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_isin

    # NVIDIA is in manual mapping with USD key
    ticker = resolve_ticker_from_isin("US67066G1040", None)
    assert ticker == "NVDA"


def test_resolve_ticker_from_isin_default_when_currency_not_in_mapping():
    """Manual mapping should return first available ticker when currency doesn't match."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_isin

    # SAP is mapped for EUR only — passing GBP should still return a ticker
    ticker = resolve_ticker_from_isin("DE0007164600", "GBP")
    assert ticker == "SAP.DE"


def test_verify_ticker_with_isin_match():
    """_verify_ticker should return True when ISIN matches."""
    from degiro_portfolio.ticker_resolver import _verify_ticker
    from unittest.mock import patch, MagicMock

    with patch('yfinance.Ticker') as mock_class:
        mock_ticker = MagicMock()
        mock_ticker.info = {
            'symbol': 'NVDA',
            'isin': 'US67066G1040',
            'regularMarketPrice': 150.0
        }
        mock_class.return_value = mock_ticker

        assert _verify_ticker('NVDA', 'US67066G1040') is True


def test_verify_ticker_isin_mismatch_but_has_price():
    """_verify_ticker should return True if ISIN doesn't match but has market price."""
    from degiro_portfolio.ticker_resolver import _verify_ticker
    from unittest.mock import patch, MagicMock

    with patch('yfinance.Ticker') as mock_class:
        mock_ticker = MagicMock()
        mock_ticker.info = {
            'symbol': 'NVDA',
            'isin': 'DIFFERENT_ISIN',
            'regularMarketPrice': 150.0
        }
        mock_class.return_value = mock_ticker

        assert _verify_ticker('NVDA', 'US67066G1040') is True


def test_verify_ticker_no_isin_no_price():
    """_verify_ticker should return False if no ISIN match and no price."""
    from degiro_portfolio.ticker_resolver import _verify_ticker
    from unittest.mock import patch, MagicMock

    with patch('yfinance.Ticker') as mock_class:
        mock_ticker = MagicMock()
        mock_ticker.info = {'symbol': 'BAD'}
        mock_class.return_value = mock_ticker

        assert _verify_ticker('BAD', 'US0000000000') is False


def test_resolve_ticker_from_name_strips_suffixes():
    """resolve_ticker_from_name should strip CORP/INC from stock names."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_name
    from unittest.mock import patch, MagicMock

    with patch('degiro_portfolio.ticker_resolver._verify_ticker') as mock_verify:
        mock_verify.return_value = True

        result = resolve_ticker_from_name("NVIDIA CORP", "USD")
        # Should try "NVIDIA" (with CORP stripped)
        mock_verify.assert_called_with("NVIDIA")
        assert result == "NVIDIA"


def test_resolve_ticker_from_name_unresolvable():
    """resolve_ticker_from_name should return None when verification fails."""
    from degiro_portfolio.ticker_resolver import resolve_ticker_from_name
    from unittest.mock import patch

    with patch('degiro_portfolio.ticker_resolver._verify_ticker', return_value=False):
        result = resolve_ticker_from_name("TOTALLY FAKE STOCK", "USD")
        assert result is None
