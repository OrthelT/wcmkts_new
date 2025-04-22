import pandas as pd
import datetime
from sqlalchemy import create_engine
import streamlit as st
import os
from dotenv import load_dotenv
import libsql_experimental as libsql
from logging_config import setup_logging
import json

logger = setup_logging()

# Database URLs
local_mkt_url = "sqlite:///wcmkt.db"  # Changed to standard SQLite format for local dev
local_sde_url = "sqlite:///sde.db"    # Changed to standard SQLite format for local dev

# Load environment variables


# Use environment variables for production
mkt_url = st.secrets["TURSO_DATABASE_URL"]
mkt_auth_token = st.secrets["TURSO_AUTH_TOKEN"]

sde_url = st.secrets["SDE_URL"]
sde_auth_token = st.secrets["SDE_AUTH_TOKEN"]

def sync_db(db_url="wcmkt.db", sync_url=mkt_url, auth_token=mkt_auth_token)->tuple[datetime.datetime, datetime.datetime]:
    logger.info("database sync started")
    # Skip sync in development mode or when sync_url/auth_token are not provided
    if not sync_url or not auth_token:
        logger.info("Skipping database sync in development mode or missing sync credentials")
        return None, None
        
    try:
        conn = libsql.connect(db_url, sync_url=sync_url, auth_token=auth_token)
        conn.sync()
        logger.info("Database synced")

        last_sync = datetime.datetime.now().astimezone(datetime.UTC)
        logger.info(f"updated Last sync: {last_sync.strftime('%Y-%m-%d %H:%M %Z')}")
        next_sync = last_sync.replace(hour=13, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        logger.info(f"updated Next sync: {next_sync.strftime('%Y-%m-%d %H:%M %Z')}")

        with open("last_sync_state.json", "w") as f:
            json.dump({"last_sync": last_sync.strftime("%Y-%m-%d %H:%M %Z"), "next_sync": next_sync.strftime("%Y-%m-%d %H:%M %Z")}, f)
        logger.info(f"Last sync state updated to: {last_sync.strftime('%Y-%m-%d %H:%M %Z')}")
        logger.info(f"Next sync state updated to: {next_sync.strftime('%Y-%m-%d %H:%M %Z')}")
        
        return last_sync, next_sync

    except ValueError as e:
        if "Sync is not supported" in str(e):
            logger.info("Skipping sync: This appears to be a local file database that doesn't support sync")
        else:
            # Re-raise other ValueErrors
            raise
    return None, None

def get_type_name(type_ids):
    engine = create_engine(local_sde_url)
    with engine.connect() as conn:
        df = pd.read_sql_query(f"SELECT * FROM invtypes WHERE typeID IN ({','.join(map(str, type_ids))})", conn)
    df = df[['typeID', 'typeName']]
    df.rename(columns={'typeID': 'type_id', 'typeName': 'type_name'}, inplace=True)
    return df

def get_receent_items():
    two_days_ago = datetime.datetime.now() - datetime.timedelta(days=2)
    engine = create_engine(local_mkt_url)
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM marketorders", conn)
    df['issued'] = pd.to_datetime(df['issued'])
    df = df[df['issued'] >= two_days_ago]
    df2 = get_type_name(df['type_id'].unique().tolist())
    df3 = pd.merge(df, df2, on='type_id', how='left')
    df4 = df3[['order_id', 'is_buy_order', 'type_id', 'type_name', 'price',
       'volume_remain', 'duration', 'issued']]
    return df4

def update_targets(fit_id, target_value):
    conn = libsql.connect("wcmkt.db", sync_url=mkt_url, auth_token=mkt_auth_token)
    cursor = conn.cursor()
    cursor.execute(f"""UPDATE ship_targets
    SET ship_target = {target_value}
    WHERE fit_id = {fit_id};""")
    conn.commit()
    logger.info(f"Updated target for fit_id {fit_id} to {target_value}")
    
if __name__ == "__main__":
    pass
