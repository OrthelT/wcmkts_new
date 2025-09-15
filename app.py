import streamlit as st
from db_handler import init_db



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

if not st.session_state.get('db_initialized'):
    result = init_db()
    if result:
        st.toast("Database initialized successfully", icon="✅")
        st.session_state.db_initialized = True
    else:
        st.toast("Database initialization failed", icon="❌")
        st.session_state.db_initialized = False



pg.run()
