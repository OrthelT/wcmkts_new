import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import create_engine, text, distinct
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
from db_handler import  clean_mkt_data, get_local_mkt_engine, get_local_sde_engine, get_stats,safe_format, get_mkt_data, get_market_orders, get_market_history, get_item_details, get_fitting_data, get_update_time
import sqlalchemy_libsql
import libsql_client
import logging
import time
import threading
import datetime
import pytz
from db_utils import sync_db
import json
import datetime
import millify

# Import target handling functions if set_targets.py exists
try:
    from set_targets import get_target_from_db
    USE_DB_TARGETS = True
except ImportError:
    USE_DB_TARGETS = False

# Targets for different ship types (for front-end display)
# In production, consider moving this to a database table
SHIP_TARGETS = {
    'Flycatcher': 20,
    'Griffin': 20,
    'Guardian': 25,
    'Harpy': 100,
    'Heretic': 20,
    'Hound': 50,
    'Huginn': 20,
    'Hurricane': 100,
    # Add more ships as needed
    'default': 20  # Default target if ship not found
}

def get_doctrine_fits(db_name: str = 'wc_fitting') -> pd.DataFrame:
    """Get all doctrine fits from the database"""
    engine = get_local_mkt_engine()
    query = """
        SELECT * FROM doctrines
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(query, conn)
    return df

def get_target_value(ship_name):
    """Get the target value for a ship type"""
    # First try to get from database if available
    if USE_DB_TARGETS:
        try:
            return get_target_from_db(ship_name)
        except Exception as e:
            print(f"Error getting target from database: {e}")
            # Fall back to dictionary if database lookup fails
    
    # Convert to title case for standardized lookup in dictionary
    ship_name = ship_name.title() if isinstance(ship_name, str) else ''
    
    # Look up in the targets dictionary, default to 20 if not found
    return SHIP_TARGETS.get(ship_name, SHIP_TARGETS['default'])

def create_fit_df():
    """Create a dataframe with all fit information"""
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM doctrines", conn)
    
    if df.empty:
        return pd.DataFrame()
    
    # Process each fit
    fits = []
    fit_ids = df['fit_id'].unique()
    master_df = pd.DataFrame()
    
    for fit_id in fit_ids:
        # Filter data for this fit
        df2 = df[df['fit_id'] == fit_id]
        
        if df2.empty:
            continue
        
        # Create a dataframe for this fit
        fit_df = pd.DataFrame()
        fit_df["fit_id"] = [df2['fit_id'].iloc[0]]
        fit_df["ship_name"] = [df2['ship_name'].iloc[0]]
        fit_df["ship_id"] = [df2['ship_id'].iloc[0]]
        fit_df["hulls"] = [df2['hulls'].iloc[0]]
        fit_df["fits"] = [df2["fits_on_mkt"].min()]

        #get the ship group
        ship_row = df2[df2.type_id == df2['ship_id'].iloc[0]]
        group_name = ship_row['group_name'].iloc[0]
        fit_df["ship_group"] = [group_name]
        # Get ship price
        try:
            df3 = df2[df2.type_id == df2['ship_id'].iloc[0]]
            fit_df["price"] = [df3['price'].iloc[0] if not df3.empty else 0]
        except (IndexError, KeyError):
            fit_df["price"] = [0]
        
        # Get target value based on ship name
        target_value = get_target_value(df2['ship_name'].iloc[0])
        fit_df["ship_target"] = [target_value]
        
        # Calculate target percentage - using scalar values to avoid Series comparison
        fits_value = df2["fits_on_mkt"].min()
        if target_value > 0:
            target_percentage = min(100, int((fits_value / target_value) * 100))
        else:
            target_percentage = 0
            
        fit_df["target_percentage"] = [target_percentage]
        
        # Get daily average volume if available
        avg_vol = ship_row['avg_vol'].iloc[0] if 'avg_vol' in ship_row.columns else 0
        fit_df["daily_avg"] = avg_vol
        
        # Add to master dataframe
        master_df = pd.concat([master_df, df2])
        
        # master_df = pd.merge(master_df, ship_group_df, on="ship_id", how="left")
        print(master_df.head())
        fits.append(fit_df)
    # Add all the fit summary rows if needed (for a summary view)
    if fits:
        fit_summary_df = pd.concat(fits)
        # Uncomment if you want to add the summary rows to the master dataframe
        # master_df = pd.concat([master_df, fit_summary_df])
    
    return master_df

if __name__ == "__main__":
    df = create_fit_df()
    pd.set_option('display.max_columns', None)
    print(df.head())
    
    # Print unique ship names for target reference
    if not df.empty and 'ship_name' in df.columns:
        print("\nUnique ship names:")
        print(sorted(df['ship_name'].unique()))