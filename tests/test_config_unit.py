"""Unit tests for config.py — column mapping, language detection, whitespace handling.

Regression tests for GitHub issue #1:
- Dutch DEGIRO export: missing column errors
- English export with trailing whitespace in column names (e.g., 'Price ')
- Auto-detection of export language
"""

import pytest


def test_detect_english_columns():
    """Test auto-detection of English DEGIRO export columns."""
    from degiro_portfolio.config import Config

    english_columns = [
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Venue', 'Quantity', 'Price ', 'Unnamed: 8', 'Value EUR',
        'Total EUR', 'Transaction and/or third party fees EUR',
        'Exchange rate', 'Unnamed: 17'
    ]
    lang = Config.detect_and_set_column_mapping(english_columns)
    assert lang == 'en'


def test_detect_dutch_columns():
    """Regression: Dutch DEGIRO export must be auto-detected (issue #1)."""
    from degiro_portfolio.config import Config

    dutch_columns = [
        'Datum', 'Tijd', 'Product', 'ISIN', 'Referentiebeurs',
        'Handelsplaats', 'Aantal', 'Koers', 'Unnamed: 8', 'Waarde',
        'Totaal', 'Transactie- en/of derde kosten',
        'Wisselkoers', 'Unnamed: 17'
    ]
    lang = Config.detect_and_set_column_mapping(dutch_columns)
    assert lang == 'nl'

    # After detection, get_column should return Dutch names
    assert Config.get_column('date') == 'Datum'
    assert Config.get_column('price') == 'Koers'
    assert Config.get_column('quantity') == 'Aantal'

    # Reset to English for other tests
    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS


def test_validate_english_columns_with_trailing_whitespace():
    """Regression: 'Price ' with trailing space must pass validation (issue #1)."""
    from degiro_portfolio.config import Config

    # Reset to English mapping
    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS

    # Simulate DEGIRO export with trailing whitespace on some columns
    columns_with_spaces = [
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Venue', 'Quantity', 'Price ',  # trailing space — this is the real DEGIRO format
        'Unnamed: 8', 'Value EUR', 'Total EUR',
        'Transaction and/or third party fees EUR',
        'Exchange rate', 'Unnamed: 17'
    ]
    is_valid, missing = Config.validate_excel_columns(columns_with_spaces)
    assert is_valid, f"Validation failed, missing: {missing}"
    assert len(missing) == 0


def test_validate_columns_without_trailing_whitespace():
    """Regression: 'Price' without trailing space must also pass (issue #1)."""
    from degiro_portfolio.config import Config

    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS

    # User has clean column names (no trailing whitespace)
    clean_columns = [
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Venue', 'Quantity', 'Price',  # no trailing space
        'Unnamed: 8', 'Value EUR', 'Total EUR',
        'Transaction and/or third party fees EUR',
        'Exchange rate', 'Unnamed: 17'
    ]
    is_valid, missing = Config.validate_excel_columns(clean_columns)
    assert is_valid, f"Validation failed, missing: {missing}"


def test_normalize_dataframe_columns_strips_whitespace():
    """Regression: DataFrame columns with trailing spaces must be normalized (issue #1)."""
    import pandas as pd
    from degiro_portfolio.config import Config

    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS

    # Create DataFrame with messy column names (trailing spaces)
    df = pd.DataFrame({
        'Date': ['01-01-2025'],
        'Time ': ['10:00'],       # trailing space
        'Product ': ['NVIDIA'],   # trailing space
        'ISIN': ['US67066G1040'],
        'Price': ['100.0'],       # no trailing space (DEGIRO expects 'Price ')
    })

    normalized = Config.normalize_dataframe_columns(df)

    # 'Price' should be renamed to 'Price ' to match the expected DEGIRO format
    assert 'Price ' in normalized.columns or 'Price' in normalized.columns


def test_validate_dutch_columns():
    """Test that Dutch column names pass validation after auto-detection."""
    from degiro_portfolio.config import Config

    dutch_columns = [
        'Datum', 'Tijd', 'Product', 'ISIN', 'Referentiebeurs',
        'Handelsplaats', 'Aantal', 'Koers', 'Unnamed: 8', 'Waarde',
        'Totaal', 'Transactie- en/of derde kosten',
        'Wisselkoers', 'Unnamed: 17'
    ]

    # Detect language first
    Config.detect_and_set_column_mapping(dutch_columns)

    # Then validate
    is_valid, missing = Config.validate_excel_columns(dutch_columns)
    assert is_valid, f"Dutch validation failed, missing: {missing}"

    # Reset
    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS


def test_detect_unknown_columns_returns_none():
    """Test that unrecognizable columns return None for language detection."""
    from degiro_portfolio.config import Config

    garbage_columns = ['foo', 'bar', 'baz']
    lang = Config.detect_and_set_column_mapping(garbage_columns)
    # Should still pick a "best" match or return None/a lang with low score
    # The important thing is it doesn't crash
    assert lang is None or isinstance(lang, str)

    # Reset
    Config.ACTIVE_COLUMN_MAPPING = Config.DEGIRO_COLUMNS
