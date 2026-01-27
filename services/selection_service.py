"""
Selection Service

Unified service for managing ship and module selections across doctrine pages.
Provides consistent selection workflows, sidebar formatting, and state management.

Design Principles:
1. Single source of truth for selection state
2. Consistent formatting across pages
3. Clean separation of selection logic from UI
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

from domain import StockStatus
from logging_config import setup_logging

logger = setup_logging(__name__, log_file="selection_service.log")


# =============================================================================
# Domain Models
# =============================================================================

@dataclass
class SelectedItem:
    """
    Represents a selected ship or module with its metadata.

    Attributes:
        type_id: EVE type ID
        name: Item name
        stock: Current stock on market
        target: Target stock level
        is_ship: Whether this is a ship (vs module)
        fit_id: Fit ID (if applicable)
        status: Stock status
    """
    type_id: int
    name: str
    stock: int = 0
    target: int = 0
    is_ship: bool = False
    fit_id: Optional[int] = None

    @property
    def status(self) -> StockStatus:
        """Get stock status based on stock vs target."""
        return StockStatus.from_stock_and_target(self.stock, self.target)

    @property
    def percentage(self) -> float:
        """Get stock as percentage of target."""
        if self.target == 0:
            return 100.0 if self.stock > 0 else 0.0
        return (self.stock / self.target) * 100

    def to_display_string(self) -> str:
        """Get formatted string for display."""
        if self.is_ship:
            return f"{self.name} ({self.stock}/{self.target})"
        return f"{self.name} ({self.stock})"


@dataclass
class SelectionState:
    """
    Holds the current selection state.

    Attributes:
        selected_ships: List of selected ship names
        selected_modules: List of selected module names
        selected_items: Dict mapping name to SelectedItem details
    """
    selected_ships: list[str] = field(default_factory=list)
    selected_modules: list[str] = field(default_factory=list)
    selected_items: dict[str, SelectedItem] = field(default_factory=dict)

    @property
    def total_selected(self) -> int:
        """Total number of selected items."""
        return len(self.selected_ships) + len(self.selected_modules)

    def add_ship(self, item: SelectedItem) -> None:
        """Add a ship to selection."""
        if item.name not in self.selected_ships:
            self.selected_ships.append(item.name)
            self.selected_items[item.name] = item

    def remove_ship(self, name: str) -> None:
        """Remove a ship from selection."""
        if name in self.selected_ships:
            self.selected_ships.remove(name)
            self.selected_items.pop(name, None)

    def add_module(self, item: SelectedItem) -> None:
        """Add a module to selection."""
        if item.name not in self.selected_modules:
            self.selected_modules.append(item.name)
            self.selected_items[item.name] = item

    def remove_module(self, name: str) -> None:
        """Remove a module from selection."""
        if name in self.selected_modules:
            self.selected_modules.remove(name)
            self.selected_items.pop(name, None)

    def clear(self) -> None:
        """Clear all selections."""
        self.selected_ships.clear()
        self.selected_modules.clear()
        self.selected_items.clear()


# =============================================================================
# Selection Service
# =============================================================================

class SelectionService:
    """
    Service for managing ship and module selections.

    Provides methods for:
    - Managing selection state
    - Formatting selections for sidebar display
    - Generating CSV export data

    Example:
        service = SelectionService.create_default()

        # Add selection
        item = SelectedItem(type_id=34, name="Tritanium", stock=100)
        service.add_selection(item)

        # Get formatted sidebar text
        sidebar_text = service.format_sidebar_text()
    """

    def __init__(
        self,
        state: Optional[SelectionState] = None,
        logger_instance: Optional[logging.Logger] = None
    ):
        self._state = state or SelectionState()
        self._logger = logger_instance or logger

    @classmethod
    def create_default(cls) -> "SelectionService":
        """Factory method to create service with default state."""
        return cls()

    @property
    def state(self) -> SelectionState:
        """Get current selection state."""
        return self._state

    # -------------------------------------------------------------------------
    # Selection Management
    # -------------------------------------------------------------------------

    def add_selection(self, item: SelectedItem) -> None:
        """
        Add an item to the selection.

        Args:
            item: SelectedItem to add
        """
        if item.is_ship:
            self._state.add_ship(item)
        else:
            self._state.add_module(item)
        self._logger.debug(f"Added selection: {item.name}")

    def remove_selection(self, name: str, is_ship: bool = False) -> None:
        """
        Remove an item from the selection.

        Args:
            name: Item name to remove
            is_ship: Whether this is a ship
        """
        if is_ship:
            self._state.remove_ship(name)
        else:
            self._state.remove_module(name)
        self._logger.debug(f"Removed selection: {name}")

    def toggle_selection(self, item: SelectedItem) -> bool:
        """
        Toggle an item's selection state.

        Args:
            item: SelectedItem to toggle

        Returns:
            True if item is now selected, False if unselected
        """
        items_list = self._state.selected_ships if item.is_ship else self._state.selected_modules

        if item.name in items_list:
            self.remove_selection(item.name, item.is_ship)
            return False
        else:
            self.add_selection(item)
            return True

    def is_selected(self, name: str, is_ship: bool = False) -> bool:
        """Check if an item is selected."""
        if is_ship:
            return name in self._state.selected_ships
        return name in self._state.selected_modules

    def clear_selections(self) -> None:
        """Clear all selections."""
        self._state.clear()

    # -------------------------------------------------------------------------
    # Sidebar Formatting
    # -------------------------------------------------------------------------

    def format_sidebar_text(self) -> str:
        """
        Format current selections for sidebar display.

        Uses code block formatting for clean display.

        Returns:
            Formatted string for st.sidebar.code()
        """
        lines = []

        # Ships section
        if self._state.selected_ships:
            lines.append("Ships:")
            for name in self._state.selected_ships:
                item = self._state.selected_items.get(name)
                if item:
                    lines.append(f"  {item.to_display_string()}")
                else:
                    lines.append(f"  {name}")

        # Modules section
        if self._state.selected_modules:
            if lines:
                lines.append("")  # Blank line separator
            lines.append("Modules:")
            for name in self._state.selected_modules:
                item = self._state.selected_items.get(name)
                if item:
                    lines.append(f"  {item.to_display_string()}")
                else:
                    lines.append(f"  {name}")

        if not lines:
            return "No items selected"

        return "\n".join(lines)

    def format_selection_summary(self) -> dict:
        """
        Get summary statistics for current selections.

        Returns:
            Dict with counts and totals
        """
        ship_count = len(self._state.selected_ships)
        module_count = len(self._state.selected_modules)

        # Calculate totals by status
        critical = 0
        needs_attention = 0
        good = 0

        for item in self._state.selected_items.values():
            status = item.status
            if status == StockStatus.CRITICAL:
                critical += 1
            elif status == StockStatus.NEEDS_ATTENTION:
                needs_attention += 1
            else:
                good += 1

        return {
            "ship_count": ship_count,
            "module_count": module_count,
            "total_count": ship_count + module_count,
            "critical": critical,
            "needs_attention": needs_attention,
            "good": good,
        }

    # -------------------------------------------------------------------------
    # CSV Export
    # -------------------------------------------------------------------------

    def generate_csv_data(self) -> list[dict]:
        """
        Generate CSV export data for current selections.

        Returns:
            List of dicts suitable for CSV export
        """
        data = []
        for name, item in self._state.selected_items.items():
            data.append({
                "type_id": item.type_id,
                "name": item.name,
                "stock": item.stock,
                "target": item.target,
                "percentage": item.percentage,
                "status": item.status.display_name,
                "is_ship": item.is_ship,
                "fit_id": item.fit_id or "",
            })
        return data


# =============================================================================
# Status Formatting Helpers
# =============================================================================

def get_status_filter_options() -> list[str]:
    """
    Get standard status filter options.

    Returns:
        List of filter option strings
    """
    return [
        "All",
        "All Low Stock",
        StockStatus.CRITICAL.display_name,
        StockStatus.NEEDS_ATTENTION.display_name,
        StockStatus.GOOD.display_name,
    ]


def apply_status_filter(items: list, status_filter: str, get_status_func) -> list:
    """
    Apply status filter to a list of items.

    Args:
        items: List of items to filter
        status_filter: Filter string from get_status_filter_options()
        get_status_func: Function that takes an item and returns StockStatus

    Returns:
        Filtered list of items
    """
    if status_filter == "All":
        return items

    if status_filter == "All Low Stock":
        return [item for item in items if get_status_func(item) != StockStatus.GOOD]

    # Filter by specific status
    target_status = StockStatus.from_string(status_filter)
    return [item for item in items if get_status_func(item) == target_status]


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_selection_service() -> SelectionService:
    """
    Get or create a SelectionService instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.

    Returns:
        SelectionService instance
    """
    try:
        from state import get_service
        return get_service('selection_service', SelectionService.create_default)
    except ImportError:
        logger.debug("state module unavailable, creating new SelectionService instance")
        return SelectionService.create_default()


def render_sidebar_selections(service: SelectionService) -> None:
    """
    Render current selections in the sidebar.

    Args:
        service: SelectionService instance
    """
    import streamlit as st

    summary = service.format_selection_summary()

    if summary["total_count"] > 0:
        st.sidebar.subheader("Selected Items")

        # Summary metrics
        col1, col2 = st.sidebar.columns(2)
        with col1:
            st.metric("Ships", summary["ship_count"])
        with col2:
            st.metric("Modules", summary["module_count"])

        # Status breakdown
        if summary["critical"] > 0:
            st.sidebar.markdown(f":red[Critical: {summary['critical']}]")
        if summary["needs_attention"] > 0:
            st.sidebar.markdown(f":orange[Low: {summary['needs_attention']}]")

        # Formatted selection list
        st.sidebar.code(service.format_sidebar_text(), language=None)

        # Clear button
        if st.sidebar.button("Clear Selections", use_container_width=True):
            service.clear_selections()
            st.rerun()
    else:
        st.sidebar.info("No items selected")
