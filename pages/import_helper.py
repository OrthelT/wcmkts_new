"""
Import Helper Page

Shows local market items with Jita comparison data for import decisions.
"""

import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from services import ImportHelperFilters, get_import_helper_service
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

    st.markdown(
        """
        Discover items where the local market price sits well below Jita sell.
        Shipping Cost is `m3 * 500`, Profit uses `Jita Sell - Local Price`,
        and Capital Utilis uses `(Profit - Shipping Cost) / Jita Sell`.
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
        help="Hide items where Jita sell is not above the local market price.",
    )
    min_capital_utilis = st.sidebar.number_input(
        "Minimum Capital Utilis",
        min_value=-5.0,
        max_value=5.0,
        value=0.0,
        step=0.05,
        format="%.2f",
        help="0.10 means at least 10% capital utilisation after shipping.",
    )

    filters = ImportHelperFilters(
        categories=selected_categories,
        search_text=search_text,
        profitable_only=profitable_only,
        min_capital_utilis=min_capital_utilis,
    )

    df = service.get_import_items(filters)
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
            "jita_sell_price",
            "jita_buy_price",
            "shipping_cost",
            "profit_jita_sell",
            "volume_30d",
            "capital_utilis",
        ]
    ].copy()

    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config=get_import_helper_column_config(),
    )

    st.sidebar.markdown("---")
    display_sync_status()


if __name__ == "__main__":
    main()
