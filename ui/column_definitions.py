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


def get_fitting_column_config(language_code: str = "en") -> dict:
    """
    Get column configuration for fitting detail data display.

    Used when showing individual fit items (modules, hull, ammo).

    Returns:
        Dict of column name -> st.column_config configuration
    """
    return {
        'fit_id': st.column_config.NumberColumn(
            translate_text(language_code, "doctrine_report.column_fit_id"),
            help=translate_text(language_code, "doctrine_report.column_fit_id_help")
        ),
        'ship_name': st.column_config.TextColumn(
            translate_text(language_code, "doctrine_report.column_ship"),
            help=translate_text(language_code, "doctrine_report.column_ship_help"),
        ),
        'type_id': st.column_config.NumberColumn(
            translate_text(language_code, "common.type_id"),
            help=translate_text(language_code, "doctrine_report.column_ship_id_help")
        ),
        'type_name': st.column_config.TextColumn(
            translate_text(language_code, "common.item"),
            help=translate_text(language_code, "low_stock.column_item_help"),
            width="medium"
        ),
        'fit_qty': st.column_config.NumberColumn(
            translate_text(language_code, "doctrine_status.column_qty_per_fit"),
            help=translate_text(language_code, "doctrine_status.column_qty_per_fit_help"),
            width="small"
        ),
        'Fits on Market': st.column_config.NumberColumn(
            translate_text(language_code, "low_stock.column_fits"),
            help=translate_text(language_code, "low_stock.column_fits_help"),
            width="small"
        ),
        'fits_on_mkt': st.column_config.NumberColumn(
            translate_text(language_code, "low_stock.column_fits"),
            help=translate_text(language_code, "low_stock.column_fits_help"),
            width="small"
        ),
        'total_stock': st.column_config.NumberColumn(
            translate_text(language_code, "market_stats.market_stock"),
            help=translate_text(language_code, "doctrine_status.column_total_stock_help"),
            width="small"
        ),
        'price': st.column_config.NumberColumn(
            translate_text(language_code, "common.price"),
            help=translate_text(language_code, "doctrine_report.column_price_help"),
            format="localized"
        ),
        'avg_vol': st.column_config.NumberColumn(
            translate_text(language_code, "low_stock.column_avg_vol"),
            help=translate_text(language_code, "low_stock.column_avg_vol_help"),
            width="small"
        ),
        'days': st.column_config.NumberColumn(
            translate_text(language_code, "low_stock.column_days"),
            help=translate_text(language_code, "low_stock.column_days_help"),
            width="small"
        ),
        'group_name': st.column_config.Column(
            translate_text(language_code, "low_stock.column_group"),
            help=translate_text(language_code, "low_stock.column_group_help"),
            width="small"
        ),
        'category_id': st.column_config.NumberColumn(
            translate_text(language_code, "doctrine_status.column_category_id"),
            help=translate_text(language_code, "doctrine_status.column_category_id_help"),
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
            width="large",
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
                shipping_cost_per_m3=shipping_cost_per_m3,
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
