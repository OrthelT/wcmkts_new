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
from state import clear_admin_auth_state, get_active_language, get_admin_identity
from ui.i18n import translate_text
from ui.market_selector import render_market_selector

logger = setup_logging(__name__, log_file="admin_doctrines_page.log")
EFT_EDITOR_KEY = "admin_doctrine_eft_text"
LOADED_FIT_KEY = "admin_doctrine_loaded_fit_id"
NOTICE_KEY = "admin_doctrine_notice"

MARKET_FLAG_VALUES = ("primary", "deployment", "both")


def _admin_text(language_code: str, key: str, **kwargs) -> str:
    return translate_text(language_code, f"admin.{key}", **kwargs)


def _market_flag_label(language_code: str, market_flag: str) -> str:
    if market_flag not in MARKET_FLAG_VALUES:
        return market_flag
    return _admin_text(language_code, f"doctrine.market_flag_{market_flag}")


def _market_flag_options(language_code: str) -> dict[str, str]:
    return {
        _market_flag_label(language_code, market_flag): market_flag
        for market_flag in MARKET_FLAG_VALUES
    }


def _format_doctrine_option(
    doctrine_id: int,
    doctrine_name_map: dict[int, str],
    language_code: str,
) -> str:
    doctrine_name = doctrine_name_map.get(
        doctrine_id,
        _admin_text(language_code, "doctrine.unknown_doctrine"),
    )
    return f"{format_doctrine_name(doctrine_name)} ({doctrine_id})"


def _format_fit_option(fit_id: int, fit_options: pd.DataFrame, language_code: str) -> str:
    row = fit_options[fit_options["fit_id"] == fit_id].iloc[0]
    fit_name = str(row.get("fit_name") or _admin_text(language_code, "doctrine.unknown_fit"))
    ship_name = str(row.get("ship_name") or _admin_text(language_code, "doctrine.unknown_ship"))
    market_flag = str(row.get("market_flag") or "primary")
    target = int(row.get("target") or 0)
    return _admin_text(
        language_code,
        "doctrine.fit_option",
        ship_name=ship_name,
        fit_name=fit_name,
        fit_id=fit_id,
        target=target,
        market_flag=_market_flag_label(language_code, market_flag),
    )


def main() -> None:
    language_code = get_active_language()
    market = render_market_selector()
    if not ensure_market_db_ready(market.database_alias):
        st.error(
            _admin_text(language_code, "common.database_unavailable", market_name=market.name)
        )
        st.stop()

    render_page_title(
        _admin_text(language_code, "doctrine.title"),
        subtitle=_admin_text(language_code, "doctrine.subtitle"),
    )

    auth_service = get_eve_sso_service()
    signed_identity = get_admin_identity()
    verified_identity = auth_service.verify_signed_admin_identity(signed_identity)
    if verified_identity is None:
        st.warning(_admin_text(language_code, "common.login_required"))
        st.page_link("pages/admin_login.py", label=_admin_text(language_code, "common.open_login"))
        st.stop()

    settings = SettingsService()
    service = get_admin_service()
    doctrine_options = service.get_doctrine_options()
    fit_options = service.get_doctrine_fit_options()

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

    col_logout, col_watchlist = st.columns(2)
    with col_logout:
        if st.button(_admin_text(language_code, "common.logout"), width="stretch"):
            clear_admin_auth_state()
            st.switch_page("pages/admin_login.py")
    with col_watchlist:
        st.page_link(
            "pages/admin.py",
            label=_admin_text(language_code, "common.admin_watchlist"),
            width="stretch",
        )

    notice = st.session_state.pop(NOTICE_KEY, None)
    if notice:
        st.success(notice)

    st.divider()

    with st.form("admin_create_doctrine_form", clear_on_submit=True):
        new_doctrine_name = st.text_input(
            _admin_text(language_code, "doctrine.new_doctrine_name"),
            placeholder=_admin_text(language_code, "doctrine.new_doctrine_placeholder"),
        )
        create_clicked = st.form_submit_button(
            _admin_text(language_code, "doctrine.create_doctrine"),
            type="primary",
            width="stretch",
        )
    if create_clicked:
        try:
            result = service.create_doctrine(
                doctrine_name=new_doctrine_name,
                signed_identity=signed_identity,
            )
            st.session_state[NOTICE_KEY] = (
                _admin_text(
                    language_code,
                    "doctrine.created",
                    doctrine_id=result["doctrine_id"],
                    doctrine_name=format_doctrine_name(result["doctrine_name"]),
                )
            )
            st.rerun()
        except ValueError as exc:
            logger.error("Doctrine create rejected: %s", exc, exc_info=True)
            st.error(str(exc))
        except PermissionError as exc:
            logger.error("Doctrine create unauthorized: %s", exc, exc_info=True)
            st.error(_admin_text(language_code, "common.session_expired"))
        except Exception as exc:
            logger.error("Doctrine create failed: %s", exc, exc_info=True)
            st.error(_admin_text(language_code, "doctrine.create_failed"))

    if doctrine_options.empty:
        st.warning(_admin_text(language_code, "doctrine.no_doctrines"))
        st.stop()

    doctrine_df = (
        doctrine_options[["doctrine_id", "doctrine_name"]]
        .drop_duplicates()
        .sort_values("doctrine_name")
        .reset_index(drop=True)
    )
    doctrine_name_map = {
        int(row["doctrine_id"]): str(row["doctrine_name"]) for _, row in doctrine_df.iterrows()
    }
    doctrine_ids = sorted(doctrine_name_map, key=lambda did: format_doctrine_name(doctrine_name_map[did]))

    selected_doctrine_id = st.selectbox(
        _admin_text(language_code, "doctrine.select_doctrine"),
        doctrine_ids,
        format_func=lambda did: _format_doctrine_option(did, doctrine_name_map, language_code),
    )
    selected_doctrine_name = doctrine_name_map[int(selected_doctrine_id)]
    with st.form(f"admin_rename_doctrine_form_{selected_doctrine_id}"):
        renamed_doctrine_name = st.text_input(
            _admin_text(language_code, "doctrine.doctrine_name"),
            value=selected_doctrine_name,
            key=f"rename_doctrine_name_{selected_doctrine_id}",
        )
        rename_clicked = st.form_submit_button(
            _admin_text(language_code, "doctrine.rename_doctrine"),
            width="stretch",
        )
    if rename_clicked:
        try:
            result = service.rename_doctrine(
                doctrine_id=int(selected_doctrine_id),
                doctrine_name=renamed_doctrine_name,
                signed_identity=signed_identity,
            )
            st.session_state[NOTICE_KEY] = (
                _admin_text(
                    language_code,
                    "doctrine.renamed",
                    doctrine_id=result["doctrine_id"],
                    doctrine_name=format_doctrine_name(result["doctrine_name"]),
                )
            )
            st.session_state[LOADED_FIT_KEY] = None
            st.rerun()
        except ValueError as exc:
            logger.error("Doctrine rename rejected: %s", exc, exc_info=True)
            st.error(str(exc))
        except PermissionError as exc:
            logger.error("Doctrine rename unauthorized: %s", exc, exc_info=True)
            st.error(_admin_text(language_code, "common.session_expired"))
        except Exception as exc:
            logger.error("Doctrine rename failed: %s", exc, exc_info=True)
            st.error(_admin_text(language_code, "doctrine.rename_failed"))

    if fit_options.empty:
        selected_fit_options = pd.DataFrame()
    else:
        selected_fit_options = fit_options[fit_options["doctrine_id"] == selected_doctrine_id].copy()
        selected_fit_options = selected_fit_options.sort_values(["ship_name", "fit_name", "fit_id"])
    selected_fit_ids = [
        int(fit_id)
        for fit_id in selected_fit_options.get("fit_id", pd.Series(dtype=int)).tolist()
        if pd.notna(fit_id)
    ]
    selected_fit_id = None
    if selected_fit_ids:
        selected_fit_id = st.selectbox(
            _admin_text(language_code, "doctrine.current_fit"),
            selected_fit_ids,
            format_func=lambda fit_id: _format_fit_option(
                fit_id,
                selected_fit_options,
                language_code,
            ),
        )
        selected_fit = selected_fit_options[selected_fit_options["fit_id"] == selected_fit_id].iloc[0]
        default_target = int(selected_fit.get("target") or 1)
        default_market_flag = str(selected_fit.get("market_flag") or "primary")
        default_market_label = _market_flag_label(language_code, default_market_flag)
        loaded_key = f"fit:{selected_fit_id}"
        loaded_text = service.get_doctrine_fit_eft(selected_fit_id)
    else:
        st.info(_admin_text(language_code, "doctrine.no_fits_for_doctrine"))
        default_target = 1
        default_market_label = _market_flag_label(language_code, "primary")
        loaded_key = f"doctrine:{selected_doctrine_id}:new"
        loaded_text = ""

    if st.session_state.get(LOADED_FIT_KEY) != loaded_key:
        st.session_state[EFT_EDITOR_KEY] = loaded_text
        st.session_state[LOADED_FIT_KEY] = loaded_key

    with st.form("admin_doctrine_fit_form"):
        col_target, col_flag = st.columns([1, 1.2])
        with col_target:
            target = st.number_input(
                _admin_text(language_code, "doctrine.target"),
                min_value=1,
                value=default_target,
                step=1,
                format="%d",
            )
        with col_flag:
            market_flag_options = _market_flag_options(language_code)
            market_flag_label = st.selectbox(
                _admin_text(language_code, "doctrine.market_flag"),
                list(market_flag_options),
                index=list(market_flag_options).index(default_market_label),
            )

        eft_text = st.text_area(
            _admin_text(language_code, "doctrine.eft_fit"),
            height=420,
            placeholder=_admin_text(language_code, "doctrine.eft_placeholder"),
            key=EFT_EDITOR_KEY,
        )

        add_col, update_col = st.columns(2)
        add_clicked = add_col.form_submit_button(
            _admin_text(language_code, "doctrine.add_fit"),
            type="primary",
            width="stretch",
        )
        update_clicked = update_col.form_submit_button(
            _admin_text(language_code, "doctrine.update_fit"),
            width="stretch",
            disabled=selected_fit_id is None,
        )

    if selected_fit_id is not None:
        confirm_delete = st.checkbox(_admin_text(language_code, "doctrine.confirm_delete"))
        delete_clicked = st.button(
            _admin_text(language_code, "doctrine.delete_fit"),
            width="stretch",
            disabled=not confirm_delete,
        )
        if delete_clicked:
            try:
                result = service.delete_doctrine_fit(
                    doctrine_id=int(selected_doctrine_id),
                    fit_id=int(selected_fit_id),
                    signed_identity=signed_identity,
                )
                st.session_state[NOTICE_KEY] = (
                    _admin_text(
                        language_code,
                        "doctrine.deleted",
                        doctrine_id=result["doctrine_id"],
                        fit_id=result["fit_id"],
                    )
                )
                st.session_state[LOADED_FIT_KEY] = None
                st.rerun()
            except ValueError as exc:
                logger.error("Doctrine fit delete rejected: %s", exc, exc_info=True)
                st.error(str(exc))
            except PermissionError as exc:
                logger.error("Doctrine fit delete unauthorized: %s", exc, exc_info=True)
                st.error(_admin_text(language_code, "common.session_expired"))
            except Exception as exc:
                logger.error("Doctrine fit delete failed: %s", exc, exc_info=True)
                st.error(_admin_text(language_code, "doctrine.delete_failed"))

    if eft_text.strip():
        try:
            parsed = parse_eft_fit(eft_text)
            st.info(
                _admin_text(
                    language_code,
                    "doctrine.parsed_fit",
                    ship_name=parsed.ship_name,
                    fit_name=parsed.fit_name,
                    item_count=len(parsed.item_quantities),
                )
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
            if mode == "update" and selected_fit_id is None:
                raise ValueError(_admin_text(language_code, "doctrine.select_existing_fit"))
            fit_id = None if mode == "add" else int(selected_fit_id)
            result = service.save_doctrine_fit(
                eft_text=eft_text,
                doctrine_id=int(selected_doctrine_id),
                fit_id=fit_id,
                target=int(target),
                market_flag=market_flag_options[market_flag_label],
                mode=mode,
                signed_identity=signed_identity,
            )
            action = _admin_text(
                language_code,
                "doctrine.action_added" if mode == "add" else "doctrine.action_updated",
            )
            st.session_state[NOTICE_KEY] = (
                _admin_text(
                    language_code,
                    "doctrine.saved_fit",
                    action=action,
                    doctrine_id=result["doctrine_id"],
                    fit_id=result["fit_id"],
                    item_count=result["item_count"],
                )
            )
            st.session_state[LOADED_FIT_KEY] = None
            st.rerun()
        except ValueError as exc:
            logger.error("Doctrine fit save rejected: %s", exc, exc_info=True)
            st.error(str(exc))
        except PermissionError as exc:
            logger.error("Doctrine fit save unauthorized: %s", exc, exc_info=True)
            st.error(_admin_text(language_code, "common.session_expired"))
        except Exception as exc:
            logger.error("Doctrine fit save failed: %s", exc, exc_info=True)
            st.error(_admin_text(language_code, "doctrine.save_fit_failed"))


if __name__ == "__main__":
    main()
