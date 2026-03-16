"""
Import Helper Page

Shows local market items with Jita comparison data for import decisions.
"""

import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from state import get_active_language
from services import ImportHelperFilters
from services.import_helper_service import SHIPPING_COST_PER_M3, get_import_helper_service
from ui.column_definitions import get_import_helper_column_config
from ui.i18n import translate_text
from ui.market_selector import render_market_selector
from ui.sync_display import display_sync_status

logger = setup_logging(__name__, log_file="import_helper.log")


def main():
    language_code = get_active_language()
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
        st.title(translate_text(language_code, "import_helper.title", market_name=market.name))

    st.sidebar.header(translate_text(language_code, "import_helper.filters_header"))
    category_options = service.get_category_options()
    category_name_map = {
        int(row["category_id"]): str(row["category_name"])
        for _, row in category_options.iterrows()
    }
    category_ids = sorted(category_name_map, key=lambda cid: category_name_map[cid])

    st.sidebar.subheader(translate_text(language_code, "low_stock.item_type_filters"))
    doctrine_only = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.doctrine_only"),
        value=False,
        help=translate_text(language_code, "low_stock.doctrine_only_help"),
    )
    tech2_only = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.tech2_only"),
        value=False,
        help=translate_text(language_code, "low_stock.tech2_only_help"),
    )
    faction_only = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.faction_only"),
        value=False,
        help=translate_text(language_code, "low_stock.faction_only_help"),
    )

    selected_category_ids = st.sidebar.multiselect(
        translate_text(language_code, "import_helper.categories"),
        options=category_ids,
        default=[],
        format_func=lambda cid: category_name_map[cid],
        help=translate_text(language_code, "import_helper.categories_help"),
    )
    search_text = st.sidebar.text_input(
        translate_text(language_code, "import_helper.search_items"),
        value="",
        help=translate_text(language_code, "import_helper.search_items_help"),
    )
    profitable_only = st.sidebar.checkbox(
        translate_text(language_code, "import_helper.profitable_only"),
        value=True,
        help=translate_text(language_code, "import_helper.profitable_only_help"),
    )
    min_capital_utilis = st.sidebar.number_input(
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
    shipping_cost_per_m3 = st.sidebar.number_input(
        translate_text(language_code, "import_helper.shipping_cost_per_m3"),
        min_value=0.0,
        value=float(SHIPPING_COST_PER_M3),
        step=50.0,
        format="%.0f",
        help=translate_text(language_code, "import_helper.shipping_cost_per_m3_help"),
    )
    markup_margin = st.sidebar.number_input(
        translate_text(language_code, "import_helper.markup_margin"),
        min_value=0.0,
        value=0.2,
        step=0.05,
        format="%.2f",
        help=translate_text(language_code, "import_helper.markup_margin_help"),
    )

    st.markdown(translate_text(language_code, "import_helper.description"))

    filters = ImportHelperFilters(
        category_ids=selected_category_ids,
        search_text=search_text,
        doctrine_only=doctrine_only,
        tech2_only=tech2_only,
        faction_only=faction_only,
        profitable_only=profitable_only,
        min_capital_utilis=min_capital_utilis,
        min_turnover_30d=float(min_turnover_30d),
        markup_margin=float(markup_margin),
        shipping_cost_per_m3=float(shipping_cost_per_m3),
    )

    try:
        base_df = service.fetch_base_data()
    except Exception as e:
        logger.error(f"Import helper data load failed: {e}")
        st.error("Failed to load market data. Check database connectivity and try refreshing.")
        st.stop()

    df = service.get_import_items(base_df, filters, language_code=language_code)
    if df.empty:
        st.warning("No items found with the selected filters.")
        st.sidebar.markdown("---")
        display_sync_status(language_code=language_code)
        return

    stats = service.get_summary_stats(df)
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    with metric_col1:
        st.metric(translate_text(language_code, "import_helper.metric_total_items"), stats["total_items"])
    with metric_col2:
        st.metric(
            translate_text(language_code, "import_helper.metric_profitable_items"),
            stats["profitable_items"],
        )
    with metric_col3:
        st.metric(
            translate_text(language_code, "import_helper.metric_avg_capital_utilis"),
            f"{stats['avg_capital_utilis']:.1%}",
        )

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
        width="stretch",
        column_config=get_import_helper_column_config(
            language_code=language_code,
            shipping_cost_per_m3=float(shipping_cost_per_m3),
        ),
    )

    st.sidebar.markdown("---")
    display_sync_status(language_code=language_code)


if __name__ == "__main__":
    main()
