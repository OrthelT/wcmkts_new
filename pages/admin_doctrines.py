"""Admin doctrine fit editor page."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from init_db import ensure_market_db_ready
from logging_config import setup_logging
from pages.components.header import render_page_title
from services.admin_service import get_admin_service
from services.doctrine_service import format_doctrine_name
from services.eft_parser_service import parse_eft_fit
from services.eve_sso_service import get_eve_sso_service
from settings_service import SettingsService
from state import clear_admin_auth_state, get_admin_identity
from ui.market_selector import render_market_selector

logger = setup_logging(__name__, log_file="admin_doctrines_page.log")
EFT_EDITOR_KEY = "admin_doctrine_eft_text"
LOADED_FIT_KEY = "admin_doctrine_loaded_fit_id"

MARKET_FLAG_OPTIONS = {
    "Primary": "primary",
    "Deployment": "deployment",
    "Both": "both",
}
MARKET_FLAG_LABELS = {value: label for label, value in MARKET_FLAG_OPTIONS.items()}


def _format_doctrine_option(doctrine_id: int, doctrine_name_map: dict[int, str]) -> str:
    doctrine_name = doctrine_name_map.get(doctrine_id, "Unknown Doctrine")
    return f"{format_doctrine_name(doctrine_name)} ({doctrine_id})"


def _format_fit_option(fit_id: int, fit_options: pd.DataFrame) -> str:
    row = fit_options[fit_options["fit_id"] == fit_id].iloc[0]
    fit_name = str(row.get("fit_name") or "Unknown Fit")
    ship_name = str(row.get("ship_name") or "Unknown Ship")
    market_flag = str(row.get("market_flag") or "primary")
    target = int(row.get("target") or 0)
    return f"{ship_name} - {fit_name} ({fit_id}, target {target}, {market_flag})"


def main() -> None:
    market = render_market_selector()
    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    render_page_title("Admin Doctrines", subtitle="Add or update fits in existing doctrines.")

    auth_service = get_eve_sso_service()
    signed_identity = get_admin_identity()
    verified_identity = auth_service.verify_signed_admin_identity(signed_identity)
    if verified_identity is None:
        st.warning("Admin login required.")
        st.page_link("pages/admin_login.py", label="Open Admin Login")
        st.stop()

    settings = SettingsService()
    service = get_admin_service()
    fit_options = service.get_doctrine_fit_options()
    if fit_options.empty:
        st.warning("No existing doctrines found.")
        st.stop()

    doctrine_df = (
        fit_options[["doctrine_id", "doctrine_name"]]
        .drop_duplicates()
        .sort_values("doctrine_name")
        .reset_index(drop=True)
    )
    doctrine_name_map = {
        int(row["doctrine_id"]): str(row["doctrine_name"]) for _, row in doctrine_df.iterrows()
    }
    doctrine_ids = sorted(doctrine_name_map, key=lambda did: format_doctrine_name(doctrine_name_map[did]))

    st.caption(
        f"Signed in as {verified_identity['character_name']} ({verified_identity['character_id']})"
    )
    st.caption(f"Write target: {settings.admin_write_target} | Market: {market.name}")

    col_logout, col_watchlist = st.columns(2)
    with col_logout:
        if st.button("Log out", use_container_width=True):
            clear_admin_auth_state()
            st.switch_page("pages/admin_login.py")
    with col_watchlist:
        st.page_link("pages/admin.py", label="Admin Watchlist", use_container_width=True)

    st.divider()

    selected_doctrine_id = st.selectbox(
        "Doctrine",
        doctrine_ids,
        format_func=lambda did: _format_doctrine_option(did, doctrine_name_map),
    )
    selected_fit_options = fit_options[fit_options["doctrine_id"] == selected_doctrine_id].copy()
    selected_fit_options = selected_fit_options.sort_values(["ship_name", "fit_name", "fit_id"])
    selected_fit_ids = [int(fit_id) for fit_id in selected_fit_options["fit_id"].tolist()]
    selected_fit_id = st.selectbox(
        "Current Fit",
        selected_fit_ids,
        format_func=lambda fit_id: _format_fit_option(fit_id, selected_fit_options),
    )
    selected_fit = selected_fit_options[selected_fit_options["fit_id"] == selected_fit_id].iloc[0]
    default_target = int(selected_fit.get("target") or 1)
    default_market_flag = str(selected_fit.get("market_flag") or "primary")
    default_market_label = MARKET_FLAG_LABELS.get(default_market_flag, "Primary")
    if st.session_state.get(LOADED_FIT_KEY) != selected_fit_id:
        st.session_state[EFT_EDITOR_KEY] = service.get_doctrine_fit_eft(selected_fit_id)
        st.session_state[LOADED_FIT_KEY] = selected_fit_id

    with st.form("admin_doctrine_fit_form"):
        col_target, col_flag = st.columns([1, 1.2])
        with col_target:
            target = st.number_input("Target", min_value=1, value=default_target, step=1, format="%d")
        with col_flag:
            market_flag_label = st.selectbox(
                "Market Flag",
                list(MARKET_FLAG_OPTIONS),
                index=list(MARKET_FLAG_OPTIONS).index(default_market_label),
            )

        eft_text = st.text_area(
            "EFT Fit",
            height=420,
            placeholder="[Vedmak, Example Fit]\n1600mm Rolled Tungsten Compact Plates\n...",
            key=EFT_EDITOR_KEY,
        )

        add_col, update_col = st.columns(2)
        add_clicked = add_col.form_submit_button("Add Fit", type="primary", use_container_width=True)
        update_clicked = update_col.form_submit_button("Update Fit", use_container_width=True)

    if eft_text.strip():
        try:
            parsed = parse_eft_fit(eft_text)
            st.info(
                f"Parsed {parsed.ship_name} / {parsed.fit_name} "
                f"with {len(parsed.item_quantities)} unique fitted items."
            )
        except ValueError as exc:
            st.warning(str(exc))

    mode = None
    if add_clicked:
        mode = "add"
    elif update_clicked:
        mode = "update"

    if mode is not None:
        try:
            fit_id = None if mode == "add" else int(selected_fit_id)
            result = service.save_doctrine_fit(
                eft_text=eft_text,
                doctrine_id=int(selected_doctrine_id),
                fit_id=fit_id,
                target=int(target),
                market_flag=MARKET_FLAG_OPTIONS[market_flag_label],
                mode=mode,
                signed_identity=signed_identity,
            )
            action = "Added" if mode == "add" else "Updated"
            st.success(
                f"{action} doctrine_id={result['doctrine_id']} fit_id={result['fit_id']} "
                f"with {result['item_count']} unique fitted items."
            )
            st.session_state[LOADED_FIT_KEY] = None
        except Exception as exc:
            logger.warning("Doctrine fit save failed: %s", exc)
            st.error(str(exc))


if __name__ == "__main__":
    main()
