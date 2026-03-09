"""
Import Helper Page

Shows local market items with Jita comparison data for import decisions.
"""

import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from services import ImportHelperFilters
from services.import_helper_service import get_import_helper_service
from ui.column_definitions import get_import_helper_column_config
from ui.market_selector import render_market_selector
from ui.sync_display import display_sync_status

logger = setup_logging(__name__, log_file="import_helper.log")


def main():
    market = render_market_selector()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    service = get_import_helper_service()

    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image("images/wclogo.png", width=125)
    with col2:
        st.title(f"{market.name} Import Helper")

    from services.import_helper_service import SHIPPING_COST_PER_M3

    st.markdown(
        f"""
        Discover items where the local market price sits well above Jita sell.
        Shipping Cost is `m3 * {SHIPPING_COST_PER_M3:g}`, Profit uses `Local Price - (Jita Sell + Shipping)`,
        30D Profit uses `Profit * Avg Daily Volume * 30`,
        RRP (Recommended Retail Price) uses `Jita Sell * (1 + Markup Margin) + Shipping`,
        and Cap Utilis (Capital Utilisation Efficiency) = `Profit / Jita Sell`, indicating the invest-reward ratio.
        """
    )

    st.sidebar.header("Filters")
    categories = service.get_category_options()

    selected_categories = st.sidebar.multiselect(
        "Categories",
        options=categories,
        default=[],
        help="Limit the table to one or more item categories.",
    )
    search_text = st.sidebar.text_input(
        "Search Items",
        value="",
        help="Case-insensitive name filter.",
    )
    profitable_only = st.sidebar.checkbox(
        "Positive Profit Only",
        value=True,
        help="Hide items where the local market price is not above Jita sell.",
    )
    min_capital_utilis = st.sidebar.number_input(
        "Minimum Capital Utilis",
        min_value=0.0,
        max_value=5.0,
        value=0.0,
        step=0.05,
        format="%.2f",
        help="0.10 means at least 10% capital utilisation after shipping.",
    )
    min_turnover_30d = st.sidebar.number_input(
        "Minimum 30D Turnover",
        min_value=0,
        value=0,
        step=200_000_000,
        help="Hide items whose 30D Turnover is below this value.",
    )
    markup_margin = st.sidebar.number_input(
        "Markup Margin",
        min_value=0.0,
        value=0.2,
        step=0.05,
        format="%.2f",
        help="Used for RRP. 0.20 means 20% above Jita sell.",
    )

    filters = ImportHelperFilters(
        categories=selected_categories,
        search_text=search_text,
        profitable_only=profitable_only,
        min_capital_utilis=min_capital_utilis,
        min_turnover_30d=float(min_turnover_30d),
        markup_margin=float(markup_margin),
    )

    try:
        base_df = service.fetch_base_data()
    except Exception as e:
        logger.error(f"Import helper data load failed: {e}")
        st.error("Failed to load market data. Check database connectivity and try refreshing.")
        st.stop()

    df = service.get_import_items(base_df, filters)
    if df.empty:
        st.warning("No items found with the selected filters.")
        st.sidebar.markdown("---")
        display_sync_status()
        return

    stats = service.get_summary_stats(df)
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric("Total Items", stats["total_items"])
    with metric_col2:
        st.metric("Positive Profit Items", stats["profitable_items"])
    with metric_col3:
        st.metric("Avg Capital Utilis", f"{stats['avg_capital_utilis']:.1%}")

    display_df = df[
        [
            "type_id",
            "type_name",
            "price",
            "rrp",
            "jita_sell_price",
            "jita_buy_price",
            "shipping_cost",
            "profit_jita_sell_30d",
            "turnover_30d",
            "volume_30d",
            "capital_utilis",
        ]
    ].copy()
    money_columns = [
        "price",
        "rrp",
        "jita_sell_price",
        "jita_buy_price",
        "shipping_cost",
        "profit_jita_sell_30d",
        "turnover_30d",
    ]
    display_df[money_columns] = display_df[money_columns].round().astype("Int64")
    display_df["volume_30d"] = display_df["volume_30d"].round().astype("Int64")

    st.dataframe(
        display_df,
        hide_index=True,
        width="content",
        column_config=get_import_helper_column_config(),
    )

    st.sidebar.markdown("---")
    display_sync_status()


if __name__ == "__main__":
    main()
