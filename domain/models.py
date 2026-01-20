"""
Domain Models

Dataclasses representing the core domain entities for doctrine management.
These models provide typed, structured data that replaces raw DataFrame rows
passed throughout the codebase.

Design Principles:
1. Immutability (frozen=True) - Safe for caching and hashable for dict keys
2. Factory methods - Clean construction from DataFrame rows
3. Computed properties - Business logic encapsulated in the model
4. Type safety - Explicit types instead of implicit DataFrame column access
"""

from dataclasses import dataclass, field
from typing import Optional
import pandas as pd

from domain.enums import StockStatus, ShipRole
from domain.converters import safe_int, safe_float, safe_str


# Type aliases for clarity
TypeID = int
FitID = int
Price = float


# =============================================================================
# FitItem - Individual item in a ship fit
# =============================================================================

@dataclass(frozen=True)
class FitItem:
    """
    Represents a single item (module, ship hull, ammo, etc.) in a fit.

    Corresponds to a row in the 'doctrines' table. Each fit contains
    multiple FitItems, including the ship hull itself.

    Attributes:
        fit_id: Unique identifier for the fit
        type_id: EVE type ID of the item
        type_name: Display name of the item
        fit_qty: Quantity of this item required per fit
        total_stock: Total quantity in market stock
        fits_on_mkt: Number of complete fits this stock can support
        price: Current market price per unit
        avg_vol: Average daily volume traded
        group_name: Item group (e.g., "Frigate", "Medium Energy Turret")
        category_id: Category ID (ships are category 6)
        ship_id: Type ID of the ship this item belongs to
        ship_name: Name of the ship this item belongs to
        hulls: Number of ship hulls in stock (only relevant for ship items)
    """
    fit_id: FitID
    type_id: TypeID
    type_name: str
    fit_qty: int
    total_stock: int = 0
    fits_on_mkt: int = 0
    price: Price = 0.0
    avg_vol: float = 0.0
    group_name: str = ""
    category_id: int = 0
    ship_id: TypeID = 0
    ship_name: str = ""
    hulls: int = 0

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> "FitItem":
        """
        Factory method to create FitItem from a DataFrame row.

        Handles missing/null values gracefully with sensible defaults using
        safe conversion utilities from domain.converters.

        Args:
            row: A pandas Series representing a row from the doctrines table

        Returns:
            A new FitItem instance
        """
        return cls(
            fit_id=safe_int(row.get('fit_id')),
            type_id=safe_int(row.get('type_id')),
            type_name=safe_str(row.get('type_name')),
            fit_qty=safe_int(row.get('fit_qty'), 1),
            total_stock=safe_int(row.get('total_stock')),
            fits_on_mkt=safe_int(row.get('fits_on_mkt')),
            price=safe_float(row.get('price')),
            avg_vol=safe_float(row.get('avg_vol')),
            group_name=safe_str(row.get('group_name')),
            category_id=safe_int(row.get('category_id')),
            ship_id=safe_int(row.get('ship_id')),
            ship_name=safe_str(row.get('ship_name')),
            hulls=safe_int(row.get('hulls')),
        )

    @property
    def is_ship_hull(self) -> bool:
        """True if this item is the ship hull (type_id matches ship_id)."""
        return self.type_id == self.ship_id

    @property
    def item_cost(self) -> Price:
        """Total cost for this item in a single fit."""
        return self.fit_qty * self.price

    @property
    def stock_value(self) -> Price:
        """Total value of all stock for this item."""
        return self.total_stock * self.price


# =============================================================================
# FitSummary - Aggregated summary of a complete fit
# =============================================================================

@dataclass(frozen=True)
class FitSummary:
    """
    Aggregated summary of a complete ship fit.

    Contains all the information needed to display a fit's status,
    including derived metrics like target percentage and cost.

    This replaces the summary DataFrame rows created in create_fit_df()
    and get_fit_summary().
    """
    fit_id: FitID
    ship_id: TypeID
    ship_name: str
    fit_name: str = ""
    fits: int = 0  # Minimum fits available based on lowest module stock
    hulls: int = 0  # Number of ship hulls in stock
    ship_target: int = 0  # Target number of fits to maintain
    total_cost: Price = 0.0  # Total cost of a single fit
    ship_group: str = ""  # Ship group (e.g., "Battlecruiser")
    hull_price: Price = 0.0  # Price of the ship hull
    daily_avg: float = 0.0  # Average daily sales volume
    lowest_modules: tuple[str, ...] = field(default_factory=tuple)  # Names of lowest-stock modules
    items: tuple["FitItem", ...] = field(default_factory=tuple)  # All items in the fit

    @classmethod
    def from_dataframe_row(
        cls,
        row: pd.Series,
        items: Optional[list["FitItem"]] = None,
        lowest_modules: Optional[list[str]] = None
    ) -> "FitSummary":
        """
        Factory method to create FitSummary from a summary DataFrame row.

        Args:
            row: A pandas Series from the fit_summary DataFrame
            items: Optional list of FitItem objects for this fit
            lowest_modules: Optional list of lowest-stock module names

        Returns:
            A new FitSummary instance
        """
        return cls(
            fit_id=safe_int(row.get('fit_id')),
            ship_id=safe_int(row.get('ship_id')),
            ship_name=safe_str(row.get('ship_name')),
            fit_name=safe_str(row.get('fit_name', row.get('fit', ''))),
            fits=safe_int(row.get('fits')),
            hulls=safe_int(row.get('hulls')),
            ship_target=safe_int(row.get('ship_target', row.get('target', 0))),
            total_cost=safe_float(row.get('total_cost')),
            ship_group=safe_str(row.get('ship_group')),
            hull_price=safe_float(row.get('price')),
            daily_avg=safe_float(row.get('daily_avg')),
            lowest_modules=tuple(lowest_modules) if lowest_modules else (),
            items=tuple(items) if items else (),
        )

    @property
    def target_percentage(self) -> int:
        """
        Percentage of target stock level achieved.

        Returns value from 0-100, capped at 100.
        """
        if self.ship_target <= 0:
            return 0
        return min(100, int((self.fits / self.ship_target) * 100))

    @property
    def status(self) -> StockStatus:
        """Get the stock status for this fit."""
        return StockStatus.from_percentage(self.target_percentage)

    @property
    def is_critical(self) -> bool:
        """True if this fit is at critical stock levels."""
        return self.status == StockStatus.CRITICAL

    @property
    def needs_attention(self) -> bool:
        """True if this fit needs attention (not critical but not good)."""
        return self.status == StockStatus.NEEDS_ATTENTION

    @property
    def fits_delta(self) -> int:
        """Difference between current fits and target (negative = under target)."""
        return self.fits - self.ship_target

    @property
    def hulls_delta(self) -> int:
        """Difference between current hulls and target."""
        return self.hulls - self.ship_target

    def with_target_multiplier(self, multiplier: float) -> "FitSummary":
        """
        Create a new FitSummary with an adjusted target.

        This is used for the target multiplier slider in the UI.

        Args:
            multiplier: Multiplier to apply to ship_target

        Returns:
            New FitSummary with adjusted target
        """
        # Since frozen=True, we need to create a new instance
        return FitSummary(
            fit_id=self.fit_id,
            ship_id=self.ship_id,
            ship_name=self.ship_name,
            fit_name=self.fit_name,
            fits=self.fits,
            hulls=self.hulls,
            ship_target=int(self.ship_target * multiplier),
            total_cost=self.total_cost,
            ship_group=self.ship_group,
            hull_price=self.hull_price,
            daily_avg=self.daily_avg,
            lowest_modules=self.lowest_modules,
            items=self.items,
        )


# =============================================================================
# ModuleUsage - Where a module is used
# =============================================================================

@dataclass(frozen=True)
class ModuleUsage:
    """
    Records how a module is used in a specific fit.

    Used to display "Used in: FitName(qty)" information.
    """
    ship_name: str
    ship_target: int
    fit_qty: int

    @property
    def modules_needed(self) -> int:
        """Total modules needed across all target fits."""
        return self.ship_target * self.fit_qty

    @property
    def display_string(self) -> str:
        """Formatted string for display."""
        return f"{self.ship_name}({self.modules_needed})"


# =============================================================================
# ModuleStock - Module with stock and usage information
# =============================================================================

@dataclass(frozen=True)
class ModuleStock:
    """
    Represents a module with its stock levels and usage across fits.

    Consolidates the data retrieved by get_module_stock_list() functions
    in both doctrine_status.py and doctrine_report.py.
    """
    type_id: TypeID
    type_name: str
    total_stock: int = 0
    fits_on_mkt: int = 0
    usage: tuple[ModuleUsage, ...] = field(default_factory=tuple)

    @classmethod
    def from_query_results(
        cls,
        stock_row: pd.Series,
        usage_df: Optional[pd.DataFrame] = None
    ) -> "ModuleStock":
        """
        Factory method to create ModuleStock from query results.

        Args:
            stock_row: Row from doctrines table with stock info
            usage_df: Optional DataFrame with usage information

        Returns:
            A new ModuleStock instance
        """
        usage_list = []
        if usage_df is not None and not usage_df.empty:
            # Group by ship_name and ship_target, sum fit_qty
            grouped = (
                usage_df
                .fillna({"ship_target": 0, "fit_qty": 0})
                .groupby(["ship_name", "ship_target"], dropna=False)["fit_qty"]
                .sum()
                .reset_index()
            )
            for _, row in grouped.iterrows():
                usage_list.append(ModuleUsage(
                    ship_name=safe_str(row.get("ship_name"), "Unknown Fit"),
                    ship_target=safe_int(row.get("ship_target")),
                    fit_qty=safe_int(row.get("fit_qty")),
                ))

        return cls(
            type_id=safe_int(stock_row.get('type_id')),
            type_name=safe_str(stock_row.get('type_name')),
            total_stock=safe_int(stock_row.get('total_stock')),
            fits_on_mkt=safe_int(stock_row.get('fits_on_mkt')),
            usage=tuple(usage_list),
        )

    @property
    def display_string(self) -> str:
        """Formatted string for sidebar display."""
        base = f"{self.type_name} (Total: {self.total_stock} | Fits: {self.fits_on_mkt})"
        if self.usage:
            usage_str = ", ".join(u.display_string for u in self.usage)
            return f"{base} | Used in: {usage_str}"
        return base

    @property
    def csv_line(self) -> str:
        """CSV-formatted line for export."""
        usage_str = ", ".join(u.display_string for u in self.usage) if self.usage else ""
        return f"{self.type_name},{self.type_id},{self.total_stock},{self.fits_on_mkt},,{usage_str}\n"

    def get_status(self, target: int) -> StockStatus:
        """Get stock status relative to a target."""
        return StockStatus.from_stock_and_target(self.fits_on_mkt, target)


# =============================================================================
# Doctrine - A fleet doctrine containing multiple fits
# =============================================================================

@dataclass(frozen=True)
class Doctrine:
    """
    Represents a fleet doctrine - a collection of ship fits.

    Corresponds to a row in the 'doctrine_fits' table, grouping
    multiple fit_ids under a named doctrine.
    """
    doctrine_id: int
    doctrine_name: str
    lead_ship_id: TypeID = 0
    fit_ids: tuple[FitID, ...] = field(default_factory=tuple)

    @classmethod
    def from_dataframe(
        cls,
        doctrine_row: pd.Series,
        fit_ids: list[FitID],
        lead_ship_id: Optional[TypeID] = None
    ) -> "Doctrine":
        """
        Factory method to create Doctrine from query results.

        Args:
            doctrine_row: Row from doctrine_fits table
            fit_ids: List of fit IDs belonging to this doctrine
            lead_ship_id: Optional lead ship type ID

        Returns:
            A new Doctrine instance
        """
        def safe_int(value, default: int = 0) -> int:
            if pd.isna(value):
                return default
            return int(value)

        def safe_str(value, default: str = "") -> str:
            if pd.isna(value):
                return default
            return str(value)

        return cls(
            doctrine_id=safe_int(doctrine_row.get('doctrine_id')),
            doctrine_name=safe_str(doctrine_row.get('doctrine_name')),
            lead_ship_id=lead_ship_id or 0,
            fit_ids=tuple(fit_ids),
        )

    @property
    def fit_count(self) -> int:
        """Number of fits in this doctrine."""
        return len(self.fit_ids)

    @property
    def lead_ship_image_url(self) -> str:
        """URL for the lead ship's image."""
        if self.lead_ship_id:
            return f"https://images.evetech.net/types/{self.lead_ship_id}/render?size=256"
        return ""


# =============================================================================
# ShipStock - Ship hull with stock and target information
# =============================================================================

@dataclass(frozen=True)
class ShipStock:
    """
    Represents a ship hull with its stock levels and target.

    Used for sidebar display of selected ships in doctrine_status.py.
    Consolidates the data retrieved by get_ship_stock_list().

    Attributes:
        type_id: EVE type ID of the ship
        type_name: Display name of the ship
        total_stock: Total quantity of hulls in market stock
        fits_on_mkt: Number of complete fits this stock can support
        fit_id: The fit_id used for this ship (for multi-fit ships)
        ship_target: Target number of fits to maintain
    """
    type_id: TypeID
    type_name: str
    total_stock: int = 0
    fits_on_mkt: int = 0
    fit_id: FitID = 0
    ship_target: int = 0

    @classmethod
    def from_query_result(
        cls,
        row: pd.Series,
        ship_target: int = 0
    ) -> "ShipStock":
        """
        Factory method to create ShipStock from query result.

        Args:
            row: Row from doctrines table with stock info
            ship_target: Target stock level

        Returns:
            A new ShipStock instance
        """
        return cls(
            type_id=safe_int(row.get('type_id')),
            type_name=safe_str(row.get('type_name')),
            total_stock=safe_int(row.get('total_stock')),
            fits_on_mkt=safe_int(row.get('fits_on_mkt')),
            fit_id=safe_int(row.get('fit_id')),
            ship_target=ship_target,
        )

    @property
    def display_string(self) -> str:
        """Formatted string for sidebar display."""
        return f"{self.type_name} (Qty: {self.total_stock} | Fits: {self.fits_on_mkt} | Target: {self.ship_target})"

    @property
    def csv_line(self) -> str:
        """CSV-formatted line for export."""
        return f"{self.type_name},{self.type_id},{self.total_stock},{self.fits_on_mkt},{self.ship_target},\n"

    @property
    def status(self) -> StockStatus:
        """Get stock status relative to target."""
        return StockStatus.from_stock_and_target(self.fits_on_mkt, self.ship_target)
