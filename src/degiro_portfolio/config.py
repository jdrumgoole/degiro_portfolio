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

    # -------------------------------------------------------------------------
    # DEGIRO exports always have 14 columns in this fixed order, regardless
    # of the user's language setting.  We map by position so that English,
    # Dutch, German, etc. exports all work without per-language mappings.
    # -------------------------------------------------------------------------

    # Canonical column names used internally (position -> canonical name)
    DEGIRO_COLUMN_ORDER = [
        'Date',                  # 0
        'Time',                  # 1
        'Product',               # 2
        'ISIN',                  # 3
        'Reference exchange',    # 4
        'Quantity',              # 5
        'Price',                 # 6
        'Currency',              # 7
        'Value EUR',             # 8
        'Total EUR',             # 9
        'Venue',                 # 10
        'Exchange rate',         # 11
        'Fees EUR',              # 12
        'Transaction ID',        # 13
    ]

    DEGIRO_EXPECTED_COLUMN_COUNT = len(DEGIRO_COLUMN_ORDER)  # 14

    # 18-column DEGIRO format mapping (column name → canonical name)
    # Newer DEGIRO exports have extra columns: Venue at pos 5, Local value,
    # AutoFX Fee, etc.  We map by name to extract the 14 canonical columns.
    DEGIRO_18COL_NAME_MAP = {
        'Date': 'Date',
        'Time': 'Time',
        'Product': 'Product',
        'ISIN': 'ISIN',
        'Reference exchange': 'Reference exchange',
        'Quantity': 'Quantity',
        'Price': 'Price',
        'Unnamed: 8': 'Currency',
        'Value EUR': 'Value EUR',
        'Total EUR': 'Total EUR',
        'Venue': 'Venue',
        'Exchange rate': 'Exchange rate',
        'Transaction and/or third party fees EUR': 'Fees EUR',
        'Order ID': 'Transaction ID',
    }

    # Logical key -> canonical column name mapping
    DEGIRO_COLUMNS = {
        'date': 'Date',
        'time': 'Time',
        'transaction_id': 'Transaction ID',
        'product': 'Product',
        'isin': 'ISIN',
        'exchange': 'Reference exchange',
        'quantity': 'Quantity',
        'price': 'Price',
        'currency': 'Currency',
        'venue': 'Venue',
        'value_eur': 'Value EUR',
        'total_eur': 'Total EUR',
        'fees_eur': 'Fees EUR',
        'exchange_rate': 'Exchange rate',
    }

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
        """
        return [cls.get_column(key) for key in cls.REQUIRED_COLUMNS]

    @classmethod
    def normalize_degiro_columns(cls, df):
        """
        Rename a DEGIRO DataFrame's columns to canonical names.

        Supports two DEGIRO export formats:
        - 14-column format: renamed by position (language-independent)
        - 18-column format: mapped by column name, extra columns dropped

        Args:
            df: pandas DataFrame read from a DEGIRO export

        Returns:
            DataFrame with canonical column names (14 columns)

        Raises:
            ValueError: if the DataFrame has an unsupported number of columns
        """
        ncols = len(df.columns)

        if ncols == cls.DEGIRO_EXPECTED_COLUMN_COUNT:
            df.columns = cls.DEGIRO_COLUMN_ORDER
            return df

        if ncols == 18:
            return cls._normalize_18col(df)

        raise ValueError(
            f"Expected {cls.DEGIRO_EXPECTED_COLUMN_COUNT} or 18 columns in "
            f"DEGIRO export, got {ncols}.  "
            f"Columns found: {list(df.columns)}"
        )

    @classmethod
    def _normalize_18col(cls, df):
        """Map 18-column DEGIRO format to canonical 14 columns by name."""
        col_list = list(df.columns)
        rename = {}
        selected = []

        for orig_name, canonical_name in cls.DEGIRO_18COL_NAME_MAP.items():
            if orig_name in col_list:
                rename[orig_name] = canonical_name
                selected.append(orig_name)

        missing = set(cls.DEGIRO_18COL_NAME_MAP.keys()) - set(col_list)
        if missing:
            raise ValueError(
                f"18-column DEGIRO export missing expected columns: {missing}. "
                f"Columns found: {col_list}"
            )

        df = df[selected].rename(columns=rename)
        return df

    @classmethod
    def validate_excel_columns(cls, df_columns: list) -> tuple[bool, list]:
        """
        Validate that a DataFrame has all required columns.

        Args:
            df_columns: List of column names from the DataFrame

        Returns:
            Tuple of (is_valid, missing_columns)
        """
        required = set(cls.get_required_excel_columns())
        present = set(df_columns)
        missing = list(required - present)
        return (len(missing) == 0, missing)


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
