import pandas as pd
import datetime
from sqlalchemy import create_engine
import streamlit as st
import libsql_experimental as libsql
from logging_config import setup_logging
import json
import time
from sync_scheduler import schedule_next_sync
import requests

logger = setup_logging(__name__)

# Database URLs
local_mkt_url = "sqlite:///wcmkt.db"  # Changed to standard SQLite format for local dev
local_sde_url = "sqlite:///sde.db"    # Changed to standard SQLite format for local dev
build_cost_url = "sqlite:///build_cost.db"


# Use environment variables for production
mkt_url = st.secrets["TURSO_DATABASE_URL"]
mkt_auth_token = st.secrets["TURSO_AUTH_TOKEN"]

sde_url = st.secrets["SDE_URL"]
sde_auth_token = st.secrets["SDE_AUTH_TOKEN"]

def sync_db(db_url="wcmkt.db", sync_url=mkt_url, auth_token=mkt_auth_token):
    logger.info("database sync started")

    # Clear cache of all data before syncing
    st.cache_data.clear()
    st.cache_resource.clear()
    logger.info("cache cleared")
    
    sleep_time = 0.5
    time.sleep(sleep_time)
    logger.info(f"cache cleared for sync; sleeping {sleep_time} seconds")
    # Give connections time to fully close
    # Skip sync in development mode or when sync_url/auth_token are not provided
    if not sync_url or not auth_token:
        logger.info("Skipping database sync in development mode or missing sync credentials")
        
        
    try:
        sync_start = time.time()
        conn = libsql.connect(db_url, sync_url=sync_url, auth_token=auth_token)
        logger.info("\n")
        logger.info(f"="*80)
        logger.info(f"Database sync started at {sync_start}")
        conn.sync()
        logger.info(f"Database synced in {1000*(time.time() - sync_start)} milliseconds")

        last_sync = datetime.datetime.now().astimezone(datetime.UTC)
        logger.info(f"updated Last sync: {last_sync.strftime('%Y-%m-%d %H:%M %Z')}")
        
        # Use schedule_next_sync to determine the next sync time
        next_sync = schedule_next_sync(last_sync)
        logger.info(f"updated Next sync: {next_sync.strftime('%Y-%m-%d %H:%M %Z')}")

        # Save sync state with sync_times preserved
        with open("last_sync_state.json", "r") as f:
            current_state = json.load(f)
        
        current_state.update({
            "last_sync": last_sync.strftime("%Y-%m-%d %H:%M %Z"),
            "next_sync": next_sync.strftime("%Y-%m-%d %H:%M %Z")
        })
        
        with open("last_sync_state.json", "w") as f:
            json.dump(current_state, f)
            
        logger.info(f"Last sync state updated to: {last_sync.strftime('%Y-%m-%d %H:%M %Z')}")
        logger.info(f"Next sync state updated to: {next_sync.strftime('%Y-%m-%d %H:%M %Z')}")
     

        #update session state
        st.session_state.last_sync = last_sync
        st.session_state.next_sync = next_sync
        
        logger.info(f"="*80)
        logger.info("\n")
        
    except Exception as e:
        if "Sync is not supported" in str(e):
            logger.info("Skipping sync: This appears to be a local file database that doesn't support sync")
            st.session_state.sync_status = "Skipping sync: This appears to be a local file database that doesn't support sync"
        else:
            logger.error(f"Sync failed: {str(e)}")
            st.session_state.sync_status = f"Failed: {str(e)}"

def get_type_name(type_ids):
    engine = create_engine(local_sde_url)
    with engine.connect() as conn:
        df = pd.read_sql_query(f"SELECT * FROM invtypes WHERE typeID IN ({','.join(map(str, type_ids))})", conn)
    df = df[['typeID', 'typeName']]
    df.rename(columns={'typeID': 'type_id', 'typeName': 'type_name'}, inplace=True)
    return df

def update_targets(fit_id, target_value):
    conn = libsql.connect("wcmkt.db", sync_url=mkt_url, auth_token=mkt_auth_token)
    cursor = conn.cursor()
    cursor.execute(f"""UPDATE ship_targets
    SET ship_target = {target_value}
    WHERE fit_id = {fit_id};""")
    conn.commit()
    logger.info(f"Updated target for fit_id {fit_id} to {target_value}")
    
def update_industry_index():
    indy_index = fetch_industry_system_cost_indices()
    engine = create_engine(build_cost_url)
    with engine.connect() as conn:
        indy_index.to_sql("industry_index", conn, if_exists="replace", index=False)
    indy_index.to_sql("industry_index", build_cost_url, if_exists="replace", index=False)
    logger.info("Industry index updated")

def fetch_industry_system_cost_indices():
    url = "https://esi.evetech.net/latest/industry/systems/?datasource=tranquility"
    response = requests.get(url)
    response.raise_for_status()

    systems_data = response.json()

    # Flatten data into rows of: system_id, activity, cost_index
    flat_records = []
    for system in systems_data:
        system_id = system['solar_system_id']
        for activity_info in system['cost_indices']:
            flat_records.append({
                'system_id': system_id,
                'activity': activity_info['activity'],
                'cost_index': activity_info['cost_index']
            })

    # Create DataFrame and set MultiIndex for fast lookup
    df = pd.DataFrame(flat_records)
    df = df.pivot(index='system_id', columns='activity', values='cost_index')
    df.reset_index(inplace=True)
    df.rename(columns={'system_id': 'solar_system_id'}, inplace=True)

    return df


if __name__ == "__main__":
    pass