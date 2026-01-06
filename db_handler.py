from httpx import get
import pandas as pd
from sqlalchemy import text, bindparam
import streamlit as st

import requests
from typing import Any, Mapping
from logging_config import setup_logging
import time
from config import DatabaseConfig

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


def read_df(
    db: DatabaseConfig,
    query: Any,
    params: Mapping[str, Any] | None = None,
    *,
    local: bool = True,
    fallback_remote_on_malformed: bool = True,
) -> pd.DataFrame:
    """Execute a read-only SQL query and return a DataFrame.

    - Uses `db.local_access()` + `db.engine.connect()` for local reads.
    - Optionally falls back to remote on malformed/corrupt local DB.
    - Accepts raw SQL strings or SQLAlchemy TextClause; params are optional.
    """

    def _run_local() -> pd.DataFrame:
        engine = db.engine
        with engine.connect() as conn:
            sql = query
            return pd.read_sql_query(sql, conn, params=params)

    def _run_remote() -> pd.DataFrame:
        engine = db.remote_engine
        with engine.connect() as conn:
            sql = query
            return pd.read_sql_query(sql, conn, params=params)

    if not local:
        return _run_remote()

    try:
        return _run_local()

    except Exception as e:
        msg = str(e).lower()
        if fallback_remote_on_malformed and (
            "malform" in msg 
            or "database disk image is malformed" in msg
            or "no such table" in msg
        ):
            logger.error(f"Local DB error ('{msg}'); syncing and retrying, with remote fallback…")
            try:
                db.sync()
                return _run_local()
            except Exception:
                logger.error("Failed to sync local DB; falling back to remote read.")
                return _run_remote()
        raise

def new_read_df(db: DatabaseConfig, query: Any, params: Mapping[str, Any] | None = None) -> pd.DataFrame:
    """Execute a read-only SQL query and return a DataFrame."""
    def _read_all():
        with db.local_access():
            with db.engine.connect() as conn:
                return pd.read_sql_query(query, conn, params=params)

    try:
        return _read_all()
    except Exception as e:
        logger.error(f"Failed to read data: {str(e)}")
        try:
            db.sync()
            return _read_all()
        except Exception as e2:
            logger.error(f"Failed to read data after sync: {str(e2)}")
            raise

@st.cache_data(ttl=600)
def get_all_mkt_stats()->pd.DataFrame:
    logger.info("-"*40)
    all_mkt_start = time.perf_counter()
    query = """
    SELECT * FROM marketstats
    """
    def _read_all():
        with mkt_db.local_access():
            with mkt_db.engine.connect() as conn:
                return pd.read_sql_query(query, conn)
    try:
        df = _read_all()
    except Exception as e:
        logger.error(f"Failed to get market stats: {str(e)}")
        try:
            mkt_db.sync()
            df = _read_all()
        except Exception as e2:
            logger.error(f"Failed to get market stats after sync: {str(e2)}")
            raise
    all_mkt_end = time.perf_counter()
    elapsed_time = round((all_mkt_end - all_mkt_start)*1000, 2)
    logger.info(f"TIME get_all_mkt_stats() = {elapsed_time} ms")
    logger.info("-"*40)
    df = df.reset_index(drop=True)
    return df

@st.cache_data(ttl=600)
def get_all_mkt_orders()->pd.DataFrame:
    logger.info("-"*40)
    all_mkt_start = time.perf_counter()
    query = """
    SELECT * FROM marketorders
    """
    # Proactive integrity check before reading
    try:
        if not mkt_db.integrity_check():

            logger.warning("Local DB integrity check failed; attempting resync before read…")
            mkt_db.sync()
    except Exception as e:
        logger.error(f"Pre-read sync attempt failed: {e}")

    def _read_all():
        with mkt_db.local_access():
            with mkt_db.engine.connect() as conn:
                return pd.read_sql_query(query, conn)

    try:
        df = _read_all()
    except Exception as e:
        # Handle on-the-fly corruption by resyncing and retrying once
        msg = str(e).lower()
        if "malform" in msg or "database disk image is malformed" in msg or "no such table" in msg:
            logger.error(f"Detected DB error ('{msg}') during read; resyncing and retrying once…")
            try:
                mkt_db.sync()
                df = _read_all()
            except Exception as e2:
                msg2 = str(e2).lower()
                logger.error(f"Retry after sync failed: {msg2}. Falling back to remote read.")
                # Final fallback: read directly from remote so UI stays up
                with mkt_db.remote_engine.connect() as conn:
                    df = pd.read_sql_query(query, conn)
        else:
            raise

    all_mkt_end = time.perf_counter()
    elapsed_time = round((all_mkt_end - all_mkt_start)*1000, 2)
    logger.info(f"TIME get_all_mkt_orders() = {elapsed_time} ms")
    logger.info("-"*40)
    df = df.reset_index(drop=True)
    return df

def get_price_from_mkt_orders(type_id):
    df = get_all_mkt_orders()
    df = df[df['type_id'] == type_id]
    df = df.reset_index(drop=True)
    return df['price'].iloc[0]

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

    df = df.reset_index(drop=True)

    return df

@st.cache_data(ttl=600)
def get_stats(stats_query=None):
    if stats_query is None:
        stats_query = """
            SELECT * FROM marketstats
        """
    engine = mkt_db.engine
    try:
        with mkt_db.local_access():
            with engine.connect() as conn:
                stats = pd.read_sql_query(stats_query, conn)
    except Exception as e:
        msg = str(e).lower()
        if "malform" in msg or "database disk image is malformed" in msg or "no such table" in msg:
            logger.error(f"DB error ('{msg}') during stats read; syncing and falling back to remote if needed…")
            try:
                mkt_db.sync()
                with mkt_db.engine.connect() as conn:
                    stats = pd.read_sql_query(stats_query, conn)
            except Exception:
                with mkt_db.remote_engine.connect() as conn:
                    stats = pd.read_sql_query(stats_query, conn)
        else:
            raise
    return stats

def query_local_mkt_db(query: str) -> pd.DataFrame:
    engine = mkt_db.engine
    with mkt_db.local_access():
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
def get_market_history(type_id: int)->pd.DataFrame:
    query = """
        SELECT date, average, volume
        FROM market_history
        WHERE type_id = :type_id
        ORDER BY date DESC
    """
    with mkt_db.local_access():
        with mkt_db.engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params={"type_id": type_id})

@st.cache_data(ttl=3600)
def get_all_market_history()->pd.DataFrame:
    query = """
        SELECT * FROM market_history
    """
    def _read_all():
        with mkt_db.local_access():
            with mkt_db.engine.connect() as conn:
                return pd.read_sql_query(query, conn)
    try:
        df = _read_all()
    except Exception as e:
        logger.error(f"Failed to get market history: {str(e)}")
        try:
            mkt_db.sync()
            df = _read_all()
        except Exception as e2:
            logger.error(f"Failed to get market history after sync: {e2}. Falling back to remote.")
            with mkt_db.remote_engine.connect() as conn:
                df = pd.read_sql_query(query, conn)
            # If remote also fails, we let it raise
    df = df.reset_index(drop=True)
    return df

def get_update_time()->str:
    """Return last local update time as formatted string, handling stale/bool state."""
    if "local_update_status" in st.session_state:
        status = st.session_state.local_update_status
        if isinstance(status, dict) and status.get("updated"):
            try:
                return status["updated"].strftime("%Y-%m-%d | %H:%M UTC")
            except Exception as e:
                logger.error(f"Failed to format local_update_status.updated: {e}")
    return None

def get_groups_for_category(category_id: int)->pd.DataFrame:
    sde2_db = DatabaseConfig("sde")
    if category_id == 17:
        df = pd.read_csv("build_commodity_groups.csv")
        return df
    elif category_id == 4:
        query = """
            SELECT DISTINCT groupID, groupName FROM invGroups WHERE categoryID = :category_id AND groupID = 1136
        """
    else:
        query = """
            SELECT DISTINCT groupID, groupName FROM invGroups WHERE categoryID = :category_id
        """
    with sde2_db.engine.connect() as conn:
        df = pd.read_sql_query(text(query), conn, params={"category_id": category_id})
    return df

def get_types_for_group(group_id: int)->pd.DataFrame:
    sde2_db = DatabaseConfig("sde")
    query = """
        SELECT DISTINCT t.typeID, t.typeName 
        FROM invTypes t
        JOIN industryActivityProducts iap ON t.typeID = iap.productTypeID
        WHERE t.groupID = :group_id 
        AND iap.activityID = 1
        ORDER BY t.typeName
    """
    
    def _run_local():
        with sde2_db.engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params={"group_id": group_id})
            
    def _run_remote():
        with sde2_db.remote_engine.connect() as conn:
            return pd.read_sql_query(text(query), conn, params={"group_id": group_id})

    try:
        df = _run_local()
    except Exception as e:
        msg = str(e).lower()
        logger.error(f"Error fetching types for group {group_id}: {e}")
        if "no such table" in msg or "malform" in msg:
            logger.warn(f"Attempting sync/fallback for SDE group fetch due to error: {msg}")
            # Use remote ONLY to avoid infinite sync loops on persistent local errors
            try:
                logger.info("Skipping sync and falling back directly to remote SDE read to prevent loops")
                df = _run_remote()
            except Exception as e_remote:
                logger.error(f"Remote fallback also failed: {e_remote}")
                return pd.DataFrame(columns=['typeID', 'typeName'])
        else:
            logger.error(f"sde2_db: {sde2_db.path}")
            return pd.DataFrame(columns=['typeID', 'typeName'])

    if group_id == 332 and not df.empty:
        df = df[df['typeName'].str.contains("R.A.M.") | df['typeName'].str.contains("R.Db")]
        df = df.reset_index(drop=True)

    return df

def get_4H_price(type_id):
    query = """
        SELECT * FROM marketstats WHERE type_id = :type_id
        """
    with mkt_db.local_access():
        with mkt_db.engine.connect() as conn:
            df = pd.read_sql_query(text(query), conn, params={"type_id": type_id})
    try:
        return df.price.iloc[0]
    except Exception:
        return None

def new_get_market_data(show_all):
    df = get_all_mkt_orders()

    if 'selected_category_info' in st.session_state and st.session_state.selected_category_info is not None:
        orders_df = df[df['type_id'].isin(st.session_state.selected_category_info['type_ids'])]
    if 'selected_item_id' in st.session_state and st.session_state.selected_item_id is not None:
        logger.debug(f"selected_item_id: {st.session_state.selected_item_id}")
        orders_df = df[df['type_id'] == st.session_state.selected_item_id]
    else:
        orders_df = df

    stats_df = get_stats()
    if not stats_df.empty:
        stats_df = stats_df[stats_df['type_id'].isin(orders_df['type_id'].unique())]
        stats_df = stats_df.reset_index(drop=True)
    else:
        stats_df = pd.DataFrame()

    sell_orders_df = orders_df[orders_df['is_buy_order'] == 0]
    sell_orders_df = sell_orders_df.reset_index(drop=True)

    buy_orders_df = orders_df[orders_df['is_buy_order'] == 1]
    buy_orders_df = buy_orders_df.reset_index(drop=True)
    if not sell_orders_df.empty:
        sell_orders_df = clean_mkt_data(sell_orders_df)
    if not buy_orders_df.empty:
        buy_orders_df = clean_mkt_data(buy_orders_df)

    return sell_orders_df, buy_orders_df, stats_df

def get_chart_table_data()->pd.DataFrame:
    df = get_all_market_history()
    df = df.sort_values(by='date', ascending=False)
    df = df.reset_index(drop=True)
    return df

def extract_sde_info(sde_table: str, table_name: str = None, params: dict = None, query: str = None,local: bool = True, fallback_remote: bool = True)->pd.DataFrame:
    db = DatabaseConfig("sde")
    
    if table_name is None and params and "table_name" in params:
        table_name = params["table_name"]
        
    if query is None:
        if not table_name:
            raise ValueError("Table name is required")
        query = f"SELECT * FROM {table_name}"
        
    # Remove table_name from params if it exists, as we've handled it via string injection
    # and table names cannot be bound as parameters
    run_params = params.copy() if params else {}
    if "table_name" in run_params:
        del run_params["table_name"]
    
    # If params is empty dict, pass None to avoid driver issues with empty dict vs tuple
    if not run_params:
        run_params = None
        
    df = new_read_df(db, query, params=run_params)
    df = df.reset_index(drop=True)
    return df