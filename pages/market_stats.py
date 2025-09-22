import os
import sys
import time


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from httpx import head
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text,bindparam
from sqlalchemy.orm import Session
from db_handler import safe_format,get_market_history,get_fitting_data,get_module_fits
from logging_config import setup_logging
import millify
from config import DatabaseConfig
from db_handler import new_get_market_data, get_all_mkt_orders, get_all_mkt_stats, get_all_market_history
from init_db import init_db
from sync_state import update_wcmkt_state
from type_info import get_backup_type_id
from datetime import datetime, timezone


mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")
build_cost_db = DatabaseConfig("build_cost")

# Insert centralized logging configuration
logger = setup_logging(__name__)

# Log application start
logger.info("Application started")
logger.info(f"streamlit version: {st.__version__}")
logger.info("-"*100)

@st.cache_data(ttl=600)
def get_market_type_ids()->list:
    # Get all type_ids from market orders
    mkt_query = """
    SELECT DISTINCT type_id
    FROM marketorders
    """
    with Session(mkt_db.engine) as session:
        result = session.execute(text(mkt_query))
        type_ids = [row[0] for row in result.fetchall()]
        logger.info(f"type_ids: {len(type_ids)}")
        return type_ids

# Function to get unique categories and item names
def all_sde_info(type_ids: list = None)->pd.DataFrame:
    if not type_ids:
        type_ids = get_market_type_ids()
    logger.info(f"type_ids: {len(type_ids)}")

    # Use SQLAlchemy's proper IN clause with parameter binding
    sde_query = text("""
    SELECT DISTINCT it.typeName as type_name, it.typeID as type_id, it.groupID as group_id, ig.groupName as group_name,
           ic.categoryID as category_id, ic.categoryName as category_name
    FROM invTypes it
    JOIN invGroups ig ON it.groupID = ig.groupID
    JOIN invCategories ic ON ig.categoryID = ic.categoryID
    WHERE it.typeID IN :type_ids
    """).bindparams(bindparam('type_ids', expanding=True))

    new_sde_query = text("""
    SELECT typeName as type_name, typeID as type_id, groupID as group_id, groupName as group_name,
           categoryID as category_id, categoryName as category_name
    FROM sdetypes
    WHERE typeID IN :type_ids
    """).bindparams(bindparam('type_ids', expanding=True))

    with Session(sde_db.engine) as session:
        result = session.execute(new_sde_query, {'type_ids': type_ids})
        df = pd.DataFrame(result.fetchall(),
            columns=['type_name', 'type_id', 'group_id', 'group_name', 'category_id', 'category_name'])
        logger.info(f"df: {len(df)}")
        session.close()

    return df

def get_filter_options(selected_category: str=None, show_all: bool=False)->tuple[list, list, pd.DataFrame]:

    sde_df = all_sde_info()
    sde_df = sde_df.reset_index(drop=True)
    logger.info(f"sde_df: {len(sde_df)}")
    logger.info(f"selected_category: {selected_category}")

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

    # Calculate ranges with padding
    min_price = df['average'].min()
    max_price = df['average'].max()
    price_padding = (max_price - min_price) * 0.05  # 5% padding
    min_volume = df['volume'].min()
    max_volume = df['volume'].max()

    # Update layout for both subplots
    fig.update_layout(
        title='Market History',
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
        automargin = True
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

    return fig

def display_sync_status():
    """Display sync status in the sidebar."""
    if "local_update_status" not in st.session_state:
        init_db()
    update_time = st.session_state.local_update_status["updated"]
    update_time = update_time.strftime("%Y-%m-%d | %H:%M UTC")
    time_since_update = st.session_state.local_update_status["time_since"]
    time_since_update = time_since_update.total_seconds()
    time_since_update = f"{round((time_since_update / 3600),1)} hours"
    st.markdown("&nbsp;"*5)
    st.sidebar.markdown(f"<span style='font-size: 14px; color: lightgrey;'>*Last ESI update: {update_time}*</span>", unsafe_allow_html=True)

@st.fragment
def dump_session_state():
    logger.info("*"*40)
    logger.info("Dumping session state")
    logger.info("*"*40)
    for k,v in st.session_state.items():
        if isinstance(v, dict):
            logger.info(f"{k}")
            logger.info("+++++")
            for k2,v2 in v.items():
                logger.info(f"{k2}")
        else:
            logger.info(f"{k, v}")
        logger.info("-"*40)
    logger.info("*"*40)
    logger.info("="*40)


@st.cache_data(ttl=600)
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
        check_db()
        st.session_state["last_check"] = now
        logger.info("last_check not in st.session_state, setting to now")

    last_run = st.session_state.get("last_check", 0)

    if now - last_run > 600:   # 600 seconds = 10 minutes
        logger.info("Running check_db()")
        logger.info(f"now - last_run: {now - last_run}")
        check_db()
        st.session_state["last_check"] = now


def main():
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

    maybe_run_check()

    wclogo = "images/wclogo.png"
    st.image(wclogo, width=150)

    # Title
    st.title("Winter Coalition Market Stats")

    # Sidebar filters
    st.sidebar.header("Filters")

    # Show all option
    show_all = st.sidebar.checkbox("Show All Data", value=False)

    logger.info("Getting initial categories")
    # Get initial categories
    categories, available_items, _ = get_filter_options()
    logger.info(f"categories: {len(categories)}")
    # Category filter - changed to selectbox for single selection
    selected_category = st.sidebar.selectbox(
        "Select Category",
        options=[""] + categories,  # Add empty option to allow no selection
        index=0,
        key="selected_category_choice",
        format_func=lambda x: "All Categories" if x == "" else x
    )
    if selected_category == "":
        logger.info(f"selected_category is {selected_category}")
        st.session_state.selected_category = None
        st.session_state.selected_category_info = None
        st.session_state.selected_item = None
        st.session_state.selected_item_id = None

    if selected_category and selected_category != None:
        logger.info(f"selected_category exists and is not None")
        st.sidebar.text(f"Category: {selected_category}")
        st.session_state.selected_category = selected_category
        logger.info(f"selected_category: {selected_category}")
        # Get filtered items based on selected category
        _, available_items, cat_type_info = get_filter_options(selected_category if not show_all and selected_category else None)


        # Item name filter - changed to selectbox for single selection
    selected_item = st.sidebar.selectbox(
        "Select Item",
        options=[""] + available_items,  # Add empty option to allow no selection
        index=0,
        format_func=lambda x: "All Items" if x == "" else x
    )

    if selected_item == "":
        st.session_state.selected_item = None
        st.session_state.selected_item_id = None

    if selected_item and selected_item != None:
        st.sidebar.text(f"Item: {selected_item}")
        st.session_state.selected_item = selected_item
        logger.info(f"Selected item: {selected_item}")
        st.session_state.selected_item_id = get_backup_type_id(selected_item)

    else:
        selected_item = None


    t1 = time.perf_counter()

    # sell_data, buy_data, stats = get_market_data(show_all, selected_category, selected_items)
    sell_data, buy_data, stats = new_get_market_data(show_all)

    # Main content
    t2 = time.perf_counter()
    elapsed_time = (t2-t1)*1000

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


    if not sell_data.empty:

        if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
            selected_item = st.session_state.selected_item
            if 'selected_item_id' in st.session_state:
                selected_item_id = st.session_state.selected_item_id
            else:
                selected_item_id = get_backup_type_id(selected_item)
                st.session_state.selected_item_id = selected_item_id
            sell_data = sell_data[sell_data['type_name'] == selected_item]
            if not buy_data.empty:
                buy_data = buy_data[buy_data['type_name'] == selected_item]
            stats = stats[stats['type_name'] == selected_item]
            if selected_item_id:
                try:
                    fit_df = get_fitting_data(selected_item_id)
                except:
                    logger.warning(f"Failed to get fitting data for {selected_item_id}")
                    fit_df = pd.DataFrame()
            else:
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

        # Display metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            if not sell_data.empty:
                min_price = stats['min_price'].min()
                if pd.notna(min_price) and selected_item:
                    display_min_price = millify.millify(min_price, precision=2)
                    st.metric("Sell Price (min)", f"{display_min_price} ISK")
            else:
                st.metric("Sell Price (min)", "0 ISK")

            if sell_total_value > 0:
                display_sell_total_value = millify.millify(sell_total_value, precision=2)
                st.metric("Market Value (sell orders)", f"{display_sell_total_value} ISK")
            else:
                st.metric("Market Value (sell orders)", "0 ISK")

        with col2:
            if not sell_data.empty:
                volume = sell_data['volume_remain'].sum()
                if pd.notna(volume):
                    display_volume = millify.millify(volume, precision=2)
                    st.metric("Market Stock (sell orders)", f"{display_volume}")
            else:
                st.metric("Market Stock (sell orders)", "0")

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
            isship = False
            try:
                cat_id = stats['category_id'].iloc[0]
                fits_on_mkt = fit_df['Fits on Market'].min()

                if cat_id == 6:
                    display_fits_on_mkt = f"{fits_on_mkt:,.0f}"
                    st.metric("Fits on Market", f"{display_fits_on_mkt}")
                    isship = True

            except:
                pass


        st.divider()
        # Display detailed data

        # Format the DataFrame for display with null handling
        display_df = sell_data.copy()

        #create a header for the item
        if show_all:
            st.subheader("All Sell Orders", divider="green")
        else:
            if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
                selected_item = st.session_state.selected_item
                if 'selected_item_id' in st.session_state:
                    selected_item_id = st.session_state.selected_item_id
                else:
                    selected_item_id = get_backup_type_id(selected_item)
                    st.session_state.selected_item_id = selected_item_id
                try:
                    image_id = selected_item_id
                    type_name = selected_item
                except:
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
                        if fits_on_mkt:
                            st.subheader("Winter Co. Doctrine", divider="orange")
                            if cat_id in [7,8,18]:
                                st.write(get_module_fits(selected_item_id))
                            else:
                                st.write(fit_df[fit_df['type_id'] == selected_item_id]['group_name'].iloc[0])
                    except:
                        pass
            elif 'selected_category' in st.session_state and st.session_state.selected_category is not None:
                selected_category = st.session_state.selected_category

                cat_label = selected_category
                if cat_label.endswith("s"):
                    cat_label = cat_label
                else:
                    cat_label = cat_label + "s"
                st.subheader(f"Sell Orders for {cat_label}", divider="blue")
            else:
                st.subheader("All Sell Orders", divider="green")

        display_df.type_id = display_df.type_id.astype(str)
        display_df.order_id = display_df.order_id.astype(str)
        display_df.drop(columns='is_buy_order', inplace=True)
        # Format numeric columns safely
        numeric_formats = {
            'volume_remain': '{:,.0f}',
            'price': '{:,.2f}',
            'min_price': '{:,.2f}',
            'avg_of_avg_price': '{:,.2f}',
        }

        for col, format_str in numeric_formats.items():
            if col in display_df.columns:  # Only format if column exists
                display_df[col] = display_df[col].apply(lambda x: safe_format(x, format_str))

        st.dataframe(display_df, hide_index=True)

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
            buy_display_df.type_id = buy_display_df.type_id.astype(str)
            buy_display_df.order_id = buy_display_df.order_id.astype(str)
            buy_display_df.drop(columns='is_buy_order', inplace=True)

            # Format numeric columns safely
            for col, format_str in numeric_formats.items():
                if col in buy_display_df.columns:  # Only format if column exists
                    buy_display_df[col] = buy_display_df[col].apply(lambda x: safe_format(x, format_str))

            st.dataframe(buy_display_df, hide_index=True)

        # Display charts
        st.subheader("Market Order Distribution")
        price_vol_chart = create_price_volume_chart(sell_data)
        st.plotly_chart(price_vol_chart, use_container_width=True)

        st.divider()

        st.subheader("Price History")
        try:
            if 'selected_item_id' in st.session_state:
                selected_item_id = st.session_state.selected_item_id
        except:
            selected_item_id = None

        try:
            # Get selected_item from session state if available
            if 'selected_item' in st.session_state and st.session_state.selected_item is not None:
                selected_item = st.session_state.selected_item
                selected_item_id = get_backup_type_id(selected_item)
                st.session_state.selected_item_id = selected_item_id
            else:
                selected_item_id = None
        except:
            selected_item_id = None

        if selected_item_id:
            logger.info(f"Displaying history chart for {selected_item_id}")
            history_chart = create_history_chart(selected_item_id)
        else:
            history_chart = None

        if history_chart:
            logger.info(f"Displaying history chart for {selected_item_id}")
            st.plotly_chart(history_chart, use_container_width=False)

            colh1, colh2 = st.columns(2)
            with colh1:
                # Display history data
                st.subheader("History Data")
                history_df = get_market_history(selected_item_id)
                history_df.date = pd.to_datetime(history_df.date).dt.strftime("%Y-%m-%d")
                history_df.average = round(history_df.average.astype(float), 2)
                history_df = history_df.sort_values(by='date', ascending=False)
                history_df.volume = history_df.volume.astype(int)
                st.dataframe(history_df, hide_index=True)

            with colh2:
                avgpr30 = history_df[:30].average.mean()
                avgvol30 = history_df[:30].volume.mean()
                st.subheader(f"{selected_item}",divider=True)
                st.metric("Average Price (30 days)", f"{avgpr30:,.2f} ISK")
                st.metric("Average Volume (30 days)", f"{avgvol30:,.0f}")
        else:
            st.write("History data not available for this item or no item selected")

        st.divider()

        st.subheader("Fitting Data")
        if 'selected_item' in st.session_state:
            selected_item = st.session_state.selected_item
            if isship:
                st.dataframe(fit_df, hide_index=True)
            else:
                st.write("Fitting data only available for ships")
        else:
            st.write("Fitting data not available for this item or no item selected")

    else:
        st.warning("No data found for the selected filters.")


    # Display sync status in sidebar
    with st.sidebar:
        display_sync_status()

        # utility function to dump session state in development mode -- leave off in production
        # dump = st.sidebar.button("Dump Session State", use_container_width=True)
        # if dump:
        #     dump_session_state()
        #     st.toast("Session state dumped", icon="✅")

        st.sidebar.divider()
        db_check = st.sidebar.button("Check DB State", use_container_width=True)
        if db_check:
            check_db()
        st.sidebar.divider()
        st.download_button("Download Market Orders", data=get_all_mkt_orders().to_csv(index=False), file_name="4H_market_orders.csv", mime="text/csv",type="tertiary", help="Download all 4H market orders as a CSV file",icon="📥")
        st.download_button("Download Market Stats", data=get_all_mkt_stats().to_csv(index=False), file_name="4H_market_stats.csv", mime="text/csv",type="tertiary", help="Download aggregated 4H market statistics for commonly traded items as a CSV file",icon="📥")
        st.download_button("Download Market History", data=get_all_market_history().to_csv(index=False), file_name="4H_market_history.csv", mime="text/csv",type="tertiary", help="Download 4H market history for commonly traded items as a CSV file",icon="📥")


        # st.sidebar.markdown("---")
        # force_sync = st.sidebar.button("Force Sync", use_container_width=True, type="tertiary")
        # if force_sync:
        #     st.cache_data.clear()
        #     st.cache_resource.clear()
        #     mkt_db.sync()

if __name__ == "__main__":
    main()
