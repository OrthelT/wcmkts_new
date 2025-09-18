from ast import Dict
import streamlit as st
import datetime as dt
import json
import os
from logging_config import setup_logging
from models import UpdateLog
from sqlalchemy import select
from sqlalchemy.orm import Session
from config import DatabaseConfig
from datetime import timezone, datetime, timedelta

logger = setup_logging(__name__)



# Static sync times every 2 hours starting at 12:00
SYNC_SCHEDULE = ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00", "00:00", "02:00", "04:00", "06:00", "08:00", "10:00"]

def sync_state(sync_time: dt.datetime = None) -> dict:
    """
    Manages database synchronization state with 2-hour intervals.

    Args:
        sync_time: Optional datetime object for the current sync time.
                  If provided, updates last_sync. If None, only checks sync status.

    Returns:
        dict: Contains last_sync, next_sync, and sync_status
    """
    # Use current time for calculations
    current_time = dt.datetime.now(dt.timezone.utc)
    logger.info(f"current_time: {current_time}")

    #initialise session state
    if 'sync_status' not in st.session_state:
        st.session_state.sync_status = "Not yet run"

    # Load existing state or create default
    json_file = "last_sync_state.json"
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r') as f:
                saved_sync = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            saved_sync = {
                "last_sync": "2025-01-01 00:00 UTC",
                "next_sync": "2025-01-01 12:00 UTC",
                "sync_times": SYNC_SCHEDULE
            }
    else:
        saved_sync = {
            "last_sync": "2025-01-01 00:00 UTC",
            "next_sync": "2025-01-01 12:00 UTC",
            "sync_times": SYNC_SCHEDULE
        }

    if sync_time is not None:
        current_sync_str = sync_time.strftime("%Y-%m-%d %H:%M UTC")
        next_sync_datetime = next_sync_time(sync_time)
        next_sync_str = next_sync_datetime.strftime("%Y-%m-%d %H:%M UTC")
        logger.info(f"saved_sync: {saved_sync}")
        logger.info(f"current_sync_str: {current_sync_str}")
    else:
        current_sync_str = saved_sync["last_sync"]
        next_sync_datetime = next_sync_time(saved_sync["last_sync"])
        next_sync_str = next_sync_datetime.strftime("%Y-%m-%d %H:%M UTC")

    # Parse the last_sync time (now updated if sync_time was provided)
    last_sync_datetime = dt.datetime.strptime(saved_sync["last_sync"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=dt.timezone.utc)
    logger.info(f"last_sync_datetime: {last_sync_datetime}")

    # Check if we need to sync based on last_sync time
    # If last_sync was more than 2 hours ago, we need to sync
    next_sync_datetime = dt.datetime.strptime(saved_sync["next_sync"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=dt.timezone.utc)
    time_since_next_sync = current_time - last_sync_datetime
    sync_needed = current_time > next_sync_datetime
    logger.info(f"sync_needed: {sync_needed}")
    logger.info(f"time_since_next_sync: {time_since_next_sync}")

    # Use existing next_sync time

    # Update session state and saved_sync
    st.session_state["last_sync"] = current_sync_str
    st.session_state["next_sync"] = next_sync_str

    saved_sync["last_sync"] = current_sync_str
    saved_sync["next_sync"] = next_sync_str
    saved_sync["sync_times"] = SYNC_SCHEDULE
    saved_sync["sync_needed"] = sync_needed
    # Write to JSON file
    with open(json_file, 'w') as f:
        json.dump(saved_sync, f, indent=2)

    return saved_sync

def update_saved_sync():
    sync_info = {
        "last_sync": st.session_state.last_sync,
        "next_sync": st.session_state.next_sync,
        "sync_times": SYNC_SCHEDULE
    }
    with open("last_sync_state.json", "w") as f:
        json.dump(sync_info, f, indent=2)

def next_sync_time(last_sync: dt.datetime | str):
    """ASSUMES SYNC_SCHEDULE = ["12:00", "14:00", "16:00", "18:00", "20:00", "22:00", "00:00", "02:00", "04:00", "06:00", "08:00", "10:00"] AND THAT SYNC IS NEEDED ON TWO HOUR INTERVALS"""
    if isinstance(last_sync, str):
        last_sync = dt.datetime.strptime(last_sync, "%Y-%m-%d %H:%M UTC").replace(tzinfo=dt.timezone.utc)

    last_sync_hour = last_sync.hour
    current_time = dt.datetime.now(dt.timezone.utc)

    def test_sync_in_past(test_sync_time):
        now_plus_2hrs = current_time + dt.timedelta(hours=2)

        if test_sync_time < current_time:
            if now_plus_2hrs.hour % 2 == 0:
                return current_time.replace(minute=0, second=0, microsecond=0)
            else:
                return current_time.replace(minute=0, second=0, microsecond=0) - dt.timedelta(hours=1)
        else:
            return test_sync_time

    if last_sync_hour >= 22:
        next_sync = last_sync.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(days=1)

    elif last_sync_hour % 2 == 0:
        next_sync = last_sync.replace(hour=last_sync_hour + 2, minute=0, second=0, microsecond=0)
    else:
        next_sync = last_sync.replace(hour=last_sync_hour + 1, minute=0, second=0, microsecond=0)

    next_sync = test_sync_in_past(next_sync)

    return next_sync


def get_update_status(table_names: list[str] | str = "all", remote: bool = False)-> dict:
    """
    Check the updates for the tables in the database
    if all is selected or no table is selected marketstats, market_history, doctrines, marketorders are returned
    if a specific table is selected: only that table is returned
    Args:
        table_names: list[str] - The tables to check the updates for
        remote: bool - If True, check the remote database, if False, check the local database

    Returns:
        update_status[table_name]["updated"] - The timestamp of the last update
        update_status[table_name]["needs_update"] - If the update is needed
        update_status[table_name]["time_since"] - The time since the last update
    """

    db = DatabaseConfig("wcmkt")

    update_status = {'marketstats': {'updated': None, 'needs_update': False, 'time_since': None}, 'market_history': {'updated': None, 'needs_update': False, 'time_since': None}, 'doctrines': {'updated': None, 'needs_update': False, 'time_since': None}, 'marketorders': {'updated': None, 'needs_update': False, 'time_since': None}}

    if table_names == "all":
        table_names = ["marketstats", "market_history", "doctrines", "marketorders"]
    else:
        table_names = table_names

    now = datetime.now(timezone.utc)

    for table in table_names:
        update = db.get_most_recent_update(table,remote=remote)
        update = update[0].replace(tzinfo=timezone.utc) if update is not None else None
        update_status[table]["updated"] = update if update is not None else None
        update_status[table]["time_since"] = now - update if update is not None else None
        update_status[table]["needs_update"] = update_status[table]["time_since"] > timedelta(hours=2)

    return update_status

def check_updates_and_sync():
    local_update_status = get_update_status(table_names=['all'], remote=False)
    st.session_state.local_update_status = local_update_status
    for key in local_update_status.keys():
        if local_update_status[key]["updated"] is None:
            db = DatabaseConfig("wcmkt")
            db.sync()
            st.toast(f"{key} updated", icon="✅")
        elif local_update_status[key]["updated"] is not None:
            if local_update_status[key]["updated"] > st.session_state.local_update_status[key]["updated"]:
                db = DatabaseConfig("wcmkt")
                db.sync()
                st.toast(f"{key} updated", icon="✅")
        else:
            if local_update_status[key]["updated"] > st.session_state.local_update_status[key]["updated"]:
                db = DatabaseConfig("wcmkt")
                db.sync()
                st.toast(f"{key} updated", icon="✅")




if __name__ == "__main__":

    print(DatabaseConfig("wcmkt").get_most_recent_update("marketstats", remote=False))