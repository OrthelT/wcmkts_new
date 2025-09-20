import streamlit as st
import datetime
from logging_config import setup_logging
from config import DatabaseConfig
from datetime import timezone, datetime, timedelta
from time import perf_counter

logger = setup_logging(__name__)


def update_wcmkt_state()-> None:
    """
    updates the sessions state with the remote and local state of the wcmkt database using the marketstats table last_update column.
    """
    start_time = perf_counter()
    db = DatabaseConfig("wcmkt")

    local_update_status = {'updated': None, 'needs_update': False, 'time_since': None}
    remote_update_status = {'updated': None, 'needs_update': False, 'time_since': None}

    now = datetime.now(timezone.utc)

    local_update = db.get_most_recent_update("marketstats",remote=False)
    local_update_status['updated'] = local_update
    local_update_status['time_since'] = now - local_update
    local_update_status['needs_update'] = local_update_status['time_since'] > timedelta(hours=2)
    remote_update = db.get_most_recent_update("marketstats",remote=True)
    remote_update_status['updated'] = remote_update
    remote_update_status['time_since'] = now - remote_update
    remote_update_status['needs_update'] = remote_update_status['time_since'] > timedelta(hours=2)


    logger.info("-"*60)
    st.session_state.local_update_status = local_update_status
    logger.info("local_status saved to session state:")
    for k,v in local_update_status.items():
        logger.info(f"{k}: {v}🏠")
    logger.info("-"*60)
    st.session_state.remote_update_status = remote_update_status
    logger.info("remote_status saved to session state:")
    for k,v in remote_update_status.items():
        logger.info(f"{k}: {v}🕧")
    logger.info("-"*60)

    end_time = perf_counter()
    elapsed_time = round((end_time-start_time)*1000, 2)
    logger.info(f"TIME update_wcmkt_state() = {elapsed_time} ms")
    logger.info("-"*60)



if __name__ == "__main__":
    pass
