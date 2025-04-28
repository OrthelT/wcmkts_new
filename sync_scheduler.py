import datetime as dt
import json
import os
import time
import threading
import streamlit as st
from logging_config import setup_logging

logger = setup_logging()

sync_file = "last_sync_state.json"

with open(sync_file, "r") as f:
    saved_sync_state = json.load(f)

last_saved_sync = dt.datetime.strptime(saved_sync_state['last_sync'], "%Y-%m-%d %H:%M %Z").replace(tzinfo=dt.UTC)
next_saved_sync = dt.datetime.strptime(saved_sync_state['next_sync'], "%Y-%m-%d %H:%M %Z").replace(tzinfo=dt.UTC)


def initialize_sync_state():
    if 'sync_status' not in st.session_state:
        st.session_state.sync_status = "Not yet run"
    if st.session_state.get('last_sync') is None:
        st.session_state['last_sync'] = last_saved_sync
    if st.session_state.get('next_sync') is None:
        st.session_state['next_sync'] = next_saved_sync

#cache for 15 minutes
@st.cache_data(ttl=900)
def check_sync_status():
    """Check if a sync is needed based on the next scheduled sync time"""
    now = dt.datetime.now(dt.UTC)
    
    # If we don't have a last sync time, we should sync
    if not st.session_state.get('last_sync'):
        return True
        
    # If we've passed the next sync time, we should sync
    if now >= st.session_state.next_sync:
        return True
        
    # If we're within 1 minute of the next sync time, we should sync
    time_to_next = st.session_state.next_sync - now
    if time_to_next.total_seconds() <= 60:
        return True
    
    return False

def schedule_next_sync(last_sync: dt.datetime) -> dt.datetime:
    """Schedule the next sync based on the sync times in last_sync_state.json"""
    now = dt.datetime.now(dt.UTC)
    sync_times = saved_sync_state['sync_times']
    
    # Convert sync times to today's datetime objects
    today_sync_times = []
    for time_str in sync_times:
        hour, minute = map(int, time_str.split(':'))
        sync_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # If the time is earlier in the day and we've passed it, schedule it for tomorrow
        if sync_time < now:
            sync_time += dt.timedelta(days=1)
            
        today_sync_times.append(sync_time)
    
    # Sort sync times
    today_sync_times.sort()
    
    # Find the next sync time
    for sync_time in today_sync_times:
        if sync_time > now:
            logger.info(f"Next sync time: {sync_time}, timezone: {sync_time.tzname()}")
            return sync_time
            
    # If no sync times are left today, get the first time for tomorrow
    if today_sync_times:
        logger.info(f"No sync times left for today. Next sync time: {today_sync_times[0]}, timezone: {today_sync_times[0].tzname()}")
        return today_sync_times[0]
    
    # Fallback: if no sync times defined, schedule for 3 hours from now
    return now + dt.timedelta(hours=3)

if __name__ == "__main__":
    pass