"""Admin watchlist editor page."""

from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit.elements.lib.layout_utils import WidthWithoutContent

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from pages.components.header import render_page_title
from repositories.sde_repo import SDERepository
from config import DatabaseConfig
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

PENDING_ADDS_KEY = "admin_watchlist_pending_adds"
PENDING_REMOVES_KEY = "admin_watchlist_pending_removes"
REMOVE_EDITOR_KEY = "admin_watchlist_remove_editor"
NOTICE_KEY = "admin_watchlist_notice"


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


def lookup_sde_row(
    sdetypes_df: pd.DataFrame,
    *,
    type_id: int | None = None,
    type_name: str | None = None,
) -> dict | None:
    """Resolve one sdeTypes row to a watchlist-shaped dict.

    Exactly one of `type_id` or `type_name` must be provided. Type-name
    matching is case-sensitive (mirrors AdminRepository._resolve_type_metadata
    and the project no-wrong-data rule). Returns None when no row matches.
    """
    if (type_id is None) == (type_name is None):
        raise ValueError("exactly one of type_id or type_name must be provided")

    if type_id is not None:
        match = sdetypes_df[sdetypes_df["typeID"] == int(type_id)]
    else:
        match = sdetypes_df[sdetypes_df["typeName"] == type_name]

    if match.empty:
        return None

    row = match.iloc[0]
    return {
        "type_id": int(row["typeID"]),
        "group_id": int(row["groupID"]),
        "type_name": str(row["typeName"]),
        "group_name": str(row["groupName"]),
        "category_id": int(row["categoryID"]),
        "category_name": str(row["categoryName"]),
    }


@st.cache_resource
def _get_sde_types_for_admin() -> pd.DataFrame:
    """Load the full sdeTypes table once per session for admin autocomplete + lookups."""
    return SDERepository(DatabaseConfig("sde")).get_sde_table("sdetypes")


def _ensure_state() -> None:
    if PENDING_ADDS_KEY not in st.session_state:
        st.session_state[PENDING_ADDS_KEY] = []
    if PENDING_REMOVES_KEY not in st.session_state:
        st.session_state[PENDING_REMOVES_KEY] = []


def _render_notice() -> None:
    notice = st.session_state.pop(NOTICE_KEY, None)
    if notice:
        st.success(notice)


def _render_add_section(watchlist_df: pd.DataFrame, sdetypes_df: pd.DataFrame) -> dict | None:
    """Render the add-form + pending-queue UI. Returns a payload dict when the
    admin clicks 'Save all pending adds' (caller handles the actual save)."""
    st.subheader("Add Items")

    pending: list[dict] = st.session_state[PENDING_ADDS_KEY]

    if pending:
        st.markdown(f"**Pending adds ({len(pending)})**")
        pending_df = pd.DataFrame(pending, columns=WATCHLIST_COLUMNS)
        st.dataframe(pending_df, hide_index=True, width="content")

        drop_label = st.selectbox(
            "Drop one from queue",
            options=["(none)"] + [f"{row['type_name']} ({row['type_id']})" for row in pending],
        )
        col_drop, col_clear = st.columns(2)
        with col_drop:
            if st.button("Remove from queue", disabled=drop_label == "(none)", width="content"):
                st.session_state[PENDING_ADDS_KEY] = [
                    row for row in pending
                    if f"{row['type_name']} ({row['type_id']})" != drop_label
                ]
                st.rerun()
        with col_clear:
            if st.button("Clear queue", width="content"):
                st.session_state[PENDING_ADDS_KEY] = []
                st.rerun()

    existing_ids = set(int(tid) for tid in watchlist_df["type_id"].tolist()) if not watchlist_df.empty else set()
    pending_ids = {row["type_id"] for row in pending}

    type_names = sorted(sdetypes_df["typeName"].astype(str).tolist())

    with st.form("admin_add_watchlist_form", clear_on_submit=True):
        selected_name = st.selectbox(
            "Type name",
            options=type_names,
            index=None,
            placeholder="Start typing to filter…",
        )
        queue_clicked = st.form_submit_button("Queue for add", type="primary", width="content")

    if queue_clicked:
        try:
            if not selected_name:
                raise ValueError("Select a type name from the dropdown.")
            resolved = lookup_sde_row(sdetypes_df, type_name=selected_name)

            if resolved is None:
                raise ValueError("Unknown EVE type — not found in sdeTypes.")
            if resolved["type_id"] in existing_ids:
                raise ValueError(
                    f"{resolved['type_name']} ({resolved['type_id']}) is already in the watchlist."
                )
            if resolved["type_id"] in pending_ids:
                raise ValueError(
                    f"{resolved['type_name']} ({resolved['type_id']}) is already in the pending queue."
                )

            st.session_state[PENDING_ADDS_KEY] = pending + [resolved]
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))

    can_commit = bool(pending)
    if st.button(
        "Save all pending adds",
        type="primary",
        width="content",
        disabled=not can_commit,
        key="admin_watchlist_commit_adds",
    ):
        new_full = pd.concat(
            [watchlist_df[WATCHLIST_COLUMNS], pd.DataFrame(pending, columns=WATCHLIST_COLUMNS)],
            ignore_index=True,
        )
        return {"action": "save_adds", "new_df": new_full}

    return None


def _render_remove_section(watchlist_df: pd.DataFrame) -> dict | None:
    """Render the remove-table UI. Returns a payload when the admin confirms removal."""
    st.subheader("Remove Items")

    if watchlist_df.empty:
        st.info("Watchlist is empty.")
        return None

    display_df = watchlist_df[WATCHLIST_COLUMNS].copy()
    display_df.insert(0, "Remove", False)

    edited = st.data_editor(
        display_df,
        hide_index=True,
        width="stretch",
        key=REMOVE_EDITOR_KEY,
        disabled=WATCHLIST_COLUMNS,
        column_config={
            "Remove": st.column_config.CheckboxColumn("Remove", default=False),
            "type_id": st.column_config.NumberColumn("Type ID", format="%d"),
            "group_id": st.column_config.NumberColumn("Group ID", format="%d"),
            "type_name": st.column_config.TextColumn("Type Name"),
            "group_name": st.column_config.TextColumn("Group Name"),
            "category_id": st.column_config.NumberColumn("Category ID", format="%d"),
            "category_name": st.column_config.TextColumn("Category Name"),
        },
    )

    ticked_ids = [int(row["type_id"]) for row in edited.to_dict(orient="records") if row.get("Remove")]
    pending_removes: list[int] = st.session_state[PENDING_REMOVES_KEY]

    if pending_removes:
        removed_rows = watchlist_df[watchlist_df["type_id"].isin(pending_removes)]
        st.warning(
            "About to remove "
            + ", ".join(
                f"{row['type_name']} ({row['type_id']})"
                for _, row in removed_rows.iterrows()
            )
            + ". Click 'Confirm remove' to proceed, or 'Cancel' to abort."
        )
        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button("Confirm remove", type="primary", width="content"):
                new_full = watchlist_df[~watchlist_df["type_id"].isin(pending_removes)][
                    WATCHLIST_COLUMNS
                ].reset_index(drop=True)
                return {"action": "save_removes", "new_df": new_full}
        with col_cancel:
            if st.button("Cancel", width="content"):
                st.session_state[PENDING_REMOVES_KEY] = []
                st.rerun()
        return None

    if st.button(
        "Remove selected",
        type="secondary",
        width="content",
        disabled=not ticked_ids,
        key="admin_watchlist_stage_removes",
    ):
        st.session_state[PENDING_REMOVES_KEY] = ticked_ids
        st.rerun()

    return None


def _commit_save(service, payload: dict, signed_identity: dict | None) -> None:
    new_df = payload["new_df"]
    if new_df.empty:
        st.error("Refusing to save an empty watchlist.")
        return
    try:
        result = service.save_watchlist(new_df, signed_identity=signed_identity)
        added = result.get("added_type_ids", [])
        removed = result.get("removed_type_ids", [])
        parts = [f"Saved {result['row_count']} watchlist rows."]
        if added:
            parts.append(f"Added: {added}.")
        if removed:
            parts.append(f"Removed: {removed}.")
        st.session_state[NOTICE_KEY] = " ".join(parts)
        st.session_state[PENDING_ADDS_KEY] = []
        st.session_state[PENDING_REMOVES_KEY] = []
        st.rerun()
    except ValueError as exc:
        logger.error("Watchlist save rejected: %s", exc, exc_info=True)
        st.error(str(exc))
    except PermissionError as exc:
        logger.error("Watchlist save unauthorized: %s", exc, exc_info=True)
        st.error("Admin session expired or unauthorized. Please log in again.")
    except Exception as exc:
        logger.error("Watchlist save failed: %s", exc, exc_info=True)
        st.error("Failed to save watchlist. Check admin logs for details.")


def main() -> None:
    market = render_market_selector()
    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    render_page_title(
        "Admin Watchlist",
        subtitle="Add items from sdeTypes; remove items via the table below.",
    )
    auth_service = get_eve_sso_service()
    signed_identity = get_admin_identity()
    verified_identity = auth_service.verify_signed_admin_identity(signed_identity)
    if verified_identity is None:
        st.warning("Admin login required.")
        st.page_link("pages/admin_login.py", label="Open Admin Login")
        st.stop()

    _ensure_state()

    settings = SettingsService()
    service = get_admin_service()
    watchlist_df = service.get_watchlist()
    if watchlist_df.empty:
        watchlist_df = pd.DataFrame(columns=WATCHLIST_COLUMNS)
    sdetypes_df = _get_sde_types_for_admin()

    st.caption(
        f"Signed in as {verified_identity['character_name']} ({verified_identity['character_id']})"
    )
    st.caption(f"Write target: {settings.admin_write_target} | Market: {market.name}")

    col_logout, col_login = st.columns(2)
    with col_logout:
        if st.button("Log out", width="content"):
            clear_admin_auth_state()
            st.switch_page("pages/admin_login.py")
    with col_login:
        st.page_link("pages/admin_login.py", label="Login Page", width="content")

    _render_notice()

    st.divider()
    payload = _render_add_section(watchlist_df, sdetypes_df)
    if payload is not None:
        _commit_save(service, payload, signed_identity)
        return

    st.divider()
    payload = _render_remove_section(watchlist_df)
    if payload is not None:
        _commit_save(service, payload, signed_identity)


if __name__ == "__main__":
    main()
