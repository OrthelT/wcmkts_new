"""
Service Registry

Centralized singleton management for services and repositories.
Provides a clean interface for caching service instances in session state.

This pattern removes st.session_state coupling from service/repository layers
while maintaining the singleton behavior needed for Streamlit apps.
"""

import streamlit as st
from typing import TypeVar, Callable

T = TypeVar('T')


def get_service(service_name: str, factory: Callable[[], T]) -> T:
    """Get or create a service instance in session state.

    This function provides centralized singleton management for services
    and repositories. The service layer can delegate caching here instead
    of directly using st.session_state.

    Args:
        service_name: Unique key for the service in session state
        factory: Zero-argument callable that creates the service instance

    Returns:
        The service instance (either cached or newly created)

    Example:
        def get_doctrine_service() -> DoctrineService:
            from state import get_service
            return get_service('doctrine_service', DoctrineService.create_default)
    """
    if service_name not in st.session_state:
        st.session_state[service_name] = factory()
    return st.session_state[service_name]


def register_service(service_name: str, instance: T) -> T:
    """Explicitly register a service instance in session state.

    Use this when you need to register a pre-configured instance
    rather than using a factory function.

    Args:
        service_name: Unique key for the service in session state
        instance: The service instance to register

    Returns:
        The registered instance
    """
    st.session_state[service_name] = instance
    return instance


def clear_services(*service_names: str) -> None:
    """Clear specified services from session state.

    Use this to force re-creation of services on next access.

    Args:
        *service_names: Service keys to clear.
                       If no names provided, does nothing.
    """
    for name in service_names:
        if name in st.session_state:
            del st.session_state[name]


def has_service(service_name: str) -> bool:
    """Check if a service is registered in session state.

    Args:
        service_name: The service key to check

    Returns:
        True if the service exists in session state
    """
    return service_name in st.session_state
