"""Unit tests for config.py — column mapping, normalization, validation.

Tests for the position-based column mapping approach where DEGIRO exports
are normalized to canonical column names regardless of language.
"""

import pytest
import pandas as pd

from degiro_portfolio.config import Config


def test_canonical_column_order_has_expected_count():
    """DEGIRO exports have exactly 14 columns."""
    assert Config.DEGIRO_EXPECTED_COLUMN_COUNT == 14
    assert len(Config.DEGIRO_COLUMN_ORDER) == 14


def test_get_column_returns_canonical_name():
    """get_column maps logical keys to canonical column names."""
    assert Config.get_column('date') == 'Date'
    assert Config.get_column('price') == 'Price'
    assert Config.get_column('quantity') == 'Quantity'
    assert Config.get_column('currency') == 'Currency'
    assert Config.get_column('isin') == 'ISIN'


def test_get_column_returns_key_for_unknown():
    """get_column returns the key itself if not found in mapping."""
    assert Config.get_column('nonexistent') == 'nonexistent'


def test_get_required_excel_columns():
    """Required columns should map to canonical names."""
    required = Config.get_required_excel_columns()
    assert 'Date' in required
    assert 'Product' in required
    assert 'ISIN' in required
    assert 'Price' in required
    assert 'Currency' in required


def test_normalize_degiro_columns_english():
    """English DEGIRO export columns are renamed to canonical names by position."""
    english_columns = [
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Quantity', 'Price ', 'Unnamed: 8', 'Value EUR',
        'Total EUR', 'Venue', 'Exchange rate',
        'Transaction and/or third party fees EUR', 'Unnamed: 17'
    ]
    df = pd.DataFrame([[''] * 14], columns=english_columns)
    result = Config.normalize_degiro_columns(df)
    assert list(result.columns) == Config.DEGIRO_COLUMN_ORDER


def test_normalize_degiro_columns_dutch():
    """Regression: Dutch DEGIRO export must be normalized to canonical names (issue #1)."""
    dutch_columns = [
        'Datum', 'Tijd', 'Product', 'ISIN', 'Referentiebeurs',
        'Aantal', 'Koers', 'Unnamed: 8', 'Waarde',
        'Totaal', 'Handelsplaats', 'Wisselkoers',
        'Transactie- en/of derde kosten', 'Unnamed: 17'
    ]
    df = pd.DataFrame([[''] * 14], columns=dutch_columns)
    result = Config.normalize_degiro_columns(df)
    assert list(result.columns) == Config.DEGIRO_COLUMN_ORDER
    assert result.columns[0] == 'Date'
    assert result.columns[6] == 'Price'
    assert result.columns[7] == 'Currency'


def test_normalize_degiro_columns_wrong_count_raises():
    """DataFrame with wrong number of columns should raise ValueError."""
    df = pd.DataFrame([[''] * 10], columns=[f'col{i}' for i in range(10)])
    with pytest.raises(ValueError, match="Expected 14 or 18 columns"):
        Config.normalize_degiro_columns(df)


def test_validate_excel_columns_with_canonical_names():
    """Validation passes when canonical column names are present."""
    columns = Config.DEGIRO_COLUMN_ORDER
    is_valid, missing = Config.validate_excel_columns(columns)
    assert is_valid, f"Validation failed, missing: {missing}"
    assert len(missing) == 0


def test_validate_excel_columns_missing_required():
    """Validation fails when required columns are missing."""
    columns = ['Date', 'Time', 'Product']  # missing many required
    is_valid, missing = Config.validate_excel_columns(columns)
    assert not is_valid
    assert len(missing) > 0
    assert 'ISIN' in missing


def test_validate_after_normalize():
    """Regression: columns should pass validation after normalize_degiro_columns (issue #1).

    This tests the full workflow: read DEGIRO export with any language columns,
    normalize to canonical names, then validate.
    """
    # Simulate English export with trailing whitespace (real DEGIRO format)
    messy_columns = [
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Quantity', 'Price ', 'Unnamed: 8', 'Value EUR',
        'Total EUR', 'Venue', 'Exchange rate',
        'Transaction and/or third party fees EUR', 'Unnamed: 17'
    ]
    df = pd.DataFrame([[''] * 14], columns=messy_columns)
    df = Config.normalize_degiro_columns(df)

    is_valid, missing = Config.validate_excel_columns(list(df.columns))
    assert is_valid, f"Validation failed after normalize, missing: {missing}"


def test_normalize_degiro_18col_format():
    """18-column DEGIRO CSV format should be mapped to canonical 14 columns."""
    cols_18 = [
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Venue', 'Quantity', 'Price', 'Unnamed: 8', 'Local value',
        'Unnamed: 10', 'Value EUR', 'Exchange rate', 'AutoFX Fee',
        'Transaction and/or third party fees EUR', 'Total EUR',
        'Order ID', 'Unnamed: 17'
    ]
    df = pd.DataFrame([[''] * 18], columns=cols_18)
    result = Config.normalize_degiro_columns(df)
    assert len(result.columns) == 14
    assert list(result.columns) == Config.DEGIRO_COLUMN_ORDER
    assert 'Local value' not in result.columns
    assert 'AutoFX Fee' not in result.columns


def test_normalize_degiro_18col_missing_column_raises():
    """18-column format with a missing required column should raise ValueError."""
    # Missing 'Order ID' — replaced with 'Bad Column'
    cols_18 = [
        'Date', 'Time', 'Product', 'ISIN', 'Reference exchange',
        'Venue', 'Quantity', 'Price', 'Unnamed: 8', 'Local value',
        'Unnamed: 10', 'Value EUR', 'Exchange rate', 'AutoFX Fee',
        'Transaction and/or third party fees EUR', 'Total EUR',
        'Bad Column', 'Unnamed: 17'
    ]
    df = pd.DataFrame([[''] * 18], columns=cols_18)
    with pytest.raises(ValueError, match="missing expected columns"):
        Config.normalize_degiro_columns(df)
