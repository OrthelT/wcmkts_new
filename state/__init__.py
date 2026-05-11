"""
State Management Module
Centralized state management for Streamlit session state.
This module belongs in the presentation layer and provides:
- Session state utilities (ss_get, ss_has, ss_init, ss_set, ss_clear)
- Service registry for singleton management (get_service, register_service, clear_services)
Usage:
    from state import ss_get, ss_has, ss_init
    from state import get_service, register_service
"""

from state.admin_auth_state import (
    clear_admin_auth_state,
    clear_admin_identity,
    consume_pending_oauth_state,
    get_admin_identity,
    get_pending_oauth_state,
    set_admin_identity,
    set_pending_oauth_state,
)
from state.language_state import (
    get_active_language,
    get_query_param_language,
    set_active_language,
    set_language_query_param,
    sync_active_language_with_query_params,
)
from state.market_state import get_active_market, get_active_market_key, set_active_market
from state.service_registry import clear_services, get_service, has_service, register_service
from state.session_state import ss_clear, ss_get, ss_has, ss_init, ss_set

__all__ = [
    "ss_get",
    "ss_has",
    "ss_init",
    "ss_set",
    "ss_clear",
    "get_service",
    "register_service",
    "clear_services",
    "has_service",
    "get_active_language",
    "get_query_param_language",
    "set_active_language",
    "set_language_query_param",
    "sync_active_language_with_query_params",
    "get_active_market",
    "get_active_market_key",
    "set_active_market",
    "get_pending_oauth_state",
    "set_pending_oauth_state",
    "consume_pending_oauth_state",
    "get_admin_identity",
    "set_admin_identity",
    "clear_admin_identity",
    "clear_admin_auth_state",
]
