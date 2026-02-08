"""
Domain Enums

Enumerations for categorical data used throughout the doctrine module.
These replace magic strings and provide type safety.
"""

from enum import Enum, auto


class StockStatus(Enum):
    """
    Stock status levels for fits and modules.

    Thresholds (relative to target):
    - CRITICAL: <= 20% of target (previously 40% in some places)
    - NEEDS_ATTENTION: > 20% and <= 90% of target
    - GOOD: > 90% of target

    Note: The thresholds are consistent with doctrine_status.py and
    doctrine_report.py display logic.
    """
    CRITICAL = auto()
    NEEDS_ATTENTION = auto()
    GOOD = auto()

    @classmethod
    def from_percentage(cls, percentage: float) -> "StockStatus":
        """
        Determine stock status from a target percentage.

        Args:
            percentage: Current stock as percentage of target (0-100+)

        Returns:
            Appropriate StockStatus enum value
        """
        if percentage <= 20:
            return cls.CRITICAL
        elif percentage <= 90:
            return cls.NEEDS_ATTENTION
        else:
            return cls.GOOD

    @classmethod
    def from_stock_and_target(cls, stock: int, target: int) -> "StockStatus":
        """
        Determine stock status from raw stock and target values.

        Args:
            stock: Current stock quantity
            target: Target stock quantity

        Returns:
            Appropriate StockStatus enum value
        """
        if target <= 0:
            return cls.GOOD  # No target means no concern
        percentage = (stock / target) * 100
        return cls.from_percentage(percentage)

    @property
    def display_color(self) -> str:
        """Return the Streamlit badge color for this status."""
        return {
            StockStatus.CRITICAL: "red",
            StockStatus.NEEDS_ATTENTION: "orange",
            StockStatus.GOOD: "green",
        }[self]

    @property
    def display_name(self) -> str:
        """Return human-readable status name."""
        return {
            StockStatus.CRITICAL: "Critical",
            StockStatus.NEEDS_ATTENTION: "Needs Attention",
            StockStatus.GOOD: "Good",
        }[self]


class ShipRole(Enum):
    """
    Functional roles for ships in a doctrine.

    Used by categorize_ship_by_role() in doctrine_report.py to group
    ships by their function in a fleet composition.
    """
    DPS = auto()
    LOGI = auto()
    LINKS = auto()
    SUPPORT = auto()

    @property
    def display_emoji(self) -> str:
        """Return emoji icon for this role."""
        return {
            ShipRole.DPS: "💥",
            ShipRole.LOGI: "🏥",
            ShipRole.LINKS: "📡",
            ShipRole.SUPPORT: "🛠️",
        }[self]

    @property
    def display_color(self) -> str:
        """Return display color for this role."""
        return {
            ShipRole.DPS: "red",
            ShipRole.LOGI: "green",
            ShipRole.LINKS: "blue",
            ShipRole.SUPPORT: "orange",
        }[self]

    @property
    def description(self) -> str:
        """Return description for this role."""
        return {
            ShipRole.DPS: "Primary DPS Ships",
            ShipRole.LOGI: "Logistics Ships",
            ShipRole.LINKS: "Command Ships",
            ShipRole.SUPPORT: "EWAR, Tackle & Other Support Ships",
        }[self]

    @classmethod
    def display_order(cls) -> list["ShipRole"]:
        """Return roles in logical display order."""
        return [cls.DPS, cls.LOGI, cls.LINKS, cls.SUPPORT]

    @classmethod
    def from_string(cls, role_name: str) -> "ShipRole":
        """
        Convert role name string to ShipRole enum.

        Args:
            role_name: Role name as string (case-insensitive)
                      Accepts: "DPS", "Logi", "Links", "Support"

        Returns:
            Corresponding ShipRole enum value

        Raises:
            ValueError: If role_name doesn't match a valid role

        Example:
            >>> ShipRole.from_string("DPS")
            <ShipRole.DPS: 1>
            >>> ShipRole.from_string("logi")
            <ShipRole.LOGI: 2>
        """
        role_upper = role_name.upper()
        mapping = {
            "DPS": cls.DPS,
            "LOGI": cls.LOGI,
            "LINKS": cls.LINKS,
            "SUPPORT": cls.SUPPORT,
        }

        if role_upper not in mapping:
            raise ValueError(
                f"Invalid role name: {role_name}. "
                f"Must be one of: {', '.join(mapping.keys())}"
            )

        return mapping[role_upper]

    @property
    def display_name(self) -> str:
        """Return human-readable role name matching original string format."""
        return {
            ShipRole.DPS: "DPS",
            ShipRole.LOGI: "Logi",
            ShipRole.LINKS: "Links",
            ShipRole.SUPPORT: "Support",
        }[self]
