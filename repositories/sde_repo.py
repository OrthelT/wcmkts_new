"""
SDE Repository

Encapsulates all Static Data Export (SDE) database access: type lookups,
group/category queries, and table exports.

Absorbs functions from:
- type_info.py: get_type_name(), get_type_id_from_sde()
- db_handler.py: get_groups_for_category(), get_types_for_group(), extract_sde_info()

Design:
- _impl() functions take engine param for testability
- @st.cache_resource cached wrappers (SDE data is immutable at runtime)
- Module-level get_type_name() convenience function for models.py import
"""

import logging
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

from config import DatabaseConfig
from logging_config import setup_logging
from repositories.base import BaseRepository

logger = setup_logging(__name__, log_file="sde_repo.log")

# Allowlist of valid SDE table names for get_sde_table (prevents SQL injection)
VALID_SDE_TABLES = frozenset({
    "inv_info",
    "invTypes",
    "invGroups",
    "invCategories",
    "invMetaTypes",
    "invMetaGroups",
    "sdetypes",
    "industryActivity",
    "industryActivityMaterials",
    "industryActivityProducts",
    "industryActivitySkills",
    "industryBlueprints",
})


# =============================================================================
# Implementation Functions (non-cached, for testability)
# =============================================================================

def _get_type_name_impl(engine, type_id: int) -> Optional[str]:
    """Look up a type name by ID from invTypes."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT typeName FROM invTypes WHERE typeID = :type_id"),
            {"type_id": type_id},
        )
        row = result.fetchone()
        return row[0] if row is not None else None


def _get_type_id_impl(engine, type_name: str) -> Optional[int]:
    """Look up a type ID by name from invTypes."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT typeID FROM invTypes WHERE typeName = :type_name"),
            {"type_name": type_name},
        )
        row = result.fetchone()
        return row[0] if row is not None else None


def _get_groups_for_category_impl(engine, category_id: int) -> pd.DataFrame:
    """Fetch groups for a given category ID.

    Special cases:
    - category_id 17: reads from CSV (build commodity groups)
    - category_id 4: filters to group 1136 only
    """
    if category_id == 17:
        return pd.read_csv("csvfiles/build_commodity_groups.csv")

    if category_id == 4:
        query = text(
            "SELECT DISTINCT groupID, groupName FROM invGroups "
            "WHERE categoryID = :category_id AND groupID = 1136"
        )
    else:
        query = text(
            "SELECT DISTINCT groupID, groupName FROM invGroups "
            "WHERE categoryID = :category_id"
        )

    with engine.connect() as conn:
        return pd.read_sql_query(query, conn, params={"category_id": category_id})


def _get_types_for_group_impl(engine, remote_engine, group_id: int) -> pd.DataFrame:
    """Fetch types for a group ID with malformed-DB fallback to remote.

    Joins invTypes with industryActivityProducts to find manufacturable items.
    Special case: group 332 filters to R.A.M./R.Db items only.
    """
    query = text("""
        SELECT DISTINCT t.typeID, t.typeName
        FROM invTypes t
        JOIN industryActivityProducts iap ON t.typeID = iap.productTypeID
        WHERE t.groupID = :group_id
        AND iap.activityID = 1
        ORDER BY t.typeName
    """)

    def _run_local():
        with engine.connect() as conn:
            return pd.read_sql_query(query, conn, params={"group_id": group_id})

    def _run_remote():
        with remote_engine.connect() as conn:
            return pd.read_sql_query(query, conn, params={"group_id": group_id})

    try:
        df = _run_local()
    except Exception as e:
        msg = str(e).lower()
        logger.error(f"Error fetching types for group {group_id}: {e}")
        if "no such table" in msg or "malform" in msg:
            logger.warning(f"Falling back to remote SDE read due to: {msg}")
            try:
                df = _run_remote()
            except Exception as e_remote:
                logger.error(f"Remote fallback also failed: {e_remote}")
                return pd.DataFrame(columns=["typeID", "typeName"])
        else:
            return pd.DataFrame(columns=["typeID", "typeName"])

    if group_id == 332 and not df.empty:
        df = df[df["typeName"].str.contains("R.A.M.") | df["typeName"].str.contains("R.Db")]
        df = df.reset_index(drop=True)

    return df


def _get_sde_table_impl(engine, table_name: str) -> pd.DataFrame:
    """Fetch an entire SDE table by name.

    Validates table_name against VALID_SDE_TABLES allowlist to prevent
    SQL injection (table names cannot be parameterized in SQL).
    """
    if table_name not in VALID_SDE_TABLES:
        raise ValueError(
            f"Invalid SDE table name: {table_name!r}. "
            f"Valid tables: {sorted(VALID_SDE_TABLES)}"
        )

    with engine.connect() as conn:
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    return df.reset_index(drop=True)


def _get_tech2_type_ids_impl(engine) -> list[int]:
    """Fetch type IDs for Tech 2 items (metaGroupID = 2)."""
    with engine.connect() as conn:
        df = pd.read_sql_query(
            "SELECT typeID FROM sdeTypes WHERE metaGroupID = 2", conn
        )
    return df["typeID"].tolist()


def _get_faction_type_ids_impl(engine) -> set[int]:
    """Fetch type IDs for Faction items (metaGroupID = 4)."""
    with engine.connect() as conn:
        df = pd.read_sql_query(
            "SELECT typeID FROM sdeTypes WHERE metaGroupID = 4", conn
        )
    return set(df["typeID"].tolist())


# =============================================================================
# Cached Wrappers (SDE data is immutable at runtime - no TTL needed)
# =============================================================================

@st.cache_resource
def _get_type_name_cached(_url: str, type_id: int) -> Optional[str]:
    db = DatabaseConfig("sde")
    return _get_type_name_impl(db.engine, type_id)


@st.cache_resource
def _get_type_id_cached(_url: str, type_name: str) -> Optional[int]:
    db = DatabaseConfig("sde")
    return _get_type_id_impl(db.engine, type_name)


@st.cache_resource
def _get_groups_for_category_cached(_url: str, category_id: int) -> pd.DataFrame:
    db = DatabaseConfig("sde")
    return _get_groups_for_category_impl(db.engine, category_id)


@st.cache_resource
def _get_types_for_group_cached(_url: str, group_id: int) -> pd.DataFrame:
    db = DatabaseConfig("sde")
    return _get_types_for_group_impl(db.engine, db.remote_engine, group_id)


@st.cache_resource
def _get_sde_table_cached(_url: str, table_name: str) -> pd.DataFrame:
    db = DatabaseConfig("sde")
    return _get_sde_table_impl(db.engine, table_name)


@st.cache_resource
def _get_tech2_type_ids_cached(_url: str) -> list[int]:
    db = DatabaseConfig("sde")
    return _get_tech2_type_ids_impl(db.engine)


@st.cache_resource
def _get_faction_type_ids_cached(_url: str) -> set[int]:
    db = DatabaseConfig("sde")
    return _get_faction_type_ids_impl(db.engine)


# =============================================================================
# Module-level convenience function (for models.py backward compat)
# =============================================================================

def get_type_name(type_id: int) -> Optional[str]:
    """Look up a type name by ID. Used by models.py ORM event listeners.

    This is a module-level convenience so models.py can do:
        from repositories.sde_repo import get_type_name
    without going through the class.
    """
    try:
        db = DatabaseConfig("sde")
        return _get_type_name_impl(db.engine, type_id)
    except Exception as e:
        logger.error(f"Error getting type name for type_id={type_id}: {e}")
        return None


# =============================================================================
# SDERepository Class
# =============================================================================

class SDERepository(BaseRepository):
    """Repository for SDE (Static Data Export) database access.

    Provides cached lookups for type names/IDs, group/category queries,
    and full table exports. SDE data is immutable at runtime so all caches
    use @st.cache_resource with no TTL.
    """

    def __init__(self, db: DatabaseConfig, logger_instance: Optional[logging.Logger] = None):
        super().__init__(db, logger_instance)
        self._url = getattr(db, "url", "sde")

    def get_type_name(self, type_id: int) -> Optional[str]:
        """Get type name by ID (cached)."""
        return _get_type_name_cached(self._url, type_id)

    def get_type_id(self, type_name: str) -> Optional[int]:
        """Get type ID by name (cached)."""
        return _get_type_id_cached(self._url, type_name)

    def get_groups_for_category(self, category_id: int) -> pd.DataFrame:
        """Get groups for a category ID (cached).

        Returns DataFrame with columns: groupID, groupName.
        Category 17 reads from CSV. Category 4 filters to group 1136.
        """
        return _get_groups_for_category_cached(self._url, category_id)

    def get_types_for_group(self, group_id: int) -> pd.DataFrame:
        """Get types for a group ID (cached).

        Returns DataFrame with columns: typeID, typeName.
        Joins with industryActivityProducts to find manufacturable items.
        Group 332 filters to R.A.M./R.Db items.
        """
        return _get_types_for_group_cached(self._url, group_id)

    def get_sde_table(self, table_name: str) -> pd.DataFrame:
        """Get full SDE table by name (cached).

        Validates table_name against allowlist to prevent SQL injection.
        """
        return _get_sde_table_cached(self._url, table_name)

    def get_tech2_type_ids(self) -> list[int]:
        """Get all Tech 2 type IDs (cached)."""
        return _get_tech2_type_ids_cached(self._url)

    def get_faction_type_ids(self) -> set[int]:
        """Get all Faction type IDs (metaGroupID=4, cached)."""
        return _get_faction_type_ids_cached(self._url)


# =============================================================================
# Factory Function
# =============================================================================

def get_sde_repository() -> SDERepository:
    """Get or create an SDERepository instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.
    """
    def _create() -> SDERepository:
        db = DatabaseConfig("sde")
        return SDERepository(db)

    try:
        from state import get_service
        return get_service("sde_repository", _create)
    except ImportError:
        logger.debug("state module unavailable, creating new SDERepository instance")
        return _create()
