import pandas as pd
from sqlalchemy import create_engine, text, distinct, select
from sqlalchemy.orm import Session
import streamlit as st
import os
from dotenv import load_dotenv
import requests
from tenacity import retry, stop_after_attempt, wait_exponential
import sqlalchemy_libsql
import libsql_experimental as libsql
import logging
import pytz
import datetime

logging = logging.getLogger(__name__)

# Database URLs
local_mkt_url = "sqlite:///wcmkt.db"  # Changed to standard SQLite format for local dev
local_sde_url = "sqlite:///sde.db"    # Changed to standard SQLite format for local dev

# Load environment variables
load_dotenv()

# Use environment variables for production
mkt_url = os.getenv('TURSO_DATABASE_URL')
mkt_auth_token = os.getenv("TURSO_AUTH_TOKEN")

sde_url = os.getenv('SDE_URL')
sde_auth_token = os.getenv("SDE_AUTH_TOKEN")


mkt_query = """
    SELECT * FROM marketorders 
    WHERE is_buy_order = 1 
    ORDER BY order_id
"""

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def execute_query_with_retry(session, query):
    try:
        result = session.execute(text(query))
        return result.fetchall(), result.keys()
    except Exception as e:
        print(f"Query failed, retrying... Error: {str(e)}")
        raise

def get_mkt_data(base_query, batch_size=5000):
    mkt_data = []
    offset = 0
    columns = None
    
    with Session(get_local_mkt_engine()) as session:
        while True:
            query = f"{base_query} LIMIT {batch_size} OFFSET {offset}"
            try:
                chunk, keys = execute_query_with_retry(session, query)
                if not columns:
                    columns = keys
                
                if not chunk:
                    break
                    
                mkt_data.extend(chunk)
                print(f"Processed {len(mkt_data)} rows...")
                offset += batch_size
            except Exception as e:
                print(f"Failed to get chunk at offset {offset}: {str(e)}")
                if not mkt_data:
                    raise
                return pd.DataFrame(mkt_data, columns=columns)

    return pd.DataFrame(mkt_data, columns=columns)

def request_type_names(type_ids):
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

def insert_type_names(df):
    type_names = request_type_names(df.type_id.unique().tolist())
    df_names = pd.DataFrame(type_names)
    df_names = df_names.drop(columns=['category'])
    df_names = df_names.rename(columns={'id': 'type_id', 'name': 'type_name'})
    df_names.set_index('type_id')
    df = df.merge(df_names, on='type_id', how='left')
    return df

def clean_mkt_data(df):
    # Create a copy first
    df = df.copy()
    
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

    with Session(get_local_mkt_engine()) as session:
        query = f"""
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
    return df3, timestamp


def fetch_mkt_orders():
    df = get_mkt_data(mkt_query)
    df = insert_type_names(df)
    df = clean_mkt_data(df)
    return df

def get_local_mkt_engine():
    return create_engine(local_mkt_url, echo=False)  # Set echo=False to reduce console output

def get_local_mkt_db(query: str) -> pd.DataFrame:
    engine = create_engine(local_mkt_url, echo=False)
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df

def get_local_sde_engine():
    return create_engine(local_sde_url, echo=False)

def get_local_sde_db(query: str) -> pd.DataFrame:
    engine = create_engine(local_sde_url, echo=False)
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df

def get_stats(stats_query):
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        stats = pd.read_sql_query(stats_query, conn)
    return stats


# Helper function to safely format numbers
def safe_format(value, format_string):
    try:
        if pd.isna(value) or value is None:
            return ''
        return format_string.format(float(value))
    except (ValueError, TypeError):
        return ''

def get_market_orders(type_ids=None):
    query = """
        SELECT mo.*, ms.min_price, ms.days_remaining
        FROM marketorders mo
        LEFT JOIN marketstats ms ON mo.type_id = ms.type_id
        WHERE mo.is_buy_order = 0
    """
    if type_ids:
        type_ids_str = ','.join(map(str, type_ids))
        query += f" AND mo.type_id IN ({type_ids_str})"
    
    return pd.read_sql_query(query, (get_local_mkt_engine()))

def get_market_history(type_id):
    query = f"""
        SELECT date, average, volume
        FROM market_history
        WHERE type_id = {type_id}
        ORDER BY date
    """
    return pd.read_sql_query(query, (get_local_mkt_engine()))

def get_item_details(type_ids):
    type_ids_str = ','.join(map(str, type_ids))
    query = f"""
        SELECT it.typeID as type_id, it.typeName as type_name, 
               ig.groupName as group_name, ic.categoryName as category_name
        FROM invTypes it 
        JOIN invGroups ig ON it.groupID = ig.groupID
        JOIN invCategories ic ON ig.categoryID = ic.categoryID
        WHERE it.typeID IN ({type_ids_str})
    """
    return pd.read_sql_query(query, (get_local_sde_engine()))

def get_update_time():
    query = """
        SELECT last_update FROM marketstats LIMIT 1
    """
    df = get_local_mkt_db(query)
    data_update = df.iloc[0]['last_update']
    data_update = pd.to_datetime(data_update)
    eastern = pytz.timezone('US/Eastern')
    data_update = eastern.localize(data_update)
    data_update = data_update.astimezone(pytz.utc)
    data_update = data_update.strftime('%Y-%m-%d \n %H:%M:%S')
    return data_update

def get_module_fits(type_id):
    
    with Session(get_local_mkt_engine()) as session:
        query = f"""
            SELECT * FROM doctrines WHERE type_id = {type_id}
            """
        try:
            fit = session.execute(text(query))
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
    with Session(get_local_mkt_engine()) as session:
        query = f"""
            SELECT * FROM doctrines WHERE group_id = {group_id}
            """
        return pd.read_sql_query(query, (get_local_mkt_engine()))

if __name__ == "__main__":
    pass