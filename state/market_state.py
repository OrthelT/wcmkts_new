"""
Active Market State Management

Manages which market hub is currently selected by the user.
Provides helpers to get/set the active market and handles cleanup
when the market is switched (clearing market-specific services and caches).
"""

import streamlit as st

from domain.market_config import MarketConfig, DEFAULT_MARKET_KEY
from logging_config import setup_logging

logger = setup_logging(__name__)

def get_active_market_key() -> str:
    """Return the key of the currently active market (e.g. 'primary')."""
    return st.session_state.get("active_market_key", DEFAULT_MARKET_KEY)


def get_active_market() -> MarketConfig:
    """Return the full MarketConfig for the currently active market."""
    from settings_service import get_all_market_configs

    key = get_active_market_key()
    configs = get_all_market_configs()
    if key not in configs:
        logger.error(f"Unknown market key '{key}'. Available: {list(configs.keys())}")
        logger.info("--------------------------------")
        key = DEFAULT_MARKET_KEY
        logger.info(f"Using default market key '{key}'")
        logger.info("--------------------------------")
    return configs[key]


def set_active_market(key: str) -> None:
    """Switch to a different market, clearing stale services and caches.

    Args:
        key: Market key (e.g. "primary" or "deployment")
    """
    from settings_service import get_all_market_configs

    configs = get_all_market_configs()
    if key not in configs:
        raise ValueError(f"Unknown market key '{key}'. Available: {list(configs.keys())}")

    old_key = get_active_market_key()
    if old_key == key:
        return  # no-op

    st.session_state["active_market_key"] = key

    # Clear market-specific service singletons so they get re-created
    # with the new market's DatabaseConfig on next access.
    # Clear both old and new market services: old ones are stale, and
    # incoming ones may have cached results built with wrong equiv data.
    _clear_market_services(old_key)
    _clear_market_services(key)

    # Clear market data caches
    refresh_market_caches()

    # Clear sync state so it refreshes for the new market
    for ss_key in ("local_update_status", "remote_update_status"):
        st.session_state.pop(ss_key, None)


# ── Service keys that are market-specific ────────────────────────────

_MARKET_SERVICE_NAMES = (
    "market_repository",
    "doctrine_repository",
    "market_orders_repository",
    "doctrine_service",
    "market_service",
    "build_cost_service",
    "pricer_service",
    "low_stock_service",
    "import_helper_service",
    "price_service",
    "module_equivalents_service",
    "selection_service",
)


def _clear_market_services(market_key: str) -> None:
    """Remove market-keyed service singletons from session state."""
    from state.service_registry import clear_services

    keys_to_clear = [f"{name}_{market_key}" for name in _MARKET_SERVICE_NAMES]
    clear_services(*keys_to_clear)


def refresh_market_caches() -> None:
    """Clear all Streamlit + in-memory caches holding market-scoped data.

    This is the **orchestrator** for market cache invalidation and is the
    function callers outside this module should use. It is distinct from
    ``repositories.market_repo.invalidate_market_caches()``, which only
    drops that one module's ``@st.cache_data`` entries. This function
    fans out across every layer that holds market-scoped state:
      - market_repo @st.cache_data entries
      - doctrine_repo @st.cache_data entries
      - module_equivalents @st.cache_data entries
      - DoctrineService._cached_result on the active session-state singleton
        (if one exists — we deliberately do not instantiate it here)

    Called after a DB sync and after switching market hubs.

    Does NOT remove cached service singletons themselves. The market-switch
    path handles that separately via _clear_market_services() so it can drop
    stale DatabaseConfig bindings; the sync path must preserve service
    instances so transient UI state (e.g. selection_service) survives.
    """
    try:
        from repositories.market_repo import invalidate_market_caches
        invalidate_market_caches()
    except ImportError:
        pass

    # Clear doctrine cached functions
    try:
        from repositories.doctrine_repo import (
            get_all_fits_with_cache,
            get_fit_by_id_with_cache,
            get_all_targets_with_cache,
            get_target_by_fit_id_with_cache,
            get_target_by_ship_id_with_cache,
            get_fit_name_with_cache,
        )
        get_all_fits_with_cache.clear()
        get_fit_by_id_with_cache.clear()
        get_all_targets_with_cache.clear()
        get_target_by_fit_id_with_cache.clear()
        get_target_by_ship_id_with_cache.clear()
        get_fit_name_with_cache.clear()
    except ImportError:
        pass

    # Clear module equivalents cached functions (stock data is market-specific)
    try:
        from services.module_equivalents_service import (
            _get_equivalence_group_cached,
            _get_all_equivalence_groups_cached,
        )
        _get_equivalence_group_cached.clear()
        _get_all_equivalence_groups_cached.clear()
    except ImportError:
        pass

    # Clear download page CSV caches (market/doctrine-scoped only; SDE excluded).
    # These are dual-layer: page caches wrap repo caches, so clearing only repo
    # caches leaves stale CSV bytes until page-level TTL expires.
    try:
        from pages.downloads import clear_download_caches
        clear_download_caches()
    except ImportError as e:
        logger.debug(f"Skipping download cache clear: {e}")

    # Clear DoctrineService's in-memory _cached_result on the cached singleton
    # for the active market, without creating one if none exists.
    service_key = f"doctrine_service_{get_active_market_key()}"
    svc = st.session_state.get(service_key)
    if svc is not None and hasattr(svc, "clear_cache"):
        try:
            svc.clear_cache()
        except Exception as e:
            logger.warning(f"Failed to clear DoctrineService cache: {e}")

