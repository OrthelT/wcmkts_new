import pandas as pd
import datetime
from sqlalchemy import create_engine
import streamlit as st
import os
from dotenv import load_dotenv
import libsql_experimental as libsql
import logging

logging = logging.getLogger(__name__)

# Database URLs
local_mkt_url = "sqlite:///wcmkt.db"  # Changed to standard SQLite format for local dev
local_sde_url = "sqlite:///sde.db"    # Changed to standard SQLite format for local dev

# Load environment variables
load_dotenv()

# mkt_url = st.secrets["TURSO_DATABASE_URL"]      
# mkt_auth_token = st.secrets["TURSO_AUTH_TOKEN"]

# sde_url = st.secrets["SDE_URL"]
# sde_auth_token = st.secrets["SDE_AUTH_TOKEN"]

# Use environment variables for production
mkt_url = os.getenv('TURSO_DATABASE_URL')
mkt_auth_token = os.getenv("TURSO_AUTH_TOKEN")

sde_url = os.getenv('SDE_URL')
sde_auth_token = os.getenv("SDE_AUTH_TOKEN")

def sync_db(db_url="wcmkt.db",sync_url=mkt_url, auth_token=mkt_auth_token):
    conn = libsql.connect(db_url, sync_url=sync_url, auth_token=auth_token)
    conn.sync()
    print("Database synced")

def get_type_name(type_ids):
    engine = create_engine(local_sde_url)
    with engine.connect() as conn:
        df = pd.read_sql_query(f"SELECT * FROM invtypes WHERE typeID IN ({','.join(map(str, type_ids))})", conn)
    df = df[['typeID', 'typeName']]
    df.rename(columns={'typeID': 'type_id', 'typeName': 'type_name'}, inplace=True)
    return df

def get_recent_items():
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

if __name__ == "__main__":
		pass
	