from db_handler import get_all_market_history, read_df, get_price_from_mkt_orders
from config import DatabaseConfig
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text
from logging_config import setup_logging
from datetime import datetime, timedelta
import millify

logger = setup_logging(__name__)

@st.cache_data(ttl=600)
def get_market_history_by_category(selected_category=None):
    """
    Get market history data filtered by category

    Args:
        selected_category: Category name to filter by (optional)

    Returns:
        pandas DataFrame: Market history data, optionally filtered by category
    """
    if selected_category is None:
        # Return all market history if no category selected
        return get_all_market_history()

    # Get type_ids for the selected category from SDE
    sde_db = DatabaseConfig("sde")
    category_query = text("""
        SELECT typeID as type_id
        FROM sdetypes
        WHERE categoryName = :category_name
    """)

    type_ids_df = read_df(sde_db, category_query, {'category_name': selected_category})
    if type_ids_df.empty:
        return pd.DataFrame()  # Return empty if no types found for category

    type_ids = type_ids_df['type_id'].tolist()

    # Get market history for those type_ids
    mkt_db = DatabaseConfig("wcmkt")
    # Convert type_ids to strings since the DB stores them as VARCHAR
    type_ids_str = [str(tid) for tid in type_ids]

    # Use a simpler approach with string formatting for the IN clause
    if len(type_ids_str) == 1:
        history_query = text("SELECT * FROM market_history WHERE type_id = :type_id")
        history_df = read_df(mkt_db, history_query, {'type_id': type_ids_str[0]})
    else:
        # Create a comma-separated string for multiple IDs
        type_ids_joined = ','.join(f"'{tid}'" for tid in type_ids_str)
        history_query = text(f"SELECT * FROM market_history WHERE type_id IN ({type_ids_joined})")
        history_df = read_df(mkt_db, history_query)
    return history_df

def calculate_30day_metrics(selected_category=None, selected_item_id=None):
    """
    Calculate average daily sales and total daily ISK value for the last 30 days

    Args:
        selected_category: Category name to filter by (optional)
        selected_item_id: Specific item type_id to filter by (optional)

    Returns:
        tuple: (avg_daily_volume, avg_daily_isk_value)
    """
    try:
        # Get market history data based on filters
        if selected_item_id:
            # Filter by specific item
            mkt_db = DatabaseConfig("wcmkt")
            history_query = text("SELECT * FROM market_history WHERE type_id = :type_id")
            df = read_df(mkt_db, history_query, {'type_id': str(selected_item_id)})
        elif selected_category:
            # Filter by category
            df = get_market_history_by_category(selected_category)
        else:
            # All market history
            df = get_all_market_history()

        if df.empty:
            return 0, 0

        # Convert date column to datetime
        df['date'] = pd.to_datetime(df['date'])

        # Get last 30 days of data
        cutoff_date = datetime.now() - timedelta(days=30)
        df_30days = df[df['date'] >= cutoff_date].copy()

        if df_30days.empty:
            return 0, 0

        # Calculate daily metrics
        df_30days['daily_isk_volume'] = df_30days['average'] * df_30days['volume']

        # Group by date and sum
        daily_metrics = df_30days.groupby('date').agg({
            'volume': 'sum',
            'daily_isk_volume': 'sum'
        }).reset_index()

        # Calculate averages
        avg_daily_volume = daily_metrics['volume'].mean()
        avg_daily_isk_value = daily_metrics['daily_isk_volume'].mean()

        return avg_daily_volume, avg_daily_isk_value

    except Exception as e:
        logger.error(f"Error calculating 30-day metrics: {e}")
        return 0, 0

def calculate_daily_ISK_volume():
    df = get_all_market_history()
    df['total_isk_volume'] = df['average'] * df['volume']
    df = df.groupby('date').sum()
    df2 = df['total_isk_volume']

    return df2

def calculate_ISK_volume_by_period(date_period='daily', start_date=None, end_date=None, selected_category=None):
    """
    Calculate ISK volume aggregated by different time periods

    Args:
        date_period: 'daily', 'weekly', 'monthly', 'yearly'
        start_date: datetime or None for all dates
        end_date: datetime or None for all dates
        selected_category: Category name to filter by (optional)

    Returns:
        pandas Series with ISK volume data
    """
    df = get_market_history_by_category(selected_category)

    # Convert date column to datetime first
    df['date'] = pd.to_datetime(df['date'])

    # Filter by date range if provided
    if start_date is not None:
        # Convert start_date to datetime if it's a date object
        if hasattr(start_date, 'date'):
            start_date = pd.to_datetime(start_date)
        else:
            start_date = pd.to_datetime(start_date)
        df = df[df['date'] >= start_date]

    if end_date is not None:
        # Convert end_date to datetime if it's a date object
        if hasattr(end_date, 'date'):
            end_date = pd.to_datetime(end_date)
        else:
            end_date = pd.to_datetime(end_date)
        df = df[df['date'] <= end_date]

    df['total_isk_volume'] = df['average'] * df['volume']

    # Group by different time periods
    if date_period == 'daily':
        df_grouped = df.groupby('date')['total_isk_volume'].sum()
    elif date_period == 'weekly':
        df['week'] = df['date'].dt.to_period('W')
        df_grouped = df.groupby('week')['total_isk_volume'].sum()
        df_grouped.index = df_grouped.index.to_timestamp()
    elif date_period == 'monthly':
        df['month'] = df['date'].dt.to_period('M')
        df_grouped = df.groupby('month')['total_isk_volume'].sum()
        df_grouped.index = df_grouped.index.to_timestamp()
    elif date_period == 'yearly':
        df['year'] = df['date'].dt.to_period('Y')
        df_grouped = df.groupby('year')['total_isk_volume'].sum()
        df_grouped.index = df_grouped.index.to_timestamp()
    else:
        # Default to daily
        df_grouped = df.groupby('date')['total_isk_volume'].sum()

    return df_grouped

@st.cache_data(ttl=600)
def get_available_date_range(selected_category=None):
    """
    Get the min and max dates available in the market history data

    Args:
        selected_category: Category name to filter by (optional)

    Returns:
        tuple: (min_date, max_date) as pandas datetime objects
    """
    df = get_market_history_by_category(selected_category)
    if df.empty:
        return None, None
    df['date'] = pd.to_datetime(df['date'])
    return df['date'].min(), df['date'].max()

def detect_outliers(series, method='iqr', threshold=1.5):
    """
    Detect outliers in a pandas Series

    Args:
        series: pandas Series with numeric data
        method: 'iqr' for interquartile range, 'zscore' for z-score
        threshold: threshold multiplier for outlier detection

    Returns:
        pandas Series: boolean mask where True indicates outliers
    """
    if method == 'iqr':
        Q1 = series.quantile(0.25)
        Q3 = series.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR
        return (series < lower_bound) | (series > upper_bound)

    elif method == 'zscore':
        z_scores = np.abs((series - series.mean()) / series.std())
        return z_scores > threshold

    else:
        raise ValueError("Method must be 'iqr' or 'zscore'")

def handle_outliers(series, method='cap', outlier_threshold=1.5, cap_percentile=95):
    """
    Handle outliers in a pandas Series

    Args:
        series: pandas Series with numeric data
        method: 'remove', 'cap', or 'none'
        outlier_threshold: threshold for outlier detection
        cap_percentile: percentile to cap outliers at (when method='cap')

    Returns:
        pandas Series: data with outliers handled
    """
    if method == 'none':
        return series

    outliers = detect_outliers(series, threshold=outlier_threshold)

    if method == 'remove':
        return series[~outliers]

    elif method == 'cap':
        cap_value = series.quantile(cap_percentile / 100)
        result = series.copy()
        result[outliers] = cap_value
        return result

    else:
        raise ValueError("Method must be 'remove', 'cap', or 'none'")

def create_ISK_volume_chart(moving_avg_period=14, date_period='daily', start_date=None, end_date=None,
                           outlier_method='cap', outlier_threshold=1.5, cap_percentile=95, selected_category=None):
    """
    Create an interactive ISK volume chart with moving average and outlier handling

    Args:
        moving_avg_period: Number of periods for moving average (3, 7, 14, 30)
        date_period: 'daily', 'weekly', 'monthly', 'yearly'
        start_date: Start date for filtering (optional)
        end_date: End date for filtering (optional)
        outlier_method: 'none', 'remove', or 'cap' for outlier handling
        outlier_threshold: threshold for outlier detection (1.5 for IQR method)
        cap_percentile: percentile to cap outliers at (when method='cap')
        selected_category: Category name to filter by (optional)

    Returns:
        plotly.graph_objects.Figure: The chart figure
    """
    # Get the data based on selected parameters
    df = calculate_ISK_volume_by_period(date_period, start_date, end_date, selected_category)

    # Handle outliers if requested
    if outlier_method != 'none':
        df = handle_outliers(df, method=outlier_method,
                           outlier_threshold=outlier_threshold,
                           cap_percentile=cap_percentile)

    # Create the figure
    fig = go.Figure()

    # Determine period label based on date_period
    period_labels = {
        'daily': 'Daily',
        'weekly': 'Weekly',
        'monthly': 'Monthly',
        'yearly': 'Yearly'
    }
    period_label = period_labels.get(date_period, 'Daily')

    # Add the ISK volume bars with custom hover template
    fig.add_trace(go.Bar(
        x=df.index,
        y=df.values,
        name=f'{period_label} ISK Volume',
        hovertemplate='<b>%{x}</b><br>ISK: %{y:,.0f}<extra></extra>'
    ))

    # Calculate moving average with user-selected period
    moving_avg = df.rolling(window=moving_avg_period, min_periods=1).mean()

    # Add the moving average line with custom hover template
    fig.add_trace(go.Scatter(
        x=df.index,
        y=moving_avg.values,
        name=f'{moving_avg_period}-Period Moving Average',
        line=dict(color='#FF69B4', width=2),
        hovertemplate='<b>%{x}</b><br>Mov Avg: %{y:,.0f}<extra></extra>'
    ))

    # Add outlier handling info to title
    title_suffix = ""
    if outlier_method == 'cap':
        title_suffix = f" (Outliers capped at {cap_percentile}th percentile)"
    elif outlier_method == 'remove':
        title_suffix = " (Outliers removed)"

    # Add category info to title if filtered
    category_suffix = ""
    if selected_category:
        category_suffix = f" - {selected_category}"

    fig.update_layout(
        title=f'{period_label} ISK Volume with {moving_avg_period}-Period Moving Average{category_suffix}{title_suffix}',
        xaxis_title='Date',
        yaxis_title='ISK Volume'
    )
    return fig

def create_ISK_volume_table(date_period='daily', start_date=None, end_date=None, selected_category=None):
    """
    Create an ISK volume table with the same filtering as the chart

    Args:
        date_period: 'daily', 'weekly', 'monthly', 'yearly'
        start_date: Start date for filtering (optional)
        end_date: End date for filtering (optional)
        selected_category: Category name to filter by (optional)

    Returns:
        pandas DataFrame: Formatted table data
    """
    # Get the data using the same function as the chart
    df = calculate_ISK_volume_by_period(date_period, start_date, end_date, selected_category)

    # Convert to DataFrame and format
    table_df = df.reset_index()
    table_df.columns = ['Date', 'ISK Volume']

    # Format the ISK Volume column
    table_df['ISK Volume'] = table_df['ISK Volume'].apply(lambda x: f"{x:,.0f}")

    # Sort by date descending
    table_df = table_df.sort_values('Date', ascending=False)

    return table_df

def render_ISK_volume_chart_ui():
    """
    Render the complete ISK volume chart UI with all controls

    This function handles all the UI components and chart rendering in one place.
    Uses st.fragment to prevent full app reruns when settings change.
    """

    @st.fragment
    def chart_fragment():
        # Get selected category from session state
        selected_category = st.session_state.get('selected_category', None)

        # Get available date range for validation (considering category filter)
        min_date, max_date = get_available_date_range(selected_category)

        # Handle case where no data is available for the selected category
        if min_date is None or max_date is None:
            if selected_category:
                st.warning(f"No market history data available for category: {selected_category}")
            else:
                st.warning("No market history data available")
            return


        # Second row: Date range selectors with validation
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
                key="chart_start_date"
            )

        with col4:
            end_date = st.date_input(
                "End Date",
                value=None,
                min_value=min_date.date(),
                max_value=max_date.date(),
                help=f"Select end date (available: {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')})",
                key="chart_end_date"
            )

# Chart controls section
        with st.expander("⚙️ Chart Controls"):
            # First row: Moving average and date period radio buttons
            col1, col2 = st.columns(2)

            with col1:
                st.write("**Moving Average Period:**")
                moving_avg_period = st.radio(
                    "Moving Average",
                    options=[3, 7, 14, 30],
                    index=2,  # Default to 14
                    horizontal=True,
                    key="chart_moving_avg_radio"
                )

            with col2:
                st.write("**Date Aggregation:**")
                date_period = st.radio(
                    "Date Period",
                    options=['daily', 'weekly', 'monthly', 'yearly'],
                    index=0,  # Default to daily
                    format_func=lambda x: x.title(),
                    horizontal=True,
                    key="chart_date_period_radio"
                )
            st.divider()
            st.write("**Outlier Handling:**")

            col5, col6, col7 = st.columns(3)

            with col5:
                outlier_method = st.selectbox(
                    "Outlier Method",
                    options=['cap', 'remove', 'none'],
                    index=0,  # Default to 'cap'
                    format_func=lambda x: {
                        'cap': 'Cap Outliers',
                        'remove': 'Remove Outliers',
                        'none': 'Show All Data'
                    }[x],
                    help="How to handle extreme values that skew the chart scale"
                )

            with col6:
                outlier_threshold = st.slider(
                    "Outlier Sensitivity",
                    min_value=1.0,
                    max_value=3.0,
                    value=1.5,
                    step=0.1,
                    help="Lower values = more aggressive outlier detection (1.5 = standard IQR method)"
                )

            with col7:
                cap_percentile = st.slider(
                    "Cap at Percentile",
                    min_value=85,
                    max_value=99,
                    value=95,
                    step=1,
                    help="Percentile to cap outliers at (when using 'Cap Outliers')",
                    disabled=(outlier_method != 'cap')
                )

            # Help text for advanced settings
            st.info("""
            **Outlier Handling Explained:**
            - **Cap Outliers**: Replaces extreme values with a percentile-based limit (recommended)
            - **Remove Outliers**: Completely removes extreme data points
            - **Show All Data**: No outlier handling (may skew chart scale)

            **Outlier Sensitivity**: Lower values detect more outliers. 1.5 is the standard IQR method.
            """)

        # Create and display the chart using the consolidated function
        chart = create_ISK_volume_chart(
            moving_avg_period=moving_avg_period,
            date_period=date_period,
            start_date=start_date,
            end_date=end_date,
            outlier_method=outlier_method,
            outlier_threshold=outlier_threshold,
            cap_percentile=cap_percentile,
            selected_category=selected_category
        )
        st.plotly_chart(chart, config={'width': 'stretch'})

    # Call the fragment
    chart_fragment()

def render_ISK_volume_table_ui():
    """
    Render the complete ISK volume table UI with all controls
    """
    start_date = st.session_state.get("chart_start_date", None)
    end_date = st.session_state.get("chart_end_date", None)
    date_period = st.session_state.get("chart_date_period_radio") or "daily"
    selected_category = st.session_state.get('selected_category', None)

    data_table_config = {
        "Date": st.column_config.DateColumn(
            "Date",
            help="Date of the data",
            format="YYYY-MM-DD"
        ),
        "ISK Volume": st.column_config.NumberColumn(
            "ISK Volume",
            help="ISK Volume of the data",
            format="compact"
        )
    }

    table = create_ISK_volume_table(
        date_period=str(date_period).lower(),
        start_date=start_date,
        end_date=end_date,
        selected_category=selected_category
    )

    # Display filter information
    filter_info = f"Start Date: {start_date} | End Date: {end_date} | Date Period: {date_period}"
    if selected_category:
        filter_info += f" | Category: {selected_category}"
    st.write(filter_info)

    if table.empty:
        if selected_category:
            st.warning(f"No market history data available for category: {selected_category}")
        else:
            st.warning("No market history data available for the selected filters")
    else:
        st.dataframe(table, width='content', column_config=data_table_config)

def render_30day_metrics_ui():
    """
    Render the 30-day market performance metrics section

    This function displays average daily sales and ISK value for the last 30 days,
    filtered by the current selection (item, category, or all items).
    Only displays if history data is available.
    """
    # Determine what filters to apply for the metrics
    metrics_category = None
    metrics_item_id = None

    if 'selected_item_id' in st.session_state and st.session_state.selected_item_id is not None:
        metrics_item_id = st.session_state.selected_item_id
    elif 'selected_category' in st.session_state and st.session_state.selected_category is not None:
        metrics_category = st.session_state.selected_category

    # Calculate 30-day metrics
    avg_daily_volume, avg_daily_isk_value = calculate_30day_metrics(
        selected_category=metrics_category,
        selected_item_id=metrics_item_id
    )

    # Only show metrics if we have actual history data
    if avg_daily_volume == 0 and avg_daily_isk_value == 0:
        return  st.write("No history data recorded for this item") # Don't show metrics section if no history data

    st.subheader("30-Day Market Performance", divider="gray")

    # Display 30-day metrics
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    with col_m1:
        if avg_daily_isk_value > 0:
            display_avg_isk = millify.millify(avg_daily_isk_value, precision=2)
            st.metric("Avg Daily ISK Value (30d)", f"{display_avg_isk} ISK")
        else:
            st.metric("Avg Daily ISK Value (30d)", "0 ISK")


    with col_m2:
        if avg_daily_volume > 0:
            if avg_daily_volume < 1000:
                display_avg_volume = f"{avg_daily_volume:,.0f}"
            else:
                display_avg_volume = millify.millify(avg_daily_volume, precision=1)
            st.metric("Avg Daily Sales (30d)", f"{display_avg_volume}")
        else:
            st.metric("Avg Daily Sales (30d)", "0")

    with col_m3:
        # Calculate total 30-day ISK value
        total_30d_isk = avg_daily_isk_value * 30 if avg_daily_isk_value > 0 else 0
        if total_30d_isk > 0:
            display_total_isk = millify.millify(total_30d_isk, precision=2)
            st.metric("Total ISK Value (30d)", f"{display_total_isk} ISK")
        else:
            st.metric("Total 30d ISK Value", "0 ISK")

    with col_m4:
        # Calculate total 30-day volume
        total_30d_volume = avg_daily_volume * 30 if avg_daily_volume > 0 else 0
        if total_30d_volume > 0:
            display_total_volume = millify.millify(total_30d_volume, precision=2)
            st.metric("Total Volume (30d)", f"{display_total_volume}")
        else:
            st.metric("Total 30d Volume", "0")


    st.divider()

def render_current_market_status_ui(sell_data, stats, selected_item, sell_order_count, sell_total_value, fit_df, fits_on_mkt, cat_id):
    """
    Render the current market status metrics section

    Args:
        sell_data: DataFrame with current sell orders
        stats: DataFrame with market statistics
        selected_item: Currently selected item name
        sell_order_count: Count of sell orders
        sell_total_value: Total value of sell orders
        fit_df: DataFrame with fitting data
        fits_on_mkt: Number of fits available on market
        cat_id: Category ID of the selected item
    """
    st.subheader("Current Market Status", divider="grey")

    # Display metrics - conditionally show col1 based on selected_item
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
                min_price = stats['min_price'].min()
                if jita_price is not None:
                    delta_price = (min_price - jita_price) / jita_price
                else: delta_price = None


                if pd.notna(min_price) and selected_item:
                    st.session_state.current_price = min_price
                    display_min_price = millify.millify(min_price, precision=2)
                    if delta_price is not None:
                        st.metric("4-HWWF Sell Price", f"{display_min_price} ISK", delta=f"{round(100*delta_price, 1)}%", delta_color="inverse")
                    else:
                        st.metric("4-HWWF Sell Price", f"{display_min_price} ISK")

                elif selected_item and st.session_state.selected_item_id is not None:
                    try:
                        display_min_price = millify.millify(get_price_from_mkt_orders(st.session_state.selected_item_id), precision=2)
                        st.metric("4-HWWF Sell Price", f"{display_min_price} ISK")

                    except Exception:
                        pass

                else:
                    pass

            if st.session_state.jita_price is not None:
                display_jita_price = millify.millify(st.session_state.jita_price, precision=2)
                st.metric("Jita Price", f"{display_jita_price} ISK")

    with col2:
        if not sell_data.empty:
            volume = sell_data['volume_remain'].sum()
            if pd.notna(volume):
                display_volume = millify.millify(volume, precision=2)
                st.metric("Market Stock (sell orders)", f"{display_volume}")
        else:
            st.metric("Market Stock (sell orders)", "0")
        if sell_total_value > 0:
            display_sell_total_value = millify.millify(sell_total_value, precision=2)
            st.metric("Sell Orders Value", f"{display_sell_total_value} ISK")
        else:
            st.metric("Sell Orders Value", "0 ISK")

    with col3:
        days_remaining = stats['days_remaining'].min()
        if pd.notna(days_remaining) and selected_item:
            display_days_remaining = f"{days_remaining:.1f}"
            st.metric("Days Remaining", f"{display_days_remaining}")
        elif sell_order_count > 0:
            display_sell_order_count = f"{sell_order_count:,.0f}"
            st.metric("Total Sell Orders", f"{display_sell_order_count}")
        else:
            st.metric("Total Sell Orders", "0")

    with col4:
        if fit_df is not None and fit_df.empty is False and fits_on_mkt is not None:
            if cat_id == 6:
                display_fits_on_mkt = f"{fits_on_mkt:,.0f}"
                st.metric("Fits on Market", f"{display_fits_on_mkt}")
        else:
            pass

if __name__ == "__main__":
    pass
