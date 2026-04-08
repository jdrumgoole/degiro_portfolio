"""
Configuration management for DEGIRO Portfolio application.

This module centralizes all configuration values, making the application
more maintainable and adaptable to different data sources.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # ========================================================================
    # Paths
    # ========================================================================
    PROJECT_ROOT = Path(__file__).parent.parent.parent
    DB_PATH = os.environ.get(
        'DEGIRO_PORTFOLIO_DB',
        str(PROJECT_ROOT / 'degiro_portfolio.db')
    )
    DEFAULT_TRANSACTIONS_FILE = PROJECT_ROOT / 'Transactions.xlsx'

    # ========================================================================
    # Server Configuration
    # ========================================================================
    HOST = os.environ.get('DEGIRO_PORTFOLIO_HOST', '0.0.0.0')
    PORT = int(os.environ.get('DEGIRO_PORTFOLIO_PORT', '8000'))

    # ========================================================================
    # Data Fetching Configuration
    # ========================================================================
    # Data provider: 'yahoo', 'twelvedata', or 'fmp'
    PRICE_DATA_PROVIDER = os.environ.get('PRICE_DATA_PROVIDER', 'yahoo')

    # Twelve Data API key (get free key at https://twelvedata.com/)
    TWELVEDATA_API_KEY = os.environ.get('TWELVEDATA_API_KEY', '')

    # Financial Modeling Prep API key (get key at https://site.financialmodelingprep.com/)
    FMP_API_KEY = os.environ.get('FMP_API_KEY', '')

    # How far back to fetch price data initially
    INITIAL_FETCH_PERIOD = os.environ.get('INITIAL_FETCH_PERIOD', 'max')

    # How far back to fetch index data
    INDEX_FETCH_PERIOD = os.environ.get('INDEX_FETCH_PERIOD', '5y')

    # How many days to fetch when updating prices
    UPDATE_FETCH_PERIOD = os.environ.get('UPDATE_FETCH_PERIOD', '7d')

    # ========================================================================
    # Market Indices
    # ========================================================================
    # Benchmark indices to track against portfolio performance
    INDICES = {
        "^GSPC": "S&P 500",
        "^STOXX50E": "Euro Stoxx 50",
        # Uncomment to add more indices:
        # "^FTSE": "FTSE 100",
        # "^N225": "Nikkei 225",
        # "^DJI": "Dow Jones Industrial Average",
    }

    # ========================================================================
    # Ignored Stocks
    # ========================================================================
    # Stocks to ignore during import (collapsed companies, delisted, etc.)
    # Add ISIN codes of stocks you want to exclude from portfolio tracking
    IGNORED_STOCKS = {
        'US82669G1040',  # Signature Bank (collapsed March 2023)
        # Add more ISINs here as needed:
        # 'US12345678',  # Example: Another stock to ignore
    }

    # ========================================================================
    # Excel Column Mappings
    # ========================================================================
    #
    # DEGIRO Export Format Column Mappings
    #
    # These map logical column names to the actual column names in DEGIRO's
    # Excel export format. If DEGIRO changes their export format, or if you
    # want to support another broker, you only need to update these mappings.
    #
    # NOTE: Some DEGIRO columns have unusual names:
    # - 'Price ' has a trailing space
    # - 'Unnamed: 8' is the currency column
    # - 'Unnamed: 17' is the transaction ID
    #
    # To support a different broker format, create a new mapping set below
    # and switch ACTIVE_COLUMN_MAPPING to point to it.
    # ========================================================================

    DEGIRO_COLUMNS = {
        # Transaction identification
        'date': 'Date',
        'time': 'Time',
        'transaction_id': 'Unnamed: 17',

        # Stock information
        'product': 'Product',
        'isin': 'ISIN',
        'exchange': 'Reference exchange',

        # Transaction details
        'quantity': 'Quantity',
        'price': 'Price ',  # NOTE: Trailing space in DEGIRO export!
        'currency': 'Unnamed: 8',  # NOTE: Unnamed column in DEGIRO export
        'venue': 'Venue',

        # Financial values (in EUR)
        'value_eur': 'Value EUR',
        'total_eur': 'Total EUR',
        'fees_eur': 'Transaction and/or third party fees EUR',
        'exchange_rate': 'Exchange rate',
    }

    # Dutch DEGIRO export format
    DEGIRO_COLUMNS_NL = {
        # Transaction identification
        'date': 'Datum',
        'time': 'Tijd',
        'transaction_id': 'Unnamed: 17',

        # Stock information
        'product': 'Product',
        'isin': 'ISIN',
        'exchange': 'Referentiebeurs',

        # Transaction details
        'quantity': 'Aantal',
        'price': 'Koers',
        'currency': 'Unnamed: 8',
        'venue': 'Handelsplaats',

        # Financial values (in EUR)
        'value_eur': 'Waarde',
        'total_eur': 'Totaal',
        'fees_eur': 'Transactie- en/of derde kosten',
        'exchange_rate': 'Wisselkoers',
    }

    # All known column mappings for auto-detection
    KNOWN_COLUMN_MAPPINGS = {
        'en': DEGIRO_COLUMNS,
        'nl': DEGIRO_COLUMNS_NL,
    }

    # Example: Alternative broker format (uncomment and modify as needed)
    # INTERACTIVE_BROKERS_COLUMNS = {
    #     'date': 'Date',
    #     'time': 'Time',
    #     'transaction_id': 'Order ID',
    #     'product': 'Symbol',
    #     'isin': 'ISIN',
    #     'exchange': 'Exchange',
    #     'quantity': 'Quantity',
    #     'price': 'Price',
    #     'currency': 'Currency',
    #     'venue': 'Venue',
    #     'value_eur': 'Total (EUR)',
    #     'total_eur': 'Net Total (EUR)',
    #     'fees_eur': 'Commission (EUR)',
    #     'exchange_rate': 'FX Rate',
    # }

    # Set which column mapping to use
    ACTIVE_COLUMN_MAPPING = DEGIRO_COLUMNS

    # ========================================================================
    # Required Columns
    # ========================================================================
    # These columns must be present in the Excel file for import to work
    REQUIRED_COLUMNS = [
        'date',
        'product',
        'isin',
        'exchange',
        'quantity',
        'price',
        'currency',
        'value_eur',
        'total_eur',
    ]

    # ========================================================================
    # Helper Methods
    # ========================================================================

    @classmethod
    def get_column(cls, key: str) -> str:
        """
        Get the actual Excel column name for a logical column key.

        Args:
            key: Logical column name (e.g., 'currency', 'price')

        Returns:
            Actual column name in the Excel file (e.g., 'Unnamed: 8', 'Price ')

        Example:
            >>> Config.get_column('currency')
            'Unnamed: 8'
            >>> Config.get_column('price')
            'Price '
        """
        return cls.ACTIVE_COLUMN_MAPPING.get(key, key)

    @classmethod
    def get_required_excel_columns(cls) -> list:
        """
        Get list of actual Excel column names that are required.

        Returns:
            List of actual column names as they appear in the Excel file

        Example:
            >>> Config.get_required_excel_columns()
            ['Date', 'Product', 'ISIN', 'Reference exchange', ...]
        """
        return [cls.get_column(key) for key in cls.REQUIRED_COLUMNS]

    @classmethod
    def _normalize_columns(cls, columns: list) -> dict:
        """
        Build a mapping from stripped column names to original column names.

        This handles DEGIRO exports where some columns have trailing spaces
        (e.g., 'Price ' vs 'Price').

        Returns:
            Dict mapping stripped name -> original name
        """
        return {col.strip(): col for col in columns}

    @classmethod
    def detect_and_set_column_mapping(cls, df_columns: list) -> str | None:
        """
        Auto-detect the export language from DataFrame columns and set the
        active column mapping accordingly.

        Args:
            df_columns: List of column names from the DataFrame

        Returns:
            Language code ('en', 'nl', etc.) if detected, None otherwise
        """
        normalized = {col.strip() for col in df_columns}

        best_lang = None
        best_score = 0

        for lang, mapping in cls.KNOWN_COLUMN_MAPPINGS.items():
            expected = {v.strip() for v in mapping.values()}
            score = len(expected & normalized)
            if score > best_score:
                best_score = score
                best_lang = lang

        if best_lang:
            cls.ACTIVE_COLUMN_MAPPING = cls.KNOWN_COLUMN_MAPPINGS[best_lang]
            return best_lang
        return None

    @classmethod
    def validate_excel_columns(cls, df_columns: list) -> tuple[bool, list]:
        """
        Validate that a DataFrame has all required columns.

        Handles trailing/leading whitespace in column names (e.g., DEGIRO's
        'Price ' column). Also auto-detects the export language if the
        default mapping doesn't match.

        Args:
            df_columns: List of column names from the DataFrame

        Returns:
            Tuple of (is_valid, missing_columns)

        Example:
            >>> valid, missing = Config.validate_excel_columns(df.columns.tolist())
            >>> if not valid:
            ...     print(f"Missing columns: {missing}")
        """
        # First try auto-detecting the language
        cls.detect_and_set_column_mapping(df_columns)

        # Build normalized lookup: stripped name -> original name
        normalized = cls._normalize_columns(df_columns)
        present_stripped = set(normalized.keys())

        # Check required columns, matching with stripped names
        missing = []
        for key in cls.REQUIRED_COLUMNS:
            expected_col = cls.get_column(key)
            if expected_col not in df_columns and expected_col.strip() not in present_stripped:
                missing.append(expected_col)

        return (len(missing) == 0, missing)

    @classmethod
    def normalize_dataframe_columns(cls, df):
        """
        Rename DataFrame columns to match the active column mapping.

        Handles trailing/leading whitespace mismatches (e.g., 'Price ' vs
        'Price') by stripping whitespace and matching against expected names.

        Args:
            df: pandas DataFrame to normalize

        Returns:
            DataFrame with normalized column names
        """
        expected_cols = set(cls.ACTIVE_COLUMN_MAPPING.values())
        rename_map = {}
        for col in df.columns:
            stripped = col.strip()
            if col not in expected_cols and stripped != col:
                # Check if the stripped version matches an expected column
                for expected in expected_cols:
                    if stripped == expected.strip() and expected != col:
                        rename_map[col] = expected
                        break
        if rename_map:
            df = df.rename(columns=rename_map)
        return df

    @classmethod
    def get_column_mapping_name(cls) -> str:
        """
        Get the name of the active column mapping.

        Returns:
            Name of the active mapping (e.g., 'DEGIRO', 'INTERACTIVE_BROKERS')
        """
        if cls.ACTIVE_COLUMN_MAPPING == cls.DEGIRO_COLUMNS:
            return 'DEGIRO'
        if cls.ACTIVE_COLUMN_MAPPING == cls.DEGIRO_COLUMNS_NL:
            return 'DEGIRO (NL)'
        # Add more mappings here as they're created
        return 'CUSTOM'


# Convenience function for common use case
def get_column(key: str) -> str:
    """
    Convenience function to get Excel column name.

    This is a shorthand for Config.get_column(key).

    Args:
        key: Logical column name

    Returns:
        Actual Excel column name
    """
    return Config.get_column(key)
