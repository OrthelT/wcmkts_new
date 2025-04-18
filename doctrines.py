import streamlit as st
import pandas as pd
from sqlalchemy import text
from db_handler import  get_local_mkt_engine

from logging_config import setup_logging

# Insert centralized logging configuration
logger = setup_logging()

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

def get_target_value(ship_name):
    """Get the target value for a ship type"""
    # First try to get from database if available
    if USE_DB_TARGETS:
        try:
            return get_target_from_db(ship_name)
        except Exception as e:
            logger.error(f"Error getting target from database: {e}")
            # Fall back to dictionary if database lookup fails
    logger.info(f"Getting target value for {ship_name}")
    # Convert to title case for standardized lookup in dictionary
    ship_name = ship_name.title() if isinstance(ship_name, str) else ''
    
    # Look up in the targets dictionary, default to 20 if not found
    return SHIP_TARGETS.get(ship_name, SHIP_TARGETS['default'])

@st.cache_data(ttl=600, show_spinner="Loading cached doctrine fits...")
def create_fit_df()->pd.DataFrame:
    logger.info(f"Creating fit dataframe")
    df = get_fit_info()

    if df.empty:
        return pd.DataFrame()
    
    fit_ids = df['fit_id'].unique()
    master_df = pd.DataFrame()
    
    #note: only used if you want the fit summary as its own dataframe
    fits = []

    # Process each fit
    for fit_id in fit_ids:
        # Filter data for this fit
        df2 = df[df['fit_id'] == fit_id]
        
        if df2.empty:
            continue
        logger.info(f"Processing fit {fit_id}; {df2['ship_name'].iloc[0]}")
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
        
        #uncomment this to get the fit summary as its own dataframe
        # fits.append(fit_df)
    
    # summary_df = get_fit_summary(fits)
    # return master_df, summary_df

    return master_df


def get_fit_summary(fits:list)->pd.DataFrame:
    """Get a summary of all doctrine fits"""
    # Add all the fit summary rows if needed (for a summary view)
    fit_summary_df = pd.DataFrame()
    if fits:
        fit_summary_df = pd.concat(fits)
        fit_summary_df.to_csv("fit_summary_df.csv", index=False)

    return fit_summary_df

@st.cache_data(ttl=600)
def get_fit_info()->pd.DataFrame:
    """Create a dataframe with all fit information"""
    logger.info(f"Getting fit info from doctrines table")
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM doctrines", conn)
    return df



if __name__ == "__main__":
    pass