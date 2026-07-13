from config import DatabaseConfig
import json
import os
import sqlite3 as sql
import threading
from logging_config import setup_logging
from time import perf_counter
from settings_service import get_all_market_configs

logger = setup_logging(__name__)

# Serializes bootstrap across concurrent Streamlit sessions (script-run
# threads share one process and one set of .db files). Without this, a
# second session cold-starting mid-bootstrap sees the first session's
# half-downloaded replica, judges it invalid, and re-syncs it redundantly.
# The second entrant blocks, then re-verifies and skips completed work.
_INIT_LOCK = threading.Lock()


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
        if count == 0:
            conn.close()
            return False
        conn.close()
        # pyturso pairing invariant: a replica is only ready when its -info
        # metadata exists and parses. A libsql-era or metadata-less .db must
        # be removed and re-bootstrapped (sync()'s state machine enforces the
        # same rule; enforcing it here routes cold start through resync).
        try:
            with open(path + "-info", encoding="utf-8") as f:
                json.load(f)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            logger.warning(f"DB {path} has no valid pyturso metadata; treating as not ready")
            return False
        return True
    except Exception as e:
        logger.warning(f"DB content verification failed for {path}: {e}")
        return False


def init_db():
    """Initialize ALL local databases, syncing from Turso when needed.

    Checks each database for both file existence AND valid content (tables).
    Invalid files are never removed here — sync() enforces the replica
    validity invariants under _SYNC_LOCK and rebuilds via fresh bootstrap,
    so an in-flight sync can't be clobbered from another thread.

    Serialized by _INIT_LOCK: concurrent sessions cold-starting together
    take turns, and the later ones re-verify (cheap) instead of re-syncing.

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

    with _INIT_LOCK:
        for key, value in db_paths.items():
            alias = key
            db_path = value
            db = DatabaseConfig(alias)

            try:
                if verify_db_content(db_path):
                    logger.info(f"DB exists and has content: {db_path}✔️")
                    status[key] = "success initialized🟢"
                else:
                    # Missing, empty, or invalid — sync() nukes and
                    # re-bootstraps invalid files under its own lock
                    if verify_db_path(db_path):
                        logger.warning(
                            f"DB file exists but is empty/invalid: {db_path}; "
                            "sync() will rebuild it"
                        )
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

    with _INIT_LOCK:
        # Re-verify: another session may have bootstrapped it while we waited
        if verify_db_content(db.path):
            return True

        # Missing or invalid — sync() removes invalid files under _SYNC_LOCK
        logger.warning(f"Market database '{db_alias}' ({db.path}) not ready, attempting sync")
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
