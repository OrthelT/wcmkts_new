"""Admin watchlist editor page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from pages.components.header import render_page_title
from services.admin_service import get_admin_service
from services.eve_sso_service import get_eve_sso_service
from settings_service import SettingsService
from state import clear_admin_auth_state, get_admin_identity
from ui.market_selector import render_market_selector

logger = setup_logging(__name__, log_file="admin_page.log")

WATCHLIST_COLUMNS = [
    "type_id",
    "group_id",
    "type_name",
    "group_name",
    "category_id",
    "category_name",
]


def summarize_watchlist_changes(original_df: pd.DataFrame, edited_df: pd.DataFrame) -> dict[str, int]:
    """Return counts for added, changed, and removed watchlist rows."""
    original_map = {
        int(row["type_id"]): {key: row[key] for key in WATCHLIST_COLUMNS if key != "type_id"}
        for row in original_df.to_dict(orient="records")
        if pd.notna(row.get("type_id"))
    }
    edited_map = {
        int(row["type_id"]): {key: row[key] for key in WATCHLIST_COLUMNS if key != "type_id"}
        for row in edited_df.to_dict(orient="records")
        if pd.notna(row.get("type_id"))
    }

    added = len(set(edited_map) - set(original_map))
    removed = len(set(original_map) - set(edited_map))
    changed = sum(
        1 for type_id in set(original_map) & set(edited_map) if original_map[type_id] != edited_map[type_id]
    )
    return {"added": added, "changed": changed, "removed": removed}


def main() -> None:
    market = render_market_selector()
    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    render_page_title("Admin Watchlist", subtitle="Edit the literal watchlist table only.")
    auth_service = get_eve_sso_service()
    signed_identity = get_admin_identity()
    verified_identity = auth_service.verify_signed_admin_identity(signed_identity)
    if verified_identity is None:
        st.warning("Admin login required.")
        st.page_link("pages/admin_login.py", label="Open Admin Login")
        st.stop()

    settings = SettingsService()
    service = get_admin_service()
    watchlist_df = service.get_watchlist()
    if watchlist_df.empty:
        watchlist_df = pd.DataFrame(columns=WATCHLIST_COLUMNS)

    st.caption(
        f"Signed in as {verified_identity['character_name']} ({verified_identity['character_id']})"
    )
    st.caption(f"Write target: {settings.admin_write_target} | Market: {market.name}")

    col_logout, col_login = st.columns(2)
    with col_logout:
        if st.button("Log out", use_container_width=True):
            clear_admin_auth_state()
            st.switch_page("pages/admin_login.py")
    with col_login:
        st.page_link("pages/admin_login.py", label="Login Page", use_container_width=True)

    edited_df = st.data_editor(
        watchlist_df,
        hide_index=True,
        num_rows="dynamic",
        use_container_width=True,
        key="admin_watchlist_editor",
        column_config={
            "type_id": st.column_config.NumberColumn("Type ID", required=True, step=1, format="%d"),
            "group_id": st.column_config.NumberColumn("Group ID", required=True, step=1, format="%d"),
            "type_name": st.column_config.TextColumn("Type Name", required=True),
            "group_name": st.column_config.TextColumn("Group Name", required=True),
            "category_id": st.column_config.NumberColumn(
                "Category ID", required=True, step=1, format="%d"
            ),
            "category_name": st.column_config.TextColumn("Category Name", required=True),
        },
    )

    summary = summarize_watchlist_changes(watchlist_df, edited_df)
    col_added, col_changed, col_removed = st.columns(3)
    with col_added:
        st.metric("Added", summary["added"])
    with col_changed:
        st.metric("Changed", summary["changed"])
    with col_removed:
        st.metric("Removed", summary["removed"])

    if st.button("Save Watchlist", type="primary", use_container_width=True):
        try:
            result = service.save_watchlist(edited_df, signed_identity=signed_identity)
            st.success(f"Saved {result['row_count']} watchlist rows.")
            st.rerun()
        except Exception as exc:
            logger.warning("Watchlist save failed: %s", exc)
            st.error(str(exc))


if __name__ == "__main__":
    main()
