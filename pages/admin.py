"""Admin watchlist editor page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from pages.components.header import render_page_title
from repositories.sde_repo import SDERepository
from config import DatabaseConfig
from services.admin_service import get_admin_service
from services.eve_sso_service import get_eve_sso_service
from settings_service import SettingsService
from state import clear_admin_auth_state, get_active_language, get_admin_identity
from ui.i18n import translate_text
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


def _admin_text(language_code: str, key: str, **kwargs) -> str:
    return translate_text(language_code, f"admin.{key}", **kwargs)


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
    """Resolve one sdeTypes row to a watchlist-shaped dict (case-sensitive name match)."""
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


def _render_add_section(
    watchlist_df: pd.DataFrame,
    sdetypes_df: pd.DataFrame,
    language_code: str,
) -> dict | None:
    """Render the add-form + pending-queue UI. Returns a payload dict when the
    admin clicks 'Save all pending adds' (caller handles the actual save)."""
    st.subheader(_admin_text(language_code, "watchlist.add_items"))

    pending: list[dict] = st.session_state[PENDING_ADDS_KEY]

    if pending:
        st.markdown(
            f"**{_admin_text(language_code, 'watchlist.pending_adds', count=len(pending))}**"
        )
        pending_df = pd.DataFrame(pending, columns=WATCHLIST_COLUMNS)
        st.dataframe(pending_df, hide_index=True, width="content")

        drop_label = st.selectbox(
            _admin_text(language_code, "watchlist.drop_one_from_queue"),
            options=[_admin_text(language_code, "watchlist.none_option")]
            + [f"{row['type_name']} ({row['type_id']})" for row in pending],
        )
        col_drop, col_clear = st.columns(2)
        with col_drop:
            if st.button(
                _admin_text(language_code, "watchlist.remove_from_queue"),
                disabled=drop_label == _admin_text(language_code, "watchlist.none_option"),
                width="content",
            ):
                st.session_state[PENDING_ADDS_KEY] = [
                    row for row in pending
                    if f"{row['type_name']} ({row['type_id']})" != drop_label
                ]
                st.rerun()
        with col_clear:
            if st.button(_admin_text(language_code, "watchlist.clear_queue"), width="content"):
                st.session_state[PENDING_ADDS_KEY] = []
                st.rerun()

    existing_ids = set(int(tid) for tid in watchlist_df["type_id"].tolist()) if not watchlist_df.empty else set()
    pending_ids = {row["type_id"] for row in pending}

    type_names = sorted(sdetypes_df["typeName"].astype(str).tolist())

    with st.form("admin_add_watchlist_form", clear_on_submit=True):
        selected_name = st.selectbox(
            _admin_text(language_code, "watchlist.type_name"),
            options=type_names,
            index=None,
            placeholder=_admin_text(language_code, "watchlist.type_name_placeholder"),
        )
        queue_clicked = st.form_submit_button(
            _admin_text(language_code, "watchlist.queue_for_add"),
            type="primary",
            width="content",
        )

    if queue_clicked:
        try:
            if not selected_name:
                raise ValueError(_admin_text(language_code, "watchlist.select_type_name"))
            resolved = lookup_sde_row(sdetypes_df, type_name=selected_name)

            if resolved is None:
                raise ValueError(_admin_text(language_code, "watchlist.unknown_type"))
            if resolved["type_id"] in existing_ids:
                raise ValueError(
                    _admin_text(
                        language_code,
                        "watchlist.already_in_watchlist",
                        type_name=resolved["type_name"],
                        type_id=resolved["type_id"],
                    )
                )
            if resolved["type_id"] in pending_ids:
                raise ValueError(
                    _admin_text(
                        language_code,
                        "watchlist.already_pending",
                        type_name=resolved["type_name"],
                        type_id=resolved["type_id"],
                    )
                )

            st.session_state[PENDING_ADDS_KEY] = pending + [resolved]
            st.rerun()
        except ValueError as exc:
            st.warning(str(exc))

    can_commit = bool(pending)
    if st.button(
        _admin_text(language_code, "watchlist.save_pending_adds"),
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


def _render_remove_section(watchlist_df: pd.DataFrame, language_code: str) -> dict | None:
    """Render the remove-table UI. Returns a payload when the admin confirms removal."""
    st.subheader(_admin_text(language_code, "watchlist.remove_items"))

    if watchlist_df.empty:
        st.info(_admin_text(language_code, "watchlist.empty"))
        return None

    display_df = watchlist_df[WATCHLIST_COLUMNS].copy()
    remove_column = _admin_text(language_code, "watchlist.column_remove")
    display_df.insert(0, remove_column, False)

    edited = st.data_editor(
        display_df,
        hide_index=True,
        width="stretch",
        key=REMOVE_EDITOR_KEY,
        disabled=WATCHLIST_COLUMNS,
        column_config={
            remove_column: st.column_config.CheckboxColumn(remove_column, default=False),
            "type_id": st.column_config.NumberColumn(
                _admin_text(language_code, "watchlist.column_type_id"), format="%d"
            ),
            "group_id": st.column_config.NumberColumn(
                _admin_text(language_code, "watchlist.column_group_id"), format="%d"
            ),
            "type_name": st.column_config.TextColumn(
                _admin_text(language_code, "watchlist.column_type_name")
            ),
            "group_name": st.column_config.TextColumn(
                _admin_text(language_code, "watchlist.column_group_name")
            ),
            "category_id": st.column_config.NumberColumn(
                _admin_text(language_code, "watchlist.column_category_id"), format="%d"
            ),
            "category_name": st.column_config.TextColumn(
                _admin_text(language_code, "watchlist.column_category_name")
            ),
        },
    )

    ticked_ids = [
        int(row["type_id"]) for row in edited.to_dict(orient="records") if row.get(remove_column)
    ]
    pending_removes: list[int] = st.session_state[PENDING_REMOVES_KEY]

    if pending_removes:
        removed_rows = watchlist_df[watchlist_df["type_id"].isin(pending_removes)]
        removed_items = ", ".join(
                f"{row['type_name']} ({row['type_id']})"
                for _, row in removed_rows.iterrows()
            )
        st.warning(
            _admin_text(language_code, "watchlist.remove_warning", items=removed_items)
        )
        col_confirm, col_cancel = st.columns(2)
        with col_confirm:
            if st.button(
                _admin_text(language_code, "watchlist.confirm_remove"),
                type="primary",
                width="content",
            ):
                new_full = watchlist_df[~watchlist_df["type_id"].isin(pending_removes)][
                    WATCHLIST_COLUMNS
                ].reset_index(drop=True)
                return {"action": "save_removes", "new_df": new_full}
        with col_cancel:
            if st.button(_admin_text(language_code, "watchlist.cancel"), width="content"):
                st.session_state[PENDING_REMOVES_KEY] = []
                st.rerun()
        return None

    if st.button(
        _admin_text(language_code, "watchlist.remove_selected"),
        type="secondary",
        width="content",
        disabled=not ticked_ids,
        key="admin_watchlist_stage_removes",
    ):
        st.session_state[PENDING_REMOVES_KEY] = ticked_ids
        st.rerun()

    return None


def _commit_save(
    service,
    payload: dict,
    signed_identity: dict | None,
    language_code: str = "en",
) -> None:
    new_df = payload["new_df"]
    if new_df.empty:
        st.error(_admin_text(language_code, "watchlist.refuse_empty"))
        return
    try:
        result = service.save_watchlist(new_df, signed_identity=signed_identity)
        added = result.get("added_type_ids", [])
        removed = result.get("removed_type_ids", [])
        parts = [
            _admin_text(
                language_code,
                "watchlist.save_success",
                row_count=result["row_count"],
            )
        ]
        if added:
            parts.append(_admin_text(language_code, "watchlist.added_ids", ids=added))
        if removed:
            parts.append(_admin_text(language_code, "watchlist.removed_ids", ids=removed))
        st.session_state[NOTICE_KEY] = " ".join(parts)
        st.session_state[PENDING_ADDS_KEY] = []
        st.session_state[PENDING_REMOVES_KEY] = []
        st.rerun()
    except ValueError as exc:
        logger.error("Watchlist save rejected: %s", exc, exc_info=True)
        st.error(str(exc))
    except PermissionError as exc:
        logger.error("Watchlist save unauthorized: %s", exc, exc_info=True)
        st.error(_admin_text(language_code, "common.session_expired"))
    except Exception as exc:
        logger.error("Watchlist save failed: %s", exc, exc_info=True)
        st.error(_admin_text(language_code, "watchlist.save_failed"))


def main() -> None:
    language_code = get_active_language()
    market = render_market_selector()
    if not ensure_market_db_ready(market.database_alias):
        st.error(
            _admin_text(language_code, "common.database_unavailable", market_name=market.name)
        )
        st.stop()

    render_page_title(
        _admin_text(language_code, "watchlist.title"),
        subtitle=_admin_text(language_code, "watchlist.subtitle"),
    )
    auth_service = get_eve_sso_service()
    signed_identity = get_admin_identity()
    verified_identity = auth_service.verify_signed_admin_identity(signed_identity)
    if verified_identity is None:
        st.warning(_admin_text(language_code, "common.login_required"))
        st.page_link("pages/admin_login.py", label=_admin_text(language_code, "common.open_login"))
        st.stop()

    _ensure_state()

    settings = SettingsService()
    service = get_admin_service()
    watchlist_df = service.get_watchlist()
    if watchlist_df.empty:
        watchlist_df = pd.DataFrame(columns=WATCHLIST_COLUMNS)
    sdetypes_df = _get_sde_types_for_admin()

    st.caption(
        _admin_text(
            language_code,
            "common.signed_in_as",
            character_name=verified_identity["character_name"],
            character_id=verified_identity["character_id"],
        )
    )
    st.caption(
        _admin_text(
            language_code,
            "common.write_target_market",
            write_target=settings.admin_write_target,
            market_name=market.name,
        )
    )

    col_logout, col_login = st.columns(2)
    with col_logout:
        if st.button(_admin_text(language_code, "common.logout"), width="content"):
            clear_admin_auth_state()
            st.switch_page("pages/admin_login.py")
    with col_login:
        st.page_link(
            "pages/admin_login.py",
            label=_admin_text(language_code, "common.login_page"),
            width="content",
        )

    _render_notice()

    st.divider()
    payload = _render_add_section(watchlist_df, sdetypes_df, language_code)
    if payload is not None:
        _commit_save(service, payload, signed_identity, language_code)
        return

    st.divider()
    payload = _render_remove_section(watchlist_df, language_code)
    if payload is not None:
        _commit_save(service, payload, signed_identity, language_code)


if __name__ == "__main__":
    main()
