"""
Session State Utilities

Centralized utilities for Streamlit session state management.
These functions provide a clean interface for session state operations
and belong in the presentation layer.

Moved from utils.py to proper architectural location.
"""

import streamlit as st
from typing import TypeVar, Any, Optional

T = TypeVar('T')


def ss_get(key: str, default: T = None) -> Optional[T]:
    """Get value from session_state if exists and is not None, else return default.

    Args:
        key: The session state key to retrieve
        default: Value to return if key doesn't exist or is None

    Returns:
        The session state value if it exists and is not None, otherwise default
    """
    if key in st.session_state:
        val = st.session_state[key]
        if val is not None:
            return val
    return default


def ss_has(*keys: str) -> bool:
    """Check if all keys exist in session_state AND are not None.

    Args:
        *keys: One or more session state keys to check

    Returns:
        True if all keys exist and have non-None values, False otherwise
    """
    return all(
        key in st.session_state and st.session_state[key] is not None
        for key in keys
    )


def ss_init(defaults: dict[str, Any]) -> None:
    """Initialize multiple session_state keys with defaults if they don't exist.

    Args:
        defaults: Dictionary mapping keys to their default values
    """
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def ss_set(key: str, value: Any) -> None:
    """Set a value in session_state.

    Args:
        key: The session state key to set
        value: The value to store
    """
    st.session_state[key] = value


def ss_clear(*keys: str) -> None:
    """Clear specified keys from session_state.

    Args:
        *keys: One or more session state keys to clear.
               If no keys provided, does nothing (use st.session_state.clear() for full clear).
    """
    for key in keys:
        if key in st.session_state:
            del st.session_state[key]
