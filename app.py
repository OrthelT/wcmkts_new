import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine, text, distinct
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
from db_handler import  clean_mkt_data, get_local_mkt_engine, get_local_sde_engine, get_stats, safe_format, get_mkt_data, get_market_orders, get_market_history, get_item_details
import sqlalchemy_libsql
import libsql_client
import logging
import time
import threading
import datetime
import pytz
from db_utils import sync_db
# Configure logging
logging.basicConfig(
    filename='app.log',  # Name of the log file
    level=logging.INFO,  # Set the logging level
    format='%(asctime)s - %(levelname)s - %(message)s',  # Log message format
)
# Log application start
logging.info("Application started")

mkt_url = st.secrets["TURSO_DATABASE_URL"]
mkt_auth_token = st.secrets["TURSO_AUTH_TOKEN"]

sde_url = st.secrets["SDE_URL"]
sde_auth_token = st.secrets["SDE_AUTH_TOKEN"]

# Function to schedule daily database sync at 1300 UTC
def schedule_db_sync():
    def sync_at_scheduled_time():
        while True:
            now = datetime.datetime.now(datetime.UTC)
            target_time = now.replace(hour=13, minute=0, second=0, microsecond=0)
            
            # If it's already past 13:00 UTC today, sync now and then schedule for tomorrow
            if now >= target_time:
                # Sync immediately if it's past 1300 UTC
                try:
                    logging.info("Past 1300 UTC, running initial sync now")
                    sync_db()
                    logging.info("Initial database sync completed successfully")
                    
                    # Update session state
                    if "last_sync" not in st.session_state:
                        st.session_state.last_sync = datetime.datetime.now(datetime.UTC)
                        st.session_state.sync_status = "Success"
                except Exception as e:
                    logging.error(f"Initial database sync failed: {str(e)}")
                    if "last_sync" in st.session_state:
                        st.session_state.sync_status = f"Failed: {str(e)}"
                
                # Schedule for tomorrow
                target_time += datetime.timedelta(days=1)
            
            # Calculate seconds until the next sync
            seconds_until_sync = (target_time - now).total_seconds()
            logging.info(f"Next database sync scheduled at {target_time} UTC ({seconds_until_sync/3600:.2f} hours from now)")
            
            # Sleep until the scheduled time
            time.sleep(seconds_until_sync)
            
            # Perform sync
            try:
                logging.info("Starting scheduled database sync")
                sync_db()
                logging.info("Database sync completed successfully")
                
                # Display sync status in Streamlit
                st.session_state.last_sync = datetime.datetime.now(datetime.UTC)
                st.session_state.sync_status = "Success"
            except Exception as e:
                logging.error(f"Database sync failed: {str(e)}")
                st.session_state.sync_status = f"Failed: {str(e)}"
    
    # Start the sync scheduler in a separate thread
    sync_thread = threading.Thread(target=sync_at_scheduled_time, daemon=True)
    sync_thread.start()
    logging.info("Database sync scheduler started")

mkt_query = """
    SELECT DISTINCT type_id 
    FROM marketorders 
    WHERE is_buy_order = 0
    """

# Function to get unique categories and item names
def get_filter_options(selected_categories=None):
    try:
        # First get type_ids from market orders
        mkt_query = """
        SELECT DISTINCT type_id 
        FROM marketorders 
        WHERE is_buy_order = 0
        """
        logging.info(f"mkt_query: {mkt_query}, get_local_mkt_engine()")
        with Session(get_local_mkt_engine()) as session:
            result = session.execute(text(mkt_query))
            type_ids = [row[0] for row in result.fetchall()]
       
            if not type_ids:
                return [], []
            type_ids_str = ','.join(map(str, type_ids))
        
        logging.info(f"type_ids: {len(type_ids)}")

        # Then get category info from SDE database
        sde_query = f"""
        SELECT DISTINCT it.typeName as type_name, it.typeID as type_id, it.groupID as group_id, ig.groupName as group_name, 
               ic.categoryID as category_id, ic.categoryName as category_name
        FROM invTypes it 
        JOIN invGroups ig ON it.groupID = ig.groupID
        JOIN invCategories ic ON ig.categoryID = ic.categoryID
        WHERE it.typeID IN ({type_ids_str})
        """
        logging.info(f"sde_query: {sde_query}, get_local_sde_engine()")
        with Session(get_local_sde_engine()) as session:
            result = session.execute(text(sde_query))
            df = pd.DataFrame(result.fetchall(), 
                              columns=['type_name', 'type_id', 'group_id', 'group_name', 'category_id', 'category_name'])

            categories = sorted(df['category_name'].unique())
            
            if selected_categories:
                df = df[df['category_name'].isin(selected_categories)]   
        
        items = sorted(df['type_name'].unique())
        logging.info(f"items: {len(items)}")
        logging.info(f"categories: {len(categories)}")
        
        return categories, items
        

    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return [], []

# Query function
def get_market_data(show_all, selected_categories, selected_items):
    # Start with base condition for buy orders
    mkt_conditions = ["is_buy_order = 0"]

    print(f'selected_categories: {selected_categories}')
    print(f'selected_items: {selected_items}')

    if not show_all:
        # Get type_ids for the selected categories from SDE first
        sde_conditions = []
        if selected_categories:
            categories_str = ', '.join(f"'{cat}'" for cat in selected_categories)
            sde_conditions.append(f"ic.categoryName IN ({categories_str})")
        
        if selected_items:
            items_str = ', '.join(f"'{item}'" for item in selected_items)
            sde_conditions.append(f"it.typeName IN ({items_str})")
            
        if sde_conditions:
            sde_where = " AND ".join(sde_conditions)
            sde_query = f"""
                SELECT DISTINCT it.typeID
                FROM invTypes it 
                JOIN invGroups ig ON it.groupID = ig.groupID
                JOIN invCategories ic ON ig.categoryID = ic.categoryID
                WHERE {sde_where}
            """
            
            with Session(get_local_sde_engine()) as session:
                result = session.execute(text(sde_query))
                filtered_type_ids = [str(row[0]) for row in result.fetchall()]
                session.commit()
                session.close()
            
            logging.info(f"filtered_type_ids: {len(filtered_type_ids)}")
            
            if filtered_type_ids:
                type_ids_str = ','.join(filtered_type_ids)
                mkt_conditions.append(f"type_id IN ({type_ids_str})")
            else:
                return pd.DataFrame()  # Return empty if no matching types
    
    # Build final market query
    where_clause = " AND ".join(mkt_conditions)
    mkt_query = f"""
        SELECT mo.* 
        FROM marketorders mo
        WHERE {where_clause}
        ORDER BY type_id
    """
    stats_query = f"""
        SELECT * FROM marketstats

    """
    # Get market data
    df = get_mkt_data(mkt_query)
    logging.info(f"df: {type(df)}")

    if df.empty:
        logging.info(f"df is empty")
        return df
    
    stats = get_stats(stats_query)

    logging.info(f"stats: {stats.head()}")


    logging.info(f"stats: {type(stats)}")
    # Get SDE data for all type_ids in the result
    type_ids_str = ','.join(map(str, df['type_id'].unique()))
    sde_query = f"""
        SELECT it.typeID as type_id, it.typeName, ig.groupName, ic.categoryName
        FROM invTypes it 
        JOIN invGroups ig ON it.groupID = ig.groupID
        JOIN invCategories ic ON ig.categoryID = ic.categoryID
        WHERE it.typeID IN ({type_ids_str})
    """
    
    with Session(get_local_sde_engine()) as session:
        result = session.execute(text(sde_query))
        sde_df = pd.DataFrame(result.fetchall(), 
                            columns=['type_id', 'type_name', 'group_name', 'category_name'])
        session.commit()
        session.close()

    # Merge market data with SDE data
    df = df.merge(sde_df, on='type_id', how='left')
    df = clean_mkt_data(df)

    logging.info(f"df: {df.head()}")
    logging.info(f"stats: {stats.head()}")
    logging.info(f"df.columns: {df.columns}")
    logging.info(f"stats.columns: {stats.columns}")


    return df, stats

def load_data(selected_categories=None, selected_items=None):
    # Get all market orders
    df = get_market_orders()
    if df.empty:
        return pd.DataFrame()
    
    # Get item details from SDE
    items_df = get_item_details(df['type_id'].unique())
    df = df.merge(items_df, on='type_id', how='left')
    
    # Apply filters
    if selected_categories:
        df = df[df['category_name'].isin(selected_categories)]
    if selected_items:
        df = df[df['type_name'].isin(selected_items)]
    
    return df

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
    
    # Create figure with secondary y-axis
    fig = go.Figure()
    
    # Add volume bars
    fig.add_trace(
        go.Bar(
            x=df['date'],
            y=df['volume'],
            name='Volume',
            yaxis='y2',
            opacity=0.5,
            marker_color='#00B5F7'  # Bright blue bars
        )
    )
    
    # Add price line
    fig.add_trace(
        go.Scatter(
            x=df['date'],
            y=df['average'],
            name='Average Price',
            line=dict(color='#FF69B4', width=2)  # Hot pink line
        )
    )
    
    # Update layout for dual axis with dark theme
    fig.update_layout(
        title='Market History',
        paper_bgcolor='#0F1117',  # Dark background
        plot_bgcolor='#0F1117',   # Dark background
        yaxis=dict(
            title=dict(
                text='Price (ISK)',
                font=dict(color='white')
            ),
            gridcolor='rgba(128,128,128,0.2)',  # Subtle grid
            tickfont=dict(color='white')
        ),
        yaxis2=dict(
            title=dict(
                text='Volume',
                font=dict(color='white')
            ),
            tickfont=dict(color='white'),
            gridcolor='rgba(128,128,128,0.2)',  # Subtle grid
            overlaying='y',
            side='right'
        ),
        xaxis=dict(
            gridcolor='rgba(128,128,128,0.2)',  # Subtle grid
            tickfont=dict(color='white')
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color='white')
        ),
        margin=dict(t=50, b=50),
        title_font_color='white'
    )
    
    # Format price axis with commas for thousands
    fig.update_yaxes(tickformat=",")
    
    return fig

def main():

    logging.info("Starting main function")

    st.set_page_config(
        page_title="Market Stats Viewer",
        page_icon="📈",
        layout="wide"
    )
    
    # Start database sync scheduler (only once)
    logging.info("Starting sync scheduler")
    if 'sync_scheduler_started' not in st.session_state:
        schedule_db_sync()
        st.session_state.sync_scheduler_started = True
        logging.info("Sync scheduler started from main function")

    # Initialize sync status in session state if not present
    if 'last_sync' not in st.session_state:
        st.session_state.last_sync = None
        st.session_state.sync_status = "Not yet run"
    logging.info("Sync status initialized")
    wclogo = "images/wclogo.png"
    st.image(wclogo, width=150)

    # Title
    st.title("Winter Coalition 4H Market Stats")
    

    # Sidebar filters
    st.sidebar.header("Filters")

    # Show all option
    show_all = st.sidebar.checkbox("Show All Data", value=False)

    logging.info("Getting initial categories")
    # Get initial categories
    categories, _ = get_filter_options()

    # Category filter - changed to selectbox for single selection
    selected_category = st.sidebar.selectbox(
        "Select Category",
        options=[""] + categories,  # Add empty option to allow no selection
        index=0,
        format_func=lambda x: "All Categories" if x == "" else x
    )
    
    # Convert to list format for compatibility with existing code
    selected_categories = [selected_category] if selected_category else []

    logging.info(f"Selected category: {selected_category}")
    
    # Debug info
    if selected_category:
        st.sidebar.text(f"Category: {selected_category}")
    
    # Get filtered items based on selected category
    _, available_items = get_filter_options(selected_categories if not show_all and selected_category else None)

    # Item name filter - changed to selectbox for single selection
    selected_item = st.sidebar.selectbox(
        "Select Item",
        options=[""] + available_items,  # Add empty option to allow no selection
        index=0,
        format_func=lambda x: "All Items" if x == "" else x
    )
    
    # Convert to list format for compatibility with existing code
    selected_items = [selected_item] if selected_item else []
    
    # Debug info
    if selected_item:
        st.sidebar.text(f"Item: {selected_item}")
    
    logging.info(f"Selected item: {selected_item}")
    # Main content
    data, stats = get_market_data(show_all, selected_categories, selected_items)
    
    logging.info(f"Data: {data.head()}")
    logging.info(f"Stats: {stats.head()}")
    

    if not data.empty:
        if len(selected_items) == 1:
            data = data[data['type_name'] == selected_items[0]]
            stats = stats[stats['type_name'] == selected_items[0]]
        elif len(selected_categories) == 1:
            stats = stats[stats['category_name'] == selected_categories[0]]
        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            min_price = stats['min_price'].min()
            if pd.notna(min_price):
                st.metric("Sell Price (min)", f"{min_price:,.2f} ISK")
        with col2:
            volume = data['volume_remain'].sum()
            if pd.notna('volume_remain'):
                st.metric("Market Stock", f"{volume:,.0f}")
        with col3:
            days_remaining = stats['days_remaining'].min()
            if pd.notna(days_remaining):
                st.metric("Days Remaining", f"{days_remaining:.1f}")
        # Format the DataFrame for display with null handling
        display_df = data.copy()
        # Display detailed data

        if len(selected_items) == 1:
            image_id = display_df.iloc[0]['type_id']
            type_name = display_df.iloc[0]['type_name']
            st.subheader(f"Detailed Market Data: {type_name}")
            st.image(f'https://images.evetech.net/types/{image_id}/render?size=64')
        else:
            st.subheader("Detailed Market Data")

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

        # Display charts
        st.subheader("Market Order Distribution")
        price_vol_chart = create_price_volume_chart(data)
        st.plotly_chart(price_vol_chart, use_container_width=True)

        # If single item is selected, show history chart
        if len(data['type_id'].unique()) == 1:
            st.subheader("Price History")
            history_chart = create_history_chart(data['type_id'].iloc[0])
            if history_chart:
                st.plotly_chart(history_chart, use_container_width=True)
        else:
            st.subheader("Price History")
            st.write("Price history is not available for multiple items. Select one item to view history")
        # Footer

    else:
        st.warning("No data found for the selected filters.")

    # Display database sync status in a small info area
    with st.sidebar:
        st.sidebar.markdown("---")
        st.sidebar.subheader("Database Sync Status")
        status_color = "green" if st.session_state.sync_status == "Success" else "red"
        
        if st.session_state.last_sync:
            last_sync_time = st.session_state.last_sync.strftime("%Y-%m-%d %H:%M UTC")
            st.sidebar.markdown(f"**Last sync:** {last_sync_time}")
        else:
            st.sidebar.markdown("**Last sync:** Not yet run")
            
        st.sidebar.markdown(f"**Status:** <span style='color:{status_color}'>{st.session_state.sync_status}</span>", unsafe_allow_html=True)
        
        # Manual sync button
        if st.sidebar.button("Sync Now"):
            try:
                sync_db()
                st.session_state.last_sync = datetime.datetime.now(datetime.UTC)
                st.session_state.sync_status = "Success"
                st.sidebar.success("Database sync completed successfully!")
            except Exception as e:
                st.session_state.sync_status = f"Failed: {str(e)}"
                st.sidebar.error(f"Sync failed: {str(e)}")
        
        st.sidebar.markdown("---")

        if 'last_update' in stats.columns:
            last_update = stats['last_update'].max()
            if pd.notna(last_update):
                # Parse the timestamp as US Eastern
                eastern = pytz.timezone('US/Eastern')
                last_update = datetime.datetime.strptime(last_update, "%Y-%m-%d %H:%M:%S.%f")
                last_update = eastern.localize(last_update)
                # Convert to UTC
                last_update_utc = last_update.astimezone(pytz.UTC)
                formatted_time = last_update_utc.strftime("%Y-%m-%d %H:%M UTC")
                st.sidebar.markdown(f"Last data update: {formatted_time}")
if __name__ == "__main__":
    main()
