"""
Builder Helper Page (Prototype)

Displays manufacture cost vs. market price data for a fixed list of items,
helping builders identify the most profitable items to manufacture.
"""

import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from state import get_active_language
from services.builder_helper_service import get_builder_helper_service
from ui.column_definitions import get_builder_helper_column_config
from ui.i18n import translate_text
from ui.market_selector import render_market_selector
from ui.sync_display import display_sync_status
from pages.components.header import render_page_title

logger = setup_logging(__name__, log_file="builder_helper.log")


def main():
    language_code = get_active_language()
    market = render_market_selector()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    render_page_title(translate_text(language_code, "builder_helper.title"))

    st.markdown(translate_text(language_code, "builder_helper.description"))

    service = get_builder_helper_service()

    price_basis_options = {
        "avg": translate_text(language_code, "builder_helper.price_basis_avg"),
        "current": translate_text(language_code, "builder_helper.price_basis_current"),
    }
    price_basis = st.segmented_control(
        translate_text(language_code, "builder_helper.price_basis_label"),
        options=list(price_basis_options.keys()),
        format_func=lambda key: price_basis_options[key],
        default="avg",
        key="builder_helper_price_basis",
    )
    if price_basis not in price_basis_options:
        price_basis = "avg"

    with st.spinner(translate_text(language_code, "builder_helper.loading")):
        try:
            df = service.get_builder_data(
                language_code=language_code,
                price_basis=price_basis,
            )
        except Exception as exc:
            logger.error("Builder helper data load failed: %s", exc)
            st.error(translate_text(language_code, "builder_helper.error_loading_data"))
            st.stop()

    if df.empty:
        st.warning(translate_text(language_code, "builder_helper.no_data"))
        display_sync_status(language_code=language_code)
        return

    # -----------------------------------------------------------------------
    # Sidebar filters
    # -----------------------------------------------------------------------
    st.sidebar.header(translate_text(language_code, "builder_helper.filters_header"))

    category_options = sorted(df["category"].dropna().unique().tolist())
    selected_categories = st.sidebar.multiselect(
        translate_text(language_code, "builder_helper.categories"),
        options=category_options,
        default=[],
        help=translate_text(language_code, "builder_helper.categories_help"),
    )

    search_text = st.sidebar.text_input(
        translate_text(language_code, "builder_helper.search_items"),
        value="",
        help=translate_text(language_code, "builder_helper.search_items_help"),
    )

    min_cap_utils = st.sidebar.number_input(
        translate_text(language_code, "import_helper.min_capital_utilis"),
        min_value=0.0,
        max_value=5.0,
        value=0.0,
        step=0.05,
        format="%.2f",
        help=translate_text(language_code, "import_helper.min_capital_utilis_help"),
    )

    min_turnover_30d = st.sidebar.number_input(
        translate_text(language_code, "import_helper.min_turnover_30d"),
        min_value=0,
        value=0,
        step=200_000_000,
        help=translate_text(language_code, "import_helper.min_turnover_30d_help"),
    )

    profitable_only = st.sidebar.checkbox(
        translate_text(language_code, "import_helper.profitable_only"),
        value=True,
        help=translate_text(language_code, "import_helper.profitable_only_help"),
    )

    show_zero_volume = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.show_zero_volume_items"),
        value=False,
        help=translate_text(language_code, "low_stock.show_zero_volume_items_help"),
    )

    # -----------------------------------------------------------------------
    # Apply filters
    # -----------------------------------------------------------------------
    filtered_df = df.copy()

    if profitable_only:
        filtered_df = filtered_df[filtered_df["cap_utils"].fillna(0) > 0]

    if not show_zero_volume:
        filtered_df = filtered_df[filtered_df["volume_30d"].fillna(0) > 0.5]

    if selected_categories:
        filtered_df = filtered_df[filtered_df["category"].isin(selected_categories)]

    if search_text:
        mask = filtered_df["item_name"].str.contains(search_text, case=False, na=False)
        filtered_df = filtered_df[mask]

    if min_cap_utils > 0:
        filtered_df = filtered_df[filtered_df["cap_utils"].fillna(0) >= min_cap_utils]

    if min_turnover_30d > 0:
        filtered_df = filtered_df[filtered_df["turnover_30d"].fillna(0) >= min_turnover_30d]

    # Sort by cap_utils descending by default (NaN last)
    filtered_df = filtered_df.sort_values("cap_utils", ascending=False, na_position="last")

    # -----------------------------------------------------------------------
    # Summary metrics
    # -----------------------------------------------------------------------
    with_build_cost = filtered_df["build_cost"].notna()
    profitable = filtered_df["cap_utils"].notna() & (filtered_df["cap_utils"] > 0)

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric(translate_text(language_code, "builder_helper.metric_items"), len(filtered_df))
    with col_m2:
        st.metric(translate_text(language_code, "builder_helper.metric_with_build_cost"), int(with_build_cost.sum()))
    with col_m3:
        st.metric(translate_text(language_code, "builder_helper.metric_profitable"), int(profitable.sum()))

    # -----------------------------------------------------------------------
    # Column config and display
    # -----------------------------------------------------------------------
    display_df = filtered_df.copy()
    isk_cols = ["market_sell_price", "jita_sell_price", "build_cost"]
    display_df[isk_cols] = display_df[isk_cols].round().astype("Int64")

    st.dataframe(
        display_df,
        hide_index=True,
        width="stretch",
        height=600,
        column_config=get_builder_helper_column_config(language_code=language_code),
    )

    st.caption(translate_text(language_code, "builder_helper.footer"))

    st.sidebar.markdown("---")
    display_sync_status(language_code=language_code)


if __name__ == "__main__":
    main()
