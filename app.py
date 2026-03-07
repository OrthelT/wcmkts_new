import streamlit as st
from logging_config import setup_logging

logger = setup_logging(__name__)

pages = {
    "Market Stats": [
        st.Page("pages/market_stats.py", title="📈Market Stats"),
    ],
    "Analysis Tools": [
        st.Page("pages/low_stock.py", title="⚠️Low Stock"),
        st.Page("pages/import_helper.py", title="📦Import Helper"),
        st.Page("pages/doctrine_status.py", title="⚔️Doctrine Status"),
        st.Page("pages/doctrine_report.py", title="📝Doctrine Report"),
        st.Page("pages/build_costs.py", title="🏗️Build Costs"),
        st.Page("pages/pricer.py", title="🏷️Pricer")
    ],
    "Data": [
        st.Page("pages/downloads.py", title="📥Downloads")
    ]
}
pg = st.navigation(pages)

st.set_page_config(
        page_title="WinterCo Markets",
        page_icon="🐼",
        layout="wide"
    )

pg.run()
