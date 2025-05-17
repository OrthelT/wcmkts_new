import pandas as pd
from sqlalchemy import create_engine, text
from db_handler import get_local_mkt_engine
import streamlit as st
from logging_config import setup_logging

# Set up logging
logger = setup_logging(__name__)

# Ship targets based on the Excel file
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

def create_targets_table():
    """Create a targets table in the database if it doesn't exist"""
    engine = get_local_mkt_engine()
    
    # Check if the table exists
    with engine.connect() as conn:
        result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='ship_targets'"))
        table_exists = result.fetchone() is not None
    
    # Create the table if it doesn't exist
    if not table_exists:
        print("ship_targets table does not exist")
        # with engine.connect() as conn:
        #     conn.execute(text("""
        #         CREATE TABLE ship_targets (
        #             id INTEGER PRIMARY KEY AUTOINCREMENT,
        #             ship_name TEXT UNIQUE,
        #             target INTEGER,
        #             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        #         )
        #     """))
        #     conn.commit()
        #     print("Created ship_targets table")
    else:
        print("ship_targets table already exists")

def set_targets():
    """Utility function to initialize or update ship targets in the database.
    
    This function is a standalone utility that:
    1. Creates the ship_targets table if it doesn't exist
    2. Populates/updates the table with default target values from SHIP_TARGETS dictionary
    3. Skips the 'default' entry as it's used as a fallback value only
    
    Usage:
    - Run this function manually when you need to:
        * Initialize the ship_targets table for the first time
        * Reset targets to default values
        * Update targets after modifying the SHIP_TARGETS dictionary
    
    The targets set by this function are used by the doctrine status page
    to calculate whether ship and module stocks meet target levels.
    
    Note: This function is not called automatically by the application.
    It should be run manually when target values need to be initialized or reset.
    """
    create_targets_table()
    
    engine = get_local_mkt_engine()
    
    # Insert or update target values
    for ship_name, target in SHIP_TARGETS.items():
        if ship_name == 'default':
            continue  # Skip the default value
            
        with engine.connect() as conn:
            # Using SQLite's "INSERT OR REPLACE" to update if the ship already exists
            conn.execute(text("""
                INSERT OR REPLACE INTO ship_targets (ship_name, target)
                VALUES (:ship_name, :target)
            """), {"ship_name": ship_name, "target": target})
            conn.commit()
    
    print("Target values set in database")

def get_target_from_db(ship_name):
    """Get the target value for a ship from the database"""
    engine = get_local_mkt_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT ship_target FROM ship_targets WHERE ship_name = :ship_name
        """), {"ship_name": ship_name})
        row = result.fetchone()
        
    if row:
        return row[0]
    else:
        # Return default if not found
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT ship_target FROM ship_targets WHERE ship_name = 'default'
            """))
            row = result.fetchone()
            
        return row[0] if row else 20  # Default to 20 if nothing in database

def list_targets():
    """List all targets in the database"""
    engine = get_local_mkt_engine()
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT ship_name, ship_target FROM ship_targets ORDER BY ship_name
        """))
        targets = result.fetchall()
    
    if targets:
        print("\nCurrent ship targets in database:")
        for ship_name, target in targets:
            print(f"{ship_name}: {target}")
    else:
        print("No targets set in database")

def update_target(fit_id: int, new_target: int) -> bool:
    """Update the target value for a specific fit ID in the ship_targets table.
    
    Args:
        fit_id (int): The ID of the fit to update
        new_target (int): The new target value to set
        
    Returns:
        bool: True if update was successful, False otherwise
        
    Example:
        >>> update_target(123, 50)  # Sets target to 50 for fit ID 123
    """
    try:
        engine = get_local_mkt_engine()
        with engine.connect() as conn:
            # First check if the fit_id exists
            result = conn.execute(text("""
                SELECT fit_id FROM ship_targets 
                WHERE fit_id = :fit_id
            """), {"fit_id": fit_id})
            
            if result.fetchone() is None:
                logger.warning(f"No target found for fit ID {fit_id}")
                return False
            
            # Update the target value
            conn.execute(text("""
                UPDATE ship_targets 
                SET ship_target = :new_target 
                WHERE fit_id = :fit_id
            """), {"fit_id": fit_id, "new_target": new_target})
            
            conn.commit()
            logger.info(f"Successfully updated target for fit ID {fit_id} to {new_target}")
            return True
            
    except Exception as e:
        logger.error(f"Error updating target: {str(e)}")
        return False
    
def get_full_ship_targets():
    """Get all ship targets from the database"""
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM ship_targets"))

    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df

def update_ship_targets(old_ship_targets: pd.DataFrame, updated_targets: pd.DataFrame):
    """Update the ship targets with the new targets from a csv file
    Example usage:     
    ship_targets = pd.read_csv("data/ship_targets.csv")
    updated_targets = pd.read_csv("data/new_targets.csv")
    update_ship_targets(ship_targets, updated_targets)"""
    
    old_length = len(old_ship_targets)
    new_ship_targets = pd.concat([old_ship_targets, updated_targets])
    new_ship_targets=new_ship_targets.reset_index(drop=True)
    new_ship_targets['id'] = new_ship_targets.index
    print(new_ship_targets)
    new_length = len(new_ship_targets)

    print(f"Old length: {old_length}")
    print(f"New length: {new_length}")
    print(f"Difference: {new_length - old_length}")

    if new_ship_targets.duplicated(subset=['fit_id']).any():
        print("Duplicates found")
    else:
        print("No duplicates found")
    confirm = input("Confirm? (y/n)")
    if confirm == "y":
        #confirm update
        if len(updated_targets) > len(ship_targets):
            new_ship_targets = new_ship_targets[~new_ship_targets['fit_id'].isin(ship_targets['fit_id'])]
            print(f"New ships: {len(new_ship_targets)}")
            print(new_ship_targets)
            
            confirm_update = input("Confirm update? (y/n)")
        else:
            print("No new ships found")
            confirm_update = "y"
        if confirm_update == "y":
            updated_target_values = new_ship_targets[new_ship_targets['fit_id'].isin(updated_targets['fit_id'])]
            if len(updated_target_values) > 0:
                print(updated_target_values)
                confirm_update_values = input("Confirm update values? (y/n)")
            else:
                print("No updated target values found")
                confirm_update_values = "y"



        if confirm_update == "y" and confirm_update_values == "y":
            
            
            new_ship_targets.to_csv("data/ship_targets.csv", index=False)
        else:
            print("Update cancelled")
    else:
        print("No update needed")
    
    return new_ship_targets

def compare_ship_targets(old_df: pd.DataFrame, new_df: pd.DataFrame):
    """Compare the old and new ship targets"""
    # Merge on fit_id only
    merged = pd.merge(
        old_df[["fit_id", "fit_name", "ship_name", "ship_target"]].rename(columns={"ship_target": "old_target"}),
        new_df[["fit_id", "fit_name", "ship_name", "ship_target"]].rename(columns={"ship_target": "new_target"}),
        on="fit_id",
        how="inner",
        suffixes=("_old", "_new")
    )

    # Filter where the ship_target changed
    changed = merged[merged["old_target"] != merged["new_target"]].copy()
    changed = changed.drop(columns=["fit_name_old", "ship_name_old"])

    # Drop duplicate fit_id (keeping first match)
    changed = changed.drop_duplicates(subset="fit_id").reset_index(drop=True)

    # Optional: select clean output
    result = changed[["fit_id", "fit_name_new", "ship_name_new", "old_target", "new_target"]].rename(
        columns={"fit_name_new": "fit_name", "ship_name_new": "ship_name"}
    )

    result.to_csv("data/ship_targets_comparison.csv", index=False)
    return result

def load_ship_targets(new_targets: pd.DataFrame):
    """Load the ship targets to the database"""
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        logger.info("Deleting ship_targets table")
        conn.execute(text("DELETE FROM ship_targets"))
        conn.commit()

        if new_targets is not None:
            logger.info("Loading new targets")
            new_targets.to_sql("ship_targets", get_local_mkt_engine(), if_exists="replace", index=False)
            conn.commit()
        else:
            logger.info("No new targets found")
    logger.info("Ship targets loaded")

if __name__ == "__main__":
    
    new_targets = pd.read_csv("data/ship_targets.csv")
    load_ship_targets(new_targets)

    targets = get_full_ship_targets()
    print(targets)

