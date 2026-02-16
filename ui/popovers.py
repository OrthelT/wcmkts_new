"""
Market Data Popovers

Reusable popover components for displaying market data
on item names in doctrine pages.

Design Principles:
- Self-contained popover rendering
- Fetches data on demand (lazy loading)
- Uses caching for repeated lookups
"""

import streamlit as st
import pandas as pd
from typing import Optional
from millify import millify

from ui.formatters import get_image_url


def format_price(price: float) -> str:
    """Format price for display."""
    if price is None or price == 0:
        return "N/A"
    return millify(price, precision=2)


def get_item_market_data(type_id: int, type_name: str) -> dict:
    """
    Get market data for an item from marketstats.

    Args:
        type_id: EVE type ID
        type_name: Item name for display

    Returns:
        Dict with market stats or empty dict if not found
    """
    from repositories import get_market_repository

    try:
        repo = get_market_repository()
        stats_df = repo.get_all_stats()
        item_stats = stats_df[stats_df["type_id"] == type_id]

        if item_stats.empty:
            return {}

        row = item_stats.iloc[0]
        return {
            "type_id": type_id,
            "type_name": type_name,
            "price": row.get("price", 0),
            "min_price": row.get("min_price", 0),
            "avg_price": row.get("avg_price", 0),
            "avg_volume": row.get("avg_volume", 0),
            "total_volume_remain": row.get("total_volume_remain", 0),
            "days_remaining": row.get("days_remaining", 0),
            "category_name": row.get("category_name", ""),
            "group_name": row.get("group_name", ""),
        }

    except Exception:
        return {}


def get_doctrine_usage(type_id: int) -> list[dict]:
    """
    Get doctrine usage information for an item.

    Args:
        type_id: EVE type ID

    Returns:
        List of dicts with ship_name, fit_qty, fits_on_mkt
    """
    from config import DatabaseConfig
    from sqlalchemy import text

    try:
        mkt_db = DatabaseConfig("wcmkt")
        query = text("""
            SELECT DISTINCT ship_name, fit_qty, fits_on_mkt
            FROM doctrines
            WHERE type_id = :type_id
        """)

        with mkt_db.engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"type_id": type_id})

        return df.to_dict("records")

    except Exception:
        return []


def get_equivalent_modules(type_id: int) -> list[dict]:
    """
    Get equivalent modules for an item.

    Args:
        type_id: EVE type ID

    Returns:
        List of dicts with type_id, type_name, stock, price for each
        equivalent module, or empty list if no equivalents
    """
    try:
        from services import get_module_equivalents_service

        equiv_service = get_module_equivalents_service()
        group = equiv_service.get_equivalence_group(type_id)

        if not group or len(group.modules) <= 1:
            return []

        return [
            {
                "type_id": m.type_id,
                "type_name": m.type_name,
                "stock": m.stock,
                "price": m.price,
            }
            for m in group.modules
        ]

    except Exception:
        return []


def has_equivalent_modules(type_id: int) -> bool:
    """
    Check if a module has equivalent interchangeable modules.

    Args:
        type_id: EVE type ID

    Returns:
        True if module has equivalents, False otherwise
    """
    try:
        from services import get_module_equivalents_service

        equiv_service = get_module_equivalents_service()
        return equiv_service.has_equivalents(type_id)

    except Exception:
        return False


def get_equivalents_indicator(type_id: int) -> str:
    """
    Get the equivalents indicator icon if module has equivalents.

    Args:
        type_id: EVE type ID

    Returns:
        "🔄 " if module has equivalents, empty string otherwise
    """
    if has_equivalent_modules(type_id):
        return "🔄 "
    return ""


def get_jita_price(type_id: int) -> float:
    """
    Get Jita sell price for an item.

    Args:
        type_id: EVE type ID

    Returns:
        Jita sell price or 0.0 if not found
    """
    from services import get_price_service

    try:
        price_service = get_price_service()
        result = price_service.get_jita_prices([type_id])
        # Use BatchPriceResult.get_price() which returns float, not PriceResult
        return result.get_price(type_id, default=0.0)
    except Exception:
        return 0.0


def render_market_popover(
    type_id: int,
    type_name: str,
    quantity: int = 1,
    display_text: Optional[str] = None,
    show_doctrine_usage: bool = True,
    show_jita: bool = False,
    show_equivalents: bool = True,
    key_suffix: str = "",
    jita_prices: Optional[dict[int, float]] = None,
) -> None:
    """
    Render a clickable item name with a market data popover.

    Args:
        type_id: EVE type ID
        type_name: Item name
        quantity: Quantity to show (default 1)
        display_text: Text to display (defaults to type_name)
        show_doctrine_usage: Whether to show doctrine usage info
        show_jita: Whether to show Jita prices (default False to avoid API calls)
        show_equivalents: Whether to show equivalent modules section
        key_suffix: Unique suffix for the popover key
        jita_prices: Pre-fetched Jita prices dict {type_id: price} to avoid API calls
    """
    display = display_text or type_name
    unique_key = f"popover_{type_id}_{key_suffix}"

    with st.popover(display, width="content", type="tertiary"):
        # Header with image
        col1, col2 = st.columns([0.25, 0.75])

        with col1:
            is_ship = False
            market_data = get_item_market_data(type_id, type_name)
            if market_data.get("category_name") == "Ship":
                is_ship = True
            st.image(get_image_url(type_id, 64, isship=is_ship), width=64)

        with col2:
            st.markdown(f"**{type_name}**")
            st.caption(f"Type ID: {type_id}")
            if quantity > 1:
                st.caption(f"Qty: {quantity:,}")

        st.divider()

        # Check for equivalent modules
        equiv_modules = []
        if show_equivalents:
            equiv_modules = get_equivalent_modules(type_id)

        # Market data
        if market_data:
            try:
                from state.market_state import get_active_market
                _mkt_name = get_active_market().name
            except Exception:
                _mkt_name = "Local Market"
            st.markdown(f"**{_mkt_name}**")

            # If has equivalents, show combined stock
            if equiv_modules:
                combined_stock = sum(m["stock"] for m in equiv_modules)
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Price", format_price(market_data.get("price", 0)))
                with col2:
                    st.metric("Stock (Combined)", f"{combined_stock:,}")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Price", format_price(market_data.get("price", 0)))
                with col2:
                    st.metric("Stock", f"{market_data.get('total_volume_remain', 0):,}")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Avg/Day", format_price(market_data.get("avg_volume", 0)))
            with col2:
                days = market_data.get("days_remaining", 0)
                if days > 0:
                    st.metric("Days Stock", f"{days:.1f}")
                else:
                    st.metric("Days Stock", "N/A")

            # Jita price comparison
            if show_jita or jita_prices:
                # Use pre-fetched price if available, otherwise fetch
                if jita_prices and type_id in jita_prices:
                    jita_price = jita_prices[type_id]
                elif show_jita:
                    jita_price = get_jita_price(type_id)
                else:
                    jita_price = 0.0

                if jita_price > 0:
                    st.divider()
                    st.markdown("**Jita**")
                    local_price = market_data.get("price", 0)

                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Jita Sell", format_price(jita_price))
                    with col2:
                        if local_price > 0:
                            delta_pct = ((local_price - jita_price) / jita_price) * 100
                            st.metric("vs 4-H", f"{delta_pct:+.1f}%")

        else:
            st.info("No market data available")

        # Equivalent modules section
        if equiv_modules:
            st.divider()
            st.markdown("**Equivalent Modules (combined)**")
            combined_stock = sum(m["stock"] for m in equiv_modules)

            for mod in equiv_modules:
                mod_name = mod["type_name"]
                mod_stock = mod["stock"]
                mod_type_id = mod["type_id"]

                # Show which fits use this specific equivalent
                mod_usage = get_doctrine_usage(mod_type_id) if show_doctrine_usage else []
                fit_names = [u.get("ship_name", "") for u in mod_usage[:3]]
                usage_suffix = f" (used in: {', '.join(fit_names)})" if fit_names else ""

                if mod_type_id == type_id:
                    st.text(f"  ► {mod_name}: {mod_stock:,}{usage_suffix}")
                else:
                    st.text(f"  {mod_name}: {mod_stock:,}{usage_suffix}")

            st.caption(f"  **Total: {combined_stock:,}**")

        # Doctrine usage
        if show_doctrine_usage:
            usage = get_doctrine_usage(type_id)
            if usage:
                st.divider()
                st.markdown("**Used In Fits**")
                for item in usage[:5]:  # Limit to 5 fits
                    ship = item.get("ship_name", "Unknown")
                    qty = item.get("fit_qty", 0)
                    fits = item.get("fits_on_mkt", 0)
                    st.text(f"  {ship}: {qty}x ({int(fits)} fits)")

                if len(usage) > 5:
                    st.caption(f"  ...and {len(usage) - 5} more")


def render_item_with_popover(
    type_id: int,
    type_name: str,
    quantity: int = 1,
    stock: int = 0,
    show_stock: bool = True,
    key_suffix: str = "",
) -> None:
    """
    Render an item display with market popover.

    Format: "Item Name (stock)" with popover on click.

    Args:
        type_id: EVE type ID
        type_name: Item name
        quantity: Quantity in fit
        stock: Current stock on market
        show_stock: Whether to show stock in display text
        key_suffix: Unique key suffix
    """
    if show_stock:
        display_text = f"{type_name} ({stock:,})"
    else:
        display_text = type_name

    render_market_popover(
        type_id=type_id,
        type_name=type_name,
        quantity=quantity,
        display_text=display_text,
        key_suffix=key_suffix,
    )


def render_ship_with_popover(
    ship_id: int,
    ship_name: str,
    fits: int = 0,
    hulls: int = 0,
    target: int = 0,
    key_suffix: str = "",
) -> None:
    """
    Render a ship display with market popover.

    Args:
        ship_id: Ship type ID
        ship_name: Ship name
        fits: Number of fits on market
        hulls: Number of hulls on market
        target: Target stock level
        key_suffix: Unique key suffix
    """
    with st.popover(ship_name, width="content", type="tertiary"):
        # Header with ship image
        col1, col2 = st.columns([0.3, 0.7])

        with col1:
            st.image(get_image_url(ship_id, 128, isship=True), width=128)

        with col2:
            st.markdown(f"**{ship_name}**")
            st.caption(f"Type ID: {ship_id}")

        st.divider()

        # Stock metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Fits", fits)
        with col2:
            st.metric("Hulls", hulls)
        with col3:
            st.metric("Target", target)

        # Market data
        market_data = get_item_market_data(ship_id, ship_name)
        if market_data:
            st.divider()
            st.markdown("**Market Data**")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Price", format_price(market_data.get("price", 0)))
            with col2:
                st.metric("Stock", f"{market_data.get('total_volume_remain', 0):,}")

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Avg/Day", format_price(market_data.get("avg_volume", 0)))
            with col2:
                days = market_data.get("days_remaining", 0)
                st.metric("Days Stock", f"{days:.1f}" if days > 0 else "N/A")
