from db_handler import get_all_market_history
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import streamlit as st

def calculate_daily_ISK_volume():
    df = get_all_market_history()
    df['total_isk_volume'] = df['average'] * df['volume']
    df = df.groupby('date').sum()
    df2 = df['total_isk_volume']

    return df2

def calculate_ISK_volume_by_period(date_period='daily', start_date=None, end_date=None):
    """
    Calculate ISK volume aggregated by different time periods

    Args:
        date_period: 'daily', 'weekly', 'monthly', 'yearly'
        start_date: datetime or None for all dates
        end_date: datetime or None for all dates

    Returns:
        pandas Series with ISK volume data
    """
    df = get_all_market_history()

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

def get_available_date_range():
    """
    Get the min and max dates available in the market history data

    Returns:
        tuple: (min_date, max_date) as pandas datetime objects
    """
    df = get_all_market_history()
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
                           outlier_method='cap', outlier_threshold=1.5, cap_percentile=95):
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

    Returns:
        plotly.graph_objects.Figure: The chart figure
    """
    # Get the data based on selected parameters
    df = calculate_ISK_volume_by_period(date_period, start_date, end_date)

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

    # Add the ISK volume bars
    fig.add_trace(go.Bar(x=df.index, y=df.values, name=f'{period_label} ISK Volume'))

    # Calculate moving average with user-selected period
    moving_avg = df.rolling(window=moving_avg_period, min_periods=1).mean()

    # Add the moving average line
    fig.add_trace(go.Scatter(
        x=df.index,
        y=moving_avg.values,
        name=f'{moving_avg_period}-Period Moving Average',
        line=dict(color='#FF69B4', width=2)
    ))

    # Add outlier handling info to title
    title_suffix = ""
    if outlier_method == 'cap':
        title_suffix = f" (Outliers capped at {cap_percentile}th percentile)"
    elif outlier_method == 'remove':
        title_suffix = " (Outliers removed)"

    fig.update_layout(
        title=f'{period_label} ISK Volume with {moving_avg_period}-Period Moving Average{title_suffix}',
        xaxis_title='Date',
        yaxis_title='ISK Volume'
    )
    return fig

def create_ISK_volume_table(date_period='daily', start_date=None, end_date=None):
    """
    Create an ISK volume table with the same filtering as the chart

    Args:
        date_period: 'daily', 'weekly', 'monthly', 'yearly'
        start_date: Start date for filtering (optional)
        end_date: End date for filtering (optional)

    Returns:
        pandas DataFrame: Formatted table data
    """
    # Get the data using the same function as the chart
    df = calculate_ISK_volume_by_period(date_period, start_date, end_date)

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
        # Get available date range for validation
        min_date, max_date = get_available_date_range()


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
            cap_percentile=cap_percentile
        )
        st.plotly_chart(chart, use_container_width=True)

    # Call the fragment
    chart_fragment()

def render_ISK_volume_table_ui():
    """
    Render the complete ISK volume table UI with all controls
    """
    start_date = st.session_state.get("chart_start_date", None)
    end_date = st.session_state.get("chart_end_date", None)
    date_period = st.session_state.get("chart_date_period_radio") or "daily"

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

    )
    st.write(f"Start Date: {start_date} | End Date: {end_date} | Date Period: {date_period}")
    st.dataframe(table, use_container_width=False, column_config=data_table_config)


if __name__ == "__main__":
    pass
