"""
Doctrine Display Names

Provides a passthrough for doctrine name resolution at the domain layer.
DB-backed friendly-name lookup lives in the repository layer:

    from repositories.doctrine_repo import get_doctrine_display_name

Usage:
    get_doctrine_display_name("SUBS - WC AHACs")  # -> "SUBS - WC AHACs" (passthrough)

For display with friendly names, use the service-layer wrapper:

    from services.doctrine_service import format_doctrine_name
"""

import logging

logger = logging.getLogger(__name__)


def get_doctrine_display_name(raw_name: str) -> str:
    """Return raw_name unchanged.

    This domain-layer function is intentionally a passthrough.
    For the DB-backed friendly name, use:
        repositories.doctrine_repo.get_doctrine_display_name
    """
    return raw_name


# Kept for backwards compatibility; always empty at the domain layer.
# Populated lookups are owned by the repository/service layers.
DOCTRINE_DISPLAY_NAMES: dict[str, str] = {}
