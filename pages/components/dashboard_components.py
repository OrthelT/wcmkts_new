"""Shared dashboard components for market comparison tables.

Extracted from market_stats.py so the dashboard page can render
mineral/isotope/doctrine/module comparison tables.

When a ``dataframe_key`` is passed, tables become selectable: clicking a row
returns the selected ``type_id`` so the calling page can navigate to a detail
page via ``st.switch_page()``.
"""

import pandas as pd
import streamlit as st
from logging_config import setup_logging
from services.type_name_localization import apply_localized_type_names
from ui.column_definitions import get_market_comparison_column_config
from ui.formatters import drop_localized_backup_columns
from ui.i18n import translate_text
from domain.enums import StockStatus

logger = setup_logging(__name__)

# =========================================================================
# Constants
# =========================================================================

MINERAL_TYPE_IDS: tuple[int, ...] = (34, 35, 36, 37, 38, 39, 40, 11399, 81143)
ISOTOPE_AND_FUEL_BLOCK_TYPE_IDS: tuple[int, ...] = (
    16274, 17887, 17888, 17889, 4247, 4312, 4051, 4246, 16273, 16275
)

# =========================================================================
# Helpers
# =========================================================================


def _get_price_result_value(price_result, field_name: str) -> float:
    """Return a numeric price field from a PriceResult-like object."""
    if price_result is None:
        return 0.0
    try:
        return float(getattr(price_result, field_name) or 0.0)
    except (AttributeError, TypeError, ValueError):
        logger.debug("Failed to extract %s from price result: %r", field_name, price_result)
        return 0.0


def _get_eve_icon_url(type_id: int) -> str:
    """Return the EVE icon URL for an item type."""
    return f"https://images.evetech.net/types/{int(type_id)}/icon?size=32"


def _add_jita_prices(df: pd.DataFrame, price_service, type_ids: list[int]) -> pd.DataFrame:
    """Add jita_sell_price, jita_buy_price, and pct_diff_vs_jita_sell columns to a DataFrame."""
    jita_price_map = price_service.get_jita_price_data_map(type_ids)
    df["jita_sell_price"] = df["type_id"].map(
        lambda tid: _get_price_result_value(jita_price_map.get(int(tid)), "sell_price")
    )
    df["jita_buy_price"] = df["type_id"].map(
        lambda tid: _get_price_result_value(jita_price_map.get(int(tid)), "buy_price")
    )
    df["pct_diff_vs_jita_sell"] = 0.0
    has_jita_sell = df["jita_sell_price"] > 0
    df.loc[has_jita_sell, "pct_diff_vs_jita_sell"] = (
        (
            df.loc[has_jita_sell, "current_sell_price"]
            - df.loc[has_jita_sell, "jita_sell_price"]
        )
        / df.loc[has_jita_sell, "jita_sell_price"]
    ) * 100
    return df


def _coerce_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Coerce columns to numeric, filling NaN with 0."""
    for col in columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
    return df


def _get_selected_type_id(event, source_df: pd.DataFrame) -> int | None:
    """Extract the type_id from a dataframe selection event.

    Args:
        event: The return value from st.dataframe(on_select="rerun").
        source_df: The full DataFrame (with type_id column) that was displayed.

    Returns:
        The selected type_id, or None if nothing was selected.
    """
    if event is None:
        return None
    rows = event.selection.get("rows", [])
    if not rows:
        return None
    row_idx = rows[0]
    if row_idx < 0 or row_idx >= len(source_df):
        return None
    return int(source_df.iloc[row_idx]["type_id"])


def _status_cell_style(status_label: str) -> str:
    """Return CSS style for doctrine status cell background color.

    Uses translucent backgrounds so the tint adapts to both light and dark
    Streamlit themes — a soft glow rather than an opaque swatch.
    """
    if isinstance(status_label, str):
        if status_label.startswith("🟡"):
            return "background-color: rgba(220, 250, 60, 0.25)"
        if status_label.startswith("🔴"):
            return "background-color: rgba(239, 83, 80, 0.28)"
    return ""


def _fits_avail_column_style(column: pd.Series, status_labels: pd.Series) -> list[str]:
    """Style only fits_on_mkt cells using status labels."""
    if column.name != "fits_on_mkt":
        return [""] * len(column)
    return [_status_cell_style(status_labels.get(idx, "")) for idx in column.index]


def _jita_diff_cell_style(diff_value: float) -> str:
    """Return CSS text color style for % vs Jita cell based on threshold.

    Uses mid-luminance tones that stay readable on both light and dark
    Streamlit themes.
    """
    try:
        value = float(diff_value)
    except (TypeError, ValueError):
        return ""
    if value > 5:
        return "color: #66bb6a"
    if value < 0:
        return "color: #ef5350"
    return "color: #728049"


# =========================================================================
# Comparison Table (minerals, isotopes, popular modules)
# =========================================================================


def render_comparison_table(
    market_service,
    price_service,
    sde_repo,
    type_ids: list[int],
    title_key: str,
    language_code: str,
    dataframe_key: str | None = None,
) -> int | None:
    """Render a fixed item price comparison table for the active market.

    Args:
        dataframe_key: If provided, enables row selection and returns
            the selected type_id when a row is clicked.

    Returns:
        Selected type_id if a row was clicked, None otherwise.
    """
    comparison_df = market_service.get_current_market_snapshot(type_ids)
    if comparison_df.empty:
        return None

    comparison_df = _add_jita_prices(comparison_df, price_service, type_ids)

    comparison_df["order_volume"] = (
        pd.to_numeric(comparison_df["order_volume"], errors="coerce").fillna(0).round().astype(int)
    )
    comparison_df = apply_localized_type_names(
        comparison_df, sde_repo, language_code, logger,
    )
    comparison_df["type_name"] = comparison_df["type_name"].fillna(
        comparison_df["type_id"].astype(str)
    )
    comparison_df["image_url"] = comparison_df["type_id"].map(_get_eve_icon_url)
    comparison_df = _coerce_numeric(comparison_df, [
        "current_sell_price", "order_volume",
        "jita_sell_price", "jita_buy_price", "pct_diff_vs_jita_sell",
    ])

    display_cols = [
        "image_url", "type_name", "current_sell_price", "order_volume",
        "jita_sell_price", "jita_buy_price", "pct_diff_vs_jita_sell",
    ]
    display_df = comparison_df[display_cols].copy()
    table_df = drop_localized_backup_columns(display_df)
    styled_table = table_df.style.map(
        _jita_diff_cell_style, subset=["pct_diff_vs_jita_sell"]
    )

    st.subheader(translate_text(language_code, title_key), divider="gray")

    if dataframe_key:
        st.caption(translate_text(language_code, "dashboard.hint_click_market_stats"))
        event = st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_market_comparison_column_config(language_code),
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key=dataframe_key,
        )
        return _get_selected_type_id(event, comparison_df)
    else:
        st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_market_comparison_column_config(language_code),
            width="stretch",
        )
        return None


# =========================================================================
# Popular Modules
# =========================================================================


def get_popular_module_type_ids(doctrine_repo, n: int = 10) -> list[int]:
    """Return top N module type_ids by avg_vol from doctrine fits.

    Filters to category_id 7 (Modules) and excludes ship hull rows.
    """
    fits_df = doctrine_repo.get_all_fits()
    if fits_df.empty:
        return []
    modules = fits_df[
        (fits_df["type_id"] != fits_df["ship_id"]) & (fits_df["category_id"] == 7)
    ].copy()
    modules = modules.sort_values("avg_vol", ascending=False).drop_duplicates(
        subset=["type_id"], keep="first"
    )
    return modules.head(n)["type_id"].tolist()


def render_popular_modules_table(
    market_service,
    price_service,
    doctrine_repo,
    sde_repo,
    language_code: str,
    n: int = 10,
    dataframe_key: str | None = None,
) -> int | None:
    """Render popular modules demand & pricing table.

    Returns:
        Selected type_id if a row was clicked, None otherwise.
    """
    type_ids = get_popular_module_type_ids(doctrine_repo, n)
    if not type_ids:
        return None

    snapshot = market_service.get_current_market_snapshot(type_ids)
    if snapshot.empty:
        return None

    snapshot = _add_jita_prices(snapshot, price_service, type_ids)
    snapshot["order_volume"] = (
        pd.to_numeric(snapshot["order_volume"], errors="coerce").fillna(0).round().astype(int)
    )
    snapshot = apply_localized_type_names(snapshot, sde_repo, language_code, logger)
    snapshot["type_name"] = snapshot["type_name"].fillna(snapshot["type_id"].astype(str))
    snapshot["image_url"] = snapshot["type_id"].map(_get_eve_icon_url)
    snapshot = _coerce_numeric(snapshot, [
        "current_sell_price", "order_volume",
        "jita_sell_price", "jita_buy_price", "pct_diff_vs_jita_sell",
    ])

    display_cols = [
        "image_url", "type_name", "current_sell_price", "order_volume",
        "jita_sell_price", "jita_buy_price", "pct_diff_vs_jita_sell",
    ]
    display_df = snapshot[display_cols].copy()
    table_df = drop_localized_backup_columns(display_df)
    styled_table = table_df.style.map(
        _jita_diff_cell_style, subset=["pct_diff_vs_jita_sell"]
    )

    st.subheader(
        translate_text(language_code, "dashboard.popular_modules"), divider="gray",
    )

    if dataframe_key:
        st.caption(translate_text(language_code, "dashboard.hint_click_market_stats"))
        event = st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_market_comparison_column_config(
                language_code, price_format="compact",
            ),
            width="stretch",
            on_select="rerun",
            selection_mode="single-row",
            key=dataframe_key,
        )
        return _get_selected_type_id(event, snapshot)
    else:
        st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_market_comparison_column_config(
                language_code, price_format="compact",
            ),
            width="stretch",
        )
        return None


# =========================================================================
# Doctrine Ships — Stock vs Targets
# =========================================================================


def render_doctrine_ships_table(
    doctrine_repo,
    market_service,
    price_service,
    sde_repo,
    language_code: str,
    dataframe_key: str | None = None,
) -> tuple[int | None, str | None]:
    """Render doctrine ships stock vs targets table with dual navigation.

    Returns:
        (type_id, target) where target is "market_stats" or "doctrine_status",
        or (None, None) if nothing was clicked.
    """
    from ui.column_definitions import get_doctrine_ships_column_config

    fits_df = doctrine_repo.get_all_fits()
    if fits_df.empty:
        return None, None

    # Compute bottleneck fits per fit_id: min fits_on_mkt across all items in each fit.
    # This reflects the true number of complete fits that can be assembled.
    fits_on_mkt_col = pd.to_numeric(fits_df["fits_on_mkt"], errors="coerce").fillna(0).astype(int)
    bottleneck_fits = (
        fits_on_mkt_col.groupby(fits_df["fit_id"])
        .min()
        .rename("bottleneck_fits")
    )

    # One row per fit_id: use hull rows (type_id == ship_id) to get ship info
    hull_rows = fits_df[fits_df["type_id"] == fits_df["ship_id"]].copy()
    hull_rows = hull_rows.drop_duplicates(subset=["fit_id"], keep="first")
    if hull_rows.empty:
        return None, None

    ship_type_ids = hull_rows["ship_id"].unique().tolist()

    # Targets — keyed by fit_id
    targets_df = doctrine_repo.get_all_targets()
    if not targets_df.empty:
        targets_map = targets_df.set_index("fit_id")["ship_target"].to_dict()
    else:
        targets_map = {}

    # Local prices via snapshot
    snapshot = market_service.get_current_market_snapshot(ship_type_ids)

    # Jita prices — batch fetch
    jita_map = price_service.get_jita_price_data_map(ship_type_ids)

    # Build result DataFrame — one row per fit_id
    rows = []
    for _, hull in hull_rows.iterrows():
        sid = int(hull["ship_id"])
        fid = int(hull["fit_id"])
        # Local price from snapshot if available, else from doctrines table
        local_price = 0.0
        if not snapshot.empty and sid in snapshot["type_id"].values:
            match = snapshot[snapshot["type_id"] == sid]
            if not match.empty:
                local_price = float(match.iloc[0].get("current_sell_price", 0) or 0)
        if local_price == 0.0:
            local_price = float(hull.get("price", 0) or 0)

        stock = int(hull.get("total_stock", 0) or 0)
        fits_on_mkt = int(bottleneck_fits.get(fid, 0))
        target = targets_map.get(fid, 0)
        jita_sell = _get_price_result_value(jita_map.get(sid), "sell_price")
        status = StockStatus.from_stock_and_target(fits_on_mkt, target)
        status_icons = {
            StockStatus.CRITICAL: "🔴",
            StockStatus.NEEDS_ATTENTION: "🟡",
            StockStatus.GOOD: "🟢",
        }

        rows.append({
            "type_id": sid,
            "fit_id": fid,
            "image_url": _get_eve_icon_url(sid),
            "type_name": hull.get("ship_name", str(sid)),
            "current_sell_price": local_price,
            "order_volume": stock,
            "jita_sell_price": jita_sell,
            "ship_target": target,
            "fits_on_mkt": fits_on_mkt,
            "status": f"{status_icons.get(status, '')} {status.display_name}",
            "_mkt": False,
            "_doc": False,
        })

    result_df = pd.DataFrame(rows)
    result_df = apply_localized_type_names(result_df, sde_repo, language_code, logger)
    result_df["type_name"] = result_df["type_name"].fillna(result_df["type_id"].astype(str))

    display_cols = [
        "image_url", "type_name", "fit_id", "current_sell_price", "order_volume",
        "jita_sell_price", "ship_target", "fits_on_mkt", "_mkt", "_doc",
    ]
    display_df = result_df[display_cols].copy()

    st.subheader(
        translate_text(language_code, "dashboard.doctrine_ships"), divider="gray",
    )

    if dataframe_key:
        st.caption(
            "📈 = "
            + translate_text(language_code, "dashboard.hint_click_market_stats")
            + "  ·  ⚔️ = "
            + translate_text(language_code, "dashboard.hint_click_doctrine_status")
        )
        table_df = drop_localized_backup_columns(display_df)
        status_labels = result_df["status"]
        styled_table = table_df.style.apply(
            lambda col: _fits_avail_column_style(col, status_labels), axis=0
        )
        edited_df = st.data_editor(
            styled_table,
            hide_index=True,
            column_config=get_doctrine_ships_column_config(language_code),
            disabled=[c for c in display_cols if c not in ("_mkt", "_doc")],
            width="stretch",
            key=dataframe_key,
        )
        # Detect which checkbox was clicked
        for idx in range(len(edited_df)):
            if edited_df.iloc[idx]["_mkt"]:
                return int(result_df.iloc[idx]["type_id"]), "market_stats"
            if edited_df.iloc[idx]["_doc"]:
                return int(result_df.iloc[idx]["type_id"]), "doctrine_status"
        return None, None
    else:
        table_df = drop_localized_backup_columns(result_df[display_cols[:8]].copy())
        status_labels = result_df["status"]
        styled_table = table_df.style.apply(
            lambda col: _fits_avail_column_style(col, status_labels), axis=0
        )
        st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_doctrine_ships_column_config(language_code),
            width="stretch",
        )
        return None, None
