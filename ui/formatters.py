"""
UI Formatting Utilities

Helper functions for consistent display formatting across Streamlit pages.
These functions handle common UI patterns like color coding, text formatting,
and status display.

Design Principles:
- Pure functions with no side effects
- Use domain enums (StockStatus) for business logic
- Return simple types (str, tuple) for flexibility
"""

import streamlit as st

from domain.enums import ShipRole, StockStatus

def format_module_list(modules_list: list[str]) -> str:
    """
    Format a list of modules for HTML display.

    Args:
        modules_list: List of module strings

    Returns:
        HTML-formatted string with <br> separators
    """
    if not modules_list:
        return ""
    return "<br>".join(modules_list)


def format_price(price: float, precision: int = 2) -> str:
    """
    Format a price value with millify notation.

    Args:
        price: Price in ISK
        precision: Number of decimal places

    Returns:
        Formatted price string (e.g., "1.5M", "250K")
    """
    from millify import millify

    if price is None or price == 0:
        return "N/A"
    return millify(price, precision=precision)


def get_status_badge_color(status: StockStatus) -> str:
    """
    Get Streamlit badge color for a stock status.

    Args:
        status: StockStatus enum value

    Returns:
        Color string for st.badge() ("red", "orange", "green")
    """
    return status.display_color


def get_status_from_percentage(percentage: float) -> tuple[str, str]:
    """
    Get status name and color from a target percentage.

    Args:
        percentage: Target percentage (0-100+)

    Returns:
        Tuple of (status_name, color)
    """
    status = StockStatus.from_percentage(percentage)
    return status.display_name, status.display_color


def get_progress_bar_color(percentage: float) -> str:
    """
    Get progress bar color based on percentage.

    Uses consistent thresholds from StockStatus:
    - >= 90%: green
    - >= 20%: orange (adjusted from 50% for visual balance)
    - < 20%: red

    Args:
        percentage: Target percentage (0-100)

    Returns:
        Color string for CSS styling
    """
    if percentage >= 90:
        return "green"
    elif percentage >= 50:
        return "orange"
    else:
        return "red"


def get_progress_bar_background(percentage: float) -> str:
    """
    Get progress bar background color for empty portion.

    Args:
        percentage: Target percentage (0-100)

    Returns:
        CSS color string
    """
    if percentage == 0:
        return "#5c1f06"  # Dark red for empty
    return "#333"  # Standard dark background


def render_progress_bar_html(percentage: float, height: int = 20) -> str:
    """
    Generate HTML for a styled progress bar.

    Args:
        percentage: Target percentage (0-100)
        height: Bar height in pixels

    Returns:
        Complete HTML string for the progress bar
    """
    color = get_progress_bar_color(percentage)
    bg_color = get_progress_bar_background(percentage)

    return f"""
    <div style="margin-top: 5px;">
        <div style="background-color: {bg_color}; width: 100%; height: {height}px; border-radius: 3px;">
            <div style="background-color: {color}; width: {percentage}%; height: {height}px; border-radius: 3px; text-align: center; line-height: {height}px; color: white; font-weight: bold;">
                {int(percentage)}%
            </div>
        </div>
    </div>
    """


def format_delta_percentage(delta: float) -> str:
    """
    Format a delta percentage for metric display.

    Args:
        delta: Percentage difference

    Returns:
        Formatted string with sign (e.g., "+5.2%", "-3.1%")
    """
    if delta is None:
        return ""
    return f"{delta:+.2f}%"


def parse_module_display_string(module_str: str) -> tuple[str, int]:
    """
    Parse a module display string into name and quantity.

    Args:
        module_str: String like "Damage Control II (15)"

    Returns:
        Tuple of (module_name, quantity)
    """
    try:
        # Split on " (" to separate name from quantity
        parts = module_str.rsplit(" (", 1)
        if len(parts) == 2:
            name = parts[0]
            qty_str = parts[1].rstrip(")")
            return name, int(qty_str)
    except (ValueError, IndexError):
        pass

    return module_str, 0

def display_build_cost_tool_description() -> str:
    return """
    - <span style="font-weight: bold; color: orange;">Runs:</span> The number of runs to calculate the cost for.
    - <span style="font-weight: bold; color: orange;">ME:</span> The material efficiency of the blueprint. (default 0)
    - <span style="font-weight: bold; color: orange;">TE:</span> The time efficiency of the blueprint. (default 0)
    - <span style="font-weight: bold; color: orange;">Material price source:</span> The source of the material prices used in the calculations.
        - *ESI Average* - the CCP average price used in the in-game industry window.
        - *Jita Sell* - the minimum price of sale orders in Jita.
        - *Jita Buy* - the maximum price of buy orders in Jita.
    - <span style="font-weight: bold; color: orange;">Structure:</span> The structure to compare the cost to build versus. (optional)
    - <span style="font-weight: bold; color: orange;">Skills:</span> All skills are assumed to be at level 5.
    """


def get_ship_role_format(role: str) -> str:
    """
    Get formatted display string for a ship role.

    Args:
        role: Role name string ("DPS", "Logi", "Links", "Support")

    Returns:
        Formatted string with emoji, bold name, and description
        e.g., "💥 **DPS** - Primary DPS Ships"
    """
    ship_role = ShipRole.from_string(role)
    return f"{ship_role.display_emoji} **{ship_role.display_name}** - {ship_role.description}"

def get_doctrine_report_column_config() -> dict:
    """
    Get the column configuration for the doctrine_report.py display table.
    Returns:
        Column configuration for the doctrine_report.py display table
    """
    config = {'target_percentage': st.column_config.ProgressColumn(
                        "Target %",
                        format="percent",
                        width="medium",
                    ),
            'ship_target': st.column_config.Column(
                "Target",
                help="Number of fits required for stock",

            ),
            'daily_avg': st.column_config.NumberColumn(
                "Daily Sales",
                help="Average daily sales over the last 30 days"
            ),
            'ship_group': st.column_config.Column(
                "Group",
                help="Ship group"
            ),
            'ship_name': st.column_config.Column(
                "Ship",
                help="Ship name"
            ),
            'ship_id': st.column_config.Column(
                "Type ID",
                help="Ship ID"
            ),
            'fit_id': st.column_config.Column(
                "Fit ID",
                help="Fit ID"
            ),
            'price': st.column_config.NumberColumn(
                "Price",
                format="compact",
                help="Price of the ship"
            ),
            'total_cost': st.column_config.NumberColumn(
                "Total Cost",
                format="compact",
                help="Total cost of the fit"
            ) 
            }
    return config

def get_image_url(type_id: int, size: int = 64) -> str:
    """
    Get the image URL for a type.

    Args:
        type_id: Type ID
        size: Size of the image

    Returns:
        Image URL for the type
    """
    return f"https://images.evetech.net/types/{type_id}/render?size={size}"

