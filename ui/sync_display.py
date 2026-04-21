"""
Sync Status Display Component

Shared UI component for displaying database sync status in the sidebar.
Used by Market Stats, Doctrine Status, Doctrine Report, and Low Stock pages.
"""

from datetime import datetime, timedelta, timezone

import streamlit as st

from config import DatabaseConfig
from logging_config import setup_logging
from state.sync_state import minutes_until_next_update
from ui.i18n import translate_text

logger = setup_logging(__name__, log_file="sync_display.log")

# Tolerance before flagging an update as overdue. Ingestion lag of a few
# minutes is normal, so the overdue banner only fires once the window has
# been open for this many minutes past the expected 60-minute interval.
_OVERDUE_GRACE_MINUTES = 10
_UPDATE_INTERVAL_MINUTES = 60


def display_sync_status(language_code: str = "en"):
    """Display sync status in the sidebar."""
    from state.market_state import get_active_market
    active_alias = get_active_market().database_alias

    update_time: datetime | None = None
    time_since: timedelta | None = None
    total_minutes: int | None = None
    display_time = "Unavailable"
    display_time_since = "Unavailable"

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
            suffix = "minute" if total_minutes == 1 else "minutes"
            display_time_since = f"{total_minutes} {suffix}"
        except Exception as exc:
            logger.error(f"Error formatting time since update: {exc}")

    st.sidebar.markdown(
        (
            "<span style='font-size: 14px; color: lightgrey;'>"
            f"*Last ESI update: {display_time}*</span> "
            "<p style='margin: 0;'>"
            "<span style='font-size: 14px; color: lightgrey;'>"
            f"*Time since update: {display_time_since}*</span>"
            "</p>"
        ),
        unsafe_allow_html=True,
    )

    overdue_threshold = _UPDATE_INTERVAL_MINUTES + _OVERDUE_GRACE_MINUTES
    if total_minutes is not None and total_minutes > overdue_threshold:
        overdue_by = total_minutes - _UPDATE_INTERVAL_MINUTES
        st.sidebar.markdown(
            translate_text(language_code, "sync_status.update_overdue", minutes=overdue_by)
        )
        return

    minutes_remaining = minutes_until_next_update()
    if minutes_remaining is None:
        st.sidebar.caption(translate_text(language_code, "sync_status.countdown_unavailable"))
        return

    percent_until_next = (_UPDATE_INTERVAL_MINUTES - minutes_remaining) / _UPDATE_INTERVAL_MINUTES
    if minutes_remaining == 0:
        bar_text = translate_text(language_code, "sync_status.awaiting_update")
    elif minutes_remaining == 1:
        bar_text = translate_text(language_code, "sync_status.minute_remaining")
    else:
        bar_text = translate_text(
            language_code, "sync_status.minutes_remaining", minutes=minutes_remaining
        )
    st.sidebar.progress(percent_until_next, text=bar_text)
