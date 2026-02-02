"""
Market Repository

Encapsulates all market data access: stats, orders, and history.
Extracts cached query functions from db_handler.py into the repository pattern.

Design Principles:
1. Single Responsibility - Only market data access, no business logic or UI
2. Cached Functions - Module-level @st.cache_data functions (Streamlit can't hash `self`)
3. Targeted Invalidation - invalidate_market_caches() clears only market caches
4. BaseRepository - Inherits read_df() with malformed-DB recovery for ad-hoc queries
"""

from typing import Optional
import logging
import time

import pandas as pd
import streamlit as st
from sqlalchemy import text

from config import DatabaseConfig
from logging_config import setup_logging
from repositories.base import BaseRepository

logger = setup_logging(__name__, log_file="market_repo.log")


# =============================================================================
# Implementation Functions (non-cached, for testability)
# =============================================================================

def _get_all_stats_impl() -> pd.DataFrame:
    """Fetch all rows from marketstats with malformed-DB recovery."""
    db = DatabaseConfig("wcmkt")
    start = time.perf_counter()
    query = "SELECT * FROM marketstats"

    def _read_local():
        with db.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    try:
        df = _read_local()
    except Exception as e:
        msg = str(e).lower()
        if "malform" in msg or "database disk image is malformed" in msg or "no such table" in msg:
            logger.error(f"DB error during stats read ('{msg}'); syncing and retrying...")
            try:
                db.sync()
                df = _read_local()
            except Exception:
                logger.error("Retry after sync failed; falling back to remote read.")
                with db.remote_engine.connect() as conn:
                    df = pd.read_sql_query(query, conn)
        else:
            raise

    elapsed = round((time.perf_counter() - start) * 1000, 2)
    logger.info(f"TIME get_all_stats() = {elapsed} ms")
    return df.reset_index(drop=True)


def _get_all_orders_impl() -> pd.DataFrame:
    """Fetch all rows from marketorders with malformed-DB recovery."""
    db = DatabaseConfig("wcmkt")
    start = time.perf_counter()
    query = "SELECT * FROM marketorders"

    def _read_local():
        with db.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    try:
        df = _read_local()
    except Exception as e:
        msg = str(e).lower()
        if "malform" in msg or "database disk image is malformed" in msg or "no such table" in msg:
            logger.error(f"DB error during orders read ('{msg}'); syncing and retrying...")
            try:
                db.sync()
                df = _read_local()
            except Exception as e2:
                logger.error(f"Retry after sync failed: {e2}. Falling back to remote read.")
                with db.remote_engine.connect() as conn:
                    df = pd.read_sql_query(query, conn)
        else:
            raise

    elapsed = round((time.perf_counter() - start) * 1000, 2)
    logger.info(f"TIME get_all_orders() = {elapsed} ms")
    return df.reset_index(drop=True)


def _get_all_history_impl() -> pd.DataFrame:
    """Fetch all rows from market_history with malformed-DB recovery."""
    db = DatabaseConfig("wcmkt")
    query = "SELECT * FROM market_history"

    def _read_local():
        with db.engine.connect() as conn:
            return pd.read_sql_query(query, conn)

    try:
        df = _read_local()
    except Exception as e:
        logger.error(f"Failed to get market history: {e}")
        try:
            db.sync()
            df = _read_local()
        except Exception as e2:
            logger.error(f"Failed after sync: {e2}. Falling back to remote.")
            with db.remote_engine.connect() as conn:
                df = pd.read_sql_query(query, conn)

    return df.reset_index(drop=True)


def _get_history_by_type_impl(type_id: int) -> pd.DataFrame:
    """Fetch market history for a specific type_id."""
    db = DatabaseConfig("wcmkt")
    query = text("""
        SELECT date, average, volume
        FROM market_history
        WHERE type_id = :type_id
        ORDER BY date DESC
    """)
    with db.engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"type_id": type_id})


# =============================================================================
# Cached Wrappers (Streamlit cache layer)
# =============================================================================

@st.cache_data(ttl=600, show_spinner="Loading market stats...")
def _get_all_stats_cached() -> pd.DataFrame:
    return _get_all_stats_impl()


@st.cache_data(ttl=1800, show_spinner="Loading market orders...")
def _get_all_orders_cached() -> pd.DataFrame:
    return _get_all_orders_impl()


@st.cache_data(ttl=3600, show_spinner="Loading market history...")
def _get_all_history_cached() -> pd.DataFrame:
    return _get_all_history_impl()


@st.cache_data(ttl=3600)
def _get_history_by_type_cached(type_id: int) -> pd.DataFrame:
    return _get_history_by_type_impl(type_id)


# =============================================================================
# Cache Invalidation
# =============================================================================

def invalidate_market_caches():
    """Clear only market-data caches, preserving SDE, settings, and other caches.

    Call this after a database sync instead of the global st.cache_data.clear().
    """
    _get_all_stats_cached.clear()
    _get_all_orders_cached.clear()
    _get_all_history_cached.clear()
    _get_history_by_type_cached.clear()
    logger.info("Market caches invalidated")


# =============================================================================
# Utility Functions
# =============================================================================

def get_update_time(local_update_status: Optional[dict] = None) -> Optional[str]:
    """Return last local update time as formatted string.

    Args:
        local_update_status: Optional dict with 'updated' key (datetime).
                            If None, reads from session state.

    Returns:
        Formatted timestamp string or None if unavailable.
    """
    if local_update_status is None:
        try:
            from state import ss_get
            local_update_status = ss_get("local_update_status")
        except ImportError:
            logger.debug("state module unavailable, cannot retrieve local_update_status")
            return None

    if isinstance(local_update_status, dict) and local_update_status.get("updated"):
        try:
            return local_update_status["updated"].strftime("%Y-%m-%d | %H:%M UTC")
        except Exception as e:
            logger.error(f"Failed to format local_update_status.updated: {e}")
    return None


# =============================================================================
# MarketRepository Class
# =============================================================================

class MarketRepository(BaseRepository):
    """
    Repository for market data access.

    Provides cached access to marketstats, marketorders, and market_history.
    Inherits read_df() from BaseRepository for ad-hoc queries with
    malformed-DB recovery.

    Methods delegate to module-level cached functions so Streamlit
    doesn't need to hash the repository instance.
    """

    def __init__(self, db: DatabaseConfig, logger_instance: Optional[logging.Logger] = None):
        super().__init__(db, logger_instance)

    def get_all_stats(self) -> pd.DataFrame:
        """Get all market statistics (cached, TTL=600s)."""
        return _get_all_stats_cached()

    def get_all_orders(self) -> pd.DataFrame:
        """Get all market orders (cached, TTL=1800s)."""
        return _get_all_orders_cached()

    def get_all_history(self) -> pd.DataFrame:
        """Get all market history (cached, TTL=3600s)."""
        return _get_all_history_cached()

    def get_history_by_type(self, type_id: int) -> pd.DataFrame:
        """Get market history for a specific type (cached, TTL=3600s)."""
        return _get_history_by_type_cached(type_id)

    def get_price(self, type_id: int) -> Optional[float]:
        """Get the current sell price for a type from marketstats."""
        stats = self.get_all_stats()
        row = stats[stats["type_id"] == type_id]
        if row.empty:
            return None
        try:
            return float(row["price"].iloc[0])
        except (IndexError, KeyError, ValueError):
            return None

    def get_update_time(self, local_update_status: Optional[dict] = None) -> Optional[str]:
        """Get formatted last update time string."""
        return get_update_time(local_update_status)


# =============================================================================
# Factory Function (Streamlit Integration)
# =============================================================================

def get_market_repository() -> MarketRepository:
    """
    Get or create a MarketRepository instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.
    """
    def _create() -> MarketRepository:
        db = DatabaseConfig("wcmkt")
        return MarketRepository(db)

    try:
        from state import get_service
        return get_service("market_repository", _create)
    except ImportError:
        logger.debug("state module unavailable, creating new MarketRepository instance")
        return _create()
