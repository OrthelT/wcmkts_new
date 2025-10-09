import os
import sys
import time
from datetime import datetime, timedelta
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text,bindparam
from db_handler import safe_format, get_market_history, get_fitting_data, get_module_fits, read_df
from logging_config import setup_logging
import millify
from config import DatabaseConfig
from db_handler import new_get_market_data, get_all_mkt_orders, get_all_mkt_stats, get_all_market_history
from init_db import init_db
from sync_state import update_wcmkt_state
from type_info import get_backup_type_id
from datetime import datetime
from market_metrics import render_ISK_volume_chart_ui, render_ISK_volume_table_ui, render_30day_metrics_ui, render_current_market_status_ui
from utils import get_jita_price

mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")
build_cost_db = DatabaseConfig("build_cost")

# Insert centralized logging configuration
logger = setup_logging(__name__)

# Log application start
logger.info("Application started")
logger.info(f"streamlit version: {st.__version__}")
logger.info("-"*100)


@st.cache_data(ttl=3600)
def get_watchlist_type_ids()->list:
    # Get all type_ids from watchlist
    watchlist_query = """
    SELECT DISTINCT type_id
    FROM watchlist
    """
    df = read_df(mkt_db, watchlist_query)
    type_ids = df['type_id'].tolist()
    logger.debug(f"type_ids: {len(type_ids)}")
    return type_ids

@st.cache_data(ttl=1800)
def get_market_type_ids()->list:
    # Get all type_ids from market orders
    mkt_query = """
    SELECT DISTINCT type_id
    FROM marketorders
    """
    df = read_df(mkt_db, mkt_query)
    type_ids = df['type_id'].tolist()
    watchlist_type_ids = get_watchlist_type_ids()
    type_ids = list(set(type_ids + watchlist_type_ids))
    logger.debug(f"type_ids: {len(type_ids)}")
    return type_ids

# Function to get unique categories and item names
@st.cache_data(ttl=1800)
def all_sde_info(type_ids: list = None)->pd.DataFrame:
    if not type_ids:
        type_ids = get_market_type_ids()
    logger.info(f"type_ids: {len(type_ids)}")

    new_sde_query = text("""
    SELECT typeName as type_name, typeID as type_id, groupID as group_id, groupName as group_name,
           categoryID as category_id, categoryName as category_name
    FROM sdetypes
    WHERE typeID IN :type_ids
    """).bindparams(bindparam('type_ids', expanding=True))

    df = read_df(sde_db, new_sde_query, {'type_ids': type_ids})
    logger.debug(f"df: {len(df)}")
    return df

def get_filter_options(selected_category: str=None, show_all: bool=False)->tuple[list, list, pd.DataFrame]:

    sde_df = all_sde_info()
    sde_df = sde_df.reset_index(drop=True)
    logger.info(f"sde_df: {len(sde_df)}")
    logger.debug(f"selected_category: {selected_category}")

    if show_all:
        categories = sorted(sde_df['category_name'].unique().tolist())
        items = sorted(sde_df['type_name'].unique().tolist())
        cat_type_info = sde_df.copy()
        return categories, items, cat_type_info
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
            'type_names': selected_type_names}
        items = selected_type_names
        categories = [selected_category]
    else:
        categories = sorted(sde_df['category_name'].unique().tolist())
        items = sorted(sde_df['type_name'].unique().tolist())
        cat_type_info = sde_df.copy()
    return categories, items, cat_type_info

# Query function
def create_price_volume_chart(df):
    # Create histogram with price bins
    fig = px.histogram(
        df,
        x='price',
        y='volume_remain',
        histfunc='sum',  # Sum the volumes for each price point
        nbins=50,  # Adjust number of bins as needed
        title='Market Orders Distribution',
        labels={
            'price': 'Price (ISK)',
            'volume_remain': 'Volume Available'
        }
    )

    # Update layout for better readability
    fig.update_layout(
        bargap=0.1,  # Add small gaps between bars
        xaxis_title="Price (ISK)",
        yaxis_title="Volume Available",
        showlegend=False
    )

    # Format price labels with commas for thousands
    fig.update_xaxes(tickformat=",")

    return fig

def create_history_chart(type_id):
    df = get_market_history(type_id)
    if df.empty:
        return None

    # Calculate 14-day moving average
    df['ma_14'] = df['average'].rolling(window=14).mean()

    fig = go.Figure()
    # Create subplots: 2 rows, 1 column, shared x-axis
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],  # Price gets more space than volume

    )

    # Add price line to the top subplot (row 1)
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['average'],
            name='Average Price',
            line=dict(color='#FF69B4', width=2)  # Hot pink line
        ),
        row=1, col=1
    )

    # Add 14-day moving average to the top subplot (row 1)
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['ma_14'],
            name='14-Day MA',
            line=dict(color='#b87fe3', width=2, dash='dot')  # Orange dashed line
        ),
        row=1, col=1
    )

    # Add volume bars to the bottom subplot (row 2)
    fig.add_trace(
        go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            opacity=0.5,
            marker_color='#00B5F7',
            base=0,
              # Bright blue bars
        ),
        row=2, col=1
    )

    # Update layout for both subplots
    fig.update_layout(
        title = st.session_state.selected_item,
        paper_bgcolor='#0F1117',  # Dark background
        plot_bgcolor='#0F1117',   # Dark background
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1,
            xanchor="right",
            x=1,
            font=dict(color='white'),
            bgcolor='rgba(10,10,10,0)'  # Transparent background
        ),
        # margin=dict(t=50, b=50, r=20, l=50),
        title_font_color='white',
        # height=600,  # Taller to accommodate both plots
        hovermode='x unified',  # Show all data on hover
        autosize=True,
    )

    fig.update_yaxes(
        title=dict(text='Price (ISK)', font=dict(color='white', size=10), standoff=5),
        gridcolor='rgba(128,128,128,0.2)',
        tickfont=dict(color='white'),
        tickformat=",",
        row=1, col=1,
        automargin = True
    )

    # Update axes for the volume subplot (bottom)
    fig.update_yaxes(
        title=dict(text='Volume', font=dict(color='white', size=10), standoff=5),
        gridcolor='rgba(128,128,128,0.2)',
        tickfont=dict(color='white'),
        tickformat=",",
        row=2, col=1,
        automargin = True,
        color='white',
    )

    # Update shared x-axis
    fig.update_xaxes(
        gridcolor='rgba(128,128,128,0.2)',
        tickfont=dict(color='white'),
        row=2, col=1  # Apply to the bottom subplot's x-axis
    )

    # Hide x-axis labels for top subplot
    fig.update_xaxes(
        showticklabels=False,
        row=1, col=1
    )
    # Add background color for row 2 (volume subplot)
    fig.add_shape(
        type="rect",
        xref="paper",  # Use paper coordinates (0 to 1)
        yref="paper",
        x0=0,
        y0=0,
        x1=1,
        y1=0.3,  # Matches your row_heights=[0.7, 0.3]
        fillcolor="#1a1a2e",  # Your custom color here
        layer="below",
        line_width=0,
    )
    return fig

def new_display_sync_status():
    """Display sync status in the sidebar."""
    if "local_update_status" in st.session_state:
        update_time = st.session_state.local_update_status["updated"]
        logger.info(f"type of update_time: {type(update_time)}")
        display_time = update_time.strftime("%Y-%m-%d | %H:%M UTC")
        logger.info(f"display_time: {display_time}")
    else:
        update_time = None
    if update_time is None:
        try:
            update_time = DatabaseConfig("wcmkt").get_most_recent_update("marketstats", remote=False)
        except Exception as e:
            logger.error(f"Error getting update time: {e}")
            update_time = None
            logger.info("update_time is None")
    if update_time is not None:
        display_time = update_time.strftime("%Y-%m-%d | %H:%M UTC")
    else:
        display_time = "N/A"

    st.sidebar.markdown(f"<span style='font-size: 14px; color: lightgrey;'>*Last ESI update: {display_time}*</span>", unsafe_allow_html=True)

@st.cache_data(ttl=1800)
def check_for_db_updates()->tuple[bool, float]:
    db = DatabaseConfig("wcmkt")
    check = db.validate_sync()
    local_time = datetime.now()
    return check, local_time

def check_db():
    check, local_time = check_for_db_updates()
    now = time.time()
    logger.info(f"check_db() check: {check}, time: {local_time}")
    logger.info(f"last_check: {round(now - st.session_state.get('last_check', 0), 2)} seconds ago")

    if not check:
        st.toast("More recent remote database data available, syncing local database", icon="🕧")
        logger.info("check_db() check is False, syncing local database 🛜")
        db = DatabaseConfig("wcmkt")
        st.cache_data.clear()
        st.cache_resource.clear()
        db.sync()

        if db.validate_sync():
            logger.info("Local database synced and validated🟢")
            update_wcmkt_state()
        else:
            logger.info("Local database synced but validation failed❌")
    else:
        if 'local_update_status' in st.session_state:
            local_update_since = st.session_state.local_update_status["time_since"]
            local_update_since = local_update_since.total_seconds()
            local_update_since = local_update_since // 60
            local_update_since = f"{int(local_update_since)} mins"
        else:
            local_update_since = DatabaseConfig("wcmkt").get_time_since_update("marketstats", remote=False)
        st.toast(f"DB updated: {local_update_since} ago", icon="✅")

# Run this once every 600 seconds (10 minutes)
def maybe_run_check():
    now = time.time()
    if "last_check" not in st.session_state:
        logger.info("last_check not in st.session_state, setting to now")
        check_db()
        st.session_state["last_check"] = now
        logger.info("last_check set to now")

    elif now - st.session_state.get("last_check", 0) > 600:   # 600 seconds = 10 minutes
        logger.info(f"now - last_check={now - st.session_state.get('last_check', 0)}, running check_db()")
        check_db()
        st.session_state["last_check"] = now

def get_fitting_col_config()->dict:
    col_config = {
                'fit_id': st.column_config.NumberColumn(
                    "Fit ID",
                    help="WC Doctrine Fit ID"
                ),
                'ship_name': st.column_config.TextColumn(
                    "Ship Name",
                    help="Ship Name",
                    width="medium"
                ),
                'type_id': st.column_config.NumberColumn(
                    "Type ID",
                    help="Type ID"
                ),
                'type_name': st.column_config.TextColumn(
                    "Type Name",
                    help="Type Name",
                    width="medium"
                ),
                'hulls': st.column_config.NumberColumn(
                    "Hulls",
                    help="Number of ship hulls available for this fit",
                    width="small"
                ),
                'fit_qty': st.column_config.NumberColumn(
                    "Qty/fit",
                    help="Quantity of this item per fit",
                    format="localized",
                    width="small"
                ),
                'Fits on Market': st.column_config.NumberColumn(
                    "Fits",
                    help="Total fits available on market for this item",
                    format="localized",
                    width="small"
                ),
                'total_stock': st.column_config.NumberColumn(
                    "Stock",
                    help="Total stock of this item",
                    format="localized",
                    width="small"
                ),
                'price': st.column_config.NumberColumn(
                    "Price",
                    help="Price of this item (lowest 5-percentile price of current sell orders, or if no sell orders, the historical average price)",
                    format="localized"
                ),
                'avg_vol': st.column_config.NumberColumn(
                    "Avg Vol",
                    help="Average volume of this item over the last 30 days",
                    format="localized",
                    width="small"
                ),
                'days': st.column_config.NumberColumn(
                    "Days",
                    help="Days remaining for this item (based on historical average sales for the last 30 days)",
                    format="localized",
                    width="small"
                ),
                'group_name': st.column_config.Column(
                    "Group",
                    help="Group of this item",
                    width="small"
                ),
                'category_id': st.column_config.NumberColumn(
                    "Category ID",
                    help="Category ID of this item",
                    format="plain",
                    width="small"
                ),
            }
    return col_config

def get_display_formats()->dict:
    display_formats = {
        'type_id': st.column_config.NumberColumn("Type ID", help="Type ID of this item", width="small"),
        'order_id': st.column_config.NumberColumn("Order ID", help="Order ID of this item", width="small"),
        'type_name': st.column_config.TextColumn("Type Name", help="Type Name of this item", width="medium"),
        'volume_remain': st.column_config.NumberColumn("Qty", help="Quantity of this item", format="localized", width="small"),
        'price': st.column_config.NumberColumn("Price", help="Price of this item", format="localized"),
        'duration': st.column_config.NumberColumn("Duration", help="Duration of this item", format="localized", width="small"),
        'issued': st.column_config.DateColumn("Issued", help="Issued date of this item", format="YYYY-MM-DD"),
        'expiry': st.column_config.DateColumn("Expires", help="Expiration date of this item", format="YYYY-MM-DD"),
        'days_remaining': st.column_config.NumberColumn("Days Remaining", help="Days remaining of this item", format="plain", width="small"),
    }
    return display_formats

def check_selected_item(selected_item: str)->str | None:
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
        st.session_state.selected_item_id = get_backup_type_id(selected_item)
        jita_price = get_jita_price(st.session_state.selected_item_id)
        if jita_price:
            st.session_state.jita_price = jita_price
        else:
            st.session_state.jita_price = None
        logger.info(f"selected_item_id: {st.session_state.selected_item_id}")
        return selected_item

    else:
        selected_item = None
        st.session_state.jita_price = None
        st.session_state.current_price = None

def check_selected_category(selected_category: str, show_all: bool)->list | None:
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
        # Get filtered items based on selected category
        _, available_items, _ = get_filter_options(selected_category if not show_all and selected_category else None)
        return available_items
    else:
        st.session_state.selected_category = None
        st.session_state.selected_category_info = None
        st.session_state.selected_item = None
        st.session_state.selected_item_id = None
        st.session_state.jita_price = None
        return None

def initialize_main_function():
    logger.info("*****************************************************")
    logger.info("Starting main function")
    logger.info("*****************************************************")

    if not st.session_state.get('db_initialized'):
        logger.info("-"*30)
        logger.info("Initializing database")
        result = init_db()
        if result:
            st.toast("Database initialized successfully", icon="✅")
            st.session_state.db_initialized = True
        else:
            st.toast("Database initialization failed", icon="❌")
            st.session_state.db_initialized = False
    else:
        logger.info("Databases already initialized in session state")
    logger.info("*"*60)
    st.session_state.db_init_time = datetime.now()

def render_headers():
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        wclogo = "images/wclogo.png"
        st.image(wclogo, width=125)
    with col2:
        st.title("Winter Coalition Market Stats")

@st.fragment
def display_downloads():
    st.download_button("Download Market Orders", data=get_all_mkt_orders().to_csv(index=False), file_name="4H_market_orders.csv", mime="text/csv",type="tertiary", help="Download all 4H market orders as a CSV file",icon="📥")
    st.download_button("Download Market Stats", data=get_all_mkt_stats().to_csv(index=False), file_name="4H_market_stats.csv", mime="text/csv",type="tertiary", help="Download aggregated 4H market statistics for commonly traded items as a CSV file",icon="📥")
    st.download_button("Download Market History", data=get_all_market_history().to_csv(index=False), file_name="4H_market_history.csv", mime="text/csv",type="tertiary", help="Download 4H market history for commonly traded items as a CSV file",icon="📥")

def display_history_data(history_df):

    history_df.date = pd.to_datetime(history_df.date).dt.strftime("%Y-%m-%d")
    history_df.average = round(history_df.average.astype(float), 2)
    history_df = history_df.sort_values(by='date', ascending=False)
    history_df.volume = history_df.volume.astype(int)
    hist_col_config = {
        "date": st.column_config.DateColumn(
            "Date",
            help="Date of the history data",
            format="localized"
        ),
        "average": st.column_config.NumberColumn(
            "Average Price",
            help="Average price of the item",
            format="localized"
        ),
        "volume": st.column_config.NumberColumn(
            "Volume",
            help="Volume of the item",
            format="localized"
        ),
    }
    st.dataframe(history_df, hide_index=True, column_config=hist_col_config, width=600)
    return history_df

def display_history_metrics(history_df):
    avgpr30 = history_df[:30].average.mean()
    avgpr7 = history_df[:7].average.mean()

    avgvol30 = history_df[:30].volume.mean()
    avgvol7 = history_df[:7].volume.mean()

    prdelta = (avgpr7 - avgpr30) / avgpr30
    prdelta = round(prdelta * 100, 1)
    voldelta = (avgvol7 - avgvol30) / avgvol30
    voldelta = round(voldelta * 100, 1)
    col1h1,col1h2 = st.columns(2, border=True)
    with col1h1:
        st.metric("Average Price (7 days)", f"{millify.millify(avgpr7, precision=2)} ISK", delta=f"{prdelta}% this week")
        st.metric("Average Volume (7 days)", f"{millify.millify(avgvol7, precision=0)}", delta=f"{voldelta}% this week")
    with col1h2:
        st.metric("Average Price (30 days)", f"{millify.millify(avgpr30, precision=2)} ISK")
        st.metric("Average Volume (30 days)", f"{millify.millify(avgvol30, precision=0)}")


def main():
    if 'db_init_time' not in st.session_state:
        initialize_main_function()
    elif datetime.now() - st.session_state.db_init_time > timedelta(hours=1):
        initialize_main_function()

    maybe_run_check()
    render_headers()

    st.sidebar.header("Filters")
    show_all = st.sidebar.checkbox("Show All Data", value=False)

    categories, all_items, _ = get_filter_options()
    logger.debug(f"categories: {len(categories)}")
    selected_category = st.sidebar.selectbox(
        "Select Category",
        options=[""] + categories,  # Add empty option to allow no selection
        index=0,
        key="selected_category_choice",
        format_func=lambda x: "All Categories" if x == "" else x
    )

    available_items = check_selected_category(selected_category, show_all)
    if not available_items:
        available_items = all_items

    selected_item = st.sidebar.selectbox(
        "Select Item",
        options=[""] + available_items,  # Add empty option to allow no selection
        index=0,
        format_func=lambda x: "All Items" if x == "" else x
    )

    selected_item = check_selected_item(selected_item)

    t1 = time.perf_counter()
    sell_data, buy_data, stats = new_get_market_data(show_all)
    t2 = time.perf_counter()
    elapsed_time = (t2 - t1) * 1000
    logger.info(f"new_get_market_data elapsed: {elapsed_time:.2f} ms")

    # # Process sell orders
    sell_order_count = 0
    sell_total_value = 0
    if not sell_data.empty:
        sell_order_count = sell_data['order_id'].nunique()
        sell_total_value = (sell_data['price'] * sell_data['volume_remain']).sum()

    # Process buy orders
    buy_order_count = 0
    buy_total_value = 0
    if not buy_data.empty:
        buy_order_count = buy_data['order_id'].nunique()
        buy_total_value = (buy_data['price'] * buy_data['volume_remain']).sum()

    fit_df = pd.DataFrame()

    if not sell_data.empty:
        if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
            selected_item = st.session_state.selected_item
            sell_data = sell_data[sell_data['type_name'] == selected_item]

            if not buy_data.empty:
                buy_data = buy_data[buy_data['type_name'] == selected_item]
            stats = stats[stats['type_name'] == selected_item]

            if 'selected_item_id' in st.session_state:
                selected_item_id = st.session_state.selected_item_id
                logger.debug(f"selected_item_id in st.session_state: {selected_item_id}")
            else:
                logger.debug(f"selected_item_id not in st.session_state, getting backup type id")
                selected_item_id = get_backup_type_id(selected_item)
                st.session_state.selected_item_id = selected_item_id

            if selected_item_id:
                try:
                    fit_df = get_fitting_data(selected_item_id)
                except Exception:
                    logger.warning(f"Failed to get fitting data for {selected_item_id}")
                    fit_df = pd.DataFrame()

        elif show_all:
            selected_category = None
            selected_item = None
            selected_item_id = None
            fit_df = pd.DataFrame()

        elif 'selected_category' in st.session_state and st.session_state.selected_category is not None:
            selected_category = st.session_state.selected_category

            stats = stats[stats['category_name'] == selected_category]
            stats = stats.reset_index(drop=True)
            stats_type_ids = st.session_state.selected_category_info['type_ids']

            if not buy_data.empty:
                buy_data = buy_data[buy_data['type_id'].isin(stats_type_ids)]
                buy_data = buy_data.reset_index(drop=True)
            if not sell_data.empty:
                sell_data = sell_data[sell_data['type_id'].isin(stats_type_ids)]
                sell_data = sell_data.reset_index(drop=True)

        # Initialize variables needed for header display
        isship = False
        fits_on_mkt = None
        cat_id = None

        if fit_df is not None and fit_df.empty is False:
            cat_id = stats['category_id'].iloc[0]
            fits_on_mkt = fit_df['Fits on Market'].min()
            if cat_id == 6:
                isship = True

        # Create headers for different filter states
        if show_all:
            st.header("All Sell Orders", divider="green")
        elif 'selected_item' in st.session_state and st.session_state.selected_item is not None:
            selected_item = st.session_state.selected_item
            if 'selected_item_id' in st.session_state:
                selected_item_id = st.session_state.selected_item_id
            else:
                selected_item_id = get_backup_type_id(selected_item)
                st.session_state.selected_item_id = selected_item_id
            try:
                image_id = selected_item_id
                type_name = selected_item
            except Exception as e:
                logger.error(f"Error: {e}")
                logger.info(f"No type_id or type_name found for {selected_item}")
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
                        if cat_id in [7,8,18]:
                            st.write(get_module_fits(selected_item_id))
                        else:
                            st.write(fit_df[fit_df['type_id'] == selected_item_id]['group_name'].iloc[0])
                except Exception as e:
                    logger.error(f"Error: {e}")
                    pass
        elif 'selected_category' in st.session_state and st.session_state.selected_category is not None:
            selected_category = st.session_state.selected_category
            st.header(selected_category + "s", divider="green")

        # Current Market Metrics Section
        render_current_market_status_ui(
            sell_data=sell_data,
            stats=stats,
            selected_item=selected_item,
            sell_order_count=sell_order_count,
            sell_total_value=sell_total_value,
            fit_df=fit_df,
            fits_on_mkt=fits_on_mkt,
            cat_id=cat_id
        )

        # 30-Day Historical Metrics Section

        with st.expander("30-Day Market Stats (expand to view metrics)", expanded=False):
            render_30day_metrics_ui()

        st.divider()

        # Format the DataFrame for display with null handling
        display_df = sell_data.copy()

        # Add subheader for sell orders section
        if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
            selected_item = st.session_state.selected_item
            st.subheader("Sell Orders for " + selected_item, divider="blue")
        elif 'selected_category' in st.session_state and st.session_state.selected_category is not None:
            selected_category = st.session_state.selected_category
            cat_label = selected_category
            if not cat_label.endswith("s"):
                cat_label = cat_label + "s"
            st.subheader(f"Sell Orders for {cat_label}", divider="blue")

        else:
            st.subheader("All Sell Orders", divider="green")

        display_df.drop(columns='is_buy_order', inplace=True)

        display_formats = get_display_formats()

        st.dataframe(display_df, hide_index=True, column_config=display_formats)

    # Display buy orders if they exist
    if not buy_data.empty:
        if show_all:
            st.subheader("All Buy Orders", divider="orange")
        else:
                # Display buy orders header
            if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
                selected_item = st.session_state.selected_item
                type_name = selected_item
                st.subheader(f"Buy Orders for {type_name}", divider="orange")
            elif 'selected_category' in st.session_state and st.session_state.selected_category is not None:
                selected_category = st.session_state.selected_category
                cat_label = selected_category
                if cat_label.endswith("s"):
                    cat_label = cat_label
                else:
                    cat_label = cat_label + "s"
                st.subheader(f"Buy Orders for {cat_label}", divider="orange")

            else:
                st.subheader("All Buy Orders", divider="orange")

        # Display buy orders metrics
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

        # Format buy orders for display
        buy_display_df = buy_data.copy()
        buy_display_df.type_id = buy_display_df.type_id
        buy_display_df.order_id = buy_display_df.order_id
        buy_display_df.drop(columns='is_buy_order', inplace=True)

        st.dataframe(buy_display_df, hide_index=True, column_config=display_formats)

    elif not sell_data.empty:
        if st.session_state.selected_item is not None:
            st.write(f"No current buy orders found for {st.session_state.selected_item}")
        else:
            pass
    else:
        if st.session_state.selected_item is not None:
            st.write(f"No current market orders found for {st.session_state.selected_item}")
        else:
            pass

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
        render_ISK_volume_chart_ui()
        with st.expander("Expand to view Market History Data"):
            render_ISK_volume_table_ui()

    # Get selected_item from session state if available
    if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
        selected_item = st.session_state.selected_item
        if 'selected_item_id' in st.session_state and st.session_state.selected_item_id is not None:
            selected_item_id = st.session_state.selected_item_id
        else:
            try:
                selected_item_id = get_backup_type_id(selected_item)
            except Exception as e:
                logger.error(f"Error: {e}")
                selected_item_id = None
            st.session_state.selected_item_id = selected_item_id
    else:
        selected_item_id = None
        st.session_state.selected_item_id = selected_item_id

    if selected_item_id is not None:
        logger.debug(f"Displaying history chart for {selected_item_id}")

        history_chart = create_history_chart(selected_item_id)
        selected_history = get_market_history(selected_item_id)

        if history_chart:
            logger.debug(f"Displaying history chart for {selected_item_id}")
            st.plotly_chart(history_chart, config={'width': 'content'})

        if selected_history is not None and selected_history.empty is False:
            logger.info(f"Displaying history data for {selected_item_id}")
            colh1, colh2 = st.columns(2)
            with colh1:
                # Display history data
                history_df = display_history_data(selected_history)

            with colh2:
                if not history_df.empty:
                    display_history_metrics(history_df)

        st.divider()

    if fit_df is None:
        fit_df = pd.DataFrame()
    if fit_df.empty is False and fit_df is not None:
        st.subheader("Fitting Data",divider="blue")

        if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
            selected_item = st.session_state.selected_item
        else:
            selected_item = " "
        if 'selected_item_id' in st.session_state and st.session_state.selected_item_id is not None:
            selected_item_id = st.session_state.selected_item_id
        else:
            selected_item_id = get_backup_type_id(selected_item)
        try:
            fit_id = fit_df['fit_id'].iloc[0]
        except Exception as e:
            logger.error(f"Error: {e}")
            fit_id = " "
        st.markdown(f"<span style='font-weight: bold; color: orange;'>{selected_item}</span> | type_id: {selected_item_id} | fit_id: {fit_id}", unsafe_allow_html=True)

        if isship:
            column_config = get_fitting_col_config()
            st.dataframe(fit_df, hide_index=True, column_config=column_config, width='content')

    # Display sync status in sidebar
    with st.sidebar:
        new_display_sync_status()

        st.sidebar.divider()

        db_check = st.sidebar.button("Check DB State", width='content')
        if db_check:
            check_db()
        st.sidebar.divider()

        display_downloads()

if __name__ == "__main__":
    main()
