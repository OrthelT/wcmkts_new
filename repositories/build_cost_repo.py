"""
Build Cost Repository

Encapsulates all build cost database access: structures, rigs, industry indices.
Extracts DB functions from pages/build_costs.py into the repository pattern.
"""

import logging
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, text

from config import DatabaseConfig
from logging_config import setup_logging
from repositories.base import BaseRepository

logger = setup_logging(__name__, log_file="build_cost_repo.log")


# =============================================================================
# Constants
# =============================================================================

VALID_STRUCTURE_TYPE_IDS = [35827, 35825, 35826]
SUPER_SHIPYARD_ID = 1046452498926
INVALID_RIG_IDS = [46640, 46641, 46496, 46497, 46634]


# =============================================================================
# Implementation Functions (non-cached, for testability)
#
# All reads go through BaseRepository.read_df() so a malformed/mid-bootstrap
# local replica self-heals (sync + retry, then backup restore) instead of
# raising "no such table" into the page.
# =============================================================================

def _build_cost_reader() -> BaseRepository:
    """Plain BaseRepository for read_df access (recovery ladder included)."""
    return BaseRepository(DatabaseConfig("build_cost"), logger)


def _fetch_rigs_impl(repo: BaseRepository) -> dict[str, int]:
    """Fetch all rigs as {type_name: type_id} dict."""
    df = repo.read_df(text("SELECT type_name, type_id FROM rigs"))
    return dict(zip(df["type_name"], df["type_id"]))


def _get_valid_rigs_impl(repo: BaseRepository) -> dict[str, int]:
    """Fetch rigs, filtering out invalid rig IDs."""
    all_rigs = _fetch_rigs_impl(repo)
    return {name: tid for name, tid in all_rigs.items() if tid not in INVALID_RIG_IDS}


def _get_structure_rigs_impl(repo: BaseRepository) -> dict[str, list[str]]:
    """Get rigs per structure as {structure_name: [rig_name, ...]}."""
    valid_rigs = _get_valid_rigs_impl(repo)
    query = text(
        "SELECT structure, rig_1, rig_2, rig_3 FROM structures "
        "WHERE structure_type_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    df = repo.read_df(query, params={"ids": VALID_STRUCTURE_TYPE_IDS})

    rig_dict = {}
    for row in df.itertuples(index=False):
        raw_rigs = [row.rig_1, row.rig_2, row.rig_3]
        clean_rigs = [
            r for r in raw_rigs
            if r is not None and r != "0" and r in valid_rigs
        ]
        rig_dict[row.structure] = clean_rigs
    return rig_dict


def _get_manufacturing_cost_index_impl(repo: BaseRepository, system_id: int) -> float:
    """Get the manufacturing cost index for a solar system."""
    df = repo.read_df(
        text("SELECT manufacturing FROM industry_index WHERE solar_system_id = :sid"),
        params={"sid": system_id},
    )
    if df.empty or pd.isna(df["manufacturing"].iloc[0]):
        raise ValueError(f"No manufacturing cost index found for system {system_id}")
    return float(df["manufacturing"].iloc[0])


def _get_all_structures_impl(repo: BaseRepository, is_super: bool) -> pd.DataFrame:
    """Fetch structures filtered by super mode.

    Returns a DataFrame (picklable for st.cache_data); the repository method
    converts rows to attribute-access tuples for consumers.
    """
    if is_super:
        query = text("SELECT * FROM structures WHERE structure_id = :sid")
        params = {"sid": SUPER_SHIPYARD_ID}
    else:
        query = text(
            "SELECT * FROM structures WHERE structure_id != :sid "
            "AND structure_type_id IN :ids"
        ).bindparams(bindparam("ids", expanding=True))
        params = {"sid": SUPER_SHIPYARD_ID, "ids": VALID_STRUCTURE_TYPE_IDS}
    return repo.read_df(query, params=params)


def _write_industry_index_impl(engine, df: pd.DataFrame) -> None:
    """Write industry index DataFrame to the database."""
    with engine.connect() as conn:
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
def _get_valid_rigs_cached(_url: str) -> dict[str, int]:
    return _get_valid_rigs_impl(_build_cost_reader())


@st.cache_data(ttl=3600)
def _get_structure_rigs_cached(_url: str) -> dict[str, list[str]]:
    return _get_structure_rigs_impl(_build_cost_reader())


@st.cache_data(ttl=3600)
def _get_manufacturing_cost_index_cached(_url: str, system_id: int) -> float:
    return _get_manufacturing_cost_index_impl(_build_cost_reader(), system_id)


@st.cache_data(ttl=3600)
def _get_all_structures_cached(_url: str, is_super: bool) -> pd.DataFrame:
    return _get_all_structures_impl(_build_cost_reader(), is_super)


@st.cache_data(ttl=600, show_spinner="Loading builder cost catalog...")
def _get_builder_cost_catalog_cached(_url: str) -> pd.DataFrame:
    return _get_builder_cost_catalog_impl()


# =============================================================================
# Cache Invalidation
# =============================================================================

def invalidate_build_cost_caches():
    """Clear only build cost caches."""
    _get_valid_rigs_cached.clear()
    _get_structure_rigs_cached.clear()
    _get_manufacturing_cost_index_cached.clear()
    _get_all_structures_cached.clear()
    _get_builder_cost_catalog_cached.clear()
    logger.info("Build cost caches invalidated")


def invalidate_structure_caches():
    """Clear only the structures cache (e.g. after super-mode toggle)."""
    _get_all_structures_cached.clear()
    logger.info("Structure caches invalidated")


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

    def get_valid_rigs(self) -> dict[str, int]:
        """Get valid rigs (excludes invalid rig IDs), cached TTL=3600s."""
        return _get_valid_rigs_cached(self._cache_key)

    def get_structure_rigs(self) -> dict[str, list[str]]:
        """Get rigs per structure, cached TTL=3600s."""
        return _get_structure_rigs_cached(self._cache_key)

    def get_manufacturing_cost_index(self, system_id: int) -> float:
        """Get manufacturing cost index for a solar system, cached TTL=3600s."""
        return _get_manufacturing_cost_index_cached(self._cache_key, system_id)

    def get_all_structures(self, is_super: bool = False):
        """Get structures filtered by super mode, cached TTL=3600s.

        Returns attribute-access rows (structure.rig_1, structure.system_id).
        """
        df = _get_all_structures_cached(self._cache_key, is_super)
        return list(df.itertuples(index=False))

    def write_industry_index(self, df: pd.DataFrame) -> None:
        """Write industry index DataFrame to the database."""
        _write_industry_index_impl(self.db.engine, df)

    def get_builder_cost_catalog(self) -> pd.DataFrame:
        """Get the synced builder-cost catalog (cached, TTL=600s)."""
        return _get_builder_cost_catalog_cached(self._cache_key)

    def invalidate_structure_caches(self):
        """Clear the structures cache (e.g. after super-mode toggle)."""
        invalidate_structure_caches()


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
