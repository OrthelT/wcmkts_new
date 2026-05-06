"""
Shared page header helpers.

These helpers keep page titles and logos aligned cleanly while the language
switch lives in the sidebar.
"""

from __future__ import annotations

import streamlit as st

from state.language_state import set_active_language, set_language_query_param
from ui.i18n import get_language_label, get_language_options, translate_text

_GLOBAL_LANGUAGE_SELECTOR_KEY = "app_language_selector"


def render_language_selector(
    current_language: str,
    *,
    sidebar: bool = False,
    label_visibility: str = "visible",
    key: str = _GLOBAL_LANGUAGE_SELECTOR_KEY,
) -> str:
    """Render the language switcher and persist changes to session state and the URL."""
    available_language_codes = get_language_options()
    if current_language not in available_language_codes:
        current_language = available_language_codes[0]

    widget = st.sidebar.selectbox if sidebar else st.selectbox
    selected_language = widget(
        translate_text(current_language, "app.language_label"),
        options=available_language_codes,
        index=available_language_codes.index(current_language),
        format_func=get_language_label,
        key=key,
        label_visibility=label_visibility,
    )

    if selected_language != current_language:
        set_active_language(selected_language)
        set_language_query_param(selected_language)
        st.rerun()

    return selected_language


def render_page_title(title: str, *, subtitle: str | None = None) -> None:
    """Render a standard page title and optional subtitle."""
    st.title(title)
    if subtitle:
        st.markdown(subtitle)
