"""Database initialization and refresh logic shared across pages.

Moved from market_stats.py so the dashboard (default landing page)
can drive DB initialization and periodic staleness checks.
"""

import threading
import time
from datetime import datetime

import streamlit as st

from config import DatabaseConfig
from init_db import ensure_market_db_ready, init_db
from logging_config import setup_logging
from repositories import invalidate_build_cost_caches
from state.market_state import refresh_market_caches
from state.sync_state import update_wcmkt_state

logger = setup_logging(__name__)

# Minimum gap between staleness checks for a given database.
_CHECK_INTERVAL_SECONDS = 600

# When each alias was last checked, keyed by alias. Process-wide rather than
# per-session on purpose: the replica is a process-wide file, so a check one
# session just performed is equally valid for every other session. Holding
# this in st.session_state made every new browser session pay a full
# multi-database sync before its first paint.
_last_check_by_alias: dict[str, float] = {}
_last_check_lock = threading.Lock()


def initialize_databases() -> bool:
    """Initialize all databases (market, SDE, and build cost).

    Only sets ``db_initialized`` to True once *every* database has been
    verified to contain tables.  If a previous attempt partially failed,
    init_db() is re-run on the next rerun so the missing databases get
    another chance to sync.

    Returns:
        True if databases are initialized, False otherwise.
    """
    logger.info("*" * 60)
    logger.info("Starting database initialization")
    logger.info("*" * 60)

    if not st.session_state.get("db_initialized"):
        logger.info("-" * 30)
        logger.info("Initializing databases (all markets + shared)")
        result = init_db()
        if result:
            st.session_state.db_initialized = True
        else:
            st.toast("One or more databases failed to initialize", icon="❌")
    else:
        logger.info("Databases already initialized in session state")

    logger.info("*" * 60)
    st.session_state.db_init_time = datetime.now()
    return st.session_state.get("db_initialized", False)


def aliases_to_check() -> list[str]:
    """Databases the periodic check covers: the active hub + shared DBs.

    Inactive market hubs are deliberately excluded. Each was costing a pull
    plus a full-file verification on every check, and nothing reads them until
    the user switches hubs -- at which point ensure_market_db_ready() bootstraps
    the replica and this function starts including it.
    """
    from settings_service import get_periodic_sync_aliases
    from state.market_state import get_active_market

    return [get_active_market().database_alias] + get_periodic_sync_aliases()


def check_db(manual_override: bool = False, aliases: list[str] | None = None):
    """Pull the given DBs (active hub + shared by default); refresh UI on change.

    pull() IS the staleness check under pyturso: a cheap no-op round-trip
    when the replica is current, True when new data was applied.
    """
    from settings_service import get_all_market_configs

    market_aliases = {cfg.database_alias for cfg in get_all_market_configs().values()}
    all_aliases = aliases if aliases is not None else aliases_to_check()

    synced_aliases: list[str] = []
    any_sync_failed = False
    local_only_mode = False
    status_ctx = None  # lazily created the first time a pull returns changes

    for alias in all_aliases:
        # Mark before pulling, not after: a successful pull ends in st.rerun(),
        # which aborts this function, and an unmarked alias would re-enter the
        # guard on the next run and sync in a loop.
        with _last_check_lock:
            _last_check_by_alias[alias] = time.time()
        db = DatabaseConfig(alias)
        if not db.has_remote_credentials:
            logger.info(f"check_db(): skipping {alias}; no remote credentials configured")
            local_only_mode = True
            continue
        try:
            result = db.sync()
        except Exception:
            logger.error(f"Sync error for {alias}", exc_info=True)
            any_sync_failed = True
            st.toast(f"Sync error for {alias}", icon="❌")
            continue
        logger.info(f"check_db() {alias}: ok={result.ok} changed={result.changed}")
        if not result.ok:
            any_sync_failed = True
            st.toast(f"Sync failed for {alias}", icon="❌")
            continue
        if result.changed:
            synced_aliases.append(alias)
            if status_ctx is None:
                st.toast("Syncing database…", icon="🔄")
                st.space("medium")
                status_ctx = st.status("Syncing database…", expanded=False)
            status_ctx.update(label=f"Synced {alias}", state="running")

    if synced_aliases:
        if not market_aliases.isdisjoint(synced_aliases):
            refresh_market_caches()
        if "build_cost" in synced_aliases:
            invalidate_build_cost_caches()
        update_wcmkt_state()
        if status_ctx is not None:
            final_state = "error" if any_sync_failed else "complete"
            final_label = (
                "Sync finished with errors" if any_sync_failed else "Sync complete — refreshing"
            )
            status_ctx.update(label=final_label, state=final_state, expanded=False)
        st.toast("Database synced successfully. Loading updated data.", icon="✅")
        st.rerun()
    elif local_only_mode and manual_override:
        st.toast("Local-only mode: remote sync checks skipped", icon="ℹ️")
    elif not any_sync_failed and manual_override:
        # User clicked "Update Data" but there's nothing new — tell them
        # when the next automated update will land.
        from state.language_state import get_active_language
        from state.sync_state import minutes_until_next_update
        from ui.i18n import translate_text

        lang = get_active_language()
        minutes = minutes_until_next_update()
        no_new = translate_text(lang, "market_stats.no_new_data")
        if minutes is None:
            st.toast(no_new, icon="⏳")
        else:
            countdown = translate_text(
                lang, "market_stats.next_update_countdown", minutes=minutes
            )
            st.toast(f"{no_new} {countdown}", icon="⏳")


def maybe_run_check():
    """Check any database whose last check is older than the interval.

    The timestamps are per-alias and process-wide, so a second session on the
    same hub inherits the first session's check instead of repeating it, while
    a hub the user has just switched to has no timestamp and is checked at once.
    """
    now = time.time()
    with _last_check_lock:
        stale = [
            alias
            for alias in aliases_to_check()
            if now - _last_check_by_alias.get(alias, 0.0) > _CHECK_INTERVAL_SECONDS
        ]
        # Claim the stale aliases while still holding the lock. check_db()
        # marks them too, but it re-acquires the lock to do so; without this
        # claim two concurrent sessions can both see the same alias as stale
        # and start the same pull.
        for alias in stale:
            _last_check_by_alias[alias] = now
    if not stale:
        return
    logger.info(f"running check_db() for stale aliases: {stale}")
    check_db(aliases=stale)


def ensure_active_market_fresh(alias: str) -> bool:
    """Ready the active hub's replica and run the periodic staleness check.

    Every market-aware page calls this instead of ensure_market_db_ready()
    directly. ensure_market_db_ready() returns immediately when a replica has
    content, however stale, so a page that only called it served a hub the
    user had just switched to without ever pulling it.

    Returns:
        True if the replica is ready to query, False otherwise.
    """
    if not ensure_market_db_ready(alias):
        return False
    maybe_run_check()
    return True


def ensure_init_and_check() -> bool:
    """Combined initialization + periodic check. Call from any landing page.

    Returns:
        True if databases are ready, False otherwise.
    """
    if "db_init_time" not in st.session_state:
        init_result = initialize_databases()
    elif (datetime.now() - st.session_state.db_init_time).total_seconds() > 3600:
        init_result = initialize_databases()
    else:
        init_result = True

    if not init_result:
        return False

    # Guard against querying a market DB that has no tables yet.
    # update_wcmkt_state() and maybe_run_check() open DatabaseConfig.engine
    # and query marketstats — on an empty/missing replica this would create
    # an empty .db file and raise "no such table: marketstats".
    from state.market_state import get_active_market

    active_alias = get_active_market().database_alias
    if not ensure_market_db_ready(active_alias):
        logger.warning(
            f"Active market DB '{active_alias}' not ready; "
            "skipping state update and staleness check"
        )
        return False

    update_wcmkt_state()
    maybe_run_check()
    return True
