"""
UI Package

Presentation layer components for Streamlit pages.
Contains column definitions, formatting utilities, and display configuration.

This package separates UI-specific concerns from business logic,
keeping page files focused on layout and user interaction.
"""

from ui.column_definitions import (
    get_fitting_column_config,
    get_summary_column_config,
)
from ui.formatters import (
    format_module_list,
    format_price,
    get_status_badge_color,
    get_progress_bar_color,
    render_progress_bar_html,
)
from ui.popovers import (
    render_market_popover,
    render_item_with_popover,
    render_ship_with_popover,
)

__all__ = [
    # Column configs
    "get_fitting_column_config",
    "get_summary_column_config",
    # Formatters
    "format_module_list",
    "format_price",
    "get_status_badge_color",
    "get_progress_bar_color",
    "render_progress_bar_html",
    # Popovers
    "render_market_popover",
    "render_item_with_popover",
    "render_ship_with_popover",
]
