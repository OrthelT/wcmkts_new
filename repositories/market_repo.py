"""
Market Repository

Encapsulates all market data access: stats, orders, and history.
Cached query functions follow the repository pattern established in Phase 10.

Design Principles:
1. Single Responsibility - Only market data access, no business logic or UI
2. Cached Functions - Module-level @st.cache_data functions (Streamlit can't hash `self`)
3. Targeted Invalidation - invalidate_market_caches() clears only market caches
4. BaseRepository - Inherits read_df() with malformed-DB recovery for ad-hoc queries
"""

from typing import Optional
import logging
import time
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from sqlalchemy import text, bindparam

from config import DatabaseConfig
from logging_config import setup_logging
from repositories.base import BaseRepository

logger = setup_logging(__name__, log_file="market_repo.log")


# =============================================================================
# Implementation Functions (non-cached, for testability)
# =============================================================================

def _get_all_stats_impl(db_alias: str = "wcmkt") -> pd.DataFrame:
    """Fetch all rows from marketstats with malformed-DB recovery."""
    start = time.perf_counter()
    repo = BaseRepository(DatabaseConfig(db_alias), logger)
    df = repo.read_df("SELECT * FROM marketstats")
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    logger.info(f"TIME get_all_stats() = {elapsed} ms")
    return df.reset_index(drop=True)


def _get_all_orders_impl(db_alias: str = "wcmkt") -> pd.DataFrame:
    """Fetch all rows from marketorders with malformed-DB recovery."""
    start = time.perf_counter()
    repo = BaseRepository(DatabaseConfig(db_alias), logger)
    df = repo.read_df("SELECT * FROM marketorders")
    elapsed = round((time.perf_counter() - start) * 1000, 2)
    logger.info(f"TIME get_all_orders() = {elapsed} ms")
    return df.reset_index(drop=True)


def _get_all_history_impl(db_alias: str = "wcmkt") -> pd.DataFrame:
    """Fetch all rows from market_history with malformed-DB recovery."""
    repo = BaseRepository(DatabaseConfig(db_alias), logger)
    df = repo.read_df("SELECT * FROM market_history")
    return df.reset_index(drop=True)


def _get_history_by_type_impl(type_id: int, db_alias: str = "wcmkt") -> pd.DataFrame:
    """Fetch market history for a specific type_id."""
    db = DatabaseConfig(db_alias)
    query = text("""
        SELECT date, average, volume
        FROM market_history
        WHERE type_id = :type_id
        ORDER BY date DESC
    """)
    with db.engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"type_id": type_id})


def _get_history_by_type_ids_impl(type_ids: list, db_alias: str = "wcmkt") -> pd.DataFrame:
    """Fetch market history for multiple type_ids."""
    if not type_ids:
        return pd.DataFrame()
    db = DatabaseConfig(db_alias)
    query = text(
        "SELECT * FROM market_history WHERE type_id IN :type_ids"
    ).bindparams(bindparam("type_ids", expanding=True))
    with db.engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"type_ids": [int(tid) for tid in type_ids]})


def _get_30day_volume_metrics_impl(type_ids: list[int], db_alias: str = "wcmkt") -> pd.DataFrame:
    """Fetch 30-day volume totals and average daily volume from market_history."""
    if not type_ids:
        return pd.DataFrame(columns=["type_id", "volume_30d", "avg_volume_30d"])

    db = DatabaseConfig(db_alias)
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    query = text(
        """
        SELECT
            CAST(type_id AS INTEGER) AS type_id,
            COALESCE(SUM(volume), 0) AS volume_30d,
            COALESCE(SUM(volume), 0) / 30.0 AS avg_volume_30d
        FROM market_history
        WHERE CAST(type_id AS INTEGER) IN :type_ids
          AND date >= :cutoff
        GROUP BY CAST(type_id AS INTEGER)
        """
    ).bindparams(bindparam("type_ids", expanding=True))

    try:
        with db.engine.connect() as conn:
            df = pd.read_sql_query(
                query,
                conn,
                params={"type_ids": [int(tid) for tid in type_ids], "cutoff": cutoff},
            )
    except Exception as e:
        logger.error(f"Failed to fetch 30-day volume metrics: {e}")
        return pd.DataFrame(columns=["type_id", "volume_30d", "avg_volume_30d"])

    if df.empty:
        return pd.DataFrame(columns=["type_id", "volume_30d", "avg_volume_30d"])

    df["type_id"] = pd.to_numeric(df["type_id"], errors="coerce").astype("Int64")
    df["volume_30d"] = pd.to_numeric(df["volume_30d"], errors="coerce").fillna(0.0)
    df["avg_volume_30d"] = pd.to_numeric(df["avg_volume_30d"], errors="coerce").fillna(0.0)
    return df


def _get_category_type_ids_impl(category_name: str) -> list:
    """Fetch type_ids for a given SDE category name."""
    sde_db = DatabaseConfig("sde")
    query = text("""
        SELECT typeID as type_id
        FROM sdetypes
        WHERE categoryName = :category_name
    """)
    with sde_db.engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"category_name": category_name})
    if df.empty:
        return []
    return df["type_id"].tolist()


def _get_category_type_ids_by_id_impl(category_id: int) -> list:
    """Fetch type_ids for a given SDE category ID."""
    sde_db = DatabaseConfig("sde")
    query = text(
        """
        SELECT typeID as type_id
        FROM sdetypes
        WHERE categoryID = :category_id
        """
    )
    with sde_db.engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"category_id": category_id})
    if df.empty:
        return []
    return df["type_id"].tolist()


def _get_watchlist_type_ids_impl(db_alias: str = "wcmkt") -> list:
    """Fetch distinct type_ids from the watchlist table."""
    db = DatabaseConfig(db_alias)
    query = "SELECT DISTINCT type_id FROM watchlist"
    with db.engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df["type_id"].tolist()


def _get_market_type_ids_impl(db_alias: str = "wcmkt") -> list:
    """Fetch distinct type_ids from marketorders, merged with watchlist."""
    db = DatabaseConfig(db_alias)
    query = "SELECT DISTINCT type_id FROM marketorders"
    with db.engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    order_ids = df["type_id"].tolist()
    watchlist_ids = _get_watchlist_type_ids_impl(db_alias)
    return list(set(order_ids + watchlist_ids))


def _get_local_price_impl(type_id: int, db_alias: str = "wcmkt") -> Optional[float]:
    """Fetch the local market price for a type_id from marketstats."""
    db = DatabaseConfig(db_alias)
    query = text("SELECT price FROM marketstats WHERE type_id = :type_id")
    with db.engine.connect() as conn:
        df = pd.read_sql_query(query, conn, params={"type_id": type_id})
    if df.empty:
        return None
    try:
        return float(df["price"].iloc[0])
    except (IndexError, KeyError, ValueError):
        return None


def _get_sde_info_impl(type_ids: list) -> pd.DataFrame:
    """Fetch SDE info (name, group, category) for given type_ids."""
    if not type_ids:
        return pd.DataFrame()
    sde_db = DatabaseConfig("sde")
    query = text("""
        SELECT typeName as type_name, typeID as type_id, groupID as group_id,
               groupName as group_name, categoryID as category_id,
               categoryName as category_name
        FROM sdetypes
        WHERE typeID IN :type_ids
    """).bindparams(bindparam("type_ids", expanding=True))
    with sde_db.engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"type_ids": type_ids})


# =============================================================================
# Cached Wrappers (Streamlit cache layer)
# =============================================================================

@st.cache_data(ttl=600, show_spinner="Loading market stats...")
def _get_all_stats_cached(db_alias: str = "wcmkt") -> pd.DataFrame:
    return _get_all_stats_impl(db_alias)


@st.cache_data(ttl=1800, show_spinner="Loading market orders...")
def _get_all_orders_cached(db_alias: str = "wcmkt") -> pd.DataFrame:
    return _get_all_orders_impl(db_alias)


@st.cache_data(ttl=3600, show_spinner="Loading market history...")
def _get_all_history_cached(db_alias: str = "wcmkt") -> pd.DataFrame:
    return _get_all_history_impl(db_alias)


@st.cache_data(ttl=3600)
def _get_history_by_type_cached(type_id: int, db_alias: str = "wcmkt") -> pd.DataFrame:
    return _get_history_by_type_impl(type_id, db_alias)


@st.cache_data(ttl=1800)
def _get_history_by_type_ids_cached(type_ids: tuple, db_alias: str = "wcmkt") -> pd.DataFrame:
    return _get_history_by_type_ids_impl(list(type_ids), db_alias)


@st.cache_data(ttl=1800)
def _get_30day_volume_metrics_cached(type_ids: tuple, db_alias: str = "wcmkt") -> pd.DataFrame:
    return _get_30day_volume_metrics_impl(list(type_ids), db_alias)


@st.cache_data(ttl=3600)
def _get_category_type_ids_cached(category_name: str) -> list:
    return _get_category_type_ids_impl(category_name)


@st.cache_data(ttl=3600)
def _get_category_type_ids_by_id_cached(category_id: int) -> list:
    return _get_category_type_ids_by_id_impl(category_id)


@st.cache_data(ttl=600)
def _get_watchlist_type_ids_cached(db_alias: str = "wcmkt") -> list:
    return _get_watchlist_type_ids_impl(db_alias)


@st.cache_data(ttl=1800)
def _get_market_type_ids_cached(db_alias: str = "wcmkt") -> list:
    return _get_market_type_ids_impl(db_alias)


@st.cache_data(ttl=600)
def _get_local_price_cached(type_id: int, db_alias: str = "wcmkt") -> Optional[float]:
    return _get_local_price_impl(type_id, db_alias)


@st.cache_resource
def _get_sde_info_cached(type_ids: tuple) -> pd.DataFrame:
    return _get_sde_info_impl(list(type_ids))


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
    _get_history_by_type_ids_cached.clear()
    _get_30day_volume_metrics_cached.clear()
    _get_market_type_ids_cached.clear()
    _get_local_price_cached.clear()
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
        return _get_all_stats_cached(self.db.alias)

    def get_all_orders(self) -> pd.DataFrame:
        """Get all market orders (cached, TTL=1800s)."""
        return _get_all_orders_cached(self.db.alias)

    def get_all_history(self) -> pd.DataFrame:
        """Get all market history (cached, TTL=3600s)."""
        return _get_all_history_cached(self.db.alias)

    def get_history_by_type(self, type_id: int) -> pd.DataFrame:
        """Get market history for a specific type (cached, TTL=3600s)."""
        return _get_history_by_type_cached(type_id, self.db.alias)

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

    def get_local_price(self, type_id: int) -> Optional[float]:
        """Get local market price for a type (cached, TTL=600s).

        Direct query against marketstats for a single type_id.
        More efficient than get_price() when you don't need the full stats DataFrame.
        """
        return _get_local_price_cached(type_id, self.db.alias)

    def get_history_by_type_ids(self, type_ids: list) -> pd.DataFrame:
        """Get market history for multiple type_ids (cached, TTL=1800s)."""
        return _get_history_by_type_ids_cached(tuple(type_ids), self.db.alias)

    def get_30day_volume_metrics(self, type_ids: list[int]) -> pd.DataFrame:
        """Get 30-day total volume and average daily volume for type_ids (cached, TTL=1800s).

        The average is computed as total volume divided by 30 (a fixed window),
        not by the number of days with recorded history.
        """
        return _get_30day_volume_metrics_cached(tuple(type_ids), self.db.alias)

    def get_category_type_ids(
        self,
        category_name: Optional[str] = None,
        *,
        category_id: Optional[int] = None,
    ) -> list:
        """Get type_ids for an SDE category by ID or name (cached, TTL=3600s)."""
        if category_id is not None:
            return _get_category_type_ids_by_id_cached(category_id)
        if category_name is None:
            return []
        return _get_category_type_ids_cached(category_name)

    def get_watchlist_type_ids(self) -> list:
        """Get distinct type_ids from watchlist (cached, TTL=600s)."""
        return _get_watchlist_type_ids_cached(self.db.alias)

    def get_market_type_ids(self) -> list:
        """Get all type_ids on market + watchlist (cached, TTL=1800s)."""
        return _get_market_type_ids_cached(self.db.alias)

    def get_sde_info(self, type_ids: list = None) -> pd.DataFrame:
        """Get SDE info for type_ids. If None, uses market type_ids."""
        if not type_ids:
            type_ids = self.get_market_type_ids()
        return _get_sde_info_cached(tuple(type_ids))

    def get_update_time(self, local_update_status: Optional[dict] = None) -> Optional[str]:
        """Get formatted last update time string."""
        return get_update_time(local_update_status)


# =============================================================================
# Factory Function (Streamlit Integration)
# =============================================================================

def get_market_repository() -> MarketRepository:
    """
    Get or create a MarketRepository instance for the active market.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.
    """
    def _create() -> MarketRepository:
        from state.market_state import get_active_market
        db = DatabaseConfig(get_active_market().database_alias)
        return MarketRepository(db)

    try:
        from state import get_service
        from state.market_state import get_active_market_key
        return get_service(f"market_repository_{get_active_market_key()}", _create)
    except ImportError:
        logger.debug("state module unavailable, creating new MarketRepository instance")
        return _create()
