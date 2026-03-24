import streamlit as st
from logging_config import setup_logging
from state.language_state import (
    set_active_language,
    set_language_query_param,
    sync_active_language_with_query_params,
)
from ui.i18n import get_language_label, get_language_options, translate_text

logger = setup_logging(__name__)

st.set_page_config(
    page_title="WinterCo Markets",
    page_icon="🐼",
    layout="wide",
)

available_language_codes = get_language_options()
current_language = sync_active_language_with_query_params(available_language_codes)

_, language_col = st.columns([0.84, 0.16], vertical_alignment="top")
with language_col:
    selected_language = st.selectbox(
        translate_text(current_language, "app.language_label"),
        options=available_language_codes,
        index=available_language_codes.index(current_language),
        format_func=get_language_label,
        key="app_language_selector",
    )

if selected_language != current_language:
    set_active_language(selected_language)
    set_language_query_param(selected_language)
    current_language = selected_language

pages = {
    translate_text(current_language, "nav.section.market_stats"): [
        st.Page(
            "pages/market_dashboard.py",
            title=translate_text(current_language, "nav.page.market_dashboard"),
            default=True,
        ),
        st.Page(
            "pages/market_stats.py",
            title=translate_text(current_language, "nav.page.market_stats"),
        ),
    ],
    translate_text(current_language, "nav.section.analysis_tools"): [
        st.Page("pages/low_stock.py", title=translate_text(current_language, "nav.page.low_stock")),
        st.Page(
            "pages/import_helper.py",
            title=translate_text(current_language, "nav.page.import_helper"),
        ),
        st.Page(
            "pages/builder_helper.py",
            title=translate_text(current_language, "nav.page.builder_helper"),
        ),
        st.Page(
            "pages/doctrine_status.py",
            title=translate_text(current_language, "nav.page.doctrine_status"),
        ),
        st.Page(
            "pages/doctrine_report.py",
            title=translate_text(current_language, "nav.page.doctrine_report"),
        ),
        st.Page(
            "pages/build_costs.py",
            title=translate_text(current_language, "nav.page.build_costs"),
        ),
        st.Page("pages/pricer.py", title=translate_text(current_language, "nav.page.pricer")),
    ],
    translate_text(current_language, "nav.section.data"): [
        st.Page("pages/downloads.py", title=translate_text(current_language, "nav.page.downloads"))
    ],
}
pg = st.navigation(pages)

pg.run()
