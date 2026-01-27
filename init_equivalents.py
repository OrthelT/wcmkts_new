"""
Module Equivalents Initialization

Creates and populates the module_equivalents table from CSV files.
This table maps equivalent faction modules that can be used interchangeably
when calculating stock levels.
"""

import csv
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import DatabaseConfig
from models import Base, ModuleEquivalents
from logging_config import setup_logging

logger = setup_logging(__name__, log_file="init_equivalents.log")


def create_module_equivalents_table(db: DatabaseConfig) -> bool:
    """
    Create the module_equivalents table if it doesn't exist.

    Args:
        db: DatabaseConfig instance for the market database

    Returns:
        True if table was created or already exists, False on error
    """
    try:
        # Create table using SQLAlchemy metadata
        Base.metadata.create_all(db.engine, tables=[ModuleEquivalents.__table__])
        logger.info("module_equivalents table created or verified")
        return True
    except Exception as e:
        logger.error(f"Failed to create module_equivalents table: {e}")
        return False


def load_equivalents_from_csv(
    db: DatabaseConfig,
    csv_path: Path,
    group_id: int
) -> int:
    """
    Load module equivalents from a CSV file.

    Args:
        db: DatabaseConfig instance for the market database
        csv_path: Path to the CSV file with type_id, type_name columns
        group_id: The group_id to assign to all modules in this file

    Returns:
        Number of rows inserted
    """
    if not csv_path.exists():
        logger.error(f"CSV file not found: {csv_path}")
        return 0

    rows_inserted = 0

    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)

            with Session(db.engine) as session:
                for row in reader:
                    type_id = int(row['type_id'])
                    type_name = row['type_name'].strip()

                    # Check if this type_id already exists in the group
                    existing = session.execute(
                        text("""
                            SELECT id FROM module_equivalents
                            WHERE group_id = :group_id AND type_id = :type_id
                        """),
                        {"group_id": group_id, "type_id": type_id}
                    ).fetchone()

                    if existing:
                        logger.debug(f"Skipping existing entry: {type_name} (type_id={type_id})")
                        continue

                    equiv = ModuleEquivalents(
                        group_id=group_id,
                        type_id=type_id,
                        type_name=type_name
                    )
                    session.add(equiv)
                    rows_inserted += 1

                session.commit()

        logger.info(f"Loaded {rows_inserted} module equivalents from {csv_path.name}")
        return rows_inserted

    except Exception as e:
        logger.error(f"Failed to load equivalents from {csv_path}: {e}")
        return 0


def clear_equivalents_table(db: DatabaseConfig) -> bool:
    """
    Clear all data from the module_equivalents table.

    Args:
        db: DatabaseConfig instance for the market database

    Returns:
        True if successful, False on error
    """
    try:
        with db.engine.connect() as conn:
            conn.execute(text("DELETE FROM module_equivalents"))
            conn.commit()
        logger.info("Cleared module_equivalents table")
        return True
    except Exception as e:
        logger.error(f"Failed to clear module_equivalents table: {e}")
        return False


def init_module_equivalents(
    db: DatabaseConfig = None,
    clear_existing: bool = False
) -> bool:
    """
    Initialize the module_equivalents table and load data from CSV files.

    This function:
    1. Creates the module_equivalents table if it doesn't exist
    2. Optionally clears existing data
    3. Loads equivalents from all CSV files in csvfiles/ directory

    Args:
        db: DatabaseConfig instance (defaults to wcmkt)
        clear_existing: If True, clears existing data before loading

    Returns:
        True if initialization successful, False on error
    """
    if db is None:
        db = DatabaseConfig("wcmkt")

    logger.info("=" * 60)
    logger.info("Initializing module equivalents")
    logger.info("=" * 60)

    # Create table
    if not create_module_equivalents_table(db):
        return False

    # Optionally clear existing data
    if clear_existing:
        clear_equivalents_table(db)

    # Load from CSV files
    csv_dir = Path("csvfiles")
    total_loaded = 0

    # Currently only factionmap.csv, but designed for expansion
    csv_files = [
        ("factionmap.csv", 1),  # (filename, group_id)
        # Add more files here with incrementing group_ids:
        # ("another_equivalents.csv", 2),
    ]

    for csv_name, group_id in csv_files:
        csv_path = csv_dir / csv_name
        if csv_path.exists():
            loaded = load_equivalents_from_csv(db, csv_path, group_id)
            total_loaded += loaded
        else:
            logger.warning(f"CSV file not found: {csv_path}")

    logger.info(f"Total module equivalents loaded: {total_loaded}")
    logger.info("=" * 60)

    return total_loaded > 0


def get_equivalents_count(db: DatabaseConfig = None) -> int:
    """
    Get the count of entries in the module_equivalents table.

    Args:
        db: DatabaseConfig instance (defaults to wcmkt)

    Returns:
        Number of entries in the table
    """
    if db is None:
        db = DatabaseConfig("wcmkt")

    try:
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM module_equivalents"))
            count = result.fetchone()[0]
            return count
    except Exception as e:
        logger.error(f"Failed to get equivalents count: {e}")
        return 0


if __name__ == "__main__":
    # Run initialization when executed directly
    db = DatabaseConfig("wcmkt")
    success = init_module_equivalents(db, clear_existing=True)
    if success:
        count = get_equivalents_count(db)
        print(f"Successfully initialized module_equivalents table with {count} entries")
    else:
        print("Failed to initialize module_equivalents table")
