import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session
import streamlit as st

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from logging_config import setup_logging
import time
from config import DatabaseConfig
from sync_state import update_wcmkt_state

mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")
build_cost_db = DatabaseConfig("build_cost")

local_mkt_url = mkt_db.url
local_sde_url = sde_db.url
build_cost_url = build_cost_db.url
local_mkt_db = mkt_db.path

logger = setup_logging(__name__)

# Use environment variables for production
mkt_url = mkt_db.turso_url
mkt_auth_token = mkt_db.token

sde_url = sde_db.turso_url
sde_auth_token = sde_db.token


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def execute_query_with_retry(session, query):
    try:
        result = session.execute(text(query))
        return result.fetchall(), result.keys()
    except Exception as e:
        logger.error(f"Query failed, retrying... Error: {str(e)}")
        raise

@st.cache_data(ttl=600)
def get_all_mkt_data()->pd.DataFrame:
    logger.info("-"*40)
    logger.info("getting all market data")
    logger.info("-"*40)
    all_mkt_start = time.perf_counter()
    query = """
    SELECT * FROM marketorders
    """
    with Session(mkt_db.engine) as session:
        result = session.execute(text(query))
        columns = result.keys()
        df = pd.DataFrame(result.fetchall(), columns=columns)

        all_mkt_end = time.perf_counter()
        elapsed_time = round((all_mkt_end - all_mkt_start)*1000, 2)
        logger.info(f"TIME get_all_mkt_data() = {elapsed_time} ms")
        print("-"*100)
        return df

@st.cache_data(ttl=600)
def get_mkt_data(base_query:str)->pd.DataFrame:
    with Session(mkt_db.engine) as session:
        try:
            result, columns = execute_query_with_retry(session, base_query)
            df = pd.DataFrame(result, columns=columns)
            df = df.reset_index(drop=True)
        except Exception as e:
            logger.error(f"Failed to get market data: {str(e)}")
            raise
    return df

def request_type_names(type_ids):
    logger.info("requesting type names with cache")
    # Process in chunks of 1000
    chunk_size = 1000
    all_results = []

    for i in range(0, len(type_ids), chunk_size):
        chunk = type_ids[i:i + chunk_size]
        url = "https://esi.evetech.net/latest/universe/names/?datasource=tranquility"
        headers = {
            "Accept": "application/json",
            "User-Agent": "dfexplorer"
        }
        response = requests.post(url, headers=headers, json=chunk)
        all_results.extend(response.json())

    return all_results

def clean_mkt_data(df):
    # Create a copy first
    df = df.copy()
    df = df.reset_index(drop=True)

    df.rename(columns={'typeID': 'type_id', 'typeName': 'type_name'}, inplace=True)

    new_cols = ['order_id', 'is_buy_order', 'type_id', 'type_name', 'price',
        'volume_remain', 'duration', 'issued']
    df = df[new_cols]

    # Make sure issued is datetime before using dt accessor
    if not pd.api.types.is_datetime64_any_dtype(df['issued']):
        df['issued'] = pd.to_datetime(df['issued'])

    df['expiry'] = df.apply(lambda row: row['issued'] + pd.Timedelta(days=row['duration']), axis=1)
    df['days_remaining'] = (df['expiry'] - pd.Timestamp.now()).dt.days
    df['days_remaining'] = df['days_remaining'].apply(lambda x: x if x > 0 else 0)
    df['days_remaining'] = df['days_remaining'].astype(int)

    # Format dates after calculations are done
    df['issued'] = df['issued'].dt.date
    df['expiry'] = df['expiry'].dt.date

    return df

def get_fitting_data(type_id):
    logger.info("getting fitting data with cache")
    with Session(mkt_db.engine) as session:
        query = """
            SELECT * FROM doctrines
            """

        try:
            fit = session.execute(text(query))
            fit = fit.fetchall()
            df = pd.DataFrame(fit)
        except Exception as e:
            print(f"Failed to get data for {fit_id}: {str(e)}")
            raise
        session.close()

        df2 = df.copy()
        df2 = df2[df2['type_id'] == type_id]
        df2.reset_index(drop=True, inplace=True)
        try:
            fit_id = df2.iloc[0]['fit_id']
        except:
            return None, None

        df3 = df.copy()
        df3 = df3[df3['fit_id'] == fit_id]
        df3.reset_index(drop=True, inplace=True)

        cols = ['fit_id', 'ship_id', 'ship_name', 'hulls', 'type_id', 'type_name',
       'fit_qty', 'fits_on_mkt', 'total_stock', '4H_price', 'avg_vol', 'days',
       'group_id', 'group_name', 'category_id', 'category_name', 'timestamp',
       'id']
        timestamp = df3.iloc[0]['timestamp']
        df3.drop(columns=['ship_id', 'hulls', 'group_id', 'category_name', 'id', 'timestamp'], inplace=True)


        numeric_formats = {

            'total_stock': '{:,.0f}',
            '4H_price': '{:,.2f}',
            'avg_vol': '{:,.0f}',
            'days': '{:,.0f}',
        }

        for col, format_str in numeric_formats.items():
            if col in df3.columns:  # Only format if column exists
                df3[col] = df3[col].apply(lambda x: safe_format(x, format_str))
        df3.rename(columns={'fits_on_mkt': 'Fits on Market'}, inplace=True)
        df3 = df3.sort_values(by='Fits on Market', ascending=True)
        df3.reset_index(drop=True, inplace=True)
    return df3

@st.cache_resource(ttl=600)
def get_stats(stats_query=None):
    if stats_query is None:
        stats_query = """
            SELECT * FROM marketstats
        """
    engine = mkt_db.engine
    with engine.connect() as conn:
        stats = pd.read_sql_query(stats_query, conn)
    return stats

def query_local_mkt_db(query: str) -> pd.DataFrame:
    engine = mkt_db.engine
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df

# Helper function to safely format numbers
def safe_format(value, format_string):
    try:
        if pd.isna(value) or value is None:
            return ''
        return format_string.format(float(value))
    except (ValueError, TypeError):
        return ''

@st.cache_data(ttl=600)
def get_market_history(type_id):
    query = f"""
        SELECT date, average, volume
        FROM market_history
        WHERE type_id = {type_id}
        ORDER BY date
    """
    return pd.read_sql_query(query, (mkt_db.engine))

def get_update_time()->str:
    if "local_update_status" in st.session_state:
        update_time = st.session_state.local_update_status["updated"]
        update_time = update_time.strftime("%Y-%m-%d | %H:%M UTC")
    else:
        update_time = None
    return update_time

def get_time_since_esi_update()->str:
    if "local_update_status" in st.session_state:
        time_since = st.session_state.local_update_status["time_since"]
        time_since = time_since.total_seconds()
        time_since = f"{round((time_since / 3600),1)} hours"
    else:
        time_since = None
    return time_since

def get_module_fits(type_id):

    with Session(mkt_db.engine) as session:
        query = """
            SELECT * FROM doctrines WHERE type_id = :type_id
            """
        try:
            fit = session.execute(text(query), {'type_id': type_id})
            fit = fit.fetchall()
            df = pd.DataFrame(fit)
        except Exception as e:
            print(f"Failed to get data for {type_id}: {str(e)}")
            raise
        session.close()

        df2 = df.copy()
        try:
            ships = df2['ship_name'].tolist()
            fit_qty = df2['fit_qty'].tolist()
            ships = [f"{ship} ({qty})" for ship, qty in zip(ships, fit_qty)]
            ships = ', '.join(ships)
            return ships
        except:
            return None

def get_group_fits(group_id):
    with Session(mkt_db.engine) as session:
        query = f"""
            SELECT * FROM doctrines WHERE group_id = {group_id}
            """
        return pd.read_sql_query(query, (mkt_db.engine))

def get_groups_for_category(category_id: int)->pd.DataFrame:
    if category_id == 17:
        df = pd.read_csv("build_commodity_groups.csv")
        return df
    else:
        query = f"""
            SELECT DISTINCT groupID, groupName FROM invGroups WHERE categoryID = {category_id}
        """
    df = pd.read_sql_query(query, (sde_db.engine))
    return df

def get_types_for_group(group_id: int)->pd.DataFrame:
    df = pd.read_csv("industry_types.csv")
    df = df[df['groupID'] == group_id]
    df = df.drop_duplicates(subset=['typeID'])
    df2 = df.copy()
    df2 = df2.sort_values(by='typeName')
    if group_id == 332:
        df2 = df2[df2['typeName'].str.contains("R.A.M.") | df2['typeName'].str.contains("R.Db")]
    df2 = df2[['typeID', 'typeName']]
    df2.reset_index(drop=True, inplace=True)
    df = df2
    return df

def get_group_id_for_type(type_id: int)->int:
    df = pd.read_csv("industry_types.csv")
    df = df[df['typeID'] == type_id]
    group_id = df.iloc[0]['groupID']
    query = f"""
        SELECT groupID FROM invTypes WHERE typeID = {type_id}
        """
    return group_id

def get_type_id(type_name: str)->int:
    query = f"""
        SELECT typeID FROM invTypes WHERE typeName = '{type_name}'
        """
    return pd.read_sql_query(query, (sde_db.engine))

def get_system_id(system_name: str)->int:
    query = f"""
        SELECT solarSystemID FROM mapSolarSystems WHERE solarSystemName = '{system_name}'
        """
    return pd.read_sql_query(query, (sde_db.engine))

def get_4H_price(type_id):
    query = f"""
        SELECT * FROM marketstats WHERE type_id = {type_id}
        """
    df = pd.read_sql_query(query, (mkt_db.engine))
    try:
        return df.price.iloc[0]
    except:
        return None

@st.cache_data(ttl=600)
def new_get_market_data(show_all):
    df = get_all_mkt_data()

    if 'selected_category_info' in st.session_state:
        orders_df = df[df['type_id'].isin(st.session_state.selected_category_info['type_ids'])]
    elif 'selected_item' in st.session_state:
        orders_df = df[df['type_id'].isin(st.session_state.selected_items_type_ids)]
    elif show_all:
        orders_df = df

    stats_df = get_stats()
    stats_df = stats_df[stats_df['type_id'].isin(orders_df['type_id'].unique())]



    return orders_df

@st.cache_data(ttl=600)
def get_market_data(show_all, selected_category, selected_item):
    # Get filtered_type_ids based on selected categories and items
    filtered_type_ids = None

    if not show_all:
        # Get type_ids for the selected categories from SDE first
        sde_conditions = []
        if selected_category:
            logger.info(f"selected_categories: {selected_category}")
            categories_str = ', '.join(f"'{cat}'" for cat in selected_category)
            sde_conditions.append(f"ic.categoryName IN ({categories_str})")

        if selected_item:
            logger.info(f"selected_items: {selected_item}")
            items_str = ', '.join(f'"{item}"' for item in selected_item)
            sde_conditions.append(f"it.typeName IN ({items_str})")

        if sde_conditions:
            logger.info(f"sde_conditions: {sde_conditions}")
            sde_where = " AND ".join(sde_conditions)
            sde_query = f"""
                SELECT DISTINCT it.typeID
                FROM invTypes it
                JOIN invGroups ig ON it.groupID = ig.groupID
                JOIN invCategories ic ON ig.categoryID = ic.categoryID
                WHERE {sde_where}
            """

    # Get sell orders
    sell_conditions = ["is_buy_order = 0"]
    if filtered_type_ids:
        logger.info(f"filtered_type_ids: {filtered_type_ids}")
        type_ids_str = ','.join(filtered_type_ids)
        sell_conditions.append(f"type_id IN ({type_ids_str})")

    # Build market query for sell orders
    sell_where_clause = " AND ".join(sell_conditions)
    sell_query = f"""
        SELECT mo.*
        FROM marketorders mo
        WHERE {sell_where_clause}
        ORDER BY type_id
    """

    # Get buy orders
    buy_conditions = ["is_buy_order = 1"]
    if filtered_type_ids:
        type_ids_str = ','.join(filtered_type_ids)
        buy_conditions.append(f"type_id IN ({type_ids_str})")

    # Build market query for buy orders
    buy_where_clause = " AND ".join(buy_conditions)
    buy_query = f"""
        SELECT mo.*
        FROM marketorders mo
        WHERE {buy_where_clause}
        ORDER BY type_id
    """

    stats_query = """
        SELECT * FROM marketstats
    """

    # Get market data
    t1 = time.perf_counter()
    mkt_df = get_all_mkt_data()
    sell_df = mkt_df[mkt_df['is_buy_order'] == 0]
    buy_df = mkt_df[mkt_df['is_buy_order'] == 1]
    t2 = time.perf_counter()

    elapsed_time = round((t2-t1)*1000, 2)
    logger.info(f"TIME get_mkt_data() mkt_df and filter for sell_df and buy_df = {elapsed_time} ms")
    print("-"*100)

    sell_df = get_mkt_data(sell_query)
    buy_df = get_mkt_data(buy_query)


    if sell_df.empty and buy_df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()  # Return empty DataFrames

    stats = get_stats(stats_query)


    # Get all unique type_ids from both dataframes
    all_type_ids = set()
    if not sell_df.empty:
        all_type_ids.update(sell_df['type_id'].unique())
    if not buy_df.empty:
        all_type_ids.update(buy_df['type_id'].unique())

    # Get SDE data for all type_ids in the result
    type_ids_str = ','.join(map(str, all_type_ids))
    sde_query = f"""
        SELECT it.typeID as type_id, ig.groupName as group_name, ic.categoryName as category_name
        FROM invTypes it
        JOIN invGroups ig ON it.groupID = ig.groupID
        JOIN invCategories ic ON ig.categoryID = ic.categoryID
        WHERE it.typeID IN ({type_ids_str})
    """

    with Session(sde_db.engine) as session:
        logger.info("executing SDE query")
        result = session.execute(text(sde_query))
        sde_df = pd.DataFrame(result.fetchall(), columns=['type_id', 'group_name', 'category_name'])
        session.close()

    # Merge market data with SDE data for sell orders
    if not sell_df.empty:
        sell_df = sell_df.merge(sde_df, on='type_id', how='left')
        sell_df = sell_df.reset_index(drop=True)
        # Clean up the DataFrame
        sell_df = clean_mkt_data(sell_df)

    # Merge market data with SDE data for buy orders
    if not buy_df.empty:
        buy_df = buy_df.merge(sde_df, on='type_id', how='left')
        buy_df = buy_df.reset_index(drop=True)
        # Clean up the DataFrame
        buy_df = clean_mkt_data(buy_df)

    logger.info("returning market data")

    return sell_df, buy_df, stats

def check_if_db_not_in_session_state(remote: bool = False):
    if remote:
        if "remote_update_status" not in st.session_state:
            logger.info("Remote database is not in session state")
            return True
        else:
            return False
    else:
        if "local_update_status" not in st.session_state:
            logger.info("Local database is not in session state")
            return True
        else:
            return False

def check_db_state():
    start_time = time.perf_counter()
    """
    Check the update state of the databases. If the remote database is more recent than the local database, sync the local database.
    Args:
        table_names: list[str] | str - The tables to check the updates for

    """
    db = DatabaseConfig("wcmkt")
    update_wcmkt_state()

    try:
        local_update_time = st.session_state.local_update_status['updated']
        remote_update_time = st.session_state.remote_update_status['updated']
    except:
        raise ValueError("Local or remote database is None")

    if remote_update_time > local_update_time:
        logger.info("Remote database has been updated since last check, syncing local database⏰🛜⚠️")
        db.sync()

        if db.validate_sync():
            logger.info("Local database synced and validated✅🏠")
            update_wcmkt_state()
        else:
            logger.info("Local database synced but validation failed❌🏠")
    else:
        logger.info("Local database is up to date✅🏠")

    logger.info("-"*100)
    end_time = time.perf_counter()
    elapsed_time = round((end_time-start_time)*1000, 2)
    logger.info(f"TIME check_db_state() = {elapsed_time} ms")
    logger.info("-"*100)

if __name__ == "__main__":
    pass