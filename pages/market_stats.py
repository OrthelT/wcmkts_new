import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from db_handler import  clean_mkt_data, get_module_fits, get_local_mkt_engine, get_local_sde_engine, get_stats,safe_format, get_mkt_data, get_market_orders, get_market_history, get_item_details, get_fitting_data, get_update_time
import sqlalchemy_libsql
import time
import threading
import datetime
from db_utils import sync_db
import json
import datetime
import millify
from logging_config import setup_logging



# Insert centralized logging configuration
logger = setup_logging()

# Log application start
logger.info("Application started")

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
            
            # Check if we've already synced today
            if "last_sync" not in st.session_state:
                logger.info("No last sync state found, loading from file")
                with open("last_sync_state.json", "r") as f:
                    last_sync_state = json.load(f)
                    if 'last_sync' in last_sync_state:
                        updated_sync_state = datetime.datetime.strptime(last_sync_state['last_sync'], "%Y-%m-%d %H:%M %Z")
                        logger.info(f"Updated sync state: {updated_sync_state}")
                        st.session_state.last_sync = updated_sync_state
                    else:
                        logger.info("No last sync state found, setting to today")
                        st.session_state.last_sync = now
            else:
                logger.info("Last sync state found, using session state")
            last_sync_time = st.session_state.last_sync
            logger.info(f"Last sync time: {last_sync_time}")
            last_sync_date = last_sync_time.date()
            logger.info(f"Last sync date: {last_sync_date}")
            today = now.date()
            logger.info(f"Today's date: {today}")
            if last_sync_date == today:
                logger.info("Last sync date is today, checking time")
                if last_sync_time.hour >= 13:
                    logger.info("Last sync time is 1300 or later, waiting until tomorrow")
                    # Already synced today, wait until tomorrow
                    target_time += datetime.timedelta(days=1)
                else:
                    logger.info("Last sync time is before 1300, waiting until 1300")
            else:
                logger.info("Last sync date is not today, waiting until tomorrow")
                target_time += datetime.timedelta(days=1)

                    
            # Calculate seconds until the next sync
            seconds_until_sync = (target_time - now).total_seconds()
            logger.info(f"seconds_until_sync: {seconds_until_sync}")
            logger.info(f"Next database sync scheduled at {target_time} UTC ({seconds_until_sync/3600:.2f} hours from now)")
            
            # Sleep until the scheduled time
            time.sleep(seconds_until_sync)
            
            # Perform sync
            try:
                logger.info("Starting scheduled database sync")
                sync_db()
                logger.info("Database sync completed successfully")
                
                # Update session state
                st.session_state.last_sync = datetime.datetime.now(datetime.UTC)
                st.session_state.sync_status = "Success"
            except Exception as e:
                logger.error(f"Database sync failed: {str(e)}")
                st.session_state.sync_status = f"Failed: {str(e)}"
    
    # Start the sync scheduler in a separate thread
    sync_thread = threading.Thread(target=sync_at_scheduled_time, daemon=True)
    sync_thread.start()
    logger.info("Database sync scheduler started")



# Function to get unique categories and item names
def get_filter_options(selected_categories=None):
    try:
        # First get type_ids from market orders
        mkt_query = """
        SELECT DISTINCT type_id 
        FROM marketorders 
        WHERE is_buy_order = 0
        """
        logger.info("getting filter options")
        with Session(get_local_mkt_engine()) as session:
            result = session.execute(text(mkt_query))
            type_ids = [row[0] for row in result.fetchall()]
       
            if not type_ids:
                return [], []
            type_ids_str = ','.join(map(str, type_ids))
        
        logger.info(f"type_ids: {len(type_ids)}")

        # Then get category info from SDE database
        sde_query = f"""
        SELECT DISTINCT it.typeName as type_name, it.typeID as type_id, it.groupID as group_id, ig.groupName as group_name, 
               ic.categoryID as category_id, ic.categoryName as category_name
        FROM invTypes it 
        JOIN invGroups ig ON it.groupID = ig.groupID
        JOIN invCategories ic ON ig.categoryID = ic.categoryID
        WHERE it.typeID IN ({type_ids_str})
        """
        with Session(get_local_sde_engine()) as session:
            result = session.execute(text(sde_query))
            df = pd.DataFrame(result.fetchall(), 
                              columns=['type_name', 'type_id', 'group_id', 'group_name', 'category_id', 'category_name'])

            categories = sorted(df['category_name'].unique())
            
            if selected_categories:
                df = df[df['category_name'].isin(selected_categories)]   
        
        items = sorted(df['type_name'].unique())
      
        
        return categories, items
        

    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return [], []

# Query function
def get_market_data(show_all, selected_categories, selected_items):
    # Start with base condition for buy orders
    mkt_conditions = ["is_buy_order = 0"]

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
                try:
                    result = session.execute(text(sde_query))
                    filtered_type_ids = [str(row[0]) for row in result.fetchall()]
                    session.commit()
                    session.close()
                except Exception as e:
                    logger.error(f"Error executing SDE query: {e}")

            try:
                logger.info(f"filtered_type_ids: {len(filtered_type_ids)}")
                if filtered_type_ids:
                    type_ids_str = ','.join(filtered_type_ids)
                    mkt_conditions.append(f"type_id IN ({type_ids_str})")
                else:
                    return pd.DataFrame()  # Return empty if no matching types
            except Exception as e:
                logger.error(f"Error executing SDE query: {e}")
    
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
    if df.empty:
        return df
    stats = get_stats(stats_query)

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
    logger.info(f"returning market data")

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

def main():

    logger.info("Starting main function")


    # Start database sync scheduler (only once)
    if 'sync_scheduler_started' not in st.session_state:
        schedule_db_sync()
        st.session_state.sync_scheduler_started = True
        logger.info("Sync scheduler started from main function")

    # Initialize sync status in session state if not present
    if 'last_sync' not in st.session_state:
        try:
            with open("last_sync_state.json", "r") as f:
                last_sync_state = json.load(f)
                if 'last_sync' in last_sync_state:
                    updated_sync_state = datetime.datetime.strptime(last_sync_state['last_sync'], "%Y-%m-%d %H:%M UTC")
                    st.session_state.last_sync = updated_sync_state

        except Exception as e:
            logger.error(f"Error loading last sync state: {e}")
        
        st.session_state.last_sync = None
        st.session_state.sync_status = "Not yet run"
    
    logger.info("Sync status initialized")
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

    logger.info(f"Selected category: {selected_category}")
    
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
    
    logger.info(f"Selected item: {selected_item}")
    # Main content
    data, stats = get_market_data(show_all, selected_categories, selected_items)

    if not data.empty:
        if len(selected_items) == 1:
            data = data[data['type_name'] == selected_items[0]]
            stats = stats[stats['type_name'] == selected_items[0]]
            type_id = data['type_id'].iloc[0]
            if type_id: 
                fit_df, timestamp = get_fitting_data(type_id)
            else:
                fit_df = pd.DataFrame()
                timestamp = None
        elif len(selected_categories) == 1:
            stats = stats[stats['category_name'] == selected_categories[0]]
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            min_price = stats['min_price'].min()
            if pd.notna(min_price):
                st.metric("Sell Price (min)", f"{millify.millify(min_price, precision=2)} ISK")
        with col2:
            volume = data['volume_remain'].sum()
            if pd.notna('volume_remain'):
                st.metric("Market Stock", f"{millify.millify(volume, precision=2)}")
        with col3:
            days_remaining = stats['days_remaining'].min()
            if pd.notna(days_remaining):
                st.metric("Days Remaining", f"{days_remaining:.1f}")
        with col4:
            isship = False
            try:

                cat_id = stats['category_id'].iloc[0]
                fits_on_mkt = fit_df['Fits on Market'].min()

                if cat_id == 6:
                    st.metric("Fits on Market", f"{fits_on_mkt:,.0f}")
                    isship = True
                
            except:
                pass
        
        
        st.divider()
        # Format the DataFrame for display with null handling
        display_df = data.copy()
        # Display detailed data

        if len(selected_items) == 1:
            image_id = display_df.iloc[0]['type_id']
            type_name = display_df.iloc[0]['type_name']
            st.subheader(f"{type_name}")
            col1, col2 = st.columns(2)
            with col1:
                if isship:
                    st.image(f'https://images.evetech.net/types/{image_id}/render?size=64')
                else:
                    st.image(f'https://images.evetech.net/types/{image_id}/icon')
            with col2:
                try:
                    if fits_on_mkt:
                        st.subheader("Winter Co. Doctrine", divider="orange")
                        if cat_id in [7,8,18]:
                            st.write(get_module_fits(type_id))
                        else:
                            st.write(fit_df[fit_df['type_id'] == type_id]['group_name'].iloc[0])
                except:
                    pass
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
        
        st.divider()

        st.subheader("Price History")
        history_chart = create_history_chart(data['type_id'].iloc[0])
        if history_chart:
            st.plotly_chart(history_chart, use_container_width=False)
        
            colh1, colh2 = st.columns(2)
            with colh1:
                # Display history data
                st.subheader("History Data")
                history_df = get_market_history(data['type_id'].iloc[0])
                history_df.date = pd.to_datetime(history_df.date).dt.strftime("%Y-%m-%d")
                history_df.average = round(history_df.average.astype(float), 2)
                history_df = history_df.sort_values(by='date', ascending=False)
                history_df.volume = history_df.volume.astype(int)
                st.dataframe(history_df, hide_index=True)

            with colh2:
                avgpr30 = history_df[:30].average.mean()
                avgvol30 = history_df[:30].volume.mean()
                st.subheader(f"{data['type_name'].iloc[0]}",divider=True)
                st.metric("Average Price (30 days)", f"{avgpr30:,.2f} ISK")
                st.metric("Average Volume (30 days)", f"{avgvol30:,.0f}")
        else:
            st.write("History data not available for this item or no item selected")

        st.divider()

        st.subheader("Fitting Data")
        if len(selected_items) == 1:
            if isship:
                st.dataframe(fit_df, hide_index=True)
            else:
                st.write("Fitting data only available for ships")
        else:
            st.write("Fitting data not available for this item or no item selected")

    else:
        st.warning("No data found for the selected filters.")
    

    # Display database sync status in a small info area
    
    with st.sidebar:
        st.sidebar.write(f"Last ESI update: {get_update_time()}")
        st.sidebar.markdown("---")
        st.sidebar.subheader("Database Sync Status")
        status_color = "green" if st.session_state.sync_status == "Success" else "red"
        
        if st.session_state.last_sync:
            last_sync_time = st.session_state.last_sync.strftime("%Y-%m-%d %H:%M UTC")
            st.sidebar.markdown(f"**Last sync:** {last_sync_time}")
        else:
            st.sidebar.markdown("**Last sync:** Not yet run")
            
        sync_status = st.sidebar.markdown(f"**Status:** <span style='color:{status_color}'>{st.session_state.sync_status}</span>", unsafe_allow_html=True)
        
        # Manual sync button
        if st.sidebar.button("Sync Now"):
            try:
                sync_db()
                st.session_state.last_sync = datetime.datetime.now(datetime.UTC)
                st.session_state.sync_status = "Success"
                last_sync_time = st.session_state.last_sync.strftime("%Y-%m-%d %H:%M UTC")
                ls = st.sidebar.markdown(f"**Last sync:** {last_sync_time}")
                st.rerun()
            except Exception as e:
                st.session_state.sync_status = f"Failed: {str(e)}"
                st.sidebar.error(f"Sync failed: {str(e)}")
        if st.session_state.sync_status == "Success":
            st.sidebar.success("Database sync completed successfully!")

    if st.session_state.last_sync:
        last_sync_state = {}
        last_sync_state['last_sync'] = st.session_state.last_sync.strftime("%Y-%m-%d %H:%M UTC")

        with open("last_sync_state.json", "w") as f:
            json.dump(last_sync_state, f)
        
        st.sidebar.markdown("---")


if __name__ == "__main__":
    main()
