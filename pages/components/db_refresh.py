"""Database initialization and refresh logic shared across pages.

Moved from market_stats.py so the dashboard (default landing page)
can drive DB initialization and periodic staleness checks.
"""

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


def check_db(manual_override: bool = False):
    """Pull every market + configured shared DB; refresh UI if anything changed.

    pull() IS the staleness check under pyturso: a cheap no-op round-trip
    when the replica is current, True when new data was applied.
    """
    from settings_service import get_all_market_configs, get_periodic_sync_aliases

    market_aliases = {cfg.database_alias for cfg in get_all_market_configs().values()}
    all_aliases = list(market_aliases) + get_periodic_sync_aliases()

    synced_aliases: list[str] = []
    any_sync_failed = False
    local_only_mode = False
    status_ctx = None  # lazily created the first time a pull returns changes

    for alias in all_aliases:
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
        # Mark this run as having completed a check so the periodic guard
        # in maybe_run_check() doesn't immediately re-fire after the rerun.
        st.session_state["last_check"] = time.time()
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
    """Run a periodic staleness check every 600 seconds.

    ``last_check`` is written BEFORE ``check_db()`` runs. This matters
    because ``check_db()`` may call ``st.rerun()`` on a successful sync,
    which would abort before any post-call assignment and re-trigger this
    guard on the next run — causing an infinite sync loop.
    """
    now = time.time()
    if "last_check" not in st.session_state:
        logger.info("last_check not in st.session_state, setting to now")
        st.session_state["last_check"] = now
        check_db()
    elif now - st.session_state.get("last_check", 0) > 600:
        logger.info(
            f"now - last_check={now - st.session_state.get('last_check', 0)}, running check_db()"
        )
        st.session_state["last_check"] = now
        check_db()


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
