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
from utils import get_jita_price, get_multi_item_jita_price

# Insert centralized logging configuration
logger = setup_logging(__name__)

mktdb = DatabaseConfig("wcmkt")

def get_target_from_fit_id(fit_id):
    """Get the target value for a fit id"""
    df = new_read_df(mktdb, text("SELECT * FROM ship_targets WHERE fit_id = :fit_id"), {"fit_id": fit_id})
    return df.loc[0, 'ship_target']

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

    # Handle null prices: log warnings and fill with avg_price or Jita price
    null_price_mask = df['price'].isna()
    if null_price_mask.any():
        null_price_items = df[null_price_mask][['type_id', 'type_name', 'fit_id']].drop_duplicates()
        for _, row in null_price_items.iterrows():
            type_id = row['type_id']
            type_name = row.get('type_name', f'type_id {type_id}')
            fit_id = row['fit_id']
            logger.warning(f"Null price found for {type_name} (type_id: {type_id}) in fit_id {fit_id}")
        
        # Get unique type_ids with null prices
        null_type_ids = df[null_price_mask]['type_id'].unique().tolist()
        
        # Try to get avg_price from marketstats table
        if null_type_ids:
            placeholders = ','.join(['?'] * len(null_type_ids))
            avg_price_query = f"SELECT type_id, avg_price FROM marketstats WHERE type_id IN ({placeholders})"
            try:
                with mktdb.local_access():
                    with mktdb.engine.connect() as conn:
                        avg_price_df = pd.read_sql_query(avg_price_query, conn, params=tuple(null_type_ids))
                # Create a mapping of type_id to avg_price
                avg_price_map = dict(zip(avg_price_df['type_id'], avg_price_df['avg_price']))
            except Exception as e:
                logger.error(f"Error fetching avg_price from marketstats: {e}")
                avg_price_map = {}
        else:
            avg_price_map = {}
        
        # Fill null prices with avg_price where available
        for type_id in null_type_ids:
            if type_id in avg_price_map:
                avg_price = avg_price_map[type_id]
                if pd.notna(avg_price) and avg_price > 0:
                    # Update rows where type_id matches and price is still null
                    type_mask = (df['type_id'] == type_id) & df['price'].isna()
                    df.loc[type_mask, 'price'] = avg_price
                    logger.info(f"Filled null price for type_id {type_id} with avg_price: {avg_price}")
        
        # For remaining null prices, try Jita price
        remaining_nulls = df['price'].isna()
        if remaining_nulls.any():
            remaining_type_ids = df[remaining_nulls]['type_id'].unique().tolist()
            for type_id in remaining_type_ids:
                try:
                    jita_price = get_jita_price(type_id)
                    if jita_price is not None and jita_price > 0:
                        # Update rows where type_id matches and price is still null
                        type_mask = (df['type_id'] == type_id) & df['price'].isna()
                        df.loc[type_mask, 'price'] = jita_price
                        logger.info(f"Filled null price for type_id {type_id} with Jita price: {jita_price}")
                    else:
                        logger.warning(f"Could not get Jita price for type_id {type_id}, using 0")
                        type_mask = (df['type_id'] == type_id) & df['price'].isna()
                        df.loc[type_mask, 'price'] = 0
                except Exception as e:
                    logger.error(f"Error fetching Jita price for type_id {type_id}: {e}")
                    type_mask = (df['type_id'] == type_id) & df['price'].isna()
                    df.loc[type_mask, 'price'] = 0
        
        # Fill any remaining nulls with 0 as final fallback
        if df['price'].isna().any():
            logger.warning("Still have null prices after filling with Jita price")
            null_type_ids = df[df['price'].isna()]['type_id'].unique().tolist()
            for type_id in null_type_ids:
                logger.warning(f"Null price for type_id {type_id}")
            df['price'] = df['price'].fillna(0)

    # Calculate total cost per fit (sum of fit_qty * price for all items in the fit)
    df['item_cost'] = df['fit_qty'] * df['price']
    fit_cost = df.groupby('fit_id')['item_cost'].sum().reset_index()
    fit_cost = fit_cost.rename(columns={'item_cost': 'total_cost'})
    fit_summary = fit_summary.merge(fit_cost, on='fit_id', how='left')
    fit_summary['total_cost'] = fit_summary['total_cost'].fillna(0)

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
                      'ship_group', 'price', 'total_cost', 'ship_target', 'target_percentage', 'daily_avg']
    fit_summary = fit_summary[summary_columns]

    return df, fit_summary

def calculate_jita_fit_cost_and_delta(fit_data: pd.DataFrame, current_fit_cost: float) -> tuple[float, float | None]:
    """
    Calculate the fit cost at Jita prices and the percentage delta compared to current market prices.
    
    Args:
        fit_data: DataFrame containing fit items with columns: type_id, fit_qty
        current_fit_cost: The current fit cost at market prices
    
    Returns:
        tuple: (jita_fit_cost, percentage_delta)
            - jita_fit_cost: Total cost of the fit at Jita prices
            - percentage_delta: Percentage difference from Jita price (fit_cost - jita_fit_cost)/jita_fit_cost * 100,
              or None if calculation is not possible (e.g., jita_fit_cost is 0)
    """
    if fit_data.empty:
        return 0.0, None
    
    # Get unique type_ids from the fit
    type_ids = fit_data['type_id'].unique().tolist()
    
    # Fetch all Jita prices at once
    jita_prices = get_multi_item_jita_price(type_ids)
    
    if not jita_prices:
        logger.warning("Could not fetch any Jita prices for fit items")
        return 0.0, None
    
    jita_fit_cost = 0.0
    missing_prices = []
    
    # Calculate Jita cost for each item in the fit
    for _, row in fit_data.iterrows():
        type_id = row['type_id']
        fit_qty = row['fit_qty']
        
        if type_id in jita_prices:
            jita_price = jita_prices[type_id]
            if jita_price > 0:
                jita_fit_cost += fit_qty * jita_price
            else:
                logger.warning(f"Jita price for type_id {type_id} is not positive: {jita_price}")
        else:
            missing_prices.append(type_id)
    
    if missing_prices:
        logger.warning(f"Missing Jita prices for {len(missing_prices)} items: {missing_prices[:5]}{'...' if len(missing_prices) > 5 else ''}")
    
    # Calculate percentage delta: (fit_cost - jita_fit_cost)/jita_fit_cost * 100
    if jita_fit_cost > 0:
        percentage_delta = ((current_fit_cost - jita_fit_cost) / jita_fit_cost) * 100
    else:
        percentage_delta = None
        if current_fit_cost > 0:
            logger.warning(f"Jita fit cost is 0 but current fit cost is {current_fit_cost}, cannot calculate delta. "
                          f"This may indicate missing Jita prices for some items in the fit.")
    
    return jita_fit_cost, percentage_delta

@st.cache_data(ttl=600)
def get_all_fit_data()->pd.DataFrame:
    """Create a dataframe with all fit information"""
    logger.info("Getting fit info from doctrines table")
    query = "SELECT * FROM doctrines"

    def _read_all():
        with mktdb.local_access():
            with mktdb.engine.connect() as conn:
                return pd.read_sql_query(query, conn)

    try:
        df = _read_all()
    except Exception as e:
        logger.error(f"Failed to get fit data: {str(e)}")
        try:
            mktdb.sync()
            df = _read_all()
        except Exception as e2:
            logger.error(f"Failed to get fit data after sync: {str(e2)}")
            raise

    return df

if __name__ == "__main__":
    pass
