"""Shared Streamlit layout styling helpers."""

from __future__ import annotations

import streamlit as st

from config import DatabaseConfig
from logging_config import setup_logging
from settings_service import SettingsService

logger = setup_logging(__name__)

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

def render_legal_notice():
    st.markdown("All EVE related materials are property of Fenris Creations. &copy; 2026 Fenris Creations All rights reserved.")
    if SettingsService().show_sde_version:
        render_sde_version_footer()


class _SdeVersionUnavailable(Exception):
    """Raised inside the cached loader so a missing version is not cached."""


@st.cache_data(ttl=3600, show_spinner=False)
def _load_sde_version() -> dict:
    version = DatabaseConfig("sde").get_sde_version()
    if version is None:
        raise _SdeVersionUnavailable
    return version


def render_sde_version_footer() -> None:
    """Show the SDE build below the legal notice; render nothing if unavailable."""
    try:
        version = _load_sde_version()
    except _SdeVersionUnavailable:
        return
    except Exception:
        logger.exception("Failed to read SDE version for footer")
        return
    release = str(version["releaseDate"])[:10]
    st.caption(f"SDE build {version['build']} (released {release})")

