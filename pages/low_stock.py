"""
Low Stock Page

Displays items that are running low on the 4-HWWF market with filtering
options for categories, doctrines, fits, and item meta types.

Uses LowStockService for all data operations.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from logging_config import setup_logging
from services import get_low_stock_service, LowStockFilters
from repositories import get_sde_repository
from services.type_name_localization import get_localized_name_map
from ui.formatters import get_image_url
from services.doctrine_service import format_doctrine_name
from state import get_active_language, ss_init, ss_get, ss_set
from ui.market_selector import render_market_selector
from ui.i18n import translate_text
from pages.components.header import render_page_title
from pages.components.layout import render_legal_notice
from ui.column_definitions import get_low_stock_column_config
from init_db import ensure_market_db_ready
from ui.sync_display import display_sync_status
logger = setup_logging(__name__, log_file="low_stock.log")

# Columns written to the export CSV (visible table + the computed restock qty).
# Keep in sync with columns_to_show in main().
EXPORT_CSV_COLUMNS = [
    "type_id",
    "type_name",
    "restock_qty",
    "price",
    "days_remaining",
    "total_volume_remain",
    "fits_on_mkt",
    "avg_volume",
    "category_name",
    "group_name",
    "ships",
]
# Columns only present in some page modes (fits_on_mkt appears in single-fit mode).
OPTIONAL_EXPORT_COLUMNS = {"fits_on_mkt"}


def compute_restock_qty(avg_volume: float, max_days: float, current_stock: float) -> int:
    """Quantity to buy to restock an item to ``max_days`` days of stock.

    ``avg_volume`` is 30-day average daily sales, ``current_stock`` is the
    quantity currently on the market. Floored at 1 by design: a 0 quantity
    breaks the multibuy format for third-party tools, and a ticked row is an
    explicit request to include the item even if the stock math says it
    needs nothing (decided 2026-06-10, PR #73 review).
    """
    return max(1, int(round(avg_volume * max_days - current_stock)))


def create_days_remaining_chart(df: pd.DataFrame, language_code: str):
    """Create a bar chart showing days of stock remaining."""
    if df.empty:
        return None

    fig = px.bar(
        df,
        x="type_name",
        y="days_remaining",
        title=translate_text(language_code, "low_stock.chart_title"),
        labels={
            "days_remaining": translate_text(language_code, "low_stock.chart_days_label"),
            "type_name": translate_text(language_code, "common.item"),
        },
        color="category_name",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )

    fig.update_layout(
        xaxis_title=translate_text(language_code, "common.item"),
        yaxis_title=translate_text(language_code, "low_stock.chart_days_label"),
        xaxis={"tickangle": 45},
        height=500,
    )

    # Add a horizontal line at critical level
    fig.add_hline(
        y=3,
        line_dash="dash",
        line_color="red",
        annotation_text=translate_text(language_code, "low_stock.chart_critical_level"),
    )

    return fig


def highlight_critical(val):
    """Style function for critical days remaining values."""

    if ss_get("single_fit"):
        try:
            fit_target = ss_get("fit_target")
            val = float(val)
            perc_target = (val * 1.0) / fit_target
            if perc_target <= 0.3:
                return "background-color: #fc4103"  # Red for critical
            elif perc_target <= 0.8:
                return "background-color: #c76d14"  # Orange for low
            return ""
        except Exception:
            return ""
    else:
        try:
            val = float(val)
            if val <= 3:
                return "background-color: #fc4103"  # Red for critical
            elif val <= 7:
                return "background-color: #c76d14"  # Orange for low
            return ""
        except Exception:
            return ""


def highlight_doctrine(row):
    """Style function to highlight doctrine items."""
    try:
        if isinstance(row.get("ships"), list) and len(row["ships"]) > 0:
            styles = [""] * len(row)
            # Highlight the type_name column
            if "type_name" in row.index:
                idx = row.index.get_loc("type_name")
                styles[idx] = "background-color: #328fed"
            return styles
    except Exception:
        pass
    return [""] * len(row)


def display_fit_data(selected_fit):
    from services.doctrine_service import get_doctrine_service

    doctrine_service = get_doctrine_service()
    fit_status = doctrine_service.get_fit_summary(selected_fit.fit_id)
    fits = fit_status.fits
    hulls = fit_status.hulls
    target = fit_status.ship_target
    ss_set("fit_target", target)

    fd_col1, fd_col2 = st.columns([0.55, 0.45], width=525)
    with fd_col1:
        st.write(f"{selected_fit.fit_name} (fit_id: {selected_fit.fit_id})")
    with fd_col2:
        st.markdown(
            f"fits: :orange[{fits}] | hulls: :orange[{hulls}] | target: :orange[{target}]"
        )


def _render_low_stock_export(edited_df, max_days: float, language_code: str) -> None:
    """Render an EVE-Multibuy code block and CSV download for ticked rows.

    Each multibuy line is ``type_name<TAB>restock_qty``, where the quantity
    restocks the item to ``max_days`` days of stock — paste-ready for EVE
    Multibuy / JEveAssets. The CSV mirrors the visible table plus the computed
    restock quantity.
    """
    st.subheader(translate_text(language_code, "low_stock.export_header"))
    selected = edited_df[edited_df["select"]]
    if selected.empty:
        st.caption(translate_text(language_code, "low_stock.export_no_selection"))
        return

    st.caption(
        translate_text(language_code, "low_stock.export_qty_caption", days=f"{max_days:g}")
    )

    export = selected.copy()
    export["restock_qty"] = [
        compute_restock_qty(
            avg_volume=row.avg_volume,
            max_days=max_days,
            current_stock=row.total_volume_remain,
        )
        for row in export.itertuples(index=False)
    ]

    multibuy = "\n".join(
        f"{row.type_name}\t{row.restock_qty}"
        for row in export.itertuples(index=False)
    )
    st.code(multibuy, language=None)

    export["ships"] = export["ships"].apply(
        lambda s: "; ".join(s) if isinstance(s, list) else (s or "")
    )
    missing = [
        c for c in EXPORT_CSV_COLUMNS
        if c not in export.columns and c not in OPTIONAL_EXPORT_COLUMNS
    ]
    if missing:
        logger.error("Low stock export is missing expected columns: %s", missing)
    csv_cols = [c for c in EXPORT_CSV_COLUMNS if c in export.columns]
    csv = export[csv_cols].to_csv(index=False)
    st.download_button(
        label=translate_text(language_code, "doctrine_report.download_csv"),
        data=csv,
        file_name="low_stock_export.csv",
        mime="text/csv",
    )


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

    # Initialize service (cached in session state via get_service)
    service = get_low_stock_service()

    # Initialize session state
    ss_init(
        {
            "ls_selected_category_ids": [],
            "ls_selected_doctrine_id": None,
            "ls_selected_fit_id": None,
            "ls_doctrine_only": False,
            "ls_tech2_only": False,
            "ls_faction_only": False,
            "ls_max_days": 7.0,
        }
    )

    render_page_title(translate_text(language_code, "low_stock.title", market_name=market.name))

    st.markdown(translate_text(language_code, "low_stock.description"))

    # Sidebar filters
    st.sidebar.header(translate_text(language_code, "low_stock.filters_header"))
    st.sidebar.markdown(translate_text(language_code, "low_stock.filters_help"))

    # Item type filters
    st.sidebar.subheader(translate_text(language_code, "low_stock.item_type_filters"))

    doctrine_only = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.doctrine_only"),
        value=ss_get("ls_doctrine_only", False),
        help=translate_text(language_code, "low_stock.doctrine_only_help"),
    )
    ss_set("ls_doctrine_only", doctrine_only)

    tech2_only = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.tech2_only"),
        value=ss_get("ls_tech2_only", False),
        help=translate_text(language_code, "low_stock.tech2_only_help"),
    )
    ss_set("ls_tech2_only", tech2_only)

    faction_only = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.faction_only"),
        value=ss_get("ls_faction_only", False),
        help=translate_text(language_code, "low_stock.faction_only_help"),
    )
    ss_set("ls_faction_only", faction_only)

    # Category filter
    st.sidebar.subheader(translate_text(language_code, "low_stock.category_filter"))
    category_options = service.get_category_options()
    category_name_map = {
        int(row["category_id"]): str(row["category_name"])
        for _, row in category_options.iterrows()
    }
    category_ids = sorted(category_name_map, key=lambda cid: category_name_map[cid])

    selected_category_ids = st.sidebar.multiselect(
        translate_text(language_code, "low_stock.select_categories"),
        options=category_ids,
        default=ss_get("ls_selected_category_ids", []),
        format_func=lambda cid: category_name_map[cid],
        help=translate_text(language_code, "low_stock.select_categories_help"),
    )
    ss_set("ls_selected_category_ids", selected_category_ids)

    # Doctrine/Fit filter section
    st.sidebar.subheader(translate_text(language_code, "low_stock.doctrine_fit_filter"))

    # Get doctrine options
    doctrine_options = service.get_doctrine_options()
    all_label = "All"
    all_fits_label = "All Fits"
    doctrine_by_id = {d.doctrine_id: d for d in doctrine_options}
    doctrine_ids = sorted(
        doctrine_by_id.keys(),
        key=lambda did: format_doctrine_name(doctrine_by_id[did].doctrine_name),
    )

    selected_doctrine_id = st.sidebar.selectbox(
        translate_text(language_code, "low_stock.select_doctrine"),
        options=[None] + doctrine_ids,
        index=0,
        help=translate_text(language_code, "low_stock.select_doctrine_help"),
        format_func=lambda did: all_label if did is None else format_doctrine_name(doctrine_by_id[did].doctrine_name),
    )
    ss_set("ls_selected_doctrine_id", selected_doctrine_id)

    selected_doctrine = None
    selected_fit = None
    selected_fit_display_name = None
    fit_ids = []
    selected_doctrine_name = all_label

    if selected_doctrine_id is not None:
        selected_doctrine = doctrine_by_id.get(selected_doctrine_id)

        if selected_doctrine:
            selected_doctrine_name = selected_doctrine.doctrine_name
            # Display doctrine image
            if selected_doctrine.lead_ship_id:
                st.sidebar.image(
                    selected_doctrine.lead_ship_image_url,
                    width=128,
                    caption=format_doctrine_name(selected_doctrine_name),
                )

            # Get fit options for this doctrine
            fit_options = service.get_fit_options(selected_doctrine.doctrine_id)
            fit_by_id = {fit.fit_id: fit for fit in fit_options}
            fit_ship_name_map = {fit.ship_id: fit.ship_name for fit in fit_options}
            localized_fit_name_map = get_localized_name_map(
                list(fit_ship_name_map.keys()),
                sde_repo,
                language_code,
                logger,
            )
            fit_label_map = {
                fit_id: localized_fit_name_map.get(fit.ship_id, fit.ship_name)
                for fit_id, fit in fit_by_id.items()
            }
            fit_option_ids = sorted(fit_by_id, key=lambda fid: fit_label_map[fid].lower())

            selected_fit_id = st.sidebar.selectbox(
                translate_text(language_code, "low_stock.select_fit"),
                options=[None] + fit_option_ids,
                index=0,
                help=translate_text(language_code, "low_stock.select_fit_help"),
                format_func=lambda fid: all_fits_label if fid is None else fit_label_map[fid],
            )
            ss_set("ls_selected_fit_id", selected_fit_id)

            if selected_fit_id is not None:
                selected_fit = fit_by_id.get(selected_fit_id)
                if selected_fit:
                    selected_fit_display_name = fit_label_map.get(
                        selected_fit.fit_id,
                        selected_fit.ship_name,
                    )
                    fit_ids = [selected_fit.fit_id]
                    # Display fit ship image
                    st.sidebar.image(
                        selected_fit.ship_image_url,
                        width=128,
                        caption=f"{selected_fit_display_name}\n{selected_fit.fit_name}",
                    )
            else:
                # All fits for the selected doctrine
                fit_ids = selected_doctrine.fit_ids
                ss_set("single_fit", False)
                ss_set("fit_target", None)

    # Days remaining filter
    st.sidebar.subheader(translate_text(language_code, "low_stock.days_filter"))
    max_days_remaining = st.sidebar.slider(
        translate_text(language_code, "low_stock.max_days_remaining"),
        min_value=0.0,
        max_value=30.0,
        value=ss_get("ls_max_days", 7.0),
        step=0.5,
        help=translate_text(language_code, "low_stock.max_days_remaining_help"),
    )
    ss_set("ls_max_days", max_days_remaining)
    show_zero_volume_items = st.sidebar.checkbox(
        translate_text(language_code, "low_stock.show_zero_volume_items"),
        value=ss_get("ls_show_zero_volume_items", False),
        help=translate_text(language_code, "low_stock.show_zero_volume_items_help"),
    )
    ss_set("ls_show_zero_volume_items", show_zero_volume_items)

    # Build filters
    filters = LowStockFilters(
        category_ids=selected_category_ids,
        max_days_remaining=max_days_remaining,
        doctrine_only=doctrine_only,
        tech2_only=tech2_only,
        faction_only=faction_only,
        fit_ids=fit_ids,
        show_zero_volume_items=show_zero_volume_items,
    )

    # Get filtered data using service
    try:
        df = service.get_low_stock_items(filters, language_code=language_code)
    except RuntimeError as e:
        if "history_data_unavailable" in str(e):
            st.error("History data currently unavailable, try again later.")
        else:
            logger.error(f"Low stock data load failed: {e}")
            st.error("Failed to load low stock data. Check database connectivity.")
        st.sidebar.markdown("---")
        display_sync_status(language_code=language_code)
        return

    if not df.empty:
        # Sort by days_remaining (ascending) to show most critical items first
        df = df.sort_values("days_remaining")

        # Get statistics
        stats = service.get_stock_statistics(df)

        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(translate_text(language_code, "low_stock.metric_critical"), stats["critical"])
        with col2:
            st.metric(translate_text(language_code, "low_stock.metric_low"), stats["low"])
        with col3:
            st.metric(translate_text(language_code, "low_stock.metric_total"), stats["total"])

        st.divider()

        # Display header with selected filter info
        if selected_doctrine:
            header_col1, header_col2 = st.columns([0.15, 0.85])
            with header_col1:
                if selected_fit and selected_fit.ship_id:
                    st.image(
                        get_image_url(selected_fit.ship_id, 64, isship=True), width=64
                    )
                elif selected_doctrine.lead_ship_id:
                    st.image(
                        get_image_url(selected_doctrine.lead_ship_id, 64, isship=True),
                        width=64,
                    )
            with header_col2:
                if selected_fit:
                    ss_set("single_fit", True)
                    st.subheader(
                        translate_text(
                            language_code,
                            "low_stock.subheader_fit",
                            ship_name=selected_fit_display_name or selected_fit.ship_name,
                        )
                    )
                    display_fit_data(selected_fit)
                else:
                    st.subheader(
                        translate_text(
                            language_code,
                            "low_stock.subheader_doctrine",
                            doctrine_name=format_doctrine_name(selected_doctrine_name),
                        )
                    )
        else:
            st.subheader(translate_text(language_code, "low_stock.subheader_all"))

        # Format the DataFrame for display
        display_df = df.copy()

        # Drop columns not needed for display
        columns_to_drop = [
            "min_price",
            "avg_price",
            "category_id",
            "group_id",
            "is_doctrine",
            "ship_name",
            "last_update",
        ]
        if not ss_get("single_fit"):
            columns_to_drop.append("fits_on_mkt")

        display_df = display_df.drop(
            columns=[c for c in columns_to_drop if c in display_df.columns],
            errors="ignore",
        )

        # Prepare columns for display
        columns_to_show = [
            "select",
            "type_id",
            "type_name",
            "price",
            "days_remaining",
            "total_volume_remain",
            "avg_volume",
            "category_name",
            "group_name",
            "ships",
        ]
        # show fits_on_mkt for individual fit
        if ss_get("single_fit"):
            columns_to_show.insert(6, "fits_on_mkt")

        # Initialize checkbox column
        display_df["select"] = False

        # Ensure all columns exist
        for col in columns_to_show:
            if col not in display_df.columns:
                display_df[col] = None

        display_df = display_df[columns_to_show]
        if ss_get("single_fit"):
            display_df.sort_values("fits_on_mkt", ascending=True, inplace=True)

        column_config = get_low_stock_column_config(language_code)

        # Apply styling
        style_paramater = "fits_on_mkt" if ss_get("single_fit") else "days_remaining"
        styled_df = display_df.style.map(highlight_critical, subset=[style_paramater])
        styled_df = styled_df.apply(highlight_doctrine, axis=1)

        # Display the dataframe with editable checkbox column
        edited_df = st.data_editor(
            styled_df,
            hide_index=True,
            height=600,
            column_config=column_config,
            disabled=[col for col in display_df.columns if col != "select"],
            key="low_stock_editor",
        )

        # Export selected items (multibuy block + CSV)
        _render_low_stock_export(edited_df, max_days_remaining, language_code)

        # Display chart
        st.subheader(translate_text(language_code, "low_stock.chart_section"))
        days_chart = create_days_remaining_chart(df, language_code)
        if days_chart:
            st.plotly_chart(days_chart)

    else:
        st.warning("No items found with the selected filters.")

    # Display last update timestamp
    st.sidebar.markdown("---")
    display_sync_status(language_code=language_code)

    render_legal_notice()

if __name__ == "__main__":
    main()
