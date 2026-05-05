"""Shared Streamlit layout styling helpers."""

from __future__ import annotations

import streamlit as st

_SIDEBAR_LOGO_PATH = "images/wclogo.png"


def get_global_layout_css() -> str:
    """Return app-wide CSS overrides for Streamlit's default page chrome."""
    return """
<style>
[data-testid="stAppViewContainer"] .main .block-container,
[data-testid="stMainBlockContainer"] {
    padding-top: 1.5rem !important;
}
</style>
""".strip()


def render_global_layout_styles() -> None:
    """Inject app-wide layout CSS once from the Streamlit app shell."""
    st.markdown(get_global_layout_css(), unsafe_allow_html=True)


def render_sidebar_branding(*, logo_path: str = _SIDEBAR_LOGO_PATH) -> None:
    """Render the app logo in Streamlit's sidebar chrome."""
    st.logo(logo_path, size="large", icon_image=logo_path)
