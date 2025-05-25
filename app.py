import streamlit as st

pages = {
    "Market Stats": [
        st.Page("pages/market_stats.py", title="📈Market Stats"),
    ],
    "Analysis Tools": [
        st.Page("pages/low_stock.py", title="⚠️Low Stock"),
        st.Page("pages/doctrine_status.py", title="⚔️Doctrine Status"),
        st.Page("pages/doctrine_report.py", title="📝Doctrine Report")
    ]
}
pg = st.navigation(pages)

st.set_page_config(
        page_title="WinterCo Markets",
        page_icon="🐼",
        layout="wide"
    )


pg.run()

