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

from state.session_state import ss_get, ss_has, ss_init, ss_set, ss_clear
from state.service_registry import get_service, register_service, clear_services, has_service

__all__ = [
    # Session state utilities
    'ss_get',
    'ss_has',
    'ss_init',
    'ss_set',
    'ss_clear',
    # Service registry
    'get_service',
    'register_service',
    'clear_services',
    'has_service',
]
