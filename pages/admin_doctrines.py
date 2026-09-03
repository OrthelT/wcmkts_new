"""Admin doctrine fit editor page."""

from __future__ import annotations

import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from pages.components.header import render_page_title
from services.eve_sso_service import get_eve_sso_service
from state import get_admin_identity
from ui.market_selector import render_market_selector

logger = setup_logging(__name__, log_file="admin_doctrines_page.log")


def main() -> None:
    market = render_market_selector()
    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    render_page_title("Admin Doctrines", subtitle="Create doctrines and manage their fits.")

    auth_service = get_eve_sso_service()
    signed_identity = get_admin_identity()
    verified_identity = auth_service.verify_signed_admin_identity(signed_identity)
    if verified_identity is None:
        st.warning("Admin login required.")
        st.page_link("pages/admin_login.py", label="Open Admin Login")
        st.stop()

    st.warning(
        "Admin is disabled during the pyturso migration. Reads and writes both "
        "route through the remote write path, which was removed when pyturso "
        "made every engine local. Re-enabling it needs a local-write-plus-push "
        "rework, deferred by decision."
    )
    st.stop()


if __name__ == "__main__":
    main()
