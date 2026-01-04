"""Ship role categorization service.

This module provides ship role categorization based on configuration files,
replacing the inline TOML loading in doctrine_report.py with a cached,
testable, and extensible design.

Architecture:
    - Protocol-based abstraction (ShipRoleCategorizer)
    - Configuration-based implementation (ConfigBasedCategorizer)
    - Cached TOML loading for performance
    - Factory function for easy instantiation

Performance improvements:
    - Original: Load TOML file on every categorize_ship_by_role() call
    - New: Load once, cache forever using @cache decorator

Example:
    >>> categorizer = get_ship_role_categorizer()
    >>> role = categorizer.categorize("Hurricane", 473)
    >>> print(role.value)  # "DPS"
    >>> print(role.display_name)  # "DPS"
    >>> print(role.color)  # "#e74c3c"
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Protocol

from domain import ShipRole


# ============================================================================
# Configuration Models
# ============================================================================


@dataclass(frozen=True)
class ShipRoleConfig:
    """Ship role configuration loaded from TOML.

    Attributes:
        dps: List of ship names that are DPS ships
        logi: List of ship names that are logistics ships
        links: List of ship names that are command/links ships
        support: List of ship names that are support ships
        special_cases: Dict mapping ship_name -> {fit_id -> role_name}

    The special_cases structure handles ships that can serve different roles
    depending on their fitting. For example:
        {"Vulture": {"369": "DPS", "475": "Links"}}
    """
    dps: list[str]
    logi: list[str]
    links: list[str]
    support: list[str]
    special_cases: dict[str, dict[str, str]]  # ship_name -> {fit_id -> role}

    @classmethod
    def from_toml(cls, toml_path: str | Path = "settings.toml") -> ShipRoleConfig:
        """Load ship role configuration from TOML file.

        Args:
            toml_path: Path to settings.toml file

        Returns:
            ShipRoleConfig instance with loaded configuration

        Raises:
            FileNotFoundError: If TOML file doesn't exist
            KeyError: If required configuration keys are missing
        """
        path = Path(toml_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, "rb") as f:
            settings = tomllib.load(f)

        ship_roles = settings["ship_roles"]

        return cls(
            dps=ship_roles["dps"],
            logi=ship_roles["logi"],
            links=ship_roles["links"],
            support=ship_roles["support"],
            special_cases=ship_roles.get("special_cases", {}),
        )


# ============================================================================
# Categorizer Protocol
# ============================================================================


class ShipRoleCategorizer(Protocol):
    """Protocol for ship role categorization strategies.

    This allows different categorization implementations while maintaining
    a consistent interface. Future implementations could categorize based on:
    - Fit analysis (slot types, module categories)
    - Historical fleet composition data
    - Machine learning on fitting patterns
    """

    def categorize(self, ship_name: str, fit_id: int | str) -> ShipRole:
        """Categorize a ship by its role.

        Args:
            ship_name: Display name of the ship (e.g., "Hurricane")
            fit_id: Fit identifier (int or str)

        Returns:
            ShipRole enum representing the ship's role
        """
        ...


# ============================================================================
# Configuration-Based Categorizer
# ============================================================================


class ConfigBasedCategorizer:
    """Categorizes ships based on TOML configuration.

    This implementation follows a priority order:
    1. Special cases (ship + fit_id combination)
    2. Configured ship lists (dps, logi, links, support)
    3. Keyword-based heuristics (fallback)

    The configuration is loaded once and cached for the lifetime of the
    Python process, eliminating repeated file I/O.

    Thread-safety: The @cache decorator is thread-safe in Python 3.9+
    """

    def __init__(self, config: ShipRoleConfig | None = None):
        """Initialize categorizer with optional config.

        Args:
            config: ShipRoleConfig instance. If None, loads from settings.toml
        """
        self._config = config or self._load_config()

    @staticmethod
    @cache
    def _load_config() -> ShipRoleConfig:
        """Load configuration from TOML (cached for process lifetime).

        Returns:
            Cached ShipRoleConfig instance

        Note:
            The @cache decorator ensures this file is read exactly once
            per Python process, dramatically improving performance compared
            to the original implementation which read the file on every call.
        """
        return ShipRoleConfig.from_toml("settings.toml")

    def categorize(self, ship_name: str, fit_id: int | str) -> ShipRole:
        """Categorize ship by role using configuration.

        Args:
            ship_name: Ship display name (e.g., "Hurricane Fleet Issue")
            fit_id: Fit identifier (converted to str for special case lookup)

        Returns:
            ShipRole enum (DPS, LOGI, LINKS, or SUPPORT)

        Algorithm:
            1. Check special_cases[ship_name][fit_id] first
            2. Check if ship_name is in any configured list
            3. Fall back to keyword-based heuristics
        """
        fit_id_str = str(fit_id)

        # Priority 1: Special cases (ship + fit combination)
        if ship_name in self._config.special_cases:
            special_fit_roles = self._config.special_cases[ship_name]
            if fit_id_str in special_fit_roles:
                role_name = special_fit_roles[fit_id_str]
                return ShipRole.from_string(role_name)

        # Priority 2: Configured ship lists
        if ship_name in self._config.dps:
            return ShipRole.DPS
        elif ship_name in self._config.logi:
            return ShipRole.LOGI
        elif ship_name in self._config.links:
            return ShipRole.LINKS
        elif ship_name in self._config.support:
            return ShipRole.SUPPORT

        # Priority 3: Keyword-based heuristics (fallback)
        return self._categorize_by_keywords(ship_name)

    def _categorize_by_keywords(self, ship_name: str) -> ShipRole:
        """Fallback categorization based on ship name keywords.

        Args:
            ship_name: Ship display name

        Returns:
            ShipRole enum based on keyword matching

        Note:
            This is a last resort for ships not in the configuration.
            The keyword lists should be kept in sync with the TOML config.
        """
        ship_lower = ship_name.lower()

        # DPS keywords
        if any(keyword in ship_lower for keyword in [
            'hurricane', 'ferox', 'zealot', 'bellicose', 'tornado', 'oracle',
            'harbinger', 'brutix', 'myrmidon', 'talos', 'naga'
        ]):
            return ShipRole.DPS

        # Logi keywords
        elif any(keyword in ship_lower for keyword in [
            'osprey', 'guardian', 'basilisk', 'scimitar', 'oneiros',
            'burst', 'bantam', 'inquisitor', 'navitas'
        ]):
            return ShipRole.LOGI

        # Links keywords
        elif any(keyword in ship_lower for keyword in [
            'claymore', 'drake', 'cyclone', 'sleipnir', 'nighthawk',
            'damnation', 'astarte', 'bifrost', 'pontifex'
        ]):
            return ShipRole.LINKS

        # Default to Support
        else:
            return ShipRole.SUPPORT


# ============================================================================
# Factory Functions
# ============================================================================


def get_ship_role_categorizer(
    config: ShipRoleConfig | None = None
) -> ConfigBasedCategorizer:
    """Get a ship role categorizer instance.

    This factory function provides a single point of access for categorization,
    making it easy to swap implementations or inject test configurations.

    Args:
        config: Optional ShipRoleConfig. If None, loads from settings.toml

    Returns:
        ConfigBasedCategorizer instance

    Example:
        >>> categorizer = get_ship_role_categorizer()
        >>> role = categorizer.categorize("Hurricane", 473)
        >>> print(role.display_name)  # "DPS"
    """
    return ConfigBasedCategorizer(config)


# ============================================================================
# Backwards Compatibility
# ============================================================================


def categorize_ship_by_role(ship_name: str, fit_id: int) -> str:
    """Categorize ship by role (backwards-compatible wrapper).

    This function maintains the exact signature and return type of the
    original categorize_ship_by_role() in doctrine_report.py, allowing
    for drop-in replacement without breaking existing code.

    Args:
        ship_name: Ship display name
        fit_id: Fit identifier

    Returns:
        Role name as string ("DPS", "Logi", "Links", "Support")

    Note:
        This wrapper is provided for backwards compatibility. New code
        should use get_ship_role_categorizer() and work with ShipRole enums
        to benefit from type safety and enum methods.

    Example:
        >>> role = categorize_ship_by_role("Hurricane", 473)
        >>> print(role)  # "DPS"
    """
    categorizer = get_ship_role_categorizer()
    role = categorizer.categorize(ship_name, fit_id)
    return role.display_name
