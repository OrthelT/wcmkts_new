import time
from datetime import datetime, timedelta
import streamlit as st
import pandas as pd
from logging_config import setup_logging
import millify
from config import DatabaseConfig, get_settings
from services import get_doctrine_service, get_price_service
from services.market_service import get_market_service
from init_db import init_db, ensure_market_db_ready
from state.sync_state import update_wcmkt_state
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
from services.type_name_localization import (
    apply_localized_names,
    get_localized_name_map,
    apply_localized_type_names,
    get_localized_name,
)
from state import get_active_language, ss_has, ss_get
from repositories import get_sde_repository, invalidate_market_caches
from ui.i18n import translate_text
from ui.column_definitions import get_market_comparison_column_config
from ui.market_selector import render_market_selector
from ui.sync_display import display_sync_status  # noqa: F401
from ui.formatters import drop_localized_backup_columns
# Backwards-compatible alias for pages that may import from here
new_display_sync_status = display_sync_status

settings = get_settings()
env = settings['env']['env']
header_env = f"[{env.upper()}]" if env != "prod" else ""

logger = setup_logging(__name__)

logger.info("Application started")
logger.info(f"streamlit version: {st.__version__}")
logger.info("-" * 100)

MINERAL_TYPE_IDS: tuple[int, ...] = (34, 35, 36, 37, 38, 39, 40, 11399, 81143)
ISOTOPE_AND_FUEL_BLOCK_TYPE_IDS: tuple[int, ...] = (16274, 17887, 17888, 17889, 4247, 4312, 4051, 4246, 16273, 16275)

# =============================================================================
# Filter Options
# =============================================================================


def get_filter_options(
    selected_category_id: int | None = None,
    show_all: bool = False,
) -> tuple:
    """Get category/item filter options from SDE data via the market service repo.

    Returns:
        (categories_df, items_df, cat_type_info) tuple.
    """
    service = get_market_service()
    sde_df = service._repo.get_sde_info()
    sde_df = sde_df.reset_index(drop=True)
    logger.info(f"sde_df: {len(sde_df)}")
    logger.debug(f"selected_category_id: {selected_category_id}")

    categories_df = (
        sde_df[["category_id", "category_name"]]
        .dropna()
        .drop_duplicates()
        .sort_values("category_name")
        .reset_index(drop=True)
    )

    if show_all:
        items_df = (
            sde_df[["type_id", "type_name"]]
            .dropna()
            .drop_duplicates()
            .sort_values("type_name")
            .reset_index(drop=True)
        )
        return categories_df, items_df, sde_df.copy()

    elif selected_category_id is not None:
        cat_sde_df = sde_df[sde_df["category_id"] == selected_category_id]
        cat_type_info = cat_sde_df.copy()
        if cat_sde_df.empty:
            return categories_df, pd.DataFrame(columns=["type_id", "type_name"]), cat_type_info

        selected_categories_type_ids = cat_sde_df["type_id"].unique().tolist()
        selected_category_name = str(cat_sde_df["category_name"].iloc[0])
        selected_items_df = (
            cat_sde_df[["type_id", "type_name"]]
            .dropna()
            .drop_duplicates()
            .sort_values("type_name")
            .reset_index(drop=True)
        )
        st.session_state.selected_category = selected_category_name
        st.session_state.selected_category_id = selected_category_id
        st.session_state.selected_category_info = {
            'category_name': selected_category_name,
            'category_id': selected_category_id,
            'type_ids': selected_categories_type_ids,
            'type_names': selected_items_df["type_name"].tolist(),
        }
        return categories_df, selected_items_df, cat_type_info

    else:
        items_df = (
            sde_df[["type_id", "type_name"]]
            .dropna()
            .drop_duplicates()
            .sort_values("type_name")
            .reset_index(drop=True)
        )
        return categories_df, items_df, sde_df.copy()


def _build_item_option_labels(
    items_df: pd.DataFrame,
    sde_repo,
    language_code: str,
) -> tuple[dict[int, str], dict[int, str]]:
    """Build localized and English labels for type-id-backed item selectors."""
    if items_df.empty:
        return {}, {}

    english_name_map = {
        int(row["type_id"]): str(row["type_name"])
        for _, row in items_df[["type_id", "type_name"]].drop_duplicates().iterrows()
        if pd.notna(row["type_id"]) and pd.notna(row["type_name"])
    }
    localized_name_map = get_localized_name_map(
        list(english_name_map.keys()),
        sde_repo,
        language_code,
        logger,
    )
    item_label_map = {
        type_id: localized_name_map.get(type_id, english_name)
        for type_id, english_name in english_name_map.items()
    }
    return item_label_map, english_name_map


# =============================================================================
# Session State Helpers
# =============================================================================

def check_selected_item(
    selected_item_id: int | None,
    item_label_map: dict[int, str],
    english_name_map: dict[int, str],
) -> int | None:
    """Check if selected item is valid and set session state."""
    if selected_item_id is None:
        st.session_state.selected_item = None
        st.session_state.selected_item_en = None
        st.session_state.selected_item_id = None
        st.session_state.jita_price = None
        st.session_state.current_price = None
        return None

    elif selected_item_id is not None:
        selected_item_label = item_label_map.get(selected_item_id, f"Unknown ({selected_item_id})")
        selected_item_en = english_name_map.get(selected_item_id, selected_item_label)
        logger.info(f"selected_item_id: {selected_item_id}")
        st.sidebar.text(f"Item: {selected_item_label}")
        st.session_state.selected_item = selected_item_label
        st.session_state.selected_item_en = selected_item_en
        st.session_state.selected_item_id = selected_item_id
        jita_price = get_jita_price(selected_item_id)
        st.session_state.jita_price = jita_price if jita_price else None
        return selected_item_id

    else:
        st.session_state.jita_price = None
        st.session_state.current_price = None
        return None


def check_selected_category(
    selected_category_id: int | None,
    show_all: bool,
) -> pd.DataFrame | None:
    if selected_category_id is None:
        st.session_state.selected_category = None
        st.session_state.selected_category_id = None
        st.session_state.selected_category_info = None
        st.session_state.selected_item = None
        st.session_state.selected_item_en = None
        st.session_state.selected_item_id = None
        st.session_state.jita_price = None
        return None

    if selected_category_id is not None:
        logger.info(f"selected_category_id {selected_category_id}")
        _, available_items_df, cat_type_info = get_filter_options(
            selected_category_id if not show_all else None,
        )
        if not cat_type_info.empty:
            selected_category = str(cat_type_info["category_name"].iloc[0])
            st.sidebar.text(f"Category: {selected_category}")
            st.session_state.selected_category = selected_category
            st.session_state.selected_category_id = selected_category_id
        return available_items_df
    else:
        st.session_state.selected_category = None
        st.session_state.selected_category_id = None
        st.session_state.selected_category_info = None
        st.session_state.selected_item = None
        st.session_state.selected_item_en = None
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
def check_for_db_updates(db_alias: str) -> tuple[bool, datetime]:
    """Check whether local and remote databases are in sync.

    The db_alias must be an explicit alias (e.g. "wcmktprod", "wcmktnorth")
    so the cache key correctly distinguishes between markets.
    """
    db = DatabaseConfig(db_alias)
    if not db.has_remote_credentials:
        logger.info(f"check_for_db_updates(): skipping remote validation for {db_alias}")
        local_time = datetime.now()
        return True, local_time
    check = db.validate_sync()
    local_time = datetime.now()
    return check, local_time


def check_db(manual_override: bool = False):
    """Check for database updates on *all* markets and sync any that are stale.

    Both market databases receive ESI updates at the same time, so we check
    all of them regardless of which market is currently active.
    """
    from state.market_state import get_active_market
    from settings_service import get_all_market_configs

    active_alias = get_active_market().database_alias
    all_aliases = [cfg.database_alias for cfg in get_all_market_configs().values()]

    if manual_override:
        check_for_db_updates.clear()
        logger.info("*" * 60)
        logger.info("check_for_db_updates() cache cleared for manual override")
        logger.info("*" * 60)

    synced_any = False
    any_stale = False
    local_only_mode = False
    for alias in all_aliases:
        db = DatabaseConfig(alias)
        if not db.has_remote_credentials:
            logger.info(f"check_db(): skipping {alias}; no remote credentials configured")
            local_only_mode = True
            continue
        check, local_time = check_for_db_updates(alias)
        now = time.time()
        logger.info(f"check_db() check: {check}, time: {local_time}, alias: {alias}")
        logger.info(f"last_check: {round(now - st.session_state.get('last_check', 0), 2)} seconds ago")

        if not check:
            any_stale = True
            logger.info(f"check_db() {alias} is stale, syncing")
            db.sync()

            if db.validate_sync():
                logger.info(f"{alias} synced and validated")
                synced_any = True
            else:
                logger.info(f"{alias} sync failed validation")
                st.toast(f"Sync failed for {alias}", icon="❌")

    if synced_any:
        invalidate_market_caches()
        update_wcmkt_state()
        st.toast("Database synced successfully", icon="✅")
    elif local_only_mode and not any_stale and manual_override:
        st.toast("Local-only mode: remote sync checks skipped", icon="ℹ️")
    elif not any_stale:
        if 'local_update_status' in st.session_state:
            time_since = st.session_state.local_update_status["time_since"]
            if time_since is not None:
                local_update_since = f"{int(time_since.total_seconds() // 60)} mins"
            else:
                local_update_since = "unknown"
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
# Title
# =============================================================================

def render_title_headers(market_name: str, language_code: str):
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image("images/wclogo.png", width=125)
    with col2:
        st.title(
            translate_text(
                language_code,
                "market_stats.title",
                market_name=market_name,
                header_env=header_env,
            ).strip()
        )


def _get_price_result_value(price_result, field_name: str) -> float:
    """Return a numeric price field from a PriceResult-like object."""
    if price_result is None:
        return 0.0
    try:
        return float(getattr(price_result, field_name) or 0.0)
    except (AttributeError, TypeError, ValueError):
        return 0.0


def _get_eve_icon_url(type_id: int) -> str:
    """Return the EVE icon URL for an item type."""
    return f"https://images.evetech.net/types/{int(type_id)}/icon?size=32"


def render_comparison_table(
    market_service,
    price_service,
    sde_repo,
    type_ids: list[int],
    title_key: str,
    language_code: str,
) -> None:
    """Render a fixed item price comparison table for the active market."""
    comparison_df = market_service.get_current_market_snapshot(type_ids)
    if comparison_df.empty:
        return

    jita_price_map = price_service.get_jita_price_data_map(type_ids)
    comparison_df["jita_sell_price"] = comparison_df["type_id"].map(
        lambda type_id: _get_price_result_value(jita_price_map.get(int(type_id)), "sell_price")
    )
    comparison_df["jita_buy_price"] = comparison_df["type_id"].map(
        lambda type_id: _get_price_result_value(jita_price_map.get(int(type_id)), "buy_price")
    )
    comparison_df["pct_diff_vs_jita_sell"] = 0.0

    has_jita_sell = comparison_df["jita_sell_price"] > 0
    comparison_df.loc[has_jita_sell, "pct_diff_vs_jita_sell"] = (
        (
            comparison_df.loc[has_jita_sell, "current_sell_price"]
            - comparison_df.loc[has_jita_sell, "jita_sell_price"]
        )
        / comparison_df.loc[has_jita_sell, "jita_sell_price"]
    ) * 100

    comparison_df["order_volume"] = (
        pd.to_numeric(comparison_df["order_volume"], errors="coerce").fillna(0).round().astype(int)
    )
    comparison_df = apply_localized_type_names(
        comparison_df,
        sde_repo,
        language_code,
        logger,
    )
    comparison_df["type_name"] = comparison_df["type_name"].fillna(
        comparison_df["type_id"].astype(str)
    )
    comparison_df["image_url"] = comparison_df["type_id"].map(_get_eve_icon_url)
    comparison_df["current_sell_price"] = pd.to_numeric(
        comparison_df["current_sell_price"],
        errors="coerce",
    ).fillna(0.0)
    comparison_df["order_volume"] = pd.to_numeric(
        comparison_df["order_volume"],
        errors="coerce",
    ).fillna(0.0)
    comparison_df["jita_sell_price"] = pd.to_numeric(
        comparison_df["jita_sell_price"],
        errors="coerce",
    ).fillna(0.0)
    comparison_df["jita_buy_price"] = pd.to_numeric(
        comparison_df["jita_buy_price"],
        errors="coerce",
    ).fillna(0.0)
    comparison_df["pct_diff_vs_jita_sell"] = pd.to_numeric(
        comparison_df["pct_diff_vs_jita_sell"],
        errors="coerce",
    ).fillna(0.0)

    display_df = comparison_df[
        [
            "image_url",
            "type_name",
            "current_sell_price",
            "order_volume",
            "jita_sell_price",
            "jita_buy_price",
            "pct_diff_vs_jita_sell",
        ]
    ].copy()

    st.subheader(
        translate_text(language_code, title_key),
        divider="gray",
    )
    st.dataframe(
        drop_localized_backup_columns(display_df),
        hide_index=True,
        column_config=get_market_comparison_column_config(language_code),
        width="stretch",
    )


# =============================================================================
# Main
# =============================================================================

def main():
    """Main function for the market stats page."""
    language_code = get_active_language()
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
    render_title_headers(market.name, language_code)

    # Get service
    market_service = get_market_service()
    price_service = get_price_service(
        db_alias=market.database_alias,
        market_key=market.key,
    )
    sde_repo = get_sde_repository()

    # Sidebar filters
    st.sidebar.header(translate_text(language_code, "low_stock.filters_header"))
    show_all = st.sidebar.checkbox(translate_text(language_code, "market_stats.show_all_data"), value=False)

    category_options_df, all_items_df, _ = get_filter_options()
    category_name_map = {
        int(row["category_id"]): str(row["category_name"])
        for _, row in category_options_df.iterrows()
    }
    category_ids = sorted(category_name_map, key=lambda cid: category_name_map[cid])

    selected_category_id = st.sidebar.selectbox(
        translate_text(language_code, "market_stats.select_category"),
        options=[None] + category_ids,
        index=0,
        key="selected_category_choice",
        format_func=lambda cid: "All Categories" if cid is None else category_name_map[cid],
    )

    active_category_id = None if show_all else selected_category_id
    available_items_df = check_selected_category(active_category_id, show_all)
    if available_items_df is None or available_items_df.empty:
        available_items_df = all_items_df

    item_label_map, item_english_name_map = _build_item_option_labels(
        available_items_df,
        sde_repo,
        language_code,
    )
    item_ids = sorted(item_label_map, key=lambda tid: item_label_map[tid].lower())

    selected_item_id = st.sidebar.selectbox(
        translate_text(language_code, "market_stats.select_item"),
        options=[None] + item_ids,
        index=0,
        format_func=lambda tid: "All Items" if tid is None else item_label_map[tid],
    )
    selected_item_id = check_selected_item(
        selected_item_id,
        item_label_map,
        item_english_name_map,
    )
    selected_item = ss_get("selected_item")

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

    display_formats = get_display_formats(language_code)

    # Initialize fitting data
    fit_df = pd.DataFrame()
    service = get_doctrine_service()
    display_sell_data = apply_localized_type_names(
        sell_data,
        sde_repo,
        language_code,
        logger,
    )
    display_buy_data = apply_localized_type_names(
        buy_data,
        sde_repo,
        language_code,
        logger,
    )
    display_stats = apply_localized_type_names(
        stats,
        sde_repo,
        language_code,
        logger,
    )
    display_fit_df = fit_df.copy()
    display_selected_item = selected_item
    if selected_item_id:
        display_selected_item = get_localized_name(
            selected_item_id,
            item_english_name_map.get(selected_item_id, selected_item or ""),
            sde_repo,
            language_code,
            logger,
        )

    table_col1, table_col2 = st.columns(2, gap="small")
    with table_col1:
        render_comparison_table(
            market_service=market_service,
            price_service=price_service,
            sde_repo=sde_repo,
            type_ids=list(MINERAL_TYPE_IDS),
            title_key="market_stats.mineral_price_comparison",
            language_code=language_code,
        )
    with table_col2:
        render_comparison_table(
            market_service=market_service,
            price_service=price_service,
            sde_repo=sde_repo,
            type_ids=list(ISOTOPE_AND_FUEL_BLOCK_TYPE_IDS),
            title_key="market_stats.isotope_and_fuel_block_comparison",
            language_code=language_code,
        )

    if not sell_data.empty:
        if ss_has('selected_item_id'):
            selected_item_id = ss_get('selected_item_id')
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
        display_sell_data = apply_localized_type_names(
            sell_data,
            sde_repo,
            language_code,
            logger,
        )
        display_buy_data = apply_localized_type_names(
            buy_data,
            sde_repo,
            language_code,
            logger,
        )
        display_stats = apply_localized_type_names(
            stats,
            sde_repo,
            language_code,
            logger,
        )
        display_fit_df = apply_localized_type_names(
            fit_df,
            sde_repo,
            language_code,
            logger,
        )
        display_fit_df = apply_localized_names(
            display_fit_df,
            sde_repo,
            language_code,
            id_column="ship_id",
            name_column="ship_name",
            logger=logger,
            english_name_column="ship_name_en",
        )

        # Headers
        if show_all:
            st.header(translate_text(language_code, "market_stats.all_sell_orders"), divider="green")
        elif ss_has('selected_item_id'):
            selected_item_id = ss_get('selected_item_id')
            try:
                image_id = selected_item_id
                type_name = display_selected_item
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
                        st.subheader(
                            translate_text(language_code, "market_stats.winter_co_doctrine"),
                            divider="orange",
                        )
                        if cat_id in [7, 8, 18]:
                            all_fits = service.repository.get_all_fits()
                            module_fits = all_fits[all_fits['type_id'] == selected_item_id]
                            module_fits = apply_localized_names(
                                module_fits,
                                sde_repo,
                                language_code,
                                id_column="ship_id",
                                name_column="ship_name",
                                logger=logger,
                                english_name_column="ship_name_en",
                            )
                            st.write(
                                drop_localized_backup_columns(
                                    module_fits[['fit_id', 'ship_name', 'fit_qty']].drop_duplicates()
                                )
                            )
                        else:
                            st.write(fit_df[fit_df['type_id'] == selected_item_id]['group_name'].iloc[0])
                except Exception as e:
                    logger.error(f"Error: {e}")
        elif ss_has('selected_category'):
            st.header(
                translate_text(
                    language_code,
                    "market_stats.category_plural",
                    category_name=st.session_state.selected_category,
                ),
                divider="green",
            )

        # Current Market Status
        render_current_market_status_ui(
            sell_data=display_sell_data,
            stats=display_stats,
            selected_item=display_selected_item,
            sell_order_count=sell_order_count,
            sell_total_value=sell_total_value,
            fit_df=fit_df, fits_on_mkt=fits_on_mkt, cat_id=cat_id,
            language_code=language_code,
        )

        # 30-Day Historical Metrics
        with st.expander(
            translate_text(language_code, "market_stats.thirty_day_market_stats"),
            expanded=False,
        ):
            render_30day_metrics_ui(market_service, language_code)

        st.divider()

        # Sell orders display
        display_df = display_sell_data.copy()
        if ss_has('selected_item'):
            st.subheader(
                translate_text(
                    language_code,
                    "market_stats.sell_orders_for",
                    name=display_selected_item,
                ),
                divider="blue",
            )
        elif ss_has('selected_category'):
            cat_label = st.session_state.selected_category
            if not cat_label.endswith("s"):
                cat_label += "s"
            st.subheader(
                translate_text(language_code, "market_stats.sell_orders_for", name=cat_label),
                divider="blue",
            )
        else:
            st.subheader(translate_text(language_code, "market_stats.all_sell_orders"), divider="green")

        if 'is_buy_order' in display_df.columns:
            display_df.drop(columns='is_buy_order', inplace=True)
        st.dataframe(
            drop_localized_backup_columns(display_df),
            hide_index=True,
            column_config=display_formats,
        )

    # Buy orders
    if not buy_data.empty:
        if show_all:
            st.subheader(translate_text(language_code, "market_stats.all_buy_orders"), divider="orange")
        elif ss_has('selected_item'):
            st.subheader(
                translate_text(
                    language_code,
                    "market_stats.buy_orders_for",
                    name=display_selected_item,
                ),
                divider="orange",
            )
        elif ss_has('selected_category'):
            cat_label = st.session_state.selected_category
            if not cat_label.endswith("s"):
                cat_label += "s"
            st.subheader(
                translate_text(language_code, "market_stats.buy_orders_for", name=cat_label),
                divider="orange",
            )
        else:
            st.subheader(translate_text(language_code, "market_stats.all_buy_orders"), divider="orange")

        col1, col2 = st.columns(2)
        with col1:
            if buy_total_value > 0:
                st.metric(
                    translate_text(language_code, "market_stats.market_value_buy_orders"),
                    f"{millify.millify(buy_total_value, precision=2)} ISK",
                )
            else:
                st.metric(translate_text(language_code, "market_stats.market_value_buy_orders"), "0 ISK")
        with col2:
            if buy_order_count > 0:
                st.metric(translate_text(language_code, "market_stats.total_buy_orders"), f"{buy_order_count:,.0f}")
            else:
                st.metric(translate_text(language_code, "market_stats.total_buy_orders"), "0")

        buy_display_df = display_buy_data.copy()
        if 'is_buy_order' in buy_display_df.columns:
            buy_display_df.drop(columns='is_buy_order', inplace=True)
        st.dataframe(
            drop_localized_backup_columns(buy_display_df),
            hide_index=True,
            column_config=display_formats,
        )

    elif not sell_data.empty:
        if st.session_state.selected_item is not None:
            st.write(
                translate_text(
                    language_code,
                    "market_stats.no_current_buy_orders",
                    item_name=display_selected_item,
                )
            )
    else:
        if st.session_state.selected_item is not None:
            st.write(
                translate_text(
                    language_code,
                    "market_stats.no_current_market_orders",
                    item_name=display_selected_item,
                )
            )

    # Market History section
    if st.session_state.get('selected_item') is not None:
        st.subheader(
            translate_text(
                language_code,
                "market_stats.market_history",
                item_name=display_selected_item,
            ),
            divider="blue",
        )
    else:
        if st.session_state.get('selected_category') is not None:
            filter_info = st.session_state.get('selected_category')
            suffix = "s"
        else:
            filter_info = "All Items"
            suffix = ""

        st.subheader(
            translate_text(language_code, "market_stats.price_history", filter_info=filter_info + suffix),
            divider="blue",
        )
        render_isk_volume_chart_ui(market_service, language_code)
        with st.expander(translate_text(language_code, "market_stats.expand_market_history_data")):
            render_isk_volume_table_ui(market_service, language_code)

    # Item history chart
    if ss_has('selected_item'):
        selected_item_id = ss_get('selected_item_id')
    else:
        selected_item_id = None
        st.session_state.selected_item_id = selected_item_id

    if selected_item_id:
        logger.debug(f"Displaying history chart for {selected_item_id}")

        history_chart = market_service.create_history_chart(selected_item_id)
        # Set title from session state (service doesn't have access to st)
        if history_chart is not None and ss_has('selected_item'):
            history_chart.update_layout(title=display_selected_item)

        selected_history = market_service._repo.get_history_by_type(selected_item_id)

        if history_chart:
            st.plotly_chart(history_chart, config={'width': 'content'})

        if selected_history is not None and not selected_history.empty:
                    logger.info(f"Displaying history data for {selected_item_id}")
                    colh1, colh2 = st.columns(2)
                    with colh1:
                        history_df = display_history_data(selected_history, language_code)
                    with colh2:
                        if not history_df.empty:
                            display_history_metrics(history_df, language_code)

        st.divider()

    # Fitting data
    if fit_df is None:
        fit_df = pd.DataFrame()
    if not fit_df.empty:
        st.subheader(translate_text(language_code, "market_stats.fitting_data"), divider="blue")
        selected_item_id = ss_get('selected_item_id')
        try:
            fit_id = fit_df['fit_id'].iloc[0]
        except Exception:
            fit_id = " "
        st.markdown(
            f"<span style='font-weight: bold; color: orange;'>{display_selected_item}</span> | type_id: {selected_item_id} | fit_id: {fit_id}",
            unsafe_allow_html=True,
        )
        if isship:
            column_config = get_fitting_col_config(language_code)
            st.dataframe(
                drop_localized_backup_columns(display_fit_df),
                hide_index=True,
                column_config=column_config,
                width='content',
            )

    # Sidebar bottom
    with st.sidebar:
        display_sync_status(language_code)
        st.sidebar.divider()
        db_check = st.sidebar.button(translate_text(language_code, "market_stats.check_db_state"), width='content')
        if db_check:
            check_db(manual_override=True)
        st.sidebar.divider()
        st.markdown(f"### {translate_text(language_code, 'nav.page.downloads').lstrip('📥')}")
        st.markdown(translate_text(language_code, "market_stats.downloads_hint"))


if __name__ == "__main__":
    main()
