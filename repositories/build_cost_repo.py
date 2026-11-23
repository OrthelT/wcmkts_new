"""
Build Cost Repository

Encapsulates all build cost database access: structures, rigs, industry indices.
Extracts DB functions from pages/build_costs.py into the repository pattern.
"""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, text
from sqlalchemy.exc import OperationalError

from config import DatabaseConfig
from logging_config import setup_logging
from repositories.base import BaseRepository

logger = setup_logging(__name__, log_file="build_cost_repo.log")


# =============================================================================
# Constants
# =============================================================================

INVALID_RIG_IDS = [46640, 46641, 46496, 46497, 46634]

# structures columns flagging an online Structure Engineering Service Module.
SERVICE_MODULE_FLAGS = (
    "has_manufacturing_plant",
    "has_capital_shipyard",
    "has_supercapital_shipyard",
)

# =============================================================================
# Local-only ESI cache (industry_index)
#
# industry_index is a per-viewer ESI cache, refetched on expiry — it is not
# shared market data. Keeping it in buildcost.db meant to_sql(if_exists=
# "replace") DROPped/CREATEd the table on every viewer's page load, and pyturso
# replays DDL from sqlite_schema text on push, putting that churn into the CDC
# queue of the shared, sync-managed replica. It now lives in its own
# local-only SQLite file that is never synced, mirroring the backend's
# cli_cache.db pattern.
# =============================================================================

_CACHE_DB = Path(__file__).resolve().parents[1] / "streamlit_cache.db"


@lru_cache(maxsize=1)
def _cache_engine():
    """Local-only SQLite engine for per-viewer ESI caches (industry_index)."""
    from sqlalchemy import create_engine

    return create_engine(f"sqlite:///{_CACHE_DB}")


def _read_cache_df(query, params: Optional[dict] = None) -> pd.DataFrame:
    """Read from the local ESI cache DB.

    Returns an empty DataFrame on a clean cache miss (the table has not been
    created yet) instead of raising. Deliberately bypasses BaseRepository/
    read_df: that recovery ladder syncs the shared replica on a bad read,
    which is the wrong policy for a disposable local cache.
    """
    try:
        with _cache_engine().connect() as conn:
            return pd.read_sql_query(query, conn, params=params)
    except (OperationalError, pd.errors.DatabaseError) as e:
        if "no such table" in str(e).lower():
            return pd.DataFrame()
        raise


# =============================================================================
# Implementation Functions (non-cached, for testability)
#
# All reads go through BaseRepository.read_df() so a malformed/mid-bootstrap
# local replica self-heals (sync + retry, then backup restore) instead of
# raising "no such table" into the page. The exception is industry_index,
# which lives in the local-only cache DB above and reads via _read_cache_df().
# =============================================================================

def _build_cost_reader() -> BaseRepository:
    """Plain BaseRepository for read_df access (recovery ladder included)."""
    return BaseRepository(DatabaseConfig("build_cost"), logger)


def _get_structure_rigs_impl(repo: BaseRepository) -> pd.DataFrame:
    """Fetch fitted rigs, one row per (structure, rig), excluding INVALID_RIG_IDS.

    Columns: structure_id, structure, rig_type_id, rig_name.
    """
    query = text(
        """
        SELECT sr.structure_id, s.structure, sr.rig_type_id, r.type_name AS rig_name
        FROM structure_rigs sr
        JOIN structures s ON s.structure_id = sr.structure_id
        JOIN rigs r ON r.type_id = sr.rig_type_id
        WHERE sr.rig_type_id NOT IN :invalid
        ORDER BY s.structure, r.type_name
        """
    ).bindparams(bindparam("invalid", expanding=True))
    return repo.read_df(query, params={"invalid": INVALID_RIG_IDS})


def _get_manufacturing_cost_index_impl(system_id: int) -> float:
    """Get the manufacturing cost index for a solar system.

    Reads from the local ESI cache DB (industry_index), not the shared
    buildcost replica.
    """
    df = _read_cache_df(
        text("SELECT manufacturing FROM industry_index WHERE solar_system_id = :sid"),
        params={"sid": system_id},
    )
    if df.empty or pd.isna(df["manufacturing"].iloc[0]):
        raise ValueError(f"No manufacturing cost index found for system {system_id}")
    return float(df["manufacturing"].iloc[0])


def _get_all_structures_impl(
    repo: BaseRepository, module_flags: tuple[str, ...], include_closed: bool
) -> pd.DataFrame:
    """Fetch structures with any of ``module_flags`` set.

    Closed structures (``is_open = 0``) are left out unless ``include_closed``.
    Returns a DataFrame (picklable for st.cache_data); the repository method
    converts rows to attribute-access tuples for consumers.
    """
    unknown = set(module_flags) - set(SERVICE_MODULE_FLAGS)
    if not module_flags or unknown:
        raise ValueError(f"module_flags must be from {SERVICE_MODULE_FLAGS}, got {module_flags}")
    # Column names come from the whitelist above, so formatting them is safe.
    where = "(" + " OR ".join(f"{flag} = 1" for flag in module_flags) + ")"
    if not include_closed:
        where += " AND is_open = 1"
    return repo.read_df(text(f"SELECT * FROM structures WHERE {where} ORDER BY structure"))


def _write_industry_index_impl(df: pd.DataFrame) -> None:
    """Write industry index DataFrame to the local ESI cache DB.

    Deliberately not the shared buildcost replica: to_sql(if_exists=
    "replace") emits DROP/CREATE DDL, and pyturso replays DDL from
    sqlite_schema text on push.
    """
    with _cache_engine().begin() as conn:
        df.to_sql("industry_index", conn, if_exists="replace", index=False)


def _get_builder_cost_catalog_impl() -> pd.DataFrame:
    """Fetch all rows from buildcost.db.builder_costs."""
    repo = _build_cost_reader()
    query = text(
        """
        SELECT
            type_id,
            total_cost_per_unit,
            time_per_unit,
            me,
            runs,
            fetched_at
        FROM builder_costs
        ORDER BY type_id
        """
    )
    return repo.read_df(query).reset_index(drop=True)


# =============================================================================
# Cached Wrappers (Streamlit cache layer)
# =============================================================================

@st.cache_data(ttl=3600)
def _get_structure_rigs_cached(_url: str) -> pd.DataFrame:
    return _get_structure_rigs_impl(_build_cost_reader())


@st.cache_data(ttl=3600)
def _get_manufacturing_cost_index_cached(_url: str, system_id: int) -> float:
    return _get_manufacturing_cost_index_impl(system_id)


@st.cache_data(ttl=3600)
def _get_all_structures_cached(
    _url: str, module_flags: tuple[str, ...], include_closed: bool
) -> pd.DataFrame:
    return _get_all_structures_impl(_build_cost_reader(), module_flags, include_closed)


# Background refresh: TTL expiry never brings new data, and
# invalidate_build_cost_caches() clears this after a build_cost sync.
@st.cache_data(ttl=600, show_spinner="Loading builder cost catalog...", refresh_mode="background")
def _get_builder_cost_catalog_cached(_url: str) -> pd.DataFrame:
    return _get_builder_cost_catalog_impl()


# =============================================================================
# Cache Invalidation
# =============================================================================

def invalidate_build_cost_caches():
    """Clear only build cost caches."""
    _get_structure_rigs_cached.clear()
    _get_manufacturing_cost_index_cached.clear()
    _get_all_structures_cached.clear()
    _get_builder_cost_catalog_cached.clear()
    logger.info("Build cost caches invalidated")


# =============================================================================
# BuildCostRepository Class
# =============================================================================

class BuildCostRepository(BaseRepository):
    """Repository for build cost database access.

    Provides cached access to structures, rigs, and industry indices.
    Inherits read_df() from BaseRepository for ad-hoc queries.
    """

    def __init__(self, db: DatabaseConfig, logger_instance: Optional[logging.Logger] = None):
        super().__init__(db, logger_instance)
        self._cache_key = db.url

    def get_structure_rigs(self) -> dict[str, list[str]]:
        """Get rig names per structure name, cached TTL=3600s.

        Structures with no rigs are absent from the result.
        """
        df = _get_structure_rigs_cached(self._cache_key)
        return df.groupby("structure")["rig_name"].apply(list).to_dict()

    def get_structure_rig_ids(self) -> dict[int, list[int]]:
        """Get rig type_ids per structure_id, cached TTL=3600s.

        Structures with no rigs are absent from the result.
        """
        df = _get_structure_rigs_cached(self._cache_key)
        return {
            int(sid): [int(r) for r in rigs]
            for sid, rigs in df.groupby("structure_id")["rig_type_id"]
        }

    def get_manufacturing_cost_index(self, system_id: int) -> float:
        """Get manufacturing cost index for a solar system, cached TTL=3600s."""
        return _get_manufacturing_cost_index_cached(self._cache_key, system_id)

    def get_all_structures(
        self, module_flags: tuple[str, ...], include_closed: bool = False
    ):
        """Get structures with any of ``module_flags`` set, cached TTL=3600s.

        Closed structures are included only when ``include_closed`` is True.

        Returns attribute-access rows (structure.structure_id, structure.system_id).
        """
        df = _get_all_structures_cached(self._cache_key, tuple(module_flags), include_closed)
        return list(df.itertuples(index=False))

    def write_industry_index(self, df: pd.DataFrame) -> None:
        """Write industry index DataFrame to the local ESI cache DB."""
        _write_industry_index_impl(df)

    def get_builder_cost_catalog(self) -> pd.DataFrame:
        """Get the synced builder-cost catalog (cached, TTL=600s)."""
        return _get_builder_cost_catalog_cached(self._cache_key)


# =============================================================================
# Factory Function (Streamlit Integration)
# =============================================================================

def get_build_cost_repository() -> BuildCostRepository:
    """Get or create a BuildCostRepository instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.
    """
    def _create() -> BuildCostRepository:
        db = DatabaseConfig("build_cost")
        return BuildCostRepository(db)

    try:
        from state import get_service
        return get_service("build_cost_repository", _create)
    except ImportError:
        return _create()
