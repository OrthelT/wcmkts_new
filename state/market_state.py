"""
Active Market State Management

Manages which market hub is currently selected by the user.
Provides helpers to get/set the active market and handles cleanup
when the market is switched (clearing market-specific services and caches).
"""

import streamlit as st

from domain.market_config import MarketConfig, DEFAULT_MARKET_KEY


def get_active_market_key() -> str:
    """Return the key of the currently active market (e.g. 'primary')."""
    return st.session_state.get("active_market_key", DEFAULT_MARKET_KEY)


def get_active_market() -> MarketConfig:
    """Return the full MarketConfig for the currently active market."""
    from settings_service import get_all_market_configs

    key = get_active_market_key()
    configs = get_all_market_configs()
    if key not in configs:
        key = DEFAULT_MARKET_KEY
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
    _clear_market_services(old_key)

    # Clear market data caches
    _invalidate_market_caches()

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
    "pricer_service",
    "low_stock_service",
    "price_service",
    "module_equivalents_service",
    "selection_service",
)


def _clear_market_services(market_key: str) -> None:
    """Remove market-keyed service singletons from session state."""
    from state.service_registry import clear_services

    keys_to_clear = [f"{name}_{market_key}" for name in _MARKET_SERVICE_NAMES]
    clear_services(*keys_to_clear)


def _invalidate_market_caches() -> None:
    """Clear Streamlit caches for market-specific data."""
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
