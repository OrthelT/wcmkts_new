"""
Market Components

Streamlit-specific rendering functions for the market stats page.
Extracted from market_metrics.py and market_stats.py.

These components use MarketService for calculations and Streamlit for display.
No direct database access.
"""

import streamlit as st
import pandas as pd
import millify

from config import get_settings
from logging_config import setup_logging
from state import ss_has

logger = setup_logging(__name__)


def _get_default_outlier_method() -> str:
    """Get the default outlier method from settings."""
    settings = get_settings()
    return settings["outliers"]["default_method"]


# =============================================================================
# ISK Volume Chart UI
# =============================================================================

def render_isk_volume_chart_ui(service) -> None:
    """Render ISK volume chart with all controls as a Streamlit fragment.

    Args:
        service: MarketService instance.
    """

    @st.fragment
    def chart_fragment():
        selected_category = st.session_state.get("selected_category", None)

        min_date, max_date = service.get_available_date_range(selected_category)

        if min_date is None or max_date is None:
            msg = f"No market history data available for category: {selected_category}" if selected_category else "No market history data available"
            st.warning(msg)
            return

        st.write("**Date Range:**")
        st.caption(f"Available data range: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
        col3, col4 = st.columns(2)
        with col3:
            start_date = st.date_input(
                "Start Date",
                value=None,
                min_value=min_date.date(),
                max_value=max_date.date(),
                help=f"Select start date (available: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')})",
                key="chart_start_date",
            )
        with col4:
            end_date = st.date_input(
                "End Date",
                value=None,
                min_value=min_date.date(),
                max_value=max_date.date(),
                help=f"Select end date (available: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')})",
                key="chart_end_date",
            )

        with st.expander("Chart Controls"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Moving Average Period:**")
                moving_avg_period = st.radio(
                    "Moving Average",
                    options=[3, 7, 14, 30],
                    index=2,
                    horizontal=True,
                    key="chart_moving_avg_radio",
                )
            with col2:
                st.write("**Date Aggregation:**")
                date_period = st.radio(
                    "Date Period",
                    options=["daily", "weekly", "monthly", "yearly"],
                    index=0,
                    format_func=lambda x: x.title(),
                    horizontal=True,
                    key="chart_date_period_radio",
                )

            st.divider()
            st.write("**Outlier Handling:**")
            col5, col6, col7 = st.columns(3)

            with col5:
                default = _get_default_outlier_method()
                idx = {"none": 2, "remove": 1, "cap": 0}.get(default, 0)
                outlier_method = st.selectbox(
                    "Outlier Method",
                    options=["cap", "remove", "none"],
                    index=idx,
                    format_func=lambda x: {
                        "cap": "Cap Outliers",
                        "remove": "Remove Outliers",
                        "none": "Show All Data",
                    }[x],
                    help="How to handle extreme values that skew the chart scale",
                )
            with col6:
                outlier_threshold = st.slider(
                    "Outlier Sensitivity",
                    min_value=1.0, max_value=3.0, value=1.5, step=0.1,
                    help="Lower values = more aggressive outlier detection (1.5 = standard IQR method)",
                )
            with col7:
                cap_percentile = st.slider(
                    "Cap at Percentile",
                    min_value=85, max_value=99, value=95, step=1,
                    help="Percentile to cap outliers at (when using 'Cap Outliers')",
                    disabled=(outlier_method != "cap"),
                )

            st.info("""
            **Outlier Handling Explained:**
            - **Cap Outliers**: Replaces extreme values with a percentile-based limit (recommended)
            - **Remove Outliers**: Completely removes extreme data points
            - **Show All Data**: No outlier handling (may skew chart scale)

            **Outlier Sensitivity**: Lower values detect more outliers. 1.5 is the standard IQR method.
            """)

        chart = service.create_isk_volume_chart(
            moving_avg_period=moving_avg_period,
            date_period=date_period,
            start_date=start_date,
            end_date=end_date,
            outlier_method=outlier_method,
            outlier_threshold=outlier_threshold,
            cap_percentile=cap_percentile,
            selected_category=selected_category,
        )
        st.plotly_chart(chart, config={"width": "stretch"})

    chart_fragment()


# =============================================================================
# ISK Volume Table UI
# =============================================================================

def render_isk_volume_table_ui(service) -> None:
    """Render ISK volume data table with chart-matching filters.

    Args:
        service: MarketService instance.
    """
    start_date = st.session_state.get("chart_start_date", None)
    end_date = st.session_state.get("chart_end_date", None)
    date_period = st.session_state.get("chart_date_period_radio") or "daily"
    selected_category = st.session_state.get("selected_category", None)

    data_table_config = {
        "Date": st.column_config.DateColumn("Date", help="Date of the data", format="YYYY-MM-DD"),
        "ISK Volume": st.column_config.NumberColumn("ISK Volume", help="ISK Volume of the data", format="compact"),
    }

    table = service.create_isk_volume_table(
        date_period=str(date_period).lower(),
        start_date=start_date,
        end_date=end_date,
        selected_category=selected_category,
    )

    filter_info = f"Start Date: {start_date} | End Date: {end_date} | Date Period: {date_period}"
    if selected_category:
        filter_info += f" | Category: {selected_category}"
    st.write(filter_info)

    if table.empty:
        msg = f"No market history data available for category: {selected_category}" if selected_category else "No market history data available for the selected filters"
        st.warning(msg)
    else:
        st.dataframe(table, width="content", column_config=data_table_config)


# =============================================================================
# Top N Items UI
# =============================================================================

def configure_top_n_items_ui() -> None:
    """Render configuration pills for top N items selection."""
    colp1, colp2, colp3 = st.columns(3)
    with colp1:
        week_month_map = {0: "Week", 1: "Month"}
        st.pills(
            label="Week/Month", options=week_month_map.keys(), default=0,
            key="week_month_pill", format_func=lambda x: week_month_map[x],
            help="Select top items for the last week or the last month",
        )
    with colp2:
        isk_volume_map = {0: "ISK", 1: "Volume"}
        st.pills(
            label="ISK/Volume", options=isk_volume_map.keys(), default=0,
            key="isk_volume_pill", format_func=lambda x: isk_volume_map[x],
            help="Select top items in order of ISK or Volume",
        )
    with colp3:
        daily_total_map = {0: "Daily", 1: "Total"}
        st.pills(
            label="Daily/Total", options=daily_total_map.keys(), default=0,
            key="daily_total_pill", format_func=lambda x: daily_total_map[x],
            help="Select top items based on average daily stats or total amount",
        )
    st.number_input(
        label="Top Items", value=5, min_value=1, max_value=10, step=1,
        key="top_items_count", help="Select the number of top items to display",
    )


def render_top_n_items_ui(service, df_7days: pd.DataFrame, df_30days: pd.DataFrame) -> None:
    """Render top N items section with configuration and results.

    Args:
        service: MarketService instance (for get_top_n_items).
        df_7days: 7-day history DataFrame.
        df_30days: 30-day history DataFrame.
    """
    from services.market_service import MarketService

    configure_top_n_items_ui()

    @st.fragment
    def top_n_fragment():
        if ss_has("week_month_pill", "daily_total_pill", "isk_volume_pill", "top_items_count"):
            top_n_items = MarketService.get_top_n_items(
                df_7days, df_30days,
                period_idx=st.session_state.week_month_pill,
                agg_idx=st.session_state.daily_total_pill,
                sort_idx=st.session_state.isk_volume_pill,
                count=st.session_state.top_items_count,
            )
        else:
            top_n_items = None

        if top_n_items is not None:
            period = "this week" if st.session_state.week_month_pill == 0 else "this month"
            total = "total" if st.session_state.daily_total_pill == 1 else "daily"
            isk_volume = "ISK" if st.session_state.isk_volume_pill == 0 else "Volume"
            num_items = st.session_state.top_items_count

            if ss_has("selected_category"):
                metric_name = st.session_state.selected_category + "s"
            else:
                metric_name = "Items"

            st.markdown(
                f"Top <span style='color: orange;'>{num_items}</span> {metric_name} "
                f"<span style='color: orange;'>{period}</span> by "
                f"<span style='color: orange;'>{total}</span> "
                f"<span style='color: orange;'>{isk_volume}</span>",
                unsafe_allow_html=True,
            )

            colconfig = {
                "type_name": st.column_config.TextColumn("Type Name", width="medium"),
                "daily_isk_volume": st.column_config.NumberColumn("Daily ISK Volume", format="compact", width="small"),
                "volume": st.column_config.NumberColumn("Avg Volume", format="compact", width="small"),
            }
            st.dataframe(top_n_items, column_config=colconfig)
        else:
            st.warning("Insufficient data recorded for this item")

    top_n_fragment()


# =============================================================================
# 30-Day Metrics UI
# =============================================================================

def render_30day_metrics_ui(service) -> None:
    """Render 30-day market performance metrics section.

    Args:
        service: MarketService instance.
    """
    metrics_category = None
    metrics_item_id = None

    if ss_has("selected_item_id"):
        metrics_item_id = st.session_state.selected_item_id
    elif ss_has("selected_category"):
        metrics_category = st.session_state.selected_category

    if ss_has("selected_item"):
        metrics_label = st.session_state.selected_item
    elif ss_has("selected_category"):
        metrics_label = st.session_state.selected_category
    else:
        metrics_label = "All Items"

    st.subheader(f"30-Day Market Stats ({metrics_label})", divider="gray")

    avg_daily_volume, avg_daily_isk_value, vol_delta, isk_delta, df_7days, df_30days = (
        service.calculate_30day_metrics(
            selected_category=metrics_category,
            selected_item_id=metrics_item_id,
        )
    )

    if avg_daily_volume == 0 and avg_daily_isk_value == 0:
        logger.warning("Insufficient data recorded for this item")
        st.warning("Insufficient data recorded for this item")
        return

    colma1, colma2 = st.columns(2)
    with colma1:
        with st.container(border=True):
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                if avg_daily_isk_value > 0:
                    display_avg_isk = millify.millify(avg_daily_isk_value, precision=2)
                    st.metric("Avg Daily ISK (30d)", f"{display_avg_isk} ISK", delta=f"{isk_delta}% this week")
                else:
                    st.metric("Avg Daily ISK (30d)", "0 ISK")

                if avg_daily_volume > 0:
                    display_avg_volume = (
                        f"{avg_daily_volume:,.0f}" if avg_daily_volume < 1000
                        else millify.millify(avg_daily_volume, precision=1)
                    )
                    st.metric("Avg Daily Items (30d)", f"{display_avg_volume}", delta=f"{vol_delta}% this week")
                else:
                    st.metric("Avg Daily Items (30d)", "0")

            with col_m2:
                total_30d_isk = avg_daily_isk_value * 30 if avg_daily_isk_value > 0 else 0
                if total_30d_isk > 0:
                    st.metric("Total Value (30d)", f"{millify.millify(total_30d_isk, precision=2)} ISK")
                else:
                    st.metric("Total 30d Value", "0 ISK")

                total_30d_volume = avg_daily_volume * 30 if avg_daily_volume > 0 else 0
                if total_30d_volume > 0:
                    st.metric("Total Volume (30d)", f"{millify.millify(total_30d_volume, precision=2)}")
                else:
                    st.metric("Total 30d Volume", "0")

    with colma2:
        if st.session_state.selected_item is None:
            with st.container(border=True):
                render_top_n_items_ui(service, df_7days=df_7days, df_30days=df_30days)

    st.divider()


# =============================================================================
# Current Market Status UI
# =============================================================================

def render_current_market_status_ui(
    sell_data, stats, selected_item, sell_order_count, sell_total_value,
    fit_df, fits_on_mkt, cat_id
) -> None:
    """Render current market status metrics section.

    Args:
        sell_data: DataFrame with sell orders.
        stats: DataFrame with market statistics.
        selected_item: Currently selected item name.
        sell_order_count: Number of sell orders.
        sell_total_value: Total value of sell orders.
        fit_df: DataFrame with fitting data.
        fits_on_mkt: Number of fits on market.
        cat_id: Category ID of selected item.
    """
    st.subheader("Current Market Status", divider="grey")

    if selected_item:
        col1, col2, col3, col4 = st.columns(4)
    else:
        col2, col3, col4 = st.columns(3)

    if selected_item:
        try:
            jita_price = float(st.session_state.jita_price)
        except Exception:
            jita_price = None

        with col1:
            if not sell_data.empty:
                min_price = stats["min_price"].min()
                if jita_price is not None:
                    delta_price = (min_price - jita_price) / jita_price if jita_price > 0 else None
                else:
                    delta_price = None

                if pd.notna(min_price) and selected_item:
                    st.session_state.current_price = min_price
                    display_min_price = millify.millify(min_price, precision=2)
                    if delta_price is not None:
                        st.metric("4-HWWF Sell Price", f"{display_min_price} ISK", delta=f"{round(100 * delta_price, 1)}% Jita")
                    else:
                        st.metric("4-HWWF Sell Price", f"{display_min_price} ISK")

                elif selected_item and st.session_state.selected_item_id is not None:
                    try:
                        from repositories import get_market_repository
                        repo = get_market_repository()
                        price = repo.get_price(st.session_state.selected_item_id)
                        if price is not None:
                            display_min_price = millify.millify(price, precision=2)
                            st.metric("4-HWWF Sell Price", f"{display_min_price} ISK")
                    except Exception:
                        pass

            if st.session_state.jita_price is not None:
                display_jita_price = millify.millify(st.session_state.jita_price, precision=2)
                st.metric("Jita Sell Price", f"{display_jita_price} ISK")

    with col2:
        if not sell_data.empty:
            volume = sell_data["volume_remain"].sum()
            if pd.notna(volume) and ss_has("selected_item"):
                display_volume = millify.millify(volume, precision=2)
                st.metric("Market Stock (sell orders)", f"{display_volume}")
        if sell_total_value > 0:
            st.metric("Sell Orders Value", f"{millify.millify(sell_total_value, precision=2)} ISK")
        else:
            st.metric("Sell Orders Value", "0 ISK")

    with col3:
        days_remaining = stats["days_remaining"].min()
        if pd.notna(days_remaining) and selected_item:
            st.metric("Days Remaining", f"{days_remaining:.1f}")
        elif sell_order_count > 0:
            st.metric("Total Sell Orders", f"{sell_order_count:,.0f}")
        else:
            st.metric("Total Sell Orders", "0")

    with col4:
        if fit_df is not None and not fit_df.empty and fits_on_mkt is not None:
            if cat_id == 6:
                fits = fit_df["fit_id"].unique()
                display_fits_on_mkt = f"{fits_on_mkt:,.0f}"
                target = None
                try:
                    from services import get_doctrine_service
                    doctrine_svc = get_doctrine_service()
                    if len(fits) == 1:
                        target = doctrine_svc.repository.get_target_by_fit_id(fits[0])
                        fits_on_mkt_delta = round(fits_on_mkt - target, 0)
                        st.metric("Fits on Market", f"{display_fits_on_mkt}", delta=f"{fits_on_mkt_delta}")
                    elif len(fits) > 1:
                        for fit in fits:
                            target = doctrine_svc.repository.get_target_by_fit_id(fit)
                            fits_on_mkt_delta = fits_on_mkt - target
                            st.write(f"Fit: {fit}, Target: {target}, Fits on Market: {fits_on_mkt}, Delta: {fits_on_mkt_delta}")
                    else:
                        st.metric("Fits on Market", f"{display_fits_on_mkt}")
                except Exception as e:
                    logger.error(f"Error getting target from fit_id: {e}")
                    st.metric("Fits on Market", f"{display_fits_on_mkt}")

                if target is not None:
                    st.write(f"Target: {target}")


# =============================================================================
# History Display Helpers (from market_stats.py)
# =============================================================================

def display_history_data(history_df: pd.DataFrame) -> pd.DataFrame:
    """Format and display history data table.

    Args:
        history_df: DataFrame with date, average, volume columns.

    Returns:
        Formatted DataFrame (sorted descending by date).
    """
    history_df = history_df.copy()
    history_df.date = pd.to_datetime(history_df.date).dt.strftime("%Y-%m-%d")
    history_df.average = round(history_df.average.astype(float), 2)
    history_df = history_df.sort_values(by="date", ascending=False)
    history_df.volume = history_df.volume.astype(int)

    hist_col_config = {
        "date": st.column_config.DateColumn("Date", format="localized"),
        "average": st.column_config.NumberColumn("Average Price", format="localized"),
        "volume": st.column_config.NumberColumn("Volume", format="localized"),
    }
    st.dataframe(history_df, hide_index=True, column_config=hist_col_config, width=600)
    return history_df


def display_history_metrics(history_df: pd.DataFrame) -> None:
    """Display 7-day and 30-day history metrics.

    Args:
        history_df: DataFrame sorted by date descending with average, volume.
    """
    avgpr30 = history_df[:30].average.mean()
    avgpr7 = history_df[:7].average.mean()
    avgvol30 = history_df[:30].volume.mean()
    avgvol7 = history_df[:7].volume.mean()

    if avgpr30 == 0 and avgvol30 == 0:
        return

    prdelta = round((avgpr7 - avgpr30) / avgpr30 * 100, 1)
    voldelta = round((avgvol7 - avgvol30) / avgvol30 * 100, 1)

    col1h1, col1h2 = st.columns(2, border=True)
    with col1h1:
        st.metric("Average Price (7 days)", f"{millify.millify(avgpr7, precision=2)} ISK", delta=f"{prdelta}% this week")
        st.metric("Average Volume (7 days)", f"{millify.millify(avgvol7, precision=0)}", delta=f"{voldelta}% this week")
    with col1h2:
        st.metric("Average Price (30 days)", f"{millify.millify(avgpr30, precision=2)} ISK")
        st.metric("Average Volume (30 days)", f"{millify.millify(avgvol30, precision=0)}")


# =============================================================================
# Column Config Helpers (from market_stats.py)
# =============================================================================

def get_fitting_col_config() -> dict:
    """Get column configuration for fitting data display."""
    return {
        "fit_id": st.column_config.NumberColumn("Fit ID", help="WC Doctrine Fit ID"),
        "ship_name": st.column_config.TextColumn("Ship Name", width="medium"),
        "type_id": st.column_config.NumberColumn("Type ID"),
        "type_name": st.column_config.TextColumn("Type Name", width="medium"),
        "hulls": st.column_config.NumberColumn("Hulls", width="small"),
        "fit_qty": st.column_config.NumberColumn("Qty/fit", format="localized", width="small"),
        "fits_on_mkt": st.column_config.NumberColumn("Fits", format="localized", width="small"),
        "total_stock": st.column_config.NumberColumn("Stock", format="localized", width="small"),
        "price": st.column_config.NumberColumn("Price", format="localized"),
        "avg_vol": st.column_config.NumberColumn("Avg Vol", format="localized", width="small"),
        "days": st.column_config.NumberColumn("Days", format="localized", width="small"),
        "group_name": st.column_config.Column("Group", width="small"),
        "category_id": st.column_config.NumberColumn("Category ID", format="plain", width="small"),
    }


def get_display_formats() -> dict:
    """Get column configuration for order data display."""
    return {
        "type_id": st.column_config.NumberColumn("Type ID", width="small"),
        "order_id": st.column_config.NumberColumn("Order ID", width="small"),
        "type_name": st.column_config.TextColumn("Type Name", width="medium"),
        "volume_remain": st.column_config.NumberColumn("Qty", format="localized", width="small"),
        "price": st.column_config.NumberColumn("Price", format="localized"),
        "duration": st.column_config.NumberColumn("Duration", format="localized", width="small"),
        "issued": st.column_config.DateColumn("Issued", format="YYYY-MM-DD"),
        "expiry": st.column_config.DateColumn("Expires", format="YYYY-MM-DD"),
        "days_remaining": st.column_config.NumberColumn("Days Remaining", format="plain", width="small"),
    }
