"""
Pricer Domain Models

Dataclasses for the Pricer feature that provides item pricing from
Jita and 4-HWWF markets. Supports both EFT fitting format and
tab-separated multibuy list inputs.

Design Principles:
1. Immutability (frozen=True) - Safe for caching and hashable
2. Factory methods - Clean construction from parsed data
3. Computed properties - Business logic encapsulated
4. Type safety - Explicit types throughout
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional
import pandas as pd

from domain.converters import safe_int, safe_float, safe_str


# Type aliases for clarity
TypeID = int
Price = float


# =============================================================================
# Enums
# =============================================================================

class InputFormat(Enum):
    """Input format detected from user text."""
    EFT = "eft"
    MULTIBUY = "multibuy"
    UNKNOWN = "unknown"


class SlotType(Enum):
    """EFT fitting slot types."""
    HIGH = "high"
    MEDIUM = "med"
    LOW = "low"
    RIG = "rig"
    SUBSYSTEM = "subsystem"
    DRONE = "drone"
    CARGO = "cargo"
    IMPLANT = "implant"
    HULL = "hull"  # The ship itself
    UNKNOWN = ""

    @property
    def display_name(self) -> str:
        """Human-readable slot name."""
        return {
            SlotType.HIGH: "High Slot",
            SlotType.MEDIUM: "Med Slot",
            SlotType.LOW: "Low Slot",
            SlotType.RIG: "Rig",
            SlotType.SUBSYSTEM: "Subsystem",
            SlotType.DRONE: "Drone Bay",
            SlotType.CARGO: "Cargo",
            SlotType.IMPLANT: "Implant",
            SlotType.HULL: "Hull",
            SlotType.UNKNOWN: "",
        }[self]


# =============================================================================
# ParsedItem - Raw parsed item before pricing
# =============================================================================

@dataclass(frozen=True)
class ParsedItem:
    """
    Represents a parsed item from user input before price lookup.

    Contains the item name and quantity from parsing, plus resolved
    information from SDE lookup (type_id, canonical name, metadata).

    Attributes:
        type_name: Original name from user input
        quantity: Quantity requested
        type_id: Resolved EVE type ID (None if not found in SDE)
        resolved_name: Canonical name from SDE (None if not resolved)
        volume: Item volume in m3
        group_name: Item group (e.g., "Medium Energy Turret")
        category_name: Category (e.g., "Module", "Drone")
        slot_type: EFT slot type (high/med/low/rig/drone/cargo)
        parse_error: Error message if resolution failed
    """
    type_name: str
    quantity: int
    type_id: Optional[TypeID] = None
    resolved_name: Optional[str] = None
    volume: float = 0.0
    group_name: str = ""
    category_name: str = ""
    slot_type: SlotType = SlotType.UNKNOWN
    parse_error: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        """True if item was successfully resolved in SDE."""
        return self.type_id is not None

    @property
    def display_name(self) -> str:
        """Best available name for display."""
        return self.resolved_name or self.type_name

    @property
    def total_volume(self) -> float:
        """Total volume for this item (volume * quantity)."""
        return self.volume * self.quantity


# =============================================================================
# LocalPriceData - Aggregated local market data
# =============================================================================

@dataclass(frozen=True)
class LocalPriceData:
    """
    Aggregated local market (4-HWWF) price data for an item.

    Computed from marketorders table by aggregating buy and sell orders.

    Attributes:
        type_id: EVE type ID
        min_sell_price: Minimum sell order price
        max_buy_price: Maximum buy order price
        total_sell_volume: Total volume of sell orders
        total_buy_volume: Total volume of buy orders
    """
    type_id: TypeID
    min_sell_price: Price = 0.0
    max_buy_price: Price = 0.0
    total_sell_volume: int = 0
    total_buy_volume: int = 0

    @property
    def has_sell_orders(self) -> bool:
        """True if there are sell orders available."""
        return self.min_sell_price > 0 and self.total_sell_volume > 0

    @property
    def has_buy_orders(self) -> bool:
        """True if there are buy orders available."""
        return self.max_buy_price > 0 and self.total_buy_volume > 0

    @property
    def spread(self) -> Optional[Price]:
        """Price spread (sell - buy), None if either missing."""
        if self.has_sell_orders and self.has_buy_orders:
            return self.min_sell_price - self.max_buy_price
        return None

    @property
    def spread_percentage(self) -> Optional[float]:
        """Spread as percentage of sell price, None if either missing."""
        spread = self.spread
        if spread is not None and self.min_sell_price > 0:
            return (spread / self.min_sell_price) * 100
        return None


# =============================================================================
# PricedItem - Item with complete price information
# =============================================================================

@dataclass(frozen=True)
class PricedItem:
    """
    Represents an item with complete price information from all sources.

    Combines the parsed item data with Jita and local market prices.

    Attributes:
        item: The parsed item (contains name, qty, metadata)
        jita_sell: Jita sell price per unit
        jita_buy: Jita buy price per unit
        local_sell: 4-HWWF min sell price per unit
        local_buy: 4-HWWF max buy price per unit
        local_sell_volume: Total sell volume at 4-HWWF
        local_buy_volume: Total buy volume at 4-HWWF
        avg_daily_volume: Average daily sales volume (30-day)
        days_of_stock: Days of stock remaining based on avg sales
        is_doctrine: Whether item is used in doctrines
        doctrine_ships: List of ships/fits using this item
    """
    image_url: str
    item: ParsedItem
    jita_sell: Price = 0.0
    jita_buy: Price = 0.0
    local_sell: Price = 0.0
    local_buy: Price = 0.0
    local_sell_volume: int = 0
    local_buy_volume: int = 0
    avg_daily_volume: float = 0.0
    days_of_stock: float = 0.0
    is_doctrine: bool = False
    doctrine_ships: tuple[str, ...] = field(default_factory=tuple)

    @property
    def quantity(self) -> int:
        """Quantity from the parsed item."""
        return self.item.quantity

    @property
    def type_name(self) -> str:
        """Display name from the parsed item."""
        return self.item.display_name

    @property
    def type_id(self) -> Optional[TypeID]:
        """Type ID from the parsed item."""
        return self.item.type_id

    # Jita totals
    @property
    def jita_sell_total(self) -> Price:
        """Total Jita sell value (price * quantity)."""
        return self.jita_sell * self.quantity

    @property
    def jita_buy_total(self) -> Price:
        """Total Jita buy value (price * quantity)."""
        return self.jita_buy * self.quantity

    # Local totals
    @property
    def local_sell_total(self) -> Price:
        """Total 4-HWWF sell value (price * quantity)."""
        return self.local_sell * self.quantity

    @property
    def local_buy_total(self) -> Price:
        """Total 4-HWWF buy value (price * quantity)."""
        return self.local_buy * self.quantity

    # Comparison properties
    @property
    def jita_spread(self) -> Price:
        """Jita price spread (sell - buy)."""
        return self.jita_sell - self.jita_buy

    @property
    def local_spread(self) -> Price:
        """Local price spread (sell - buy)."""
        return self.local_sell - self.local_buy

    @property
    def jita_vs_local_sell_delta(self) -> Price:
        """Difference between Jita sell and local sell (negative = local cheaper)."""
        return self.jita_sell - self.local_sell

    @property
    def is_priced(self) -> bool:
        """True if at least one price source has data."""
        return self.jita_sell > 0 or self.local_sell > 0

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame creation."""
        return {
            "image_url": self.image_url,
            "type_id": self.type_id or 0,  # Use 0 as default if None
            "Item": self.type_name,
            "Qty": self.quantity,
            "Volume": self.item.volume,
            "Category": self.item.category_name,
            "Slot": self.item.slot_type.display_name,
            "Jita Sell": self.jita_sell,
            "Jita Buy": self.jita_buy,
            "Jita Sell Total": self.jita_sell_total,
            "Jita Buy Total": self.jita_buy_total,
            "4-HWWF Sell": self.local_sell,
            "4-HWWF Buy": self.local_buy,
            "4-HWWF Sell Total": self.local_sell_total,
            "4-HWWF Buy Total": self.local_buy_total,
            "4-HWWF Sell Vol": self.local_sell_volume,
            "4-HWWF Buy Vol": self.local_buy_volume,
            "Avg Daily Vol": self.avg_daily_volume,
            "Days of Stock": self.days_of_stock,
            "Is Doctrine": self.is_doctrine,
            "Doctrine Ships": list(self.doctrine_ships),
        }


# =============================================================================
# PricerResult - Complete pricing operation result
# =============================================================================

@dataclass
class PricerResult:
    """
    Complete result of a pricer operation.

    Contains all priced items, parse errors, and grand totals.
    Not frozen because it aggregates mutable lists.

    Attributes:
        items: List of priced items
        parse_errors: List of items that couldn't be parsed/resolved
        input_type: Detected input format (EFT or multibuy)
        fit_name: For EFT inputs, the fitting name
        ship_name: For EFT inputs, the ship name
    """
    items: list[PricedItem] = field(default_factory=list)
    parse_errors: list[str] = field(default_factory=list)
    input_type: InputFormat = InputFormat.UNKNOWN
    fit_name: Optional[str] = None
    ship_name: Optional[str] = None

    # Grand totals - Jita
    @property
    def jita_sell_grand_total(self) -> Price:
        """Sum of all Jita sell totals."""
        return sum(item.jita_sell_total for item in self.items)

    @property
    def jita_buy_grand_total(self) -> Price:
        """Sum of all Jita buy totals."""
        return sum(item.jita_buy_total for item in self.items)

    # Grand totals - Local
    @property
    def local_sell_grand_total(self) -> Price:
        """Sum of all 4-HWWF sell totals."""
        return sum(item.local_sell_total for item in self.items)

    @property
    def local_buy_grand_total(self) -> Price:
        """Sum of all 4-HWWF buy totals."""
        return sum(item.local_buy_total for item in self.items)

    # Volume
    @property
    def total_volume(self) -> float:
        """Total volume of all items in m3."""
        return sum(item.item.total_volume for item in self.items)

    # Item counts
    @property
    def item_count(self) -> int:
        """Number of successfully priced items."""
        return len(self.items)

    @property
    def error_count(self) -> int:
        """Number of items that failed to parse/resolve."""
        return len(self.parse_errors)

    @property
    def total_quantity(self) -> int:
        """Total quantity of all items."""
        return sum(item.quantity for item in self.items)

    # Status
    @property
    def has_errors(self) -> bool:
        """True if there were any parse errors."""
        return len(self.parse_errors) > 0

    @property
    def is_eft(self) -> bool:
        """True if input was EFT format."""
        return self.input_type == InputFormat.EFT

    @property
    def is_multibuy(self) -> bool:
        """True if input was multibuy format."""
        return self.input_type == InputFormat.MULTIBUY

    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert priced items to DataFrame for display.

        Returns:
            DataFrame with columns for all price and metadata fields
        """
        if not self.items:
            return pd.DataFrame()

        data = [item.to_dict() for item in self.items]
        return pd.DataFrame(data)

    def get_totals_dict(self) -> dict:
        """Get summary totals as a dictionary."""
        return {
            "Jita Sell Total": self.jita_sell_grand_total,
            "Jita Buy Total": self.jita_buy_grand_total,
            "4-HWWF Sell Total": self.local_sell_grand_total,
            "4-HWWF Buy Total": self.local_buy_grand_total,
            "Total Volume (m3)": self.total_volume,
            "Item Count": self.item_count,
            "Total Quantity": self.total_quantity,
            "Parse Errors": self.error_count,
        }
