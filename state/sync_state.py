from logging_config import setup_logging
from config import DatabaseConfig
from datetime import timezone, datetime, timedelta
from time import perf_counter

import pandas as pd
import streamlit as st
from sqlalchemy import text

from state.session_state import ss_set
from state.market_state import get_active_market
logger = setup_logging(__name__)

# Expected interval between ESI market updates. Used to derive a countdown
# from the last-observed local update timestamp without assuming a fixed
# wall-clock slot (data lands ~hourly after the previous update, not at a
# fixed :MM past the hour).
_UPDATE_INTERVAL_MINUTES = 60


class SyncStatusUnavailableError(Exception):
    """Sync-status read failed (DB unreachable, malformed row, parse error).

    Distinct from a successful read that returned no rows. ``None`` means
    "the system is healthy but has not yet ingested any updates"; this
    exception means "we don't know what the sync status is" — so the UI
    should render an explicit "unavailable" state rather than the last
    cached timestamp, which would otherwise mislead the admin.
    """


def get_most_recent_update_resilient(
    db_alias: str,
    table_name: str = "marketstats",
) -> datetime | None:
    """Return latest updatelog timestamp using read_df's sync-and-retry / backup-restore recovery for local reads.

    Returns:
        Timezone-aware datetime for the most recent ``timestamp`` row, or
        ``None`` when the query succeeded but the table held no rows.

    Raises:
        SyncStatusUnavailableError: the read itself failed or the timestamp
            could not be parsed. Callers must render an explicit "unavailable"
            state rather than treating this like a missing row.
    """
    # Deferred import: state/ must not import from repositories/ at module level
    # (CLAUDE.md layered-architecture rule). The bidirectional state↔config import
    # via DatabaseConfig is the documented exception; BaseRepository is not.
    from repositories.base import BaseRepository

    db = DatabaseConfig(db_alias)
    reader = BaseRepository(db, logger)
    query = text(
        """
        SELECT timestamp
        FROM updatelog
        WHERE table_name = :table_name
        ORDER BY timestamp DESC
        LIMIT 1
        """
    )
    try:
        df = reader.read_df(query, params={"table_name": table_name})
    except Exception as exc:
        logger.error(
            "sync_status_read_failed alias=%s table=%s: %s",
            db_alias,
            table_name,
            exc,
            exc_info=True,
        )
        raise SyncStatusUnavailableError(
            f"updatelog read failed for alias={db_alias!r} table={table_name!r}"
        ) from exc

    if df.empty or pd.isna(df.loc[0, "timestamp"]):
        return None

    parsed = _coerce_update_time(df.loc[0, "timestamp"])
    if parsed is None:
        raise SyncStatusUnavailableError(
            f"updatelog timestamp for alias={db_alias!r} table={table_name!r} could not be parsed"
        )
    return parsed


def _coerce_update_time(value) -> datetime | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        logger.error("sync_status_parse_failed: updatelog timestamp %r is not parseable", value)
        return None
    return parsed.to_pydatetime()


def update_wcmkt_state(db_alias: str = None) -> None:
    """Update session state with the local DB's most recent update time.

    Uses the updatelog table to determine when the database was last refreshed.
    Under the pyturso embedded-replica model there is no separate remote
    timestamp to record: remote is unknowable without a pull, and after a
    pull, local IS remote. Callers needing to know whether the currently
    served data is a restored backup should check
    ``config.get_degraded_aliases()`` instead.

    Args:
        db_alias: Database alias to check. If None, uses the active market.
    """
    if db_alias is None:
        try:
            db_alias = get_active_market().database_alias
        except ImportError:
            db_alias = "wcmkt"
        except Exception as e:
            logger.error(f"Failed to get active market, falling back to 'wcmkt': {e}")
            db_alias = "wcmkt"

    start_time = perf_counter()
    db = DatabaseConfig(db_alias)

    local_update_status = {'updated': None, 'needs_update': False, 'time_since': None}

    now = datetime.now(timezone.utc)

    try:
        local_update = get_most_recent_update_resilient(db.alias, "marketstats")
    except SyncStatusUnavailableError as exc:
        logger.warning(f"Local sync status unavailable for {db.alias}: {exc}")
        local_update = None
    local_update_status['updated'] = local_update
    if local_update is not None:
        local_update_status['time_since'] = now - local_update
        local_update_status['needs_update'] = (
            local_update_status['time_since'] > timedelta(hours=2)
        )

    logger.info("-"*60)
    ss_set('local_update_status', local_update_status)
    logger.info(f"local_status saved to session state: {db.alias, db.path}")
    active_market = get_active_market()
    logger.info(f"Active market: {active_market.database_alias}")
    logger.info("--------------------------------")
    for k, v in local_update_status.items():
        logger.info(f"{k}: {v}")
    logger.info("-"*60)
    end_time = perf_counter()
    elapsed_time = round((end_time-start_time)*1000, 2)
    logger.info(f"TIME update_wcmkt_state() = {elapsed_time} ms")
    logger.info("-"*60)

def minutes_until_next_update() -> int | None:
    """Return whole minutes until the next expected DB update, or None if unknown.

    Assumes ingestion arrives ~60 minutes after the last recorded update.
    Returns 0 once the window has elapsed (the update is "due").
    Returns None when local update status is unavailable — callers must
    render a neutral state rather than a misleading countdown.
    """
    if "local_update_status" not in st.session_state:
        try:
            update_wcmkt_state()
        except Exception as exc:
            logger.error(f"Error initializing local_update_status: {exc}")
            return None

    status = st.session_state.get("local_update_status")
    if status is None:
        return None
    time_since = status.get("time_since")
    if time_since is None:
        return None

    minutes_since = time_since.total_seconds() / 60
    if minutes_since >= _UPDATE_INTERVAL_MINUTES:
        return 0
    return int(_UPDATE_INTERVAL_MINUTES - minutes_since)


if __name__ == "__main__":
    pass
