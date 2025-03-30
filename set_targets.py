import pandas as pd
import sqlite3
import os
from sqlalchemy import create_engine, text
from db_handler import get_local_mkt_engine

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
    """Set target values in the database"""
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

if __name__ == "__main__":
    list_targets()
    
 