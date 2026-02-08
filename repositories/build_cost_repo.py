"""
Build Cost Repository

Encapsulates all build cost database access: structures, rigs, industry indices.
Extracts DB functions from pages/build_costs.py into the repository pattern.
"""

import logging
from typing import Optional

import pandas as pd
import streamlit as st
from sqlalchemy import text

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
# =============================================================================

def _fetch_rigs_impl(engine) -> dict[str, int]:
    """Fetch all rigs as {type_name: type_id} dict."""
    with engine.connect() as conn:
        res = conn.execute(text("SELECT type_name, type_id FROM rigs"))
        rows = res.fetchall()
    return {row[0]: row[1] for row in rows}


def _get_valid_rigs_impl(engine) -> dict[str, int]:
    """Fetch rigs, filtering out invalid rig IDs."""
    all_rigs = _fetch_rigs_impl(engine)
    return {name: tid for name, tid in all_rigs.items() if tid not in INVALID_RIG_IDS}


def _get_structure_rigs_impl(engine) -> dict[str, list[str]]:
    """Get rigs per structure as {structure_name: [rig_name, ...]}."""
    valid_rigs = _get_valid_rigs_impl(engine)
    ids_str = ", ".join(str(tid) for tid in VALID_STRUCTURE_TYPE_IDS)
    with engine.connect() as conn:
        res = conn.execute(
            text(f"SELECT structure, rig_1, rig_2, rig_3 FROM structures "
                 f"WHERE structure_type_id IN ({ids_str})")
        )
        rows = res.fetchall()

    rig_dict = {}
    for row in rows:
        structure, rig_1, rig_2, rig_3 = row
        raw_rigs = [rig_1, rig_2, rig_3]
        clean_rigs = [
            r for r in raw_rigs
            if r is not None and r != "0" and r in valid_rigs
        ]
        rig_dict[structure] = clean_rigs
    return rig_dict


def _get_manufacturing_cost_index_impl(engine, system_id: int) -> float:
    """Get the manufacturing cost index for a solar system."""
    with engine.connect() as conn:
        res = conn.execute(
            text("SELECT manufacturing FROM industry_index WHERE solar_system_id = :sid"),
            {"sid": system_id},
        )
        index = res.scalar()
        if index is not None:
            return float(index)
        raise ValueError(f"No manufacturing cost index found for system {system_id}")


def _get_all_structures_impl(engine, is_super: bool):
    """Fetch structures filtered by super mode."""
    if is_super:
        stmt = text(
            f"SELECT * FROM structures WHERE structure_id = {SUPER_SHIPYARD_ID}"
        )
    else:
        ids_str = ", ".join(str(tid) for tid in VALID_STRUCTURE_TYPE_IDS)
        stmt = text(
            f"SELECT * FROM structures WHERE structure_id != {SUPER_SHIPYARD_ID} "
            f"AND structure_type_id IN ({ids_str})"
        )
    with engine.connect() as conn:
        res = conn.execute(stmt)
        return res.fetchall()


def _write_industry_index_impl(engine, df: pd.DataFrame) -> None:
    """Write industry index DataFrame to the database."""
    with engine.connect() as conn:
        df.to_sql("industry_index", conn, if_exists="replace", index=False)


# =============================================================================
# Cached Wrappers (Streamlit cache layer)
# =============================================================================

@st.cache_data(ttl=3600)
def _get_valid_rigs_cached(_url: str) -> dict[str, int]:
    db = DatabaseConfig("build_cost")
    return _get_valid_rigs_impl(db.engine)


@st.cache_data(ttl=3600)
def _get_structure_rigs_cached(_url: str) -> dict[str, list[str]]:
    db = DatabaseConfig("build_cost")
    return _get_structure_rigs_impl(db.engine)


@st.cache_data(ttl=3600)
def _get_manufacturing_cost_index_cached(_url: str, system_id: int) -> float:
    db = DatabaseConfig("build_cost")
    return _get_manufacturing_cost_index_impl(db.engine, system_id)


@st.cache_data(ttl=3600)
def _get_all_structures_cached(_url: str, is_super: bool):
    db = DatabaseConfig("build_cost")
    return _get_all_structures_impl(db.engine, is_super)


# =============================================================================
# Cache Invalidation
# =============================================================================

def invalidate_build_cost_caches():
    """Clear only build cost caches."""
    _get_valid_rigs_cached.clear()
    _get_structure_rigs_cached.clear()
    _get_manufacturing_cost_index_cached.clear()
    _get_all_structures_cached.clear()
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
        """Get structures filtered by super mode, cached TTL=3600s."""
        return _get_all_structures_cached(self._cache_key, is_super)

    def write_industry_index(self, df: pd.DataFrame) -> None:
        """Write industry index DataFrame to the database."""
        _write_industry_index_impl(self.db.engine, df)

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
