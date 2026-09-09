from config import DatabaseConfig
import os
import sqlite3 as sql
import threading
from concurrent.futures import ThreadPoolExecutor
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

# Databases every page needs regardless of which market hub is active.
SHARED_ALIASES: tuple[str, ...] = ("sde", "build_cost")


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
        # metadata is genuinely pyturso-shaped. A libsql-era -info is valid
        # JSON (so a bare parse wrongly accepts it) or metadata-less .db must
        # be removed and re-bootstrapped (sync()'s state machine enforces the
        # same rule; enforcing it here routes cold start through resync).
        from replica_metadata import classify_metadata

        kind = classify_metadata(path)
        if kind != "pyturso":
            logger.warning(
                f"DB {path} has {kind} metadata, not pyturso; treating as not ready"
            )
            return False
        return True
    except Exception as e:
        logger.warning(f"DB content verification failed for {path}: {e}")
        return False


def _bootstrap_alias(alias: str) -> str:
    """Verify one replica, syncing it when missing or invalid.

    Returns the status string recorded for the alias. Never raises: init_db()
    runs these concurrently and needs every result, not the first failure.
    """
    try:
        db = DatabaseConfig(alias)
    except ValueError:
        logger.error(f"Unknown database alias: {alias}")
        return "failed🔴"

    try:
        if verify_db_content(db.path):
            logger.info(f"DB exists and has content: {db.path}✔️")
            return "success initialized🟢"

        # Missing, empty, or invalid — sync() nukes and re-bootstraps
        # invalid files under its own per-alias lock
        if verify_db_path(db.path):
            logger.warning(
                f"DB file exists but is empty/invalid: {db.path}; "
                "sync() will rebuild it"
            )
        else:
            logger.warning(f"DB path does not exist: {db.path}⚠️")
        logger.info(f"syncing db: {db.path}🛜")
        db.sync()
        if verify_db_content(db.path):
            return "initialized and synced🟢"
        return "synced but empty🔴"
    except Exception as e:
        logger.error(f"Error syncing db {alias}: {e}")
        return "failed🔴"


def init_db(aliases: list[str] | None = None):
    """Initialize the given local databases, syncing from Turso when needed.

    Checks each database for both file existence AND valid content (tables).
    Invalid files are never removed here — sync() enforces the replica
    validity invariants under the alias's sync lock and rebuilds via fresh
    bootstrap, so an in-flight sync can't be clobbered from another thread.

    Serialized by _INIT_LOCK: concurrent sessions cold-starting together
    take turns, and the later ones re-verify (cheap) instead of re-syncing.
    Within one call the aliases are bootstrapped concurrently — the pulls are
    network-bound and each holds only its own alias's sync lock, so a cold
    container waits roughly for the slowest pull rather than their sum.

    Args:
        aliases: databases to ready. Defaults to every market hub plus the
            shared databases; callers that only need the active hub pass
            ``aliases_to_initialize()``.

    Returns True only when every requested database has been verified to
    contain tables. Returns False if any could not be made ready (missing
    credentials, network failure, etc.).
    """
    start_time = perf_counter()
    logger.info("-"*100)
    logger.info("initializing databases")
    logger.info("-"*100)

    if aliases is None:
        aliases = [
            cfg.database_alias for cfg in get_all_market_configs().values()
        ] + list(SHARED_ALIASES)

    # dict.fromkeys: de-duplicate while keeping the caller's order
    targets = list(dict.fromkeys(aliases))

    with _INIT_LOCK:
        with ThreadPoolExecutor(max_workers=len(targets) or 1) as pool:
            status = dict(zip(targets, pool.map(_bootstrap_alias, targets)))

    for alias, result in status.items():
        logger.info(f"db initialization status: {alias}: {result}")

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

        # Missing or invalid — sync() removes invalid files under the alias's lock
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
