"""
Pricer Page

Streamlit page for pricing Eve Online items and fittings.
Accepts EFT fittings or tab-separated item lists and displays
both Jita and 4-HWWF market prices.

Layout follows the Janice appraisal pattern: results above, input below,
all wrapped in a single bordered card. EFT fittings additionally render a
"Fit Availability" hero showing how many copies of the fit are available
from current local market stock and which modules are bottlenecks.
"""

from datetime import datetime, timezone

import pandas as pd
from repositories.sde_repo import SDERepository
import streamlit as st
from millify import millify

from domain import InputFormat
from domain.enums import StockStatus
from domain.market_config import MarketConfig
from domain.pricer import FitAvailabilitySummary, ItemAvailability, PricerResult
from init_db import ensure_market_db_ready
from logging_config import setup_logging
from pages.components.header import render_page_title
from pages.components.layout import render_legal_notice
from repositories import get_sde_repository
from services import get_pricer_service
from services.module_equivalents_service import get_module_equivalents_service
from services.pricer_service import compute_fit_availability
from services.type_name_localization import apply_localized_names, get_localized_name
from state import get_active_language, ss_get, ss_has, ss_init, ss_set
from ui.formatters import (
    drop_localized_backup_columns,
    get_image_url,
)
from ui.i18n import translate_text
from ui.market_selector import render_market_selector

logger = setup_logging(__name__, log_file="pricer.log")


# =============================================================================
# Formatting helpers
# =============================================================================


def format_isk(value: float) -> str:
    """Format ISK value with millify for compact display."""
    if value == 0:
        return "0"
    return millify(value, precision=2)


def round_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Round float columns for cleaner display."""
    df2 = df.copy()
    round_cols = [col for col in df2.columns if df2[col].dtype == "float64"]
    for column in round_cols:
        df2[column] = df2[column].apply(
            lambda x: round(x, 1) if x < 1000 else round(x, 0)
        )
    return df2


# =============================================================================
# Column configs
# =============================================================================


def get_pricer_column_config(short_name: str = "4H", language_code: str = "en") -> dict:
    """Column configuration for the main pricer results table."""
    return {
        "image_url": st.column_config.ImageColumn(
            translate_text(language_code, "pricer.column_icon"),
            help=translate_text(language_code, "pricer.column_icon_help"),
            width="small",
        ),
        "type_id": st.column_config.NumberColumn(
            "ID",
            help=translate_text(language_code, "pricer.column_type_id_help"),
            width="small",
        ),
        "Item": st.column_config.TextColumn(
            translate_text(language_code, "common.item"),
            help=translate_text(language_code, "pricer.column_item_help"),
            width="medium",
        ),
        "Qty": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_qty"),
            help=translate_text(language_code, "pricer.column_qty_help"),
            format="localized",
        ),
        "Slot": st.column_config.TextColumn(
            translate_text(language_code, "pricer.column_slot"),
            help=translate_text(language_code, "pricer.column_slot_help"),
            width="small",
        ),
        "Local Sell": st.column_config.NumberColumn(
            translate_text(
                language_code, "pricer.column_local_sell", market_name=short_name
            ),
            help=translate_text(
                language_code, "pricer.column_local_sell_help", market_name=short_name
            ),
            format="localized",
        ),
        "Local Sell Vol": st.column_config.NumberColumn(
            translate_text(
                language_code, "pricer.column_local_sell_volume", market_name=short_name
            ),
            help=translate_text(
                language_code,
                "pricer.column_local_sell_volume_help",
                market_name=short_name,
            ),
            format="localized",
        ),
        "Jita Sell": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_sell"),
            help=translate_text(language_code, "pricer.column_jita_sell_help"),
            format="localized",
        ),
        "Jita Buy": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_buy"),
            help=translate_text(language_code, "pricer.column_jita_buy_help"),
            format="localized",
        ),
        "Jita Sell Total": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_sell_total"),
            help=translate_text(language_code, "pricer.column_jita_sell_total_help"),
            format="localized",
        ),
        "Jita Buy Total": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_buy_total"),
            help=translate_text(language_code, "pricer.column_jita_buy_total_help"),
            format="localized",
        ),
        "Local Buy": st.column_config.NumberColumn(
            translate_text(
                language_code, "pricer.column_local_buy", market_name=short_name
            ),
            help=translate_text(
                language_code, "pricer.column_local_buy_help", market_name=short_name
            ),
            format="localized",
        ),
        "Local Sell Total": st.column_config.NumberColumn(
            translate_text(
                language_code, "pricer.column_local_sell_total", market_name=short_name
            ),
            help=translate_text(
                language_code,
                "pricer.column_local_sell_total_help",
                market_name=short_name,
            ),
            format="localized",
        ),
        "Local Buy Total": st.column_config.NumberColumn(
            translate_text(
                language_code, "pricer.column_local_buy_total", market_name=short_name
            ),
            help=translate_text(
                language_code,
                "pricer.column_local_buy_total_help",
                market_name=short_name,
            ),
            format="localized",
        ),
        "Volume": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_volume"),
            help=translate_text(language_code, "pricer.column_volume_help"),
            format="localized",
        ),
        "Total Volume": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_total_volume"),
            help=translate_text(language_code, "pricer.column_total_volume_help"),
            format="localized",
        ),
        "Category": st.column_config.TextColumn(
            translate_text(language_code, "common.category"),
            help=translate_text(language_code, "pricer.column_category_help"),
        ),
        "Avg Daily Vol": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_avg_daily_volume"),
            help=translate_text(language_code, "pricer.column_avg_daily_volume_help"),
            format="localized",
        ),
        "Days of Stock": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_days_of_stock"),
            help=translate_text(language_code, "pricer.column_days_of_stock_help"),
            format="%.1f",
        ),
        "Is Doctrine": st.column_config.CheckboxColumn(
            translate_text(language_code, "nav.page.doctrine_status").lstrip("⚔️"),
            help=translate_text(language_code, "pricer.column_is_doctrine_help"),
            width="small",
        ),
        "Doctrine Ships": st.column_config.ListColumn(
            translate_text(language_code, "low_stock.column_used_in_fits"),
            help=translate_text(language_code, "pricer.column_doctrine_ships_help"),
            width="medium",
        ),
    }


def _fit_availability_column_config(language_code: str, short_name: str = "4H") -> dict:
    """Column configuration for the Fit Availability breakdown table."""
    return {
        "image_url": st.column_config.ImageColumn(
            translate_text(language_code, "pricer.column_icon"),
            help=translate_text(language_code, "pricer.column_icon_help"),
            width="small",
        ),
        "type_id": st.column_config.NumberColumn(
            "ID",
            help=translate_text(language_code, "pricer.column_type_id_help"),
            width="small",
        ),
        "Item": st.column_config.TextColumn(
            translate_text(language_code, "common.item"),
            help=translate_text(language_code, "pricer.column_item_help"),
            width="medium",
        ),
        "Slot": st.column_config.TextColumn(
            translate_text(language_code, "pricer.column_slot"),
            help=translate_text(language_code, "pricer.column_slot_help"),
            width="small",
        ),
        "Per Fit": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.fits.column_required"),
            format="localized",
        ),
        "In Stock": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.fits.column_in_stock"),
            format="localized",
        ),
        "Fits": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.fits.column_fits_possible"),
            format="localized",
        ),
        "Local Sell": st.column_config.NumberColumn(
            translate_text(
                language_code, "pricer.column_local_sell", market_name=short_name
            ),
            help=translate_text(
                language_code, "pricer.column_local_sell_help", market_name=short_name
            ),
            format="localized",
        ),
        "Status": st.column_config.TextColumn(
            translate_text(language_code, "pricer.fits.column_status"),
            width="small",
        ),
        "Equivalents": st.column_config.TextColumn(
            translate_text(language_code, "pricer.fits.column_equivalents"),
            help=translate_text(language_code, "pricer.fits.column_equivalents_help"),
            width="small",
        ),
    }


# =============================================================================
# Style functions
# =============================================================================


def highlight_doctrine_rows(row):
    if row.get("Is Doctrine", False):
        return ["background-color: rgba(50, 143, 237, 0.3)"] * len(row)
    return [""] * len(row)


def highlight_low_stock(val):
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v <= 3:
        return "background-color: #fc4103"
    if v <= 7:
        return "background-color: #c76d14"
    return ""


def _highlight_fit_row(row, fits_available: int):
    """Red tint for bottleneck rows, light orange for near-bottleneck."""
    fits = row.get("Fits", None)
    if fits is None:
        return [""] * len(row)
    if fits == fits_available:
        return ["background-color: rgba(239, 83, 80, 0.25)"] * len(row)
    if fits <= fits_available + 2:
        return ["background-color: rgba(216, 138, 34, 0.15)"] * len(row)
    return [""] * len(row)


# =============================================================================
# Layout helpers — Janice-style appraisal card
# =============================================================================


def render_header(language_code: str):
    render_page_title(translate_text(language_code, "pricer.title"))


def _render_appraisal_title(
    result: PricerResult | None,
    market,
    language_code: str,
):
    """Top-of-card title row, mirroring Janice's appraisal heading."""
    if result is None:
        st.markdown(
            f'<div style="font-size:0.95rem; font-weight:600; opacity:0.85; margin-bottom:6px;">'
            f"{translate_text(language_code, 'pricer.appraisal.title_empty')}"
            "</div>",
            unsafe_allow_html=True,
        )
        return

    fit_name = (
        result.fit_name
        or result.ship_name
        or translate_text(language_code, "pricer.appraisal.fit_name_default")
    )
    title = translate_text(
        language_code,
        "pricer.appraisal.title",
        fit_name=fit_name,
        market_name=market.name,
    )

    st.markdown(
        f'<div style="font-size:1rem; font-weight:600; margin-bottom:6px;">{title}</div>',
        unsafe_allow_html=True,
    )


def _render_fit_appraisal_header(
    result: PricerResult, language_code: str, sde_repo: SDERepository
):
    ship_type_id = None
    for item in result.items:
        if item.item.category_name == "Ship":
            ship_type_id = item.type_id
            break

    if result.ship_name:
        localized_ship_name = get_localized_name(
            ship_type_id,
            result.ship_name,
            sde_repo,
            language_code,
            logger,
        )

        col_image, col_header = st.columns([0.1, 0.9])
        with col_image:
            if ship_type_id:
                st.image(
                    get_image_url(ship_type_id, 128, isship=True),
                    width=128,
                )
        with col_header:
            st.subheader(localized_ship_name, divider="orange", width="stretch")


def _stat_cell(label: str, value: str) -> str:
    return (
        '<div style="display:flex; justify-content:space-between; '
        "background:rgba(127,127,127,0.08); padding:3px 10px; "
        'border-radius:3px; margin-bottom:3px; font-size:0.85rem;">'
        f'<span style="opacity:0.7;">{label}</span>'
        f'<span style="font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-weight:600;">{value}</span>'
        "</div>"
    )


def _render_summary_stats_grid(result: PricerResult, market, language_code: str):
    """2-column stats grid (Created/Priced at/Volume + local sell + Jita sell/buy totals)."""
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    local_sell_total = result.local_sell_grand_total
    jita_sell_total = result.jita_sell_grand_total
    jita_buy_total = result.jita_buy_grand_total
    volume_label = f"{result.total_volume:,.2f} m³"

    local_sell_label = translate_text(
        language_code,
        "pricer.column_local_sell_total",
        market_name=market.short_name,
    )

    left_html = "".join(
        [
            _stat_cell(
                translate_text(language_code, "pricer.appraisal.label_created"),
                created_at,
            ),
            _stat_cell(
                translate_text(language_code, "pricer.appraisal.label_priced_at"),
                market.name,
            ),
            _stat_cell(
                translate_text(language_code, "pricer.appraisal.label_volume"),
                volume_label,
            ),
        ]
    )
    right_html = "".join(
        [
            _stat_cell(
                local_sell_label,
                f"{format_isk(local_sell_total)} ISK",
            ),
            _stat_cell(
                translate_text(language_code, "pricer.column_jita_sell_total"),
                f"{format_isk(jita_sell_total)} ISK",
            ),
            _stat_cell(
                translate_text(language_code, "pricer.column_jita_buy_total"),
                f"{format_isk(jita_buy_total)} ISK",
            ),
        ]
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(left_html, unsafe_allow_html=True)
    with c2:
        st.markdown(right_html, unsafe_allow_html=True)


def _render_action_chips(result: PricerResult, language_code: str):
    """Compact action row replicating Janice's Fork/Reprocess/Compress chips."""
    csv_data = drop_localized_backup_columns(result.to_dataframe()).to_csv(index=False)
    filename = "priced_items.csv"
    if result.ship_name:
        filename = f"{result.ship_name.replace(' ', '_')}_priced.csv"

    c1, c2, _ = st.columns([1.2, 1, 6.4])
    with c1:
        st.download_button(
            translate_text(language_code, "pricer.appraisal.action_download"),
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            use_container_width=True,
        )
    with c2:
        if st.button(
            translate_text(language_code, "pricer.appraisal.action_reset"),
            use_container_width=True,
            key="pricer_reset",
        ):
            ss_set("pricer_result", None)
            st.session_state.pop("pricer_result", None)
            st.rerun()


def _render_control_row(language_code: str):
    """Toggle row above the input area."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ss_set(
            "pricer_show_jita",
            st.checkbox(
                translate_text(language_code, "pricer.show_jita_prices"),
                value=ss_get("pricer_show_jita", True),
                key="show_jita_prices",
            ),
        )
    with c2:
        ss_set(
            "pricer_show_stock_metrics",
            st.checkbox(
                translate_text(language_code, "pricer.show_stock_metrics"),
                value=ss_get("pricer_show_stock_metrics", True),
                key="show_stock_metrics",
                help=translate_text(language_code, "pricer.show_stock_metrics_help"),
            ),
        )
    with c3:
        ss_set(
            "pricer_highlight_doctrine",
            st.checkbox(
                translate_text(language_code, "pricer.highlight_doctrine_items"),
                value=ss_get("pricer_highlight_doctrine", True),
                key="highlight_doctrine",
                help=translate_text(
                    language_code, "pricer.highlight_doctrine_items_help"
                ),
            ),
        )
    with c4:
        ss_set(
            "pricer_fit_equivalents",
            st.checkbox(
                translate_text(language_code, "pricer.fits.toggle_equivalents"),
                value=ss_get("pricer_fit_equivalents", True),
                key="pricer_fit_equivalents_cb",
                help=translate_text(
                    language_code, "pricer.fits.toggle_equivalents_help"
                ),
            ),
        )


def _render_items_table(result: PricerResult, market, sde_repo, language_code: str):
    """Render the main pricer results table (existing behaviour, regrouped)."""
    if not result.items:
        return

    df = result.to_dataframe()
    df = apply_localized_names(
        df,
        sde_repo,
        language_code,
        id_column="type_id",
        name_column="Item",
        logger=logger,
        english_name_column="Item_en",
    )
    df["Total Volume"] = df["Qty"] * df["Volume"]

    show_jita = ss_get("pricer_show_jita", True)
    show_stock = ss_get("pricer_show_stock_metrics", True)
    highlight_doctrine = ss_get("pricer_highlight_doctrine", True)

    static_columns = ["image_url", "type_id", "Item", "Qty"]
    price_columns = (
        ["Local Sell", "Local Buy", "Local Sell Vol", "Jita Sell", "Jita Buy"]
        if show_jita
        else ["Local Sell", "Local Buy", "Local Sell Vol"]
    )
    stock_columns = ["Avg Daily Vol", "Days of Stock"]
    doctrine_columns = ["Is Doctrine", "Doctrine Ships"]
    always_show = ["Volume", "Category"]

    column_order = static_columns + price_columns
    if show_stock:
        column_order += stock_columns
    if highlight_doctrine:
        column_order += doctrine_columns
    column_order += always_show
    column_order = [c for c in column_order if c in df.columns]

    styled_df = drop_localized_backup_columns(df.copy())

    if highlight_doctrine and "Is Doctrine" in styled_df.columns:
        styled_df = styled_df.style.apply(highlight_doctrine_rows, axis=1)
        if show_stock and "Days of Stock" in df.columns:
            styled_df = styled_df.map(highlight_low_stock, subset=["Days of Stock"])
    elif show_stock and "Days of Stock" in df.columns:
        styled_df = styled_df.style.map(highlight_low_stock, subset=["Days of Stock"])

    st.markdown(
        f'<div style="font-size:0.9rem; font-weight:600; margin:8px 0 4px 0;">'
        f"{translate_text(language_code, 'pricer.items')}"
        "</div>",
        unsafe_allow_html=True,
    )
    st.data_editor(
        styled_df,
        hide_index=True,
        column_config=get_pricer_column_config(market.short_name, language_code),
        width="stretch",
        column_order=column_order,
        key="pricer_items_table",
    )


# =============================================================================
# Fit Availability — UI helpers
# =============================================================================


def _build_aggregated_stock_map(type_ids: list[int]) -> dict[int, int]:
    """Return {type_id: total_stock} for items that actually have equivalents.

    Items without equivalents are omitted, so compute_fit_availability falls
    back to raw_stock for them. This avoids substituting non-equivalent stock
    that comes from a different aggregation source.
    """
    service = get_module_equivalents_service()
    aggregated: dict[int, int] = {}
    for tid in type_ids:
        try:
            if not service.has_equivalents(tid):
                continue
            group = service.get_equivalence_group(tid)
            if group is not None:
                aggregated[tid] = group.total_stock
        except Exception as exc:
            logger.warning("Equivalents lookup failed for type_id %s: %s", tid, exc)
    return aggregated


def _render_fit_availability_hero(summary: FitAvailabilitySummary, language_code: str):
    """The big headline number, ship icon, key metrics, and progress bar."""

    col_count, col_right = st.columns([0.34, 0.66], vertical_alignment="center")
    with col_count:
        unit_label = translate_text(language_code, "pricer.fits.headline_unit")
        with st.container(horizontal_alignment="center"):
            st.metric(
                label=unit_label,
                value=f":green[{summary.fits_available}]",
                border=True,
                width="content",
            )
    with col_right:
        m1, m2, m3 = st.columns(3)
        m1.metric(
            translate_text(language_code, "pricer.fits.metric_items_in_fit"),
            f"{summary.counted_item_count}",
        )
        m2.metric(
            translate_text(language_code, "pricer.fits.metric_bottleneck"),
            f"{len(summary.bottleneck_items)}",
        )
        m3.metric(
            translate_text(language_code, "pricer.fits.metric_total_isk"),
            f":orange[{format_isk(summary.total_isk_per_fit)}] ISK",
        )
        if not summary.total_isk_complete:
            n = summary.unpriced_item_count
            key = "pricer.fits.total_isk_partial" if n == 1 else "pricer.fits.total_isk_partial_plural"
            m3.caption(translate_text(language_code, key, count=n))

    if summary.stock_unknown_count > 0:
        n = summary.stock_unknown_count
        key = "pricer.fits.stock_unknown_warning" if n == 1 else "pricer.fits.stock_unknown_warning_plural"
        st.warning(translate_text(language_code, key, count=n))

    if summary.bottleneck_items:
        b = summary.bottleneck_items[0]
        st.space()
        st.caption(
            translate_text(
                language_code,
                "pricer.fits.bottleneck_caption",
                name=b.type_name,
                stock=f"{b.stock_used:,}",
                required=f"{b.quantity_per_fit:,}",
            )
        )

def _format_bottleneck_line(item: ItemAvailability) -> str:
    prefix = "🔄 " if item.used_equivalents else ""
    return (
        f"- {prefix}**{item.type_name}** — have {item.stock_used:,}, "
        f"need {item.quantity_per_fit:,} per fit"
    )


def _render_bottleneck_callout(summary: FitAvailabilitySummary, language_code: str):
    if summary.fits_available >= 5:
        return
    if not summary.bottleneck_items:
        return

    items_to_show = summary.bottleneck_items[:5]
    overflow = len(summary.bottleneck_items) - len(items_to_show)
    lines = [_format_bottleneck_line(i) for i in items_to_show]
    st.space()
    if overflow > 0:
        lines.append(
            translate_text(language_code, "pricer.fits.callout_more", count=overflow)
        )
    body = "\n".join(lines)

    if summary.fits_available == 0:
        header = translate_text(language_code, "pricer.fits.callout_zero")
        st.error(f"{header}\n\n{body}")
    else:
        header = translate_text(
            language_code,
            "pricer.fits.callout_low",
            count=summary.fits_available,
        )
        st.warning(f"{header}\n\n{body}")


def _render_fit_availability_table(
    summary: FitAvailabilitySummary, market: MarketConfig, language_code: str
):
    if not summary.items:
        return

    rows = []
    for item in summary.items:
        status = StockStatus.from_stock_and_target(
            item.fits_possible, max(1, summary.fits_available + 1)
        )
        status_emoji = {"red": "🔴", "orange": "🟠", "green": "🟢"}.get(
            status.display_color, "🟢"
        )
        rows.append(
            {
                "image_url": item.image_url,
                "type_id": item.type_id,
                "Item": item.type_name,
                "Slot": item.slot_type.display_name,
                "Per Fit": item.quantity_per_fit,
                "In Stock": item.stock_used,
                "Fits": item.fits_possible,
                "Local Sell": item.isk_per_unit,
                "Status": status_emoji,
                "Equivalents": "🔄" if item.used_equivalents else "",
            }
        )
    df = pd.DataFrame(rows)
    styled = df.style.apply(
        _highlight_fit_row, axis=1, fits_available=summary.fits_available
    )

    st.data_editor(
        styled,
        hide_index=True,
        column_config=_fit_availability_column_config(language_code, market.short_name),
        width="stretch",
        column_order=[
            "image_url",
            "type_id",
            "Item",
            "Slot",
            "Per Fit",
            "In Stock",
            "Fits",
            "Local Sell",
            "Status",
            "Equivalents",
        ],
        key="fit_availability_table",
    )


def _render_fit_availability_section(
    result: PricerResult, market: MarketConfig, language_code: str
):
    """Orchestrator for the Fit Availability block (EFT only)."""
    if result.input_type != InputFormat.EFT or not result.items:
        return

    use_equivalents = ss_get("pricer_fit_equivalents", True)

    aggregated_stock: dict[int, int] | None = None
    if use_equivalents:
        type_ids = [i.type_id for i in result.items if i.type_id is not None]
        try:
            aggregated_stock = _build_aggregated_stock_map(type_ids)
            if not aggregated_stock:
                aggregated_stock = None
        except Exception as exc:
            logger.warning("Aggregated stock lookup failed: %s", exc)
            st.caption(
                translate_text(language_code, "pricer.fits.equivalents_unavailable")
            )
            aggregated_stock = None

    summary = compute_fit_availability(
        result,
        aggregated_stock=aggregated_stock,
        logger_instance=logger,
    )

    _render_fit_availability_hero(summary, language_code)
    _render_bottleneck_callout(summary, language_code)
    _render_fit_availability_table(summary, market, language_code)


# =============================================================================
# Main
# =============================================================================


def _process_input(input_text: str):
    """Run pricing and store the result in session state."""
    language_code = get_active_language()
    with st.spinner(translate_text(language_code, "pricer.fetching_prices")):
        try:
            service = get_pricer_service()
            result = service.price_input(input_text)
            ss_set("pricer_result", result)
            ss_set("pricer_input_text", input_text)
            logger.info("Priced %d items", len(result.items))
        except Exception:
            logger.exception("Error pricing items")
            ss_set("pricer_result", None)
            st.error(translate_text(language_code, "pricer.error_processing"))


def main():
    language_code = get_active_language()
    market = render_market_selector()
    sde_repo = get_sde_repository()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    ss_init(
        {
            "pricer_show_jita": True,
            "pricer_show_doctrine": True,
            "pricer_highlight_doctrine": True,
            "pricer_show_stock_metrics": True,
            "pricer_fit_equivalents": True,
            "pricer_eft_result": False,
            "pricer_input_text": "",
        }
    )

    render_header(language_code)
    st.markdown(
        translate_text(language_code, "pricer.description", market_name=market.name)
    )

    result: PricerResult = (
        ss_get("pricer_result") if ss_has("pricer_result") else None
    )

    if result is not None:
        eft_type = result.input_type == InputFormat.EFT
        ss_set("pricer_eft_result", eft_type)

    cached_input_text = ss_get("pricer_input_text", None)

    with st.container(border=True):
        _render_appraisal_title(result, market, language_code)
        if result is not None:
            if result.jita_provider_failed:
                st.warning(
                    translate_text(
                        language_code,
                        "pricer.jita_provider_failed",
                        count=result.failed_jita_count,
                    )
                )
            if eft_type:
                _render_fit_appraisal_header(
                    result=result, language_code=language_code, sde_repo=sde_repo
                )
                _render_summary_stats_grid(result, market, language_code)
                _render_fit_availability_section(result, market, language_code)
            else:
                _render_summary_stats_grid(result, market, language_code)
                _render_items_table(result, market, sde_repo, language_code)
            _render_action_chips(result, language_code)
            if result.parse_errors:
                with st.expander(
                    translate_text(
                        language_code,
                        "pricer.unpriced_items",
                        count=len(result.parse_errors),
                    ),
                    expanded=False,
                ):
                    for error in result.parse_errors:
                        st.warning(error)

        st.divider()
        _render_control_row(language_code)

        input_text = st.text_area(
            translate_text(language_code, "pricer.input_label"),
            height=220,
            placeholder=translate_text(language_code, "pricer.input_placeholder"),
            key="pricer_input",
            value=cached_input_text,
        )

        _, submit_col = st.columns([4, 1])
        with submit_col:
            price_button = st.button(
                translate_text(language_code, "pricer.price_items"),
                type="primary",
                use_container_width=True,
                key="pricer_submit",
            )

    if price_button:
        if input_text.strip():
            _process_input(input_text)
            st.rerun()
        else:
            st.warning("Please paste some items to price.")

    render_legal_notice()

if __name__ == "__main__":
    main()
