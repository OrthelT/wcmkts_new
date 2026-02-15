from config import DatabaseConfig
import os
import sqlite3 as sql
from logging_config import setup_logging
from sync_state import update_wcmkt_state
from time import perf_counter
from init_equivalents import init_module_equivalents, get_equivalents_count
from settings_service import get_all_market_configs

logger = setup_logging(__name__)


def verify_db_path(path):
    """Check if database file exists on disk."""
    if not os.path.exists(path):
        logger.warning(f"DB path does not exist: {path}")
        return False
    return True


def verify_db_content(path):
    """Check if a database file has actual user tables (not empty/corrupt).

    Returns False if the file doesn't exist, is 0 bytes, or has no tables.
    Also detects .db / .db-info mismatches from prior interrupted syncs.
    Uses read-only mode to avoid accidentally creating a new file.
    """
    if not os.path.exists(path):
        return False
    if os.path.getsize(path) == 0:
        if os.path.exists(path + "-info"):
            logger.warning(
                f"Detected .db-info without valid .db for {path} "
                f"— likely a prior interrupted sync"
            )
        return False
    try:
        conn = sql.connect(f"file:{path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except Exception as e:
        logger.warning(f"DB content verification failed for {path}: {e}")
        return False


def _remove_empty_db(path):
    """Remove an empty/invalid database file and its libsql/WAL artifacts."""
    for suffix in ("", "-shm", "-wal", "-info"):
        file_path = path + suffix
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Removed invalid db file: {file_path}")
            except OSError as e:
                logger.warning(f"Failed to remove {file_path}: {e}")


def init_db():
    """Initialize ALL local databases, syncing from Turso when needed.

    Checks each database for both file existence AND valid content (tables).
    If a file exists but is empty (e.g., left behind by a failed sync),
    it is removed and sync is re-attempted.

    Returns True only when every market and shared database has been
    verified to contain tables.  Returns False if any database could
    not be made ready (missing credentials, network failure, etc.).
    """
    start_time = perf_counter()
    logger.info("-"*100)
    logger.info("initializing databases")
    logger.info("-"*100)

    # Collect ALL market databases plus shared databases
    market_configs = get_all_market_configs()
    db_paths = {}

    for key, cfg in market_configs.items():
        try:
            mkt_db = DatabaseConfig(cfg.database_alias)
            db_paths[mkt_db.alias] = mkt_db.path
        except ValueError:
            logger.warning(f"Skipping unknown market alias: {cfg.database_alias}")

    # Add shared databases
    sde_db = DatabaseConfig("sde")
    build_cost_db = DatabaseConfig("build_cost")
    db_paths[sde_db.alias] = sde_db.path
    db_paths[build_cost_db.alias] = build_cost_db.path

    status = {}

    for key, value in db_paths.items():
        alias = key
        db_path = value
        db = DatabaseConfig(alias)

        try:
            if verify_db_content(db_path):
                logger.info(f"DB exists and has content: {db_path}✔️")
                status[key] = "success initialized🟢"
            else:
                # File is missing, empty, or has no tables — need to sync
                if verify_db_path(db_path):
                    logger.warning(f"DB file exists but is empty/invalid: {db_path}, removing")
                    _remove_empty_db(db_path)
                else:
                    logger.warning(f"DB path does not exist: {db_path}⚠️")
                logger.info("syncing db")
                logger.info(f"syncing db: {db_path}🛜")
                db.sync()
                if verify_db_content(db_path):
                    status[key] = "initialized and synced🟢"
                else:
                    status[key] = "synced but empty🔴"
        except Exception as e:
            logger.error(f"Error syncing db: {e}")
            status[key] = "failed🔴"
        logger.info(f"db initialization status: {key}: {status[key]}")
    logger.info("-"*100)
    logger.info("updating wcmkt state")
    logger.info("-"*100)

    logger.info("wcmkt state updated✅")

    # Initialize module equivalents table for all market databases
    logger.info("-"*100)
    logger.info("initializing module equivalents")
    logger.info("-"*100)

    for key, cfg in market_configs.items():
        try:
            mkt_db = DatabaseConfig(cfg.database_alias)
            equiv_count = get_equivalents_count(mkt_db)
            if equiv_count == 0:
                init_module_equivalents(mkt_db)
                equiv_count = get_equivalents_count(mkt_db)
            logger.info(f"module equivalents count ({cfg.database_alias}): {equiv_count}")
        except Exception as e:
            logger.warning(f"Could not init equivalents for {cfg.database_alias}: {e}")

    logger.info("-"*100)

    end_time = perf_counter()
    elapsed_time = round((end_time-start_time)*1000, 2)
    logger.info(f"TIME init_db() = {elapsed_time} ms")
    logger.info("-"*100)

    # Only report success if every database has content
    all_ok = all("🟢" in v for v in status.values())
    if not all_ok:
        failed = [k for k, v in status.items() if "🟢" not in v]
        logger.error(f"init_db() completed with failures: {failed}")
    return all_ok

def ensure_market_db_ready(db_alias: str) -> bool:
    """Verify a market database has content, syncing if necessary.

    Called after market switches to ensure the target database exists
    and has tables before any queries run. Without this check, accessing
    an unsynced database causes SQLite to create an empty file, leading
    to 'no such table' errors.

    Returns True if the database is ready, False if it could not be made ready.
    """
    try:
        db = DatabaseConfig(db_alias)
    except ValueError:
        logger.error(f"Unknown database alias: {db_alias}")
        return False

    if verify_db_content(db.path):
        return True

    # Database is missing or empty — attempt sync
    logger.warning(f"Market database '{db_alias}' ({db.path}) not ready, attempting sync")

    if verify_db_path(db.path):
        _remove_empty_db(db.path)

    try:
        db.sync()
    except Exception as e:
        logger.error(f"Failed to sync market database '{db_alias}': {e}")
        return False

    if verify_db_content(db.path):
        logger.info(f"Market database '{db_alias}' synced and ready")
        return True

    logger.error(f"Market database '{db_alias}' still empty after sync")
    return False


if __name__ == "__main__":
    pass
