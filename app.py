import streamlit as st
from db_handler import init_db
from sync_state import check_updates_and_sync
import os
import pathlib
from logging_config import setup_logging

logger = setup_logging(__name__)

pages = {
    "Market Stats": [
        st.Page("pages/market_stats.py", title="📈Market Stats"),
    ],
    "Analysis Tools": [
        st.Page("pages/low_stock.py", title="⚠️Low Stock"),
        st.Page("pages/doctrine_status.py", title="⚔️Doctrine Status"),
        st.Page("pages/doctrine_report.py", title="📝Doctrine Report"),
        st.Page("pages/build_costs.py", title="🏗️Build Costs")
    ]
}
pg = st.navigation(pages)

st.set_page_config(
        page_title="WinterCo Markets",
        page_icon="🐼",
        layout="wide"
    )

wcmkt_path = pathlib.Path("wcmkt*.db*")

if not st.session_state.get('db_initialized'):
    result = init_db()
    if result:
        st.toast("Database initialized successfully", icon="✅")
        st.session_state.db_initialized = True
    else:
        st.toast("Database initialization failed", icon="❌")
        st.session_state.db_initialized = False

if wcmkt_path.exists():
    logger.info(f"wcmkt_path exists: {wcmkt_path} ✅")
    check_updates_and_sync()

pg.run()