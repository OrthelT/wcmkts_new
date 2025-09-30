import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from config import DatabaseConfig
from logging_config import setup_logging
import time
from sqlalchemy import text
from db_handler import read_df, new_read_df

# Insert centralized logging configuration
logger = setup_logging(__name__)

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

mktdb = DatabaseConfig("wcmkt")

def get_target_value(ship_name):
    """Get the target value for a ship type"""
    # First try to get from database if available
    if USE_DB_TARGETS:
        try:
            return get_target_from_db(ship_name)
        except Exception as e:
            logger.error(f"Error getting target from database: {e}")
            # Fall back to dictionary if database lookup fails

    # Convert to title case for standardized lookup in dictionary
    ship_name = ship_name.title() if isinstance(ship_name, str) else ''

    # Look up in the targets dictionary, default to 20 if not found
    return SHIP_TARGETS.get(ship_name, SHIP_TARGETS['default'])

def get_target_values_batch(ship_names):
    """Get target values for multiple ship types efficiently"""
    if USE_DB_TARGETS:
        # If using DB, still call individual functions for now
        # TODO: Implement batch DB lookup if needed
        return [get_target_value(name) for name in ship_names]

    # For dictionary lookup, use vectorized pandas operations
    ship_names_title = pd.Series(ship_names).str.title().fillna('')
    return ship_names_title.map(SHIP_TARGETS).fillna(SHIP_TARGETS['default']).tolist()

def new_get_targets():
    df = new_read_df(mktdb, text("SELECT * FROM ship_targets"))
    return df

@st.cache_data(ttl=600, show_spinner="Loading cached doctrine fits...")
def create_fit_df()->pd.DataFrame:
    logger.info("Creating fit dataframe")
    t0 = time.perf_counter()
    df = get_all_fit_data()
    t1 = time.perf_counter()
    elapsed_time = round((t1 - t0)*1000, 2)
    logger.info(f"TIME get_all_fit_data() = {elapsed_time} ms")

    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Use vectorized operations instead of iterating through each fit
    logger.info("Processing fit data with vectorized operations")

    # Group by fit_id and aggregate data efficiently
    fit_summary = df.groupby('fit_id').agg({
        'ship_name': 'first',
        'ship_id': 'first',
        'hulls': 'first',
        'fits_on_mkt': 'min',
        'avg_vol': 'first' if 'avg_vol' in df.columns else lambda x: 0
    }).reset_index()

    # Get ship group and price data efficiently
    ship_data = df[df['type_id'] == df['ship_id']].groupby('fit_id').agg({
        'group_name': 'first',
        'price': 'first'
    }).reset_index()

    # Merge the data
    fit_summary = fit_summary.merge(ship_data, on='fit_id', how='left')
    fit_summary['price'] = fit_summary['price'].fillna(0)
    fit_summary['ship_group'] = fit_summary['group_name']

    # Rename columns to match expected output
    fit_summary = fit_summary.rename(columns={'fits_on_mkt': 'fits'})

    # Get target values for all ships at once (batch operation)
    t2 = time.perf_counter()
    targets_df = new_get_targets()
    targets_df = targets_df.drop_duplicates(subset=['fit_id'], keep='first')
    targets_df = targets_df.reset_index(drop=True)
    targets_df = targets_df[['fit_id', 'ship_target']]
    fit_summary = fit_summary.merge(targets_df, on='fit_id', how='left')

    t3 = time.perf_counter()
    elapsed_time = round((t3 - t2)*1000, 2)
    logger.info(f"TIME new_get_targets() = {elapsed_time} ms")

    # Calculate target percentages vectorized
    fit_summary['target_percentage'] = (
        (fit_summary['fits'] / fit_summary['ship_target'] * 100)
        .clip(upper=100)
        .fillna(0)
        .astype(int)
    )

    # Handle division by zero case
    fit_summary.loc[fit_summary['ship_target'] == 0, 'target_percentage'] = 0

    # Set daily_avg column
    if 'avg_vol' not in fit_summary.columns:
        fit_summary['daily_avg'] = 0
    else:
        fit_summary['daily_avg'] = fit_summary['avg_vol'].fillna(0)

    # Select final columns in the expected order
    summary_columns = ['fit_id', 'ship_name', 'ship_id', 'hulls', 'fits',
                      'ship_group', 'price', 'ship_target', 'target_percentage', 'daily_avg']
    fit_summary = fit_summary[summary_columns]

    return df, fit_summary

@st.cache_data(ttl=600)
def get_all_fit_data()->pd.DataFrame:
    """Create a dataframe with all fit information"""
    logger.info("Getting fit info from doctrines table")
    engine = mktdb.ro_engine
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM doctrines", conn)
    return df

if __name__ == "__main__":
    pass
