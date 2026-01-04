"""
Type Conversion Utilities for Domain Model Factories

This module provides safe type conversion functions for creating domain models
from pandas DataFrames and other data sources. These utilities handle null
values gracefully and provide sensible defaults.

These functions were extracted from duplicate implementations in:
- FitItem.from_dataframe_row()
- FitSummary.from_dataframe_row()
- ModuleStock.from_query_results()

Usage:
    ```python
    from domain.converters import safe_int, safe_float, safe_str

    fit_id = safe_int(row.get('fit_id'))  # Returns 0 if null
    price = safe_float(row.get('price'))  # Returns 0.0 if null
    name = safe_str(row.get('name'))      # Returns "" if null
    ```
"""

import pandas as pd


def safe_int(value, default: int = 0) -> int:
    """
    Convert value to int, returning default if null or invalid.

    Handles pandas NA values gracefully by checking with pd.isna().

    Args:
        value: Value to convert (can be any type including pd.NA)
        default: Default value to return if conversion fails (default: 0)

    Returns:
        Integer value or default if value is null/invalid

    Examples:
        >>> safe_int(42)
        42
        >>> safe_int(None)
        0
        >>> safe_int(pd.NA)
        0
        >>> safe_int("123")
        123
        >>> safe_int(None, default=999)
        999
    """
    if pd.isna(value):
        return default
    return int(value)


def safe_float(value, default: float = 0.0) -> float:
    """
    Convert value to float, returning default if null or invalid.

    Handles pandas NA values gracefully by checking with pd.isna().

    Args:
        value: Value to convert (can be any type including pd.NA)
        default: Default value to return if conversion fails (default: 0.0)

    Returns:
        Float value or default if value is null/invalid

    Examples:
        >>> safe_float(3.14)
        3.14
        >>> safe_float(None)
        0.0
        >>> safe_float(pd.NA)
        0.0
        >>> safe_float("123.45")
        123.45
        >>> safe_float(None, default=999.9)
        999.9
    """
    if pd.isna(value):
        return default
    return float(value)


def safe_str(value, default: str = "") -> str:
    """
    Convert value to str, returning default if null or invalid.

    Handles pandas NA values gracefully by checking with pd.isna().

    Args:
        value: Value to convert (can be any type including pd.NA)
        default: Default value to return if conversion fails (default: "")

    Returns:
        String value or default if value is null/invalid

    Examples:
        >>> safe_str("hello")
        'hello'
        >>> safe_str(None)
        ''
        >>> safe_str(pd.NA)
        ''
        >>> safe_str(123)
        '123'
        >>> safe_str(None, default="N/A")
        'N/A'
    """
    if pd.isna(value):
        return default
    return str(value)
