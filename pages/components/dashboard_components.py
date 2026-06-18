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
from ui.column_definitions import (
    get_doctrine_modules_column_config,
    get_doctrine_ships_column_config,
    get_market_comparison_column_config,
)
from ui.formatters import drop_localized_backup_columns
from ui.i18n import translate_text
from domain.enums import StockStatus
from state import ss_get

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


def _jita_price_or_na(price_result, field_name: str) -> float:
    """Return a Jita price field, or NaN when there is no usable Jita price.

    A missing (``None``) or failed/backfilled (``success`` is False) result
    yields NaN so the cell renders blank ("—") rather than a misleading 0 — a
    missing Jita price does not mean the item is free at Jita (data-integrity
    rule). Unlike ``_get_price_result_value`` (which returns 0.0 for absent
    prices), this is used for the dashboard comparison columns, where a 0 would
    compute a nonsense "% vs Jita".
    """
    if price_result is None or not getattr(price_result, "success", False):
        return float("nan")
    return _get_price_result_value(price_result, field_name)


def _get_eve_icon_url(type_id: int) -> str:
    """Return the EVE icon URL for an item type."""
    return f"https://images.evetech.net/types/{int(type_id)}/icon?size=32"


_JITA_UNAVAILABLE_MESSAGE = (
    "Jita price data is unavailable — the backend pricing pipeline may be down "
    "or the jita_prices table is empty/stale. Prices are hidden rather than "
    "shown as zero."
)


def _require_jita_prices(price_service, type_ids: list[int]) -> dict | None:
    """Fetch Jita prices from the backend, surfacing a wholesale outage to the UI.

    The dashboard renders curated, backend-priced item sets (minerals, isotopes,
    doctrine ships/modules). If the backend returns no usable price for ANY
    requested id, the jita_prices table is empty/stale or the pricing pipeline
    is broken — not a normal "unpriced item" case. Per the data-integrity rule
    we refuse to render a table of fabricated zeros: we log the failure and show
    ``st.error``, returning ``None`` so the caller can skip the table gracefully.
    Individual unpriced items still pass through and render blank ("—"), never 0
    (see ``_add_jita_prices`` / ``_jita_price_or_na``).

    This loud, all-or-nothing guard lives ONLY on the dashboard on purpose: the
    dashboard is the landing page, so a total outage is surfaced to every user
    on normal navigation. The other Jita-consuming pages (Pricer, Builder
    Helper, Import Helper, Doctrine) do not repeat the guard — they degrade
    per-item to blank rather than 0, which is correct for a partial outage. The
    only way to miss this alert is a direct deep-link straight to one of those
    pages during a full outage — a negligible edge case.

    Returns:
        The ``{type_id: PriceResult}`` map, or ``None`` when no requested item
        has a usable Jita price (after logging and showing ``st.error``).
    """
    jita_price_map = price_service.get_jita_prices(type_ids).prices
    requested = [int(t) for t in dict.fromkeys(type_ids)]
    has_any_price = any(
        (pr := jita_price_map.get(tid)) is not None
        and getattr(pr, "success", False)
        and getattr(pr, "sell_price", 0) > 0
        for tid in requested
    )
    if requested and not has_any_price:
        logger.error(
            "No Jita prices available from the backend for any of %d requested "
            "items; jita_prices table may be empty or stale.",
            len(requested),
        )
        st.error(_JITA_UNAVAILABLE_MESSAGE)
        return None
    return jita_price_map


def _add_jita_prices(df: pd.DataFrame, jita_price_map: dict) -> pd.DataFrame:
    """Add jita_sell_price, jita_buy_price, and pct_diff_vs_jita_sell columns.

    Expects an already-fetched/validated ``{type_id: PriceResult}`` map (see
    ``_require_jita_prices``); this function only applies the price columns.
    """
    df["jita_sell_price"] = df["type_id"].map(
        lambda tid: _jita_price_or_na(jita_price_map.get(int(tid)), "sell_price")
    )
    df["jita_buy_price"] = df["type_id"].map(
        lambda tid: _jita_price_or_na(jita_price_map.get(int(tid)), "buy_price")
    )
    # NaN (not 0) where there is no usable Jita sell price — a missing price is
    # not a 0% difference. Only rows with a real Jita sell get a computed value.
    df["pct_diff_vs_jita_sell"] = float("nan")
    has_jita_sell = df["jita_sell_price"] > 0
    df.loc[has_jita_sell, "pct_diff_vs_jita_sell"] = (
        (
            df.loc[has_jita_sell, "current_sell_price"]
            - df.loc[has_jita_sell, "jita_sell_price"]
        )
        / df.loc[has_jita_sell, "jita_sell_price"]
    ) * 100
    return df


def _coerce_numeric(
    df: pd.DataFrame, columns: list[str], fill_value: float | None = 0.0
) -> pd.DataFrame:
    """Coerce columns to numeric, filling NaN with ``fill_value``.

    Pass ``fill_value=None`` to preserve NaN — used for Jita price columns,
    where a fabricated 0 would misreport "no Jita data" as "free at Jita"
    (data-integrity rule). NaN renders as a blank cell ("—") instead.
    """
    for col in columns:
        series = pd.to_numeric(df[col], errors="coerce")
        df[col] = series if fill_value is None else series.fillna(fill_value)
    return df


def _get_selected_type_id(event, source_df: pd.DataFrame) -> int | None:
    """Extract the type_id from a dataframe selection event.

    Args:
        event: The return value from st.dataframe(on_select="rerun").
        source_df: A DataFrame (with a type_id column) whose row order matches
            the displayed table — on_select returns a positional index.

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
        # A legitimate click cannot produce an out-of-range index — this means
        # source_df is misaligned with the rendered table (realignment drift or
        # a stale event). Log loudly rather than silently navigating nowhere.
        logger.error(
            "on_select row_idx %r out of range for source_df of length %d "
            "(realignment drift?)",
            row_idx, len(source_df),
        )
        return None
    return int(source_df.iloc[row_idx]["type_id"])


def _resolve_selection(
    event, source_df: pd.DataFrame, display_df: pd.DataFrame, destination: str,
) -> tuple[int | None, str | None]:
    """Map a dataframe selection event back to ``(type_id, destination)``.

    on_select returns a *positional* index into the displayed rows, but
    ``source_df`` is the full (unfiltered) frame. ``display_df`` may be filtered
    (low-stock) and sorted (alphabetical), so its index is a subset of
    source_df's labels in display order. Realign source_df to that order before
    positional extraction, so a click on a filtered table resolves to the row
    the user actually saw rather than the same position in the full frame.

    Returns ``(None, None)`` when nothing was selected.
    """
    selection_source = source_df.loc[display_df.index]
    selected = _get_selected_type_id(event, selection_source)
    if selected is None:
        return None, None
    return selected, destination


def _status_cell_style(status_label: str) -> str:
    """Return CSS style for doctrine status cell background color.

    Uses translucent backgrounds so the tint adapts to both light and dark
    Streamlit themes — a soft glow rather than an opaque swatch.
    """
    if isinstance(status_label, str):
        if status_label.startswith("🟡"):
            return "background-color: rgba(220, 170, 60, 0.55)"
        if status_label.startswith("🔴"):
            return "background-color: rgba(239, 83, 80, 0.28)"
    return ""


def _fits_avail_column_style(column: pd.Series, status_labels: pd.Series) -> list[str]:
    """Style only fits_on_mkt cells using status labels."""
    if column.name != "type_name":
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
    if pd.isna(value):
        return ""
    if value > 5:
        return "color: #66bb6a"
    if value < 0:
        return "color: #ef5350"
    return "color: #728049"


_DESTINATION_OPTIONS = ("doctrine_status", "market_stats")
_DEFAULT_DESTINATION = "doctrine_status"


def _render_destination_toggle(key: str, language_code: str) -> str:
    """Render a per-table destination toggle; return the chosen page token.

    ``segmented_control`` returns None when the user deselects the active
    segment — fall back to the dashboard's primary destination so a row click
    always resolves somewhere (mirrors the prior page-level guard).
    """
    _, toggle_col = st.columns([0.6, 0.4], vertical_alignment="center")
    with toggle_col:
        choice = st.segmented_control(
            translate_text(language_code, "dashboard.row_open_in"),
            options=list(_DESTINATION_OPTIONS),
            format_func=lambda token: translate_text(language_code, f"nav.page.{token}"),
            default=_DEFAULT_DESTINATION,
            key=key,
            label_visibility="collapsed",
        )
    return choice or _DEFAULT_DESTINATION


def _render_row_open_hint(destination: str, language_code: str) -> None:
    """Render the dynamic 'click a row to open it in X' hint below the destination toggle."""
    dest_label = translate_text(language_code, f"nav.page.{destination}")
    st.caption(
        translate_text(language_code, "dashboard.row_open_hint", destination=dest_label)
    )


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

    jita_price_map = _require_jita_prices(price_service, type_ids)
    if jita_price_map is None:
        return None
    comparison_df = _add_jita_prices(comparison_df, jita_price_map)

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
    comparison_df = _coerce_numeric(comparison_df, ["current_sell_price", "order_volume"])
    # Jita columns keep NaN — a missing Jita price renders blank, never 0.
    comparison_df = _coerce_numeric(
        comparison_df,
        ["jita_sell_price", "jita_buy_price", "pct_diff_vs_jita_sell"],
        fill_value=None,
    )

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
            on_select="rerun",
            selection_mode="single-row",
            key=dataframe_key,
            height="stretch",
        )
        return _get_selected_type_id(event, comparison_df)
    else:
        st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_market_comparison_column_config(language_code),
            height="stretch",
        )
        return None


# =========================================================================
# Popular Modules
# =========================================================================


def _compute_module_targets(doctrine_repo) -> pd.DataFrame:
    """Compute target_pct and qty_needed for all non-ship doctrine items.

    Module equivalents (interchangeable faction modules) are resolved before
    aggregation, so type_ids reflect the canonical equivalent.

    For each type_id across all fits it appears in:
    - qty_needed = MAX across fits of:
        if fits_on_mkt < ship_target then (ship_target - fits_on_mkt) * fit_qty else 0
    - target_pct = MIN across fits of: round((fits_on_mkt / ship_target) * 100),
        clipped to [0, 100]. The cap masks overstock (>100%) by design — once a
        fit hits its target, the dashboard treats it as done.
    - fit_count = number of distinct fits that include this type_id.

    Raises:
        ValueError: if any fit referenced in fits_df has no matching row in
            ship_targets. Per AGENTS.md data-integrity rule, missing target
            configuration is surfaced loudly rather than coerced to 0.

    Returns DataFrame with columns: type_id, qty_needed, target_pct, fit_count
    """
    fits_df = doctrine_repo.get_all_fits()
    if fits_df.empty:
        return pd.DataFrame()

    fits_df = _apply_equivalents_to_fits(fits_df)

    targets_df = doctrine_repo.get_all_targets()
    if targets_df.empty:
        return pd.DataFrame()

    # Filter to non-ship rows
    modules = fits_df[fits_df["type_id"] != fits_df["ship_id"]].copy()
    if modules.empty:
        return pd.DataFrame()

    # Merge targets
    modules = modules.merge(
        targets_df[["fit_id", "ship_target"]], on="fit_id", how="left",
    )

    # Detect fits with no configured ship_target row (left-join miss).
    # Coercing NaN to 0 here would silently drive target_pct=0 via MIN-aggregation.
    missing_mask = modules["ship_target"].isna()
    if missing_mask.any():
        missing_fit_ids = sorted(modules.loc[missing_mask, "fit_id"].unique().tolist())
        logger.error(
            "Doctrine fits missing ship_targets configuration: %s", missing_fit_ids,
        )
        raise ValueError(
            f"Missing ship_targets configuration for fit_ids: {missing_fit_ids}"
        )

    modules["ship_target"] = (
        pd.to_numeric(modules["ship_target"], errors="coerce").fillna(0).astype(int)
    )
    modules["fits_on_mkt"] = (
        pd.to_numeric(modules["fits_on_mkt"], errors="coerce").fillna(0).astype(int)
    )
    modules["fit_qty"] = (
        pd.to_numeric(modules["fit_qty"], errors="coerce").fillna(0).astype(int)
    )

    # Per-row calculations
    shortfall = (modules["ship_target"] - modules["fits_on_mkt"]).clip(lower=0)
    modules["row_qty_needed"] = shortfall * modules["fit_qty"]

    modules["row_target_pct"] = 0.0
    has_target = modules["ship_target"] > 0
    modules.loc[has_target, "row_target_pct"] = (
        (modules.loc[has_target, "fits_on_mkt"] / modules.loc[has_target, "ship_target"] * 100)
        .round()
    )

    agg = modules.groupby("type_id").agg(
        qty_needed=("row_qty_needed", "max"),
        target_pct=("row_target_pct", "min"),
        fit_count=("fit_id", "nunique"),
    ).reset_index()

    agg["target_pct"] = agg["target_pct"].clip(upper=100).astype(int)
    agg["qty_needed"] = agg["qty_needed"].astype(int)
    agg["fit_count"] = agg["fit_count"].astype(int)

    return agg


_FILTER_OPTIONS = ("low_stock", "all")


def _render_filter_columns(filter_key: str, language_code: str) -> str:
    option_labels = {
        "low_stock": translate_text(language_code, "dashboard.filter_low_stock"),
        "all": translate_text(language_code, "dashboard.filter_all"),
    }
    filter_col1, filter_col2 = st.columns(spec=[0.3, 0.7], width=400, vertical_alignment="center")
    with filter_col1:
        st.menu_button(
            label=translate_text(language_code, "dashboard.filter_label"),
            options=[option_labels[opt] for opt in _FILTER_OPTIONS],
            type="tertiary",
            key=filter_key,
        )
    selection_label = ss_get(filter_key, option_labels["low_stock"])
    selection_token = next(
        (token for token, label in option_labels.items() if label == selection_label),
        "low_stock",
    )
    with filter_col2:
        showing_label = translate_text(language_code, "dashboard.filter_showing")
        st.markdown(
            f"<span style='color: orange;'>{showing_label}</span> {option_labels[selection_token]}",
            unsafe_allow_html=True,
        )
    return selection_token


def render_popular_modules_table(
    market_service,
    price_service,
    doctrine_repo,
    sde_repo,
    language_code: str,
    dataframe_key: str | None = None,
) -> tuple[int | None, str | None]:
    """Render doctrine modules table with stock, target %, qty needed, and fit count.

    Shows all non-ship items from the doctrines table, sorted alphabetically.
    The per-table destination toggle decides whether a row click opens Doctrine
    Status or Market Stats.

    Returns:
        (type_id, destination) where destination is the toggle's value, or
        (None, None) if nothing was clicked.
    """
    try:
        module_targets = _compute_module_targets(doctrine_repo)
    except ValueError as e:
        st.error(f"Doctrine configuration error: {e}")
        return None, None
    if module_targets.empty:
        return None, None

    type_ids = module_targets["type_id"].tolist()

    snapshot = market_service.get_current_market_snapshot(type_ids)
    if snapshot.empty:
        return None, None

    jita_price_map = _require_jita_prices(price_service, type_ids)
    if jita_price_map is None:
        return None, None
    snapshot = _add_jita_prices(snapshot, jita_price_map)
    snapshot["order_volume"] = (
        pd.to_numeric(snapshot["order_volume"], errors="coerce").fillna(0).round().astype(int)
    )

    # Merge target data
    snapshot = snapshot.merge(module_targets, on="type_id", how="left")
    snapshot["target_pct"] = snapshot["target_pct"].fillna(0).astype(int)
    snapshot["qty_needed"] = snapshot["qty_needed"].fillna(0).astype(int)
    snapshot["fit_count"] = snapshot["fit_count"].fillna(0).astype(int)

    snapshot = apply_localized_type_names(snapshot, sde_repo, language_code, logger)
    snapshot["type_name"] = snapshot["type_name"].fillna(snapshot["type_id"].astype(str))
    snapshot["image_url"] = snapshot["type_id"].map(_get_eve_icon_url)
    snapshot = _coerce_numeric(snapshot, ["current_sell_price", "order_volume"])
    # Jita columns keep NaN — a missing Jita price renders blank, never 0.
    snapshot = _coerce_numeric(
        snapshot,
        ["jita_sell_price", "jita_buy_price", "pct_diff_vs_jita_sell"],
        fill_value=None,
    )

    # Sort alphabetically by item name
    snapshot = snapshot.sort_values("type_name", key=lambda s: s.str.lower())

    display_cols = [
        "type_id", "image_url", "type_name", "target_pct", "order_volume",
        "fit_count", "qty_needed", "current_sell_price", "jita_sell_price",
        "jita_buy_price", "pct_diff_vs_jita_sell",
    ]

    st.subheader(
        translate_text(language_code, "dashboard.doctrine_modules"), divider="gray",
    )
    destination = _render_destination_toggle("dash_modules_destination", language_code)
    _render_row_open_hint(destination, language_code)
    display_df = snapshot[display_cols].copy()

    mod_dash_filter_selection = _render_filter_columns("mod_dash_filter", language_code)
    if mod_dash_filter_selection == "low_stock":
        display_df = display_df[display_df["target_pct"] < 100]

    table_df = drop_localized_backup_columns(display_df)
    styled_table = table_df.style.map(
        _jita_diff_cell_style, subset=["pct_diff_vs_jita_sell"]
    )

    if dataframe_key:
        event = st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_doctrine_modules_column_config(language_code),
            on_select="rerun",
            selection_mode="single-row",
            key=dataframe_key,
            width="stretch",
        )
        return _resolve_selection(event, snapshot, display_df, destination)

    st.dataframe(
        styled_table,
        hide_index=True,
        column_config=get_doctrine_modules_column_config(language_code),
        width="stretch",
    )
    return None, None


# =========================================================================
# Doctrine Ships — Stock vs Targets
# =========================================================================


def _compute_ship_target_pct(fits_on_mkt: int, target: int) -> int:
    """Return progress toward ship_target as an int percent in [0, 100].

    Cap at 100 mirrors `_compute_module_targets` — overstock is masked by design.
    target<=0 yields 0 (callers should detect "no target configured" upstream
    rather than relying on this fallback).
    """
    if target <= 0:
        return 0
    return min(round((fits_on_mkt / target) * 100), 100)


def _apply_equivalents_to_fits(fits_df: pd.DataFrame) -> pd.DataFrame:
    """Adjust fits_on_mkt using aggregated stock across equivalent modules.

    Mirrors FitDataBuilder.apply_module_equivalents() so the dashboard
    bottleneck calculation accounts for interchangeable faction modules.
    """
    try:
        from settings_service import SettingsService
        if not SettingsService().use_equivalents:
            return fits_df
    except Exception:
        logger.exception("Failed to read use_equivalents setting; returning unmodified fits")
        return fits_df

    try:
        from services.module_equivalents_service import get_module_equivalents_service
        equiv_service = get_module_equivalents_service()
        type_ids_with_equivs = equiv_service.get_type_ids_with_equivalents()
        if not type_ids_with_equivs:
            return fits_df
    except Exception:
        logger.exception(
            "Failed to load module equivalents service; returning unmodified fits"
        )
        return fits_df

    modules_to_update = fits_df[
        fits_df["type_id"].isin(type_ids_with_equivs)
    ]["type_id"].unique()

    if len(modules_to_update) == 0:
        return fits_df

    fits_df = fits_df.copy()
    aggregated_stocks = equiv_service.get_aggregated_stock(list(modules_to_update))

    # Vectorized update: rows whose type_id has an aggregated equivalent stock
    # get fits_on_mkt = total_stock // fit_qty (or total_stock when fit_qty<=0).
    mask = fits_df["type_id"].isin(aggregated_stocks)
    if mask.any():
        total_stock = fits_df.loc[mask, "type_id"].map(aggregated_stocks).astype("int64")
        fit_qty = pd.to_numeric(fits_df.loc[mask, "fit_qty"], errors="coerce").fillna(0).astype("int64")
        fits_df.loc[mask, "fits_on_mkt"] = total_stock.where(
            fit_qty <= 0, total_stock // fit_qty.where(fit_qty > 0, 1)
        )

    return fits_df


def render_doctrine_ships_table(
    doctrine_repo,
    market_service,
    price_service,
    sde_repo,
    language_code: str,
    dataframe_key: str | None = None,
) -> tuple[int | None, str | None]:
    """Render doctrine ships stock vs targets table.

    The per-table destination toggle decides whether a row click opens Doctrine
    Status or Market Stats.

    Returns:
        (type_id, destination) where destination is the toggle's value, or
        (None, None) if nothing was clicked.
    """
    fits_df = doctrine_repo.get_all_fits()
    if fits_df.empty:
        return None, None

    # Apply module equivalents: recalculate fits_on_mkt using combined stock
    # across interchangeable modules (mirrors FitDataBuilder.apply_module_equivalents)
    fits_df = _apply_equivalents_to_fits(fits_df)

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

    # Jita prices — batch fetch from the backend jita_prices table.
    # Surfaces st.error + logs and bails if the backend has no data at all.
    jita_map = _require_jita_prices(price_service, ship_type_ids)
    if jita_map is None:
        return None, None

    # Build result DataFrame — one row per fit_id
    rows = []
    missing_target_fids: list[int] = []
    for _, hull in hull_rows.iterrows():
        sid = int(hull["ship_id"])
        fid = int(hull["fit_id"])

        # Distinguish "no target row" (None) from "target=0" — surfacing the
        # former as 0% would silently misreport doctrine readiness.
        if fid not in targets_map:
            missing_target_fids.append(fid)
            continue

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
        target = int(targets_map[fid])
        jita_sell = _jita_price_or_na(jita_map.get(sid), "sell_price")
        status = StockStatus.from_stock_and_target(fits_on_mkt, target)
        status_icons = {
            StockStatus.CRITICAL: "🔴",
            StockStatus.NEEDS_ATTENTION: "🟡",
            StockStatus.GOOD: "🟢",
        }

        target_pct = _compute_ship_target_pct(fits_on_mkt, target)

        rows.append({
            "type_id": sid,
            "fit_id": fid,
            "image_url": _get_eve_icon_url(sid),
            "type_name": hull.get("ship_name", str(sid)),
            "target_pct": target_pct,
            "current_sell_price": local_price,
            "order_volume": stock,
            "jita_sell_price": jita_sell,
            "ship_target": target,
            "fits_on_mkt": fits_on_mkt,
            "status": f"{status_icons.get(status, '')} {status.display_name}",
        })

    if missing_target_fids:
        logger.error(
            "Doctrine fits missing ship_targets configuration (excluded from "
            "ships table): %s",
            sorted(missing_target_fids),
        )
        st.error(
            "Doctrine configuration error: fits missing ship_target rows: "
            f"{sorted(missing_target_fids)}. These fits are excluded from the "
            "ships table — add ship_targets entries to surface them."
        )

    if not rows:
        return None, None

    result_df = pd.DataFrame(rows)
    result_df = apply_localized_type_names(result_df, sde_repo, language_code, logger)
    result_df["type_name"] = result_df["type_name"].fillna(result_df["type_id"].astype(str))

    display_cols = [
        "fit_id", "image_url", "type_name", "target_pct", "order_volume",
        "fits_on_mkt", "ship_target", "current_sell_price", "jita_sell_price",
    ]

    display_df = result_df[display_cols].copy()
    st.subheader(
        translate_text(language_code, "dashboard.doctrine_ships"), divider="gray",
    )
    destination = _render_destination_toggle("dash_ships_destination", language_code)
    _render_row_open_hint(destination, language_code)
    doc_dash_filter_selection = _render_filter_columns("doc_dash_filter", language_code)
    if doc_dash_filter_selection == "low_stock":
        display_df = display_df[display_df["target_pct"] < 100]

    table_df = drop_localized_backup_columns(display_df)
    status_labels = result_df["status"]
    if doc_dash_filter_selection == "all":
        styled_table = table_df.style.apply(
            lambda col: _fits_avail_column_style(col, status_labels), axis=0
        )
    else:
        styled_table = table_df

    if dataframe_key:
        event = st.dataframe(
            styled_table,
            hide_index=True,
            column_config=get_doctrine_ships_column_config(language_code),
            on_select="rerun",
            selection_mode="single-row",
            key=dataframe_key,
            width="stretch",
        )
        return _resolve_selection(event, result_df, display_df, destination)

    st.dataframe(
        styled_table,
        hide_index=True,
        column_config=get_doctrine_ships_column_config(language_code),
        width="stretch",
    )
    return None, None
