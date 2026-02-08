"""
Module Equivalents Service

Service layer for looking up equivalent modules and calculating
aggregated stock levels across interchangeable faction modules.

Design Principles:
1. Dependency Injection - Receives DatabaseConfig
2. Caching - Uses Streamlit caching for repeated lookups
3. Service Layer - Orchestrates business operations
"""

from dataclasses import dataclass
from typing import Optional
import logging
import pandas as pd
from sqlalchemy import text
import streamlit as st

from config import DatabaseConfig
from logging_config import setup_logging

logger = setup_logging(__name__, log_file="module_equivalents_service.log")


# =============================================================================
# Domain Models
# =============================================================================

@dataclass(frozen=True)
class EquivalentModule:
    """
    Represents an equivalent module with its stock information.

    Attributes:
        type_id: EVE type ID
        type_name: Module name
        stock: Current stock on market
        price: Current market price
    """
    type_id: int
    type_name: str
    stock: int = 0
    price: float = 0.0


@dataclass
class EquivalenceGroup:
    """
    Represents a group of equivalent modules.

    Attributes:
        group_id: Unique identifier for this equivalence group
        modules: List of equivalent modules
        total_stock: Combined stock across all modules
    """
    group_id: int
    modules: list[EquivalentModule]

    @property
    def total_stock(self) -> int:
        """Calculate combined stock across all equivalent modules."""
        return sum(m.stock for m in self.modules)

    @property
    def type_ids(self) -> list[int]:
        """Get all type IDs in this equivalence group."""
        return [m.type_id for m in self.modules]

    @property
    def primary_module(self) -> Optional[EquivalentModule]:
        """Get the first module (typically the primary/reference module)."""
        return self.modules[0] if self.modules else None


# =============================================================================
# Module Equivalents Service
# =============================================================================

class ModuleEquivalentsService:
    """
    Service for looking up equivalent modules and calculating aggregated stock.

    Provides methods for:
    - Finding equivalent modules for a given type_id
    - Calculating combined stock across equivalent modules
    - Checking if a module has equivalents

    Example:
        service = ModuleEquivalentsService.create_default()

        # Check if module has equivalents
        if service.has_equivalents(13984):
            # Get all equivalent type_ids
            equiv_ids = service.get_equivalent_type_ids(13984)
            # Get aggregated stock
            total_stock = service.get_aggregated_stock([13984])[13984]
    """

    def __init__(
        self,
        mkt_db: DatabaseConfig,
        logger_instance: Optional[logging.Logger] = None
    ):
        """
        Initialize the Module Equivalents Service.

        Args:
            mkt_db: DatabaseConfig for market database (wcmkt)
            logger_instance: Optional logger instance
        """
        self._mkt_db = mkt_db
        self._logger = logger_instance or logger

    @classmethod
    def create_default(cls) -> "ModuleEquivalentsService":
        """
        Factory method to create service with default configuration.
        """
        mkt_db = DatabaseConfig("wcmkt")
        return cls(mkt_db)

    # -------------------------------------------------------------------------
    # Core Lookup Methods
    # -------------------------------------------------------------------------

    def get_equivalent_type_ids(self, type_id: int) -> list[int]:
        """
        Get all type_ids equivalent to the given type_id (including itself).

        Args:
            type_id: The EVE type ID to look up

        Returns:
            List of all equivalent type_ids, or [type_id] if no equivalents
        """
        return _get_equivalent_type_ids_cached(type_id, self._mkt_db.engine)

    def get_equivalence_group(self, type_id: int) -> Optional[EquivalenceGroup]:
        """
        Get the full equivalence group for a type_id with stock information.

        Args:
            type_id: The EVE type ID to look up

        Returns:
            EquivalenceGroup with all modules and stock, or None if not found
        """
        return _get_equivalence_group_cached(type_id, self._mkt_db.engine)

    def has_equivalents(self, type_id: int) -> bool:
        """
        Check if a type_id has equivalent modules.

        Args:
            type_id: The EVE type ID to check

        Returns:
            True if the module has equivalents (is in an equivalence group)
        """
        equiv_ids = self.get_equivalent_type_ids(type_id)
        return len(equiv_ids) > 1

    def get_aggregated_stock(self, type_ids: list[int]) -> dict[int, int]:
        """
        Get aggregated stock for each type_id across its equivalents.

        For each type_id, if it has equivalents, returns the sum of stock
        across all equivalent modules. If no equivalents, returns the
        individual module's stock.

        Args:
            type_ids: List of type IDs to look up

        Returns:
            Dict mapping type_id to aggregated stock
        """
        result = {}

        for type_id in type_ids:
            group = self.get_equivalence_group(type_id)
            if group:
                result[type_id] = group.total_stock
            else:
                # No equivalents, get individual stock
                stock = self._get_single_module_stock(type_id)
                result[type_id] = stock

        return result

    def _get_single_module_stock(self, type_id: int) -> int:
        """Get stock for a single module without equivalents."""
        query = text("""
            SELECT total_volume_remain
            FROM marketstats
            WHERE type_id = :type_id
        """)

        try:
            with self._mkt_db.engine.connect() as conn:
                result = conn.execute(query, {"type_id": type_id}).fetchone()
                if result and result[0]:
                    return int(result[0])
                return 0
        except Exception as e:
            self._logger.error(f"Failed to get stock for type_id {type_id}: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Batch Operations
    # -------------------------------------------------------------------------

    def get_all_equivalence_groups(self) -> list[EquivalenceGroup]:
        """
        Get all equivalence groups.

        Returns:
            List of all EquivalenceGroup objects
        """
        return _get_all_equivalence_groups_cached(self._mkt_db.engine)

    def get_type_ids_with_equivalents(self) -> set[int]:
        """
        Get all type_ids that have equivalents.

        Returns:
            Set of type_ids that are part of an equivalence group
        """
        groups = self.get_all_equivalence_groups()
        type_ids = set()
        for group in groups:
            type_ids.update(group.type_ids)
        return type_ids


# =============================================================================
# Cached Query Functions
# =============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def _get_equivalent_type_ids_cached(type_id: int, _engine) -> list[int]:
    """
    Cached lookup of equivalent type_ids.

    Args:
        type_id: The EVE type ID to look up
        _engine: SQLAlchemy engine (prefixed with _ to exclude from cache key)

    Returns:
        List of all equivalent type_ids
    """
    query = text("""
        SELECT me2.type_id
        FROM module_equivalents me1
        JOIN module_equivalents me2 ON me1.group_id = me2.group_id
        WHERE me1.type_id = :type_id
    """)

    try:
        with _engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"type_id": type_id})

        if df.empty:
            return [type_id]  # Return self if not in any group

        return df['type_id'].tolist()

    except Exception as e:
        logger.error(f"Failed to get equivalent type_ids for {type_id}: {e}")
        return [type_id]


@st.cache_data(ttl=600, show_spinner=False)
def _get_equivalence_group_cached(type_id: int, _engine) -> Optional[EquivalenceGroup]:
    """
    Cached lookup of equivalence group with stock information.

    Args:
        type_id: The EVE type ID to look up
        _engine: SQLAlchemy engine

    Returns:
        EquivalenceGroup or None if not found
    """
    # First get the group_id and all members
    query = text("""
        SELECT me.group_id, me.type_id, me.type_name,
               COALESCE(ms.total_volume_remain, 0) as stock,
               COALESCE(ms.price, 0) as price
        FROM module_equivalents me
        LEFT JOIN marketstats ms ON me.type_id = ms.type_id
        WHERE me.group_id = (
            SELECT group_id FROM module_equivalents WHERE type_id = :type_id
        )
    """)

    try:
        with _engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"type_id": type_id})

        if df.empty:
            return None

        group_id = int(df.iloc[0]['group_id'])
        modules = [
            EquivalentModule(
                type_id=int(row['type_id']),
                type_name=row['type_name'],
                stock=int(row['stock']) if pd.notna(row['stock']) else 0,
                price=float(row['price']) if pd.notna(row['price']) else 0.0
            )
            for _, row in df.iterrows()
        ]

        return EquivalenceGroup(group_id=group_id, modules=modules)

    except Exception as e:
        logger.error(f"Failed to get equivalence group for {type_id}: {e}")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _get_all_equivalence_groups_cached(_engine) -> list[EquivalenceGroup]:
    """
    Cached lookup of all equivalence groups.

    Args:
        _engine: SQLAlchemy engine

    Returns:
        List of all EquivalenceGroup objects
    """
    query = text("""
        SELECT me.group_id, me.type_id, me.type_name,
               COALESCE(ms.total_volume_remain, 0) as stock,
               COALESCE(ms.price, 0) as price
        FROM module_equivalents me
        LEFT JOIN marketstats ms ON me.type_id = ms.type_id
        ORDER BY me.group_id, me.type_name
    """)

    try:
        with _engine.connect() as conn:
            df = pd.read_sql_query(query, conn)

        if df.empty:
            return []

        groups = {}
        for _, row in df.iterrows():
            group_id = int(row['group_id'])
            if group_id not in groups:
                groups[group_id] = []

            groups[group_id].append(EquivalentModule(
                type_id=int(row['type_id']),
                type_name=row['type_name'],
                stock=int(row['stock']) if pd.notna(row['stock']) else 0,
                price=float(row['price']) if pd.notna(row['price']) else 0.0
            ))

        return [
            EquivalenceGroup(group_id=gid, modules=mods)
            for gid, mods in groups.items()
        ]

    except Exception as e:
        logger.error(f"Failed to get all equivalence groups: {e}")
        return []


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_module_equivalents_service() -> ModuleEquivalentsService:
    """
    Get or create a ModuleEquivalentsService instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.

    Returns:
        ModuleEquivalentsService instance
    """
    try:
        from state import get_service
        return get_service('module_equivalents_service', ModuleEquivalentsService.create_default)
    except ImportError:
        logger.debug("state module unavailable, creating new ModuleEquivalentsService instance")
        return ModuleEquivalentsService.create_default()
