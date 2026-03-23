"""Market Dashboard — at-a-glance overview of the entire market.

Sections:
1. Market Overview KPIs (6 metric cards)
2. Commodity Tables (2x2 grid: minerals, isotopes, doctrine ships, popular modules)
3. Market Activity (ISK volume chart)
4. 30-Day Summary + Top Items
"""

from datetime import datetime, timedelta

import streamlit as st
import millify

from logging_config import setup_logging
from services import get_price_service
from services.market_service import get_market_service
from init_db import init_db, ensure_market_db_ready
from state.sync_state import update_wcmkt_state
from pages.components.market_components import (
    render_isk_volume_chart_ui,
    render_30day_metrics_ui,
)
from pages.components.dashboard_components import (
    MINERAL_TYPE_IDS,
    ISOTOPE_AND_FUEL_BLOCK_TYPE_IDS,
    render_comparison_table,
    render_doctrine_ships_table,
    render_popular_modules_table,
)
from state import get_active_language
from repositories import get_sde_repository, get_doctrine_repository
from ui.i18n import translate_text
from ui.market_selector import render_market_selector
from ui.sync_display import display_sync_status  # noqa: F401

logger = setup_logging(__name__)


# =============================================================================
# Initialization
# =============================================================================


def _initialize_databases():
    """Initialize databases, returning True on success."""
    if not st.session_state.get("db_initialized"):
        result = init_db()
        if result:
            st.session_state.db_initialized = True
        else:
            st.toast("One or more databases failed to initialize", icon="❌")
            return False
    st.session_state.db_init_time = datetime.now()
    return True


# =============================================================================
# KPI Section
# =============================================================================


def _render_kpi_bar(market_service, language_code: str):
    """Render the 5 market overview KPI metric cards."""
    kpis = market_service.get_market_overview_kpis()

    cols = st.columns(5)
    with cols[0]:
        value = kpis["total_market_value"]
        display_val = f"{millify.millify(value, precision=2)} ISK" if value > 0 else "0 ISK"
        st.metric(translate_text(language_code, "dashboard.kpi_total_market_value"), display_val)
    with cols[1]:
        st.metric(
            translate_text(language_code, "dashboard.kpi_active_sell_orders"),
            f"{kpis['active_sell_orders']:,}",
        )
    with cols[2]:
        st.metric(
            translate_text(language_code, "dashboard.kpi_active_buy_orders"),
            f"{kpis['active_buy_orders']:,}",
        )
    with cols[3]:
        st.metric(
            translate_text(language_code, "dashboard.kpi_items_listed"),
            f"{kpis['items_listed']:,}",
        )
    with cols[4]:
        st.metric(
            translate_text(language_code, "dashboard.kpi_last_updated"),
            kpis["last_updated"] or "N/A",
        )


# =============================================================================
# Commodity Tables
# =============================================================================


def _render_commodity_grid(market_service, price_service, sde_repo, doctrine_repo, language_code):
    """Render the 2x2 commodity table grid."""
    top_row = st.columns(2, gap="small")
    with top_row[0]:
        render_comparison_table(
            market_service=market_service,
            price_service=price_service,
            sde_repo=sde_repo,
            type_ids=list(MINERAL_TYPE_IDS),
            title_key="market_stats.mineral_price_comparison",
            language_code=language_code,
        )
    with top_row[1]:
        render_comparison_table(
            market_service=market_service,
            price_service=price_service,
            sde_repo=sde_repo,
            type_ids=list(ISOTOPE_AND_FUEL_BLOCK_TYPE_IDS),
            title_key="market_stats.isotope_and_fuel_block_comparison",
            language_code=language_code,
        )

    bottom_row = st.columns(2, gap="small")
    with bottom_row[0]:
        render_doctrine_ships_table(
            doctrine_repo=doctrine_repo,
            market_service=market_service,
            price_service=price_service,
            sde_repo=sde_repo,
            language_code=language_code,
        )
    with bottom_row[1]:
        render_popular_modules_table(
            market_service=market_service,
            price_service=price_service,
            doctrine_repo=doctrine_repo,
            sde_repo=sde_repo,
            language_code=language_code,
        )


# =============================================================================
# Main
# =============================================================================


def main():
    """Main function for the market dashboard page."""
    language_code = get_active_language()
    market = render_market_selector()

    # Initialize databases
    if "db_init_time" not in st.session_state:
        init_result = _initialize_databases()
    elif datetime.now() - st.session_state.db_init_time > timedelta(hours=1):
        init_result = _initialize_databases()
    else:
        init_result = True

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    if init_result:
        update_wcmkt_state()

    # Title
    st.title(
        translate_text(
            language_code, "dashboard.title", market_name=market.name,
        )
    )

    # Services
    market_service = get_market_service()
    price_service = get_price_service(
        db_alias=market.database_alias,
        market_key=market.key,
    )
    sde_repo = get_sde_repository()
    doctrine_repo = get_doctrine_repository()

    # Section 1: Market Overview KPIs
    _render_kpi_bar(market_service, language_code)
    st.divider()

    # Section 2: Commodity Tables (2x2 grid)
    _render_commodity_grid(
        market_service, price_service, sde_repo, doctrine_repo, language_code,
    )
    st.divider()

    # Section 3: Market Activity — ISK Volume Chart
    st.subheader(translate_text(language_code, "dashboard.market_activity"))
    render_isk_volume_chart_ui(market_service, language_code)
    st.divider()

    # Section 4 + 5: 30-Day Summary Metrics + Top Items
    # Clear item selection so metrics show market-wide totals
    st.session_state["selected_item"] = None
    st.session_state["selected_item_id"] = None
    st.session_state["selected_category"] = None
    render_30day_metrics_ui(market_service, language_code)


main()
