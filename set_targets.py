import pandas as pd
from sqlalchemy import text
from logging_config import setup_logging
from config import DatabaseConfig
# Set up logging
logger = setup_logging(__name__)

mkt_db = DatabaseConfig("wcmkt")
def get_target_from_db(ship_name):
    """Get the target value for a ship from the database"""
    engine = mkt_db.remote_engine

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT ship_target FROM ship_targets WHERE ship_name = :ship_name
        """), {"ship_name": ship_name})
        row = result.fetchone()
    conn.close()
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
    engine = mkt_db.engine

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT ship_name, ship_target FROM ship_targets ORDER BY ship_name
        """))
        targets = result.fetchall()

    if targets:
        logger.info("Current ship targets in database:")
        for ship_name, target in targets:
            logger.info(f"{ship_name}: {target}")

    else:
        logger.info("No targets set in database")
    conn.close()


def update_from_targets_csv(targets_csv: str)->bool:
    """Update the targets from a csv file"""
    targets = pd.read_csv(targets_csv)
    for index, row in targets.iterrows():
        update_target(row['fit_id'], row['new_target'], remote=True)
    return True

def update_target(fit_id: int, new_target: int, remote: bool = True) -> bool:
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
        if remote:
            engine = mkt_db.remote_engine
        else:
            engine = mkt_db.engine
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

            result = conn.execute(text("""
                SELECT ship_target, ship_name FROM ship_targets
                WHERE fit_id = :fit_id
            """), {"fit_id": fit_id})
            result = result.fetchall()
            ship_name = result[0][1]
            conn.close()
            logger.info(f"Successfully updated target for fit ID {fit_id} to {new_target} for {ship_name}")

            return True

    except Exception as e:
        logger.error(f"Error updating target: {str(e)}")
        return False

def get_all_ship_targets()->pd.DataFrame:
    """Get all ship targets from the database"""
    engine = mkt_db.engine
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM ship_targets"))
    conn.close()
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    return df

# def update_ship_targets_from_csv(old_ship_targets: pd.DataFrame, updated_targets: pd.DataFrame)->pd.DataFrame:
#     """Update the ship targets with the new targets from a csv file
#     Example usage:
#     old_ship_targets = pd.read_csv("data/ship_targets.csv")
#     updated_targets = pd.read_csv("data/new_targets.csv")
#     update_ship_targets_from_csv(ship_targets, updated_targets)"""

#     old_length = len(old_ship_targets)
#     new_ship_targets = pd.concat([old_ship_targets, updated_targets])
#     new_ship_targets=new_ship_targets.reset_index(drop=True)
#     new_ship_targets['id'] = new_ship_targets.index
#     logger.info("Proposed new ship targets:")
#     logger.info("\n" + new_ship_targets.to_string(index=False))
#     new_length = len(new_ship_targets)

#     logger.info(f"Old length: {old_length}")
#     logger.info(f"New length: {new_length}")
#     logger.info(f"Difference: {new_length - old_length}")

#     if new_ship_targets.duplicated(subset=['fit_id']).any():
#         logger.warning("Duplicates found")
#     else:
#         logger.info("No duplicates found")
#     confirm = input("Confirm? (y/n)")
#     if confirm == "y":
#         #confirm update
#         if len(updated_targets) > len(old_ship_targets):
#             new_ship_targets = new_ship_targets[~new_ship_targets['fit_id'].isin(old_ship_targets['fit_id'])]
#             logger.info(f"New ships: {len(new_ship_targets)}")
#             logger.info("\n" + new_ship_targets.to_string(index=False))

#             confirm_update = input("Confirm update? (y/n)")
#         else:
#             logger.info("No new ships found")
#             confirm_update = "y"
#         if confirm_update == "y":
#             updated_target_values = new_ship_targets[new_ship_targets['fit_id'].isin(updated_targets['fit_id'])]
#             if len(updated_target_values) > 0:
#                 logger.info("Updated target values:")
#                 logger.info("\n" + updated_target_values.to_string(index=False))
#                 confirm_update_values = input("Confirm update values? (y/n)")
#             else:
#                 logger.info("No updated target values found")
#                 confirm_update_values = "y"



#         if confirm_update == "y" and confirm_update_values == "y":


#             new_ship_targets.to_csv("data/ship_targets.csv", index=False)
#         else:
#             logger.info("Update cancelled")
#     else:
#         logger.info("No update needed")

#     return new_ship_targets

def load_new_ship_targets(new_targets: pd.DataFrame):
    """Load the new ship targets to the database"""
    engine = mkt_db.engine
    with engine.connect() as conn:
        logger.info("Deleting ship_targets table")
        conn.execute(text("DELETE FROM ship_targets"))
        conn.commit()

        if new_targets is not None:
            logger.info("Loading new targets")
            new_targets.to_sql("ship_targets", engine, if_exists="replace", index=False)
            conn.commit()
        else:
            logger.info("No new targets found")
    conn.close()
    logger.info("Ship targets loaded")

if __name__ == "__main__":
    pass