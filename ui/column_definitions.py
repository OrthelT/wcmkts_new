"""
Column Definitions for Streamlit DataFrames

Centralized Streamlit column_config definitions for consistent
DataFrame display across all pages.

These configurations define:
- Column labels and help text
- Data formatting (numbers, percentages, currency)
- Column widths
- Display types (NumberColumn, TextColumn, etc.)

Usage:
    from ui import get_fitting_column_config

    st.dataframe(
        fit_df,
        column_config=get_fitting_column_config(),
        hide_index=True
    )
"""

import streamlit as st

from ui.i18n import translate_text


def get_fitting_column_config() -> dict:
    """
    Get column configuration for fitting detail data display.

    Used when showing individual fit items (modules, hull, ammo).

    Returns:
        Dict of column name -> st.column_config configuration
    """
    return {
        'fit_id': st.column_config.NumberColumn(
            "Fit ID",
            help="WC Doctrine Fit ID"
        ),
        'ship_name': st.column_config.TextColumn(
            "Ship Name",
            help="Ship Name",
        ),
        'type_id': st.column_config.NumberColumn(
            "Type ID",
            help="Type ID"
        ),
        'type_name': st.column_config.TextColumn(
            "Type Name",
            help="Type Name",
            width="medium"
        ),
        'fit_qty': st.column_config.NumberColumn(
            "Qty/fit",
            help="Quantity of this item per fit",
            width="small"
        ),
        'Fits on Market': st.column_config.NumberColumn(
            "Fits",
            help="Total fits available on market for this item",
            width="small"
        ),
        'fits_on_mkt': st.column_config.NumberColumn(
            "Fits",
            help="Total fits available on market for this item",
            width="small"
        ),
        'total_stock': st.column_config.NumberColumn(
            "Stock",
            help="Total stock of this item",
            width="small"
        ),
        'price': st.column_config.NumberColumn(
            "Price",
            help="Price of this item",
            format="localized"
        ),
        'avg_vol': st.column_config.NumberColumn(
            "Avg Vol",
            help="Average volume over the last 30 days",
            width="small"
        ),
        'days': st.column_config.NumberColumn(
            "Days",
            help="Days remaining (based on historical average)",
            width="small"
        ),
        'group_name': st.column_config.Column(
            "Group",
            help="Group of this item",
            width="small"
        ),
        'category_id': st.column_config.NumberColumn(
            "Category ID",
            help="Category ID (ships are 6)",
            width="small"
        ),
    }


def get_summary_column_config() -> dict:
    """
    Get column configuration for fit summary display.

    Used when showing aggregated fit status (one row per fit).

    Returns:
        Dict of column name -> st.column_config configuration
    """
    return {
        'fit_id': st.column_config.NumberColumn(
            "Fit ID",
            help="WC Doctrine Fit ID",
            width="small"
        ),
        'ship_name': st.column_config.TextColumn(
            "Ship",
            help="Ship name",
            width="medium"
        ),
        'fits': st.column_config.NumberColumn(
            "Fits",
            help="Number of complete fits available",
            width="small"
        ),
        'hulls': st.column_config.NumberColumn(
            "Hulls",
            help="Number of ship hulls in stock",
            width="small"
        ),
        'ship_target': st.column_config.NumberColumn(
            "Target",
            help="Target number of fits to maintain",
            width="small"
        ),
        'target_percentage': st.column_config.ProgressColumn(
            "Status",
            help="Percentage of target achieved",
            min_value=0,
            max_value=100,
            format="%d%%"
        ),
        'total_cost': st.column_config.NumberColumn(
            "Fit Cost",
            help="Total cost of the fit",
            format="localized"
        ),
        'ship_group': st.column_config.TextColumn(
            "Group",
            help="Ship group classification",
            width="small"
        ),
    }


def get_export_column_config() -> dict:
    """
    Get column configuration for export/download views.

    Minimal formatting for clean CSV/data export.

    Returns:
        Dict of column name -> st.column_config configuration
    """
    return {
        'type_name': st.column_config.TextColumn("Type"),
        'type_id': st.column_config.NumberColumn("Type ID"),
        'total_stock': st.column_config.NumberColumn("Stock"),
        'fits_on_mkt': st.column_config.NumberColumn("Fits"),
        'ship_target': st.column_config.NumberColumn("Target"),
    }


def get_import_helper_column_config(
    language_code: str = "en",
    shipping_cost_per_m3: float = 445,
) -> dict:
    """Get column configuration for Import Helper table display."""
    return {
        "type_id": st.column_config.NumberColumn(
            translate_text(language_code, "common.type_id"),
            help="EVE type ID.",
            width="small",
        ),
        "type_name": st.column_config.TextColumn(
            translate_text(language_code, "common.item"),
            help=translate_text(language_code, "import_helper.column_item_help"),
            width="medium",
        ),
        "price": st.column_config.NumberColumn(
            translate_text(language_code, "common.price"),
            help="Current local market price.",
            format="localized",
        ),
        "rrp": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_rrp"),
            help=translate_text(language_code, "import_helper.column_rrp_help"),
            format="localized",
        ),
        "jita_sell_price": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_jita_sell"),
            help=translate_text(language_code, "import_helper.column_jita_sell_help"),
            format="localized",
        ),
        "jita_buy_price": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_jita_buy"),
            help=translate_text(language_code, "import_helper.column_jita_buy_help"),
            format="localized",
        ),
        "shipping_cost": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_shipping"),
            help=translate_text(
                language_code,
                "import_helper.column_shipping_help",
                shipping_cost_per_m3=f"{shipping_cost_per_m3:g}",
            ),
            format="localized",
        ),
        "profit_jita_sell_30d": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_profit_30d"),
            help=translate_text(language_code, "import_helper.column_profit_30d_help"),
            format="compact",
        ),
        "turnover_30d": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_turnover_30d"),
            help=translate_text(language_code, "import_helper.column_turnover_30d_help"),
            format="compact",
        ),
        "volume_30d": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_volume_30d"),
            help=translate_text(language_code, "import_helper.column_volume_30d_help"),
            format="localized",
        ),
        "capital_utilis": st.column_config.NumberColumn(
            translate_text(language_code, "import_helper.column_capital_utilis"),
            help=translate_text(language_code, "import_helper.column_capital_utilis_help"),
            format="percent",
        ),
    }
