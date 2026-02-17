import os
import sys
import time
from datetime import datetime, timedelta, timezone
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from logging_config import setup_logging
import millify
from config import DatabaseConfig, get_settings
from services import get_doctrine_service
from services.market_service import get_market_service
from init_db import init_db, ensure_market_db_ready
from sync_state import update_wcmkt_state
from services import get_type_resolution_service
from pages.components.market_components import (
    render_isk_volume_chart_ui,
    render_isk_volume_table_ui,
    render_30day_metrics_ui,
    render_current_market_status_ui,
    display_history_data,
    display_history_metrics,
    get_fitting_col_config,
    get_display_formats,
)
from services import get_jita_price
from state import ss_has, ss_get
from repositories import invalidate_market_caches
from ui.market_selector import render_market_selector

settings = get_settings()
env = settings['env']['env']
header_env = f"[{env.upper()}]" if env != "prod" else ""

logger = setup_logging(__name__)

# Services are initialized lazily to avoid database access at module import time
def _get_doctrine_service():
    """Get doctrine service lazily to avoid database access before init_db()."""
    return get_doctrine_service()

def _resolve_type_id(type_name: str):
    """Resolve a type name to its ID via TypeResolutionService."""
    return get_type_resolution_service().resolve_type_id(type_name)

logger.info("Application started")
logger.info(f"streamlit version: {st.__version__}")
logger.info("-" * 100)


# =============================================================================
# Filter Options
# =============================================================================

def get_filter_options(selected_category: str = None, show_all: bool = False) -> tuple:
    """Get category/item filter options from SDE data via the market service repo.

    Returns:
        (categories, items, cat_type_info) tuple.
    """
    service = get_market_service()
    sde_df = service._repo.get_sde_info()
    sde_df = sde_df.reset_index(drop=True)
    logger.info(f"sde_df: {len(sde_df)}")
    logger.debug(f"selected_category: {selected_category}")

    if show_all:
        categories = sorted(sde_df['category_name'].unique().tolist())
        items = sorted(sde_df['type_name'].unique().tolist())
        return categories, items, sde_df.copy()

    elif selected_category:
        cat_sde_df = sde_df[sde_df['category_name'] == selected_category]
        cat_type_info = cat_sde_df.copy()
        selected_categories_type_ids = cat_sde_df['type_id'].unique().tolist()
        selected_category_id = cat_sde_df['category_id'].iloc[0]
        selected_type_names = sorted(cat_sde_df['type_name'].unique().tolist())
        st.session_state.selected_category = selected_category
        st.session_state.selected_category_info = {
            'category_name': selected_category,
            'category_id': selected_category_id,
            'type_ids': selected_categories_type_ids,
            'type_names': selected_type_names,
        }
        return [selected_category], selected_type_names, cat_type_info

    else:
        categories = sorted(sde_df['category_name'].unique().tolist())
        items = sorted(sde_df['type_name'].unique().tolist())
        return categories, items, sde_df.copy()


# =============================================================================
# Session State Helpers
# =============================================================================

def check_selected_item(selected_item: str) -> str | None:
    """Check if selected item is valid and set session state."""
    if selected_item == "":
        st.session_state.selected_item = None
        st.session_state.selected_item_id = None
        st.session_state.jita_price = None
        st.session_state.current_price = None
        return None

    elif selected_item and selected_item is not None:
        logger.info(f"selected_item: {selected_item}")
        st.sidebar.text(f"Item: {selected_item}")
        st.session_state.selected_item = selected_item
        st.session_state.selected_item_id = _resolve_type_id(selected_item)
        jita_price = get_jita_price(st.session_state.selected_item_id)
        st.session_state.jita_price = jita_price if jita_price else None
        logger.info(f"selected_item_id: {st.session_state.selected_item_id}")
        return selected_item

    else:
        st.session_state.jita_price = None
        st.session_state.current_price = None
        return None


def check_selected_category(selected_category: str, show_all: bool) -> list | None:
    if selected_category == "":
        st.session_state.selected_category = None
        st.session_state.selected_category_info = None
        st.session_state.selected_item = None
        st.session_state.selected_item_id = None
        st.session_state.jita_price = None
        return None

    if selected_category and selected_category is not None:
        logger.info(f"selected_category {selected_category}")
        st.sidebar.text(f"Category: {selected_category}")
        st.session_state.selected_category = selected_category
        _, available_items, _ = get_filter_options(
            selected_category if not show_all and selected_category else None
        )
        return available_items
    else:
        st.session_state.selected_category = None
        st.session_state.selected_category_info = None
        st.session_state.selected_item = None
        st.session_state.selected_item_id = None
        st.session_state.jita_price = None
        return None


# =============================================================================
# Database Initialization & Sync
# =============================================================================

def initialize_main_function():
    """Initialize all databases (primary + deployment + shared).

    Only sets ``db_initialized`` to True once *every* database has been
    verified to contain tables.  If a previous attempt partially failed,
    init_db() is re-run on the next rerun so the missing databases get
    another chance to sync.
    """
    logger.info("*" * 60)
    logger.info("Starting main function")
    logger.info("*" * 60)

    if not st.session_state.get('db_initialized'):
        logger.info("-" * 30)
        logger.info("Initializing databases (all markets + shared)")
        result = init_db()
        if result:
            st.session_state.db_initialized = True
        else:
            st.toast("One or more databases failed to initialize", icon="❌")
            # Leave db_initialized unset so the next rerun retries
    else:
        logger.info("Databases already initialized in session state")
    logger.info("*" * 60)
    st.session_state.db_init_time = datetime.now()
    return st.session_state.get('db_initialized', False)


@st.cache_data(ttl=600)
def check_for_db_updates(db_alias: str) -> tuple[bool, float]:
    """Check whether local and remote databases are in sync.

    The db_alias must be an explicit alias (e.g. "wcmktprod", "wcmktnorth")
    so the cache key correctly distinguishes between markets.
    """
    db = DatabaseConfig(db_alias)
    check = db.validate_sync()
    local_time = datetime.now()
    return check, local_time


def check_db(manual_override: bool = False):
    """Check for database updates on the *active* market and sync if needed."""
    from state.market_state import get_active_market
    active_alias = get_active_market().database_alias

    if manual_override:
        check_for_db_updates.clear()
        logger.info("*" * 60)
        logger.info("check_for_db_updates() cache cleared for manual override")
        logger.info("*" * 60)

    check, local_time = check_for_db_updates(active_alias)
    now = time.time()
    logger.info(f"check_db() check: {check}, time: {local_time}, alias: {active_alias}")
    logger.info(f"last_check: {round(now - st.session_state.get('last_check', 0), 2)} seconds ago")

    if not check:
        st.toast("More recent remote database data available, syncing local database", icon="🕧")
        logger.info("check_db() check is False, syncing local database")
        db = DatabaseConfig(active_alias)
        invalidate_market_caches()
        db.sync()

        if db.validate_sync():
            logger.info("Local database synced and validated")
            st.toast("Database synced successfully", icon="✅")
            update_wcmkt_state()
        else:
            logger.info("Local database synced but validation failed")
            st.toast("Database sync failed", icon="❌")
    else:
        if 'local_update_status' in st.session_state:
            local_update_since = st.session_state.local_update_status["time_since"]
            local_update_since = int(local_update_since.total_seconds() // 60)
            local_update_since = f"{local_update_since} mins"
            st.toast(f"DB updated: {local_update_since} ago", icon="✅")
        else:
            local_update_since = DatabaseConfig(active_alias).get_time_since_update("marketstats", remote=False)
            local_update_since = f"{local_update_since} mins"
            st.toast(f"DB updated: {local_update_since} ago", icon="✅")


def maybe_run_check():
    now = time.time()
    if "last_check" not in st.session_state:
        logger.info("last_check not in st.session_state, setting to now")
        check_db()
        st.session_state["last_check"] = now
    elif now - st.session_state.get("last_check", 0) > 600:
        logger.info(f"now - last_check={now - st.session_state.get('last_check', 0)}, running check_db()")
        check_db()
        st.session_state["last_check"] = now


# =============================================================================
# Sync Status Display
# =============================================================================

def new_display_sync_status():
    """Display sync status in the sidebar."""
    from state.market_state import get_active_market
    active_alias = get_active_market().database_alias

    update_time: datetime | None = None
    time_since: timedelta | None = None
    display_time = "Unavailable"
    display_time_since = "Unavailable"

    if "local_update_status" not in st.session_state:
        try:
            update_wcmkt_state()
        except Exception as exc:
            logger.error(f"Error initializing local_update_status: {exc}")

    status = st.session_state.get("local_update_status")
    if status is not None:
        update_time = status.get("updated")
        time_since = status.get("time_since")
        if update_time is None:
            try:
                update_time = DatabaseConfig(active_alias).get_most_recent_update("marketstats", remote=False)
                status["updated"] = update_time
            except Exception as exc:
                logger.error(f"Error fetching cached update time: {exc}")
        if time_since is None and update_time is not None:
            time_since = datetime.now(tz=timezone.utc) - update_time
            status["time_since"] = time_since
    else:
        try:
            update_time = DatabaseConfig(active_alias).get_most_recent_update("marketstats", remote=False)
        except Exception as exc:
            logger.error(f"Error fetching update time: {exc}")
        if update_time is not None:
            time_since = datetime.now(tz=timezone.utc) - update_time

    if update_time is not None:
        try:
            display_time = update_time.strftime("%m-%d | %H:%M UTC")
        except Exception as exc:
            logger.error(f"Error formatting update time: {exc}")

    if time_since is not None:
        try:
            total_minutes = int(time_since.total_seconds() // 60)
            suffix = "minute" if total_minutes == 1 else "minutes"
            display_time_since = f"{total_minutes} {suffix}"
        except Exception as exc:
            logger.error(f"Error formatting time since update: {exc}")

    st.sidebar.markdown(
        (
            "<span style='font-size: 14px; color: lightgrey;'>"
            f"*Last ESI update: {display_time}*</span> "
            "<p style='margin: 0;'>"
            "<span style='font-size: 14px; color: lightgrey;'>"
            f"*Time since update: {display_time_since}*</span>"
            "</p>"
        ),
        unsafe_allow_html=True,
    )


# =============================================================================
# Title
# =============================================================================

def render_title_headers(market_name: str):
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image("images/wclogo.png", width=125)
    with col2:
        st.title(f"Winter Coalition Market Stats - {market_name} Market {header_env}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Main function for the market stats page."""
    market = render_market_selector()

    # Initialize databases if needed
    if 'db_init_time' not in st.session_state:
        init_result = initialize_main_function()
    elif datetime.now() - st.session_state.db_init_time > timedelta(hours=1):
        init_result = initialize_main_function()
    else:
        init_result = True
    # Ensure the active market's database is synced before any queries.
    # On cold start or after a market switch, the target db may not exist yet.
    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    if init_result:
        update_wcmkt_state()

    maybe_run_check()
    render_title_headers(market.name)

    # Get service
    market_service = get_market_service()

    # Sidebar filters
    st.sidebar.header("Filters")
    show_all = st.sidebar.checkbox("Show All Data", value=False)

    categories, all_items, _ = get_filter_options()
    selected_category = st.sidebar.selectbox(
        "Select Category",
        options=[""] + categories,
        index=0,
        key="selected_category_choice",
        format_func=lambda x: "All Categories" if x == "" else x,
    )

    available_items = check_selected_category(selected_category, show_all)
    if not available_items:
        available_items = all_items

    selected_item = st.sidebar.selectbox(
        "Select Item",
        options=[""] + available_items,
        index=0,
        format_func=lambda x: "All Items" if x == "" else x,
    )
    selected_item = check_selected_item(selected_item)

    # Get market data via service
    t1 = time.perf_counter()
    category_info = ss_get('selected_category_info')
    selected_item_id = ss_get('selected_item_id')
    sell_data, buy_data, stats = market_service.get_market_data(
        show_all, category_info=category_info, selected_item_id=selected_item_id
    )
    t2 = time.perf_counter()
    logger.info(f"get_market_data elapsed: {round((t2 - t1) * 1000, 2)} ms")

    # Process order counts
    sell_order_count = sell_data['order_id'].nunique() if not sell_data.empty else 0
    sell_total_value = (sell_data['price'] * sell_data['volume_remain']).sum() if not sell_data.empty else 0
    buy_order_count = buy_data['order_id'].nunique() if not buy_data.empty else 0
    buy_total_value = (buy_data['price'] * buy_data['volume_remain']).sum() if not buy_data.empty else 0

    display_formats = get_display_formats()

    # Initialize fitting data
    fit_df = pd.DataFrame()
    service = _get_doctrine_service()

    if not sell_data.empty:
        if ss_has('selected_item'):
            selected_item = st.session_state.selected_item
            sell_data = sell_data[sell_data['type_name'] == selected_item]
            if not buy_data.empty:
                buy_data = buy_data[buy_data['type_name'] == selected_item]
            stats = stats[stats['type_name'] == selected_item]

            if selected_item_id := ss_get('selected_item_id'):
                pass
            else:
                selected_item_id = _resolve_type_id(selected_item)
                st.session_state.selected_item_id = selected_item_id

            if selected_item_id:
                try:
                    all_fits = service.repository.get_all_fits()
                    item_fits = all_fits[all_fits['type_id'] == selected_item_id]
                    if not item_fits.empty:
                        item_cat_id = item_fits['category_id'].iloc[0] if 'category_id' in item_fits.columns else None
                        if item_cat_id == 6:
                            fit_id = item_fits['fit_id'].iloc[0]
                            fit_df = service.repository.get_fit_by_id(fit_id)
                        else:
                            fit_df = item_fits
                    else:
                        fit_df = pd.DataFrame()
                except Exception as e:
                    logger.warning(f"Failed to get fitting data for {selected_item_id}: {e}")
                    fit_df = pd.DataFrame()

        elif show_all:
            fit_df = pd.DataFrame()

        elif ss_has('selected_category'):
            selected_category = st.session_state.selected_category
            stats = stats[stats['category_name'] == selected_category].reset_index(drop=True)
            stats_type_ids = st.session_state.selected_category_info['type_ids']
            if not buy_data.empty:
                buy_data = buy_data[buy_data['type_id'].isin(stats_type_ids)].reset_index(drop=True)
            if not sell_data.empty:
                sell_data = sell_data[sell_data['type_id'].isin(stats_type_ids)].reset_index(drop=True)

        # Fit header info
        isship = False
        fits_on_mkt = None
        cat_id = None

        if fit_df is not None and not fit_df.empty:
            try:
                cat_id = stats['category_id'].iloc[0]
            except Exception:
                cat_id = None
            try:
                fits_on_mkt = fit_df['fits_on_mkt'].min()
            except Exception:
                fits_on_mkt = None
            if cat_id == 6:
                isship = True

        # Headers
        if show_all:
            st.header("All Sell Orders", divider="green")
        elif ss_has('selected_item'):
            selected_item = st.session_state.selected_item
            selected_item_id = ss_get('selected_item_id') or _resolve_type_id(selected_item)
            if 'selected_item_id' not in st.session_state:
                st.session_state.selected_item_id = selected_item_id
            try:
                image_id = selected_item_id
                type_name = selected_item
            except Exception:
                image_id = None
                type_name = None

            st.subheader(f"{type_name}", divider="blue")
            col1, col2 = st.columns(2)
            with col1:
                if image_id:
                    if isship:
                        st.image(f'https://images.evetech.net/types/{image_id}/render?size=64')
                    else:
                        st.image(f'https://images.evetech.net/types/{image_id}/icon')
            with col2:
                try:
                    if fits_on_mkt is not None and fits_on_mkt:
                        st.subheader("Winter Co. Doctrine", divider="orange")
                        if cat_id in [7, 8, 18]:
                            all_fits = service.repository.get_all_fits()
                            module_fits = all_fits[all_fits['type_id'] == selected_item_id]
                            st.write(module_fits[['fit_id', 'ship_name', 'fit_qty']].drop_duplicates())
                        else:
                            st.write(fit_df[fit_df['type_id'] == selected_item_id]['group_name'].iloc[0])
                except Exception as e:
                    logger.error(f"Error: {e}")
        elif ss_has('selected_category'):
            st.header(st.session_state.selected_category + "s", divider="green")

        # Current Market Status
        render_current_market_status_ui(
            sell_data=sell_data, stats=stats,
            selected_item=selected_item,
            sell_order_count=sell_order_count,
            sell_total_value=sell_total_value,
            fit_df=fit_df, fits_on_mkt=fits_on_mkt, cat_id=cat_id,
        )

        # 30-Day Historical Metrics
        with st.expander("30-Day Market Stats (expand to view metrics)", expanded=False):
            render_30day_metrics_ui(market_service)

        st.divider()

        # Sell orders display
        display_df = sell_data.copy()
        if ss_has('selected_item'):
            st.subheader("Sell Orders for " + st.session_state.selected_item, divider="blue")
        elif ss_has('selected_category'):
            cat_label = st.session_state.selected_category
            if not cat_label.endswith("s"):
                cat_label += "s"
            st.subheader(f"Sell Orders for {cat_label}", divider="blue")
        else:
            st.subheader("All Sell Orders", divider="green")

        if 'is_buy_order' in display_df.columns:
            display_df.drop(columns='is_buy_order', inplace=True)
        st.dataframe(display_df, hide_index=True, column_config=display_formats)

    # Buy orders
    if not buy_data.empty:
        if show_all:
            st.subheader("All Buy Orders", divider="orange")
        elif ss_has('selected_item'):
            st.subheader(f"Buy Orders for {st.session_state.selected_item}", divider="orange")
        elif ss_has('selected_category'):
            cat_label = st.session_state.selected_category
            if not cat_label.endswith("s"):
                cat_label += "s"
            st.subheader(f"Buy Orders for {cat_label}", divider="orange")
        else:
            st.subheader("All Buy Orders", divider="orange")

        col1, col2 = st.columns(2)
        with col1:
            if buy_total_value > 0:
                st.metric("Market Value (buy orders)", f"{millify.millify(buy_total_value, precision=2)} ISK")
            else:
                st.metric("Market Value (buy orders)", "0 ISK")
        with col2:
            if buy_order_count > 0:
                st.metric("Total Buy Orders", f"{buy_order_count:,.0f}")
            else:
                st.metric("Total Buy Orders", "0")

        buy_display_df = buy_data.copy()
        if 'is_buy_order' in buy_display_df.columns:
            buy_display_df.drop(columns='is_buy_order', inplace=True)
        st.dataframe(buy_display_df, hide_index=True, column_config=display_formats)

    elif not sell_data.empty:
        if st.session_state.selected_item is not None:
            st.write(f"No current buy orders found for {st.session_state.selected_item}")
    else:
        if st.session_state.selected_item is not None:
            st.write(f"No current market orders found for {st.session_state.selected_item}")

    # Market History section
    if st.session_state.get('selected_item') is not None:
        st.subheader("Market History - " + st.session_state.get('selected_item'), divider="blue")
    else:
        if st.session_state.get('selected_category') is not None:
            filter_info = f"Category: {st.session_state.get('selected_category')}"
            suffix = "s"
        else:
            filter_info = "All Items"
            suffix = ""

        st.subheader("Price History - " + filter_info + suffix, divider="blue")
        render_isk_volume_chart_ui(market_service)
        with st.expander("Expand to view Market History Data"):
            render_isk_volume_table_ui(market_service)

    # Item history chart
    if ss_has('selected_item'):
        selected_item = st.session_state.selected_item
        if selected_item_id := ss_get('selected_item_id'):
            pass
        else:
            try:
                selected_item_id = _resolve_type_id(selected_item)
            except Exception:
                selected_item_id = None
            st.session_state.selected_item_id = selected_item_id
    else:
        selected_item_id = None
        st.session_state.selected_item_id = selected_item_id

    if selected_item_id:
        logger.debug(f"Displaying history chart for {selected_item_id}")

        history_chart = market_service.create_history_chart(selected_item_id)
        # Set title from session state (service doesn't have access to st)
        if history_chart is not None and ss_has('selected_item'):
            history_chart.update_layout(title=st.session_state.selected_item)

        selected_history = market_service._repo.get_history_by_type(selected_item_id)

        if history_chart:
            st.plotly_chart(history_chart, config={'width': 'content'})

        if selected_history is not None and not selected_history.empty:
            logger.info(f"Displaying history data for {selected_item_id}")
            colh1, colh2 = st.columns(2)
            with colh1:
                history_df = display_history_data(selected_history)
            with colh2:
                if not history_df.empty:
                    display_history_metrics(history_df)

        st.divider()

    # Fitting data
    if fit_df is None:
        fit_df = pd.DataFrame()
    if not fit_df.empty:
        st.subheader("Fitting Data", divider="blue")
        selected_item = ss_get('selected_item', " ")
        selected_item_id = ss_get('selected_item_id') or _resolve_type_id(selected_item)
        try:
            fit_id = fit_df['fit_id'].iloc[0]
        except Exception:
            fit_id = " "
        st.markdown(
            f"<span style='font-weight: bold; color: orange;'>{selected_item}</span> | type_id: {selected_item_id} | fit_id: {fit_id}",
            unsafe_allow_html=True,
        )
        if isship:
            column_config = get_fitting_col_config()
            st.dataframe(fit_df, hide_index=True, column_config=column_config, width='content')

    # Sidebar bottom
    with st.sidebar:
        new_display_sync_status()
        st.sidebar.divider()
        db_check = st.sidebar.button("Check DB State", width='content')
        if db_check:
            check_db(manual_override=True)
        st.sidebar.divider()
        st.markdown("### Data Downloads")
        st.markdown("*Visit the **Downloads** page for market data, doctrine fits, and SDE table exports.*")


if __name__ == "__main__":
    main()
