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
from init_db import ensure_market_db_ready
from ui.sync_display import display_sync_status
logger = setup_logging(__name__, log_file="low_stock.log")



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

    # Title and logo
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image("images/wclogo.png", width=125)
    with col2:
        st.title(translate_text(language_code, "low_stock.title", market_name=market.name))

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

        # Column configuration
        column_config = {
            "select": st.column_config.CheckboxColumn(
                translate_text(language_code, "common.select"),
                help=translate_text(language_code, "low_stock.column_select_help"),
                default=False,
                width="small",
            ),
            "type_id": st.column_config.NumberColumn(
                translate_text(language_code, "common.type_id"),
                help="Type ID of the item",
                width="small",
            ),
            "type_name": st.column_config.TextColumn(
                translate_text(language_code, "common.item"),
                help=translate_text(language_code, "low_stock.column_item_help"),
                width="medium",
            ),
            "total_volume_remain": st.column_config.NumberColumn(
                translate_text(language_code, "low_stock.column_volume_remaining"),
                format="localized",
                help=translate_text(language_code, "low_stock.column_volume_remaining_help"),
                width="small",
            ),
            "fits_on_mkt": st.column_config.NumberColumn(
                translate_text(language_code, "low_stock.column_fits"),
                format="localized",
                help=translate_text(language_code, "low_stock.column_fits_help"),
                width="small",
            ),
            "price": st.column_config.NumberColumn(
                translate_text(language_code, "common.price"),
                format="localized",
                help="Lowest 5-percentile price of current sell orders",
            ),
            "days_remaining": st.column_config.NumberColumn(
                translate_text(language_code, "low_stock.column_days"),
                format="%.1f",
                help=translate_text(language_code, "low_stock.column_days_help"),
                width="small",
            ),
            "avg_volume": st.column_config.NumberColumn(
                translate_text(language_code, "low_stock.column_avg_vol"),
                format="%.1f",
                help=translate_text(language_code, "low_stock.column_avg_vol_help"),
                width="small",
            ),
            "ships": st.column_config.ListColumn(
                translate_text(language_code, "low_stock.column_used_in_fits"),
                help=translate_text(language_code, "low_stock.column_used_in_fits_help"),
                width="large",
            ),
            "category_name": st.column_config.TextColumn(
                translate_text(language_code, "common.category"),
                help=translate_text(language_code, "low_stock.column_category_help"),
            ),
            "group_name": st.column_config.TextColumn(
                translate_text(language_code, "common.group"),
                help=translate_text(language_code, "low_stock.column_group_help"),
            ),
        }

        # Apply styling
        style_paramater = "fits_on_mkt" if ss_get("single_fit") else "days_remaining"
        styled_df = display_df.style.map(highlight_critical, subset=[style_paramater])
        styled_df = styled_df.apply(highlight_doctrine, axis=1)

        # Display the dataframe with editable checkbox column
        edited_df = st.data_editor(
            styled_df,
            hide_index=True,
            column_config=column_config,
            disabled=[col for col in display_df.columns if col != "select"],
            key="low_stock_editor",
        )

        # Selected items info
        selected_rows = edited_df[edited_df["select"]]
        if len(selected_rows) > 0:
            st.info(
                translate_text(language_code, "low_stock.selected_items", count=len(selected_rows))
            )

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


if __name__ == "__main__":
    main()
