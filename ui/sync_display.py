"""
Sync Status Display Component

Shared UI component for displaying database sync status in the sidebar.
Used by Market Stats, Doctrine Status, Doctrine Report, and Low Stock pages.
"""

from datetime import datetime, timedelta, timezone

import streamlit as st

from config import DatabaseConfig
from logging_config import setup_logging
from ui.i18n import translate_text

logger = setup_logging(__name__, log_file="sync_display.log")


def display_sync_status(language_code: str = "en"):
    """Display sync status in the sidebar."""
    from state.market_state import get_active_market
    active_alias = get_active_market().database_alias

    update_time: datetime | None = None
    time_since: timedelta | None = None
    display_time = translate_text(language_code, "common.unavailable")
    display_time_since = translate_text(language_code, "common.unavailable")

    if "local_update_status" not in st.session_state:
        try:
            from state.sync_state import update_wcmkt_state
            update_wcmkt_state()
        except Exception as exc:
            logger.error(f"Error initializing local_update_status: {exc}")

    status = st.session_state.get("local_update_status")
    if status is not None:
        update_time = status.get("updated")
        time_since = status.get("time_since")
        if update_time is None:
            try:
                update_time = DatabaseConfig(active_alias).get_most_recent_update("marketstats", remote=False)
                status["updated"] = update_time
            except Exception as exc:
                logger.error(f"Error fetching cached update time: {exc}")
        if time_since is None and update_time is not None:
            time_since = datetime.now(tz=timezone.utc) - update_time
            status["time_since"] = time_since
    else:
        try:
            update_time = DatabaseConfig(active_alias).get_most_recent_update("marketstats", remote=False)
        except Exception as exc:
            logger.error(f"Error fetching update time: {exc}")
        if update_time is not None:
            time_since = datetime.now(tz=timezone.utc) - update_time

    if update_time is not None:
        try:
            display_time = update_time.strftime("%m-%d | %H:%M UTC")
        except Exception as exc:
            logger.error(f"Error formatting update time: {exc}")

    if time_since is not None:
        try:
            total_minutes = int(time_since.total_seconds() // 60)
            suffix = (
                translate_text(language_code, "sync.minute")
                if total_minutes == 1
                else translate_text(language_code, "sync.minutes")
            )
            display_time_since = f"{total_minutes} {suffix}"
        except Exception as exc:
            logger.error(f"Error formatting time since update: {exc}")

    st.sidebar.markdown(
        (
            "<span style='font-size: 14px; color: lightgrey;'>"
            f"*{translate_text(language_code, 'sync.last_esi_update')}: {display_time}*</span> "
            "<p style='margin: 0;'>"
            "<span style='font-size: 14px; color: lightgrey;'>"
            f"*{translate_text(language_code, 'sync.time_since_update')}: {display_time_since}*</span>"
            "</p>"
        ),
        unsafe_allow_html=True,
    )
