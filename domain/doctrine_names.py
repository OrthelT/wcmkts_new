"""
Doctrine Display Names

Maps raw database doctrine names to user-friendly display names.
Source: friendly_name column in doctrine_fits table.

Usage:
    get_doctrine_display_name("SUBS - WC AHACs")  # -> "AHACs"
    get_doctrine_display_name("Unknown")           # -> "Unknown" (passthrough)
"""

import logging

logger = logging.getLogger(__name__)


def _load_friendly_names_from_db() -> dict[str, str]:
    """Load doctrine_name -> friendly_name mapping from doctrine_fits table.

    Returns a dict of {doctrine_name: friendly_name} for all rows
    where friendly_name is not NULL. Uses Streamlit caching internally.
    """
    try:
        import streamlit as st
        from config import DatabaseConfig

        @st.cache_data(ttl=600)
        def _cached_load(db_alias: str) -> dict[str, str]:
            db = DatabaseConfig(db_alias)
            query = (
                "SELECT DISTINCT doctrine_name, friendly_name "
                "FROM doctrine_fits "
                "WHERE friendly_name IS NOT NULL"
            )
            try:
                with db.engine.connect() as conn:
                    from sqlalchemy import text
                    rows = conn.execute(text(query)).fetchall()
                return {row[0]: row[1] for row in rows}
            except Exception as e:
                logger.warning(f"Failed to load friendly names from DB: {e}")
                return {}

        return _cached_load("wcmkt")

    except Exception as e:
        logger.debug(f"DB friendly names unavailable: {e}")
        return {}


def get_doctrine_display_name(raw_name: str) -> str:
    """Return user-friendly display name for a doctrine, or the raw name if unknown."""
    return _load_friendly_names_from_db().get(raw_name, raw_name)


# Backward compatibility for consumers importing the dict directly.
# At import time (before Streamlit is ready) this is empty;
# callers should prefer get_doctrine_display_name().
DOCTRINE_DISPLAY_NAMES: dict[str, str] = {}
