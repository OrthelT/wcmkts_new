"""Admin login page for EVE SSO."""

from __future__ import annotations

import streamlit as st

from logging_config import setup_logging
from pages.components.header import render_page_title
from services.eve_sso_service import get_eve_sso_service
from state import (
    clear_admin_auth_state,
    get_admin_identity,
    set_admin_identity,
)

logger = setup_logging(__name__, log_file="admin_login.log")


def _query_param(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _clear_callback_params() -> None:
    for key in ("code", "state", "error", "error_description"):
        if key in st.query_params:
            del st.query_params[key]


def _build_authorization_url(service) -> str:
    oauth_state = service.build_oauth_state()
    return service.create_authorization_url(oauth_state)


def _complete_callback_login(service, code: str, returned_state: str) -> dict:
    # OAuth state is verified by HMAC signature + 15-min TTL only; it is
    # intentionally NOT bound to the originating browser session.
    #
    # Trade-off: strict OAuth (RFC 6749 §10.12) recommends binding state to the
    # user agent to prevent login CSRF — an allow-listed admin tricking another
    # admin into completing the attacker's login flow in the victim's browser,
    # so subsequent actions are attributed to the attacker in the audit log.
    # Accepted risk: the admin allow-list is intentionally small (currently 2
    # trusted characters) and the alternative — storing pending state in
    # st.session_state — breaks login across tab refresh and server restart.
    # Re-evaluate if the allow-list grows beyond the in-circle trust boundary.
    if not service.verify_oauth_state(returned_state):
        logger.error(
            "admin_oauth_callback_rejected: state failed HMAC/TTL verification"
        )
        raise ValueError("Invalid OAuth state (tampered, malformed, or expired)")
    return service.complete_login(
        code=code,
        returned_state=returned_state,
        expected_state=returned_state,
    )


def main() -> None:
    render_page_title("Admin Login", subtitle="Sign in with EVE to edit the watchlist.")
    service = get_eve_sso_service()
    verified_identity = service.verify_signed_admin_identity(get_admin_identity())

    if verified_identity is not None:
        st.info(
            f"Signed in as {verified_identity['character_name']} "
            f"({verified_identity['character_id']})."
        )
        col_open, col_logout = st.columns(2)
        with col_open:
            st.page_link("pages/admin.py", label="Open Admin Watchlist")
        with col_logout:
            if st.button("Log out", width="stretch"):
                clear_admin_auth_state()
                st.rerun()
        return

    error_code = _query_param("error")
    if error_code:
        # Do not echo EVE's error_description into st.error — st.error renders
        # markdown, so a crafted ?error_description=[click+here](https://evil)
        # would inject a phishing link into the trusted admin page before any
        # auth check runs. Log the upstream detail and show a generic message.
        error_description = _query_param("error_description") or ""
        logger.error(
            "admin_oauth_callback_error: error=%r error_description=%r",
            error_code,
            error_description,
        )
        st.error("EVE returned an authorization error. Check admin logs for details.")
        _clear_callback_params()

    code = _query_param("code")
    returned_state = _query_param("state")
    if code and returned_state:
        try:
            signed_identity = _complete_callback_login(service, code, returned_state)
        except ValueError as exc:
            logger.error("Admin login rejected: %s", exc, exc_info=True)
            clear_admin_auth_state()
            _clear_callback_params()
            st.error(str(exc))
        except PermissionError as exc:
            logger.error("Admin login unauthorized: %s", exc, exc_info=True)
            clear_admin_auth_state()
            _clear_callback_params()
            st.error("This character is not authorized to use the admin tools.")
        except Exception as exc:
            logger.error("Admin login failed: %s", exc, exc_info=True)
            clear_admin_auth_state()
            _clear_callback_params()
            st.error("Admin login failed. Check admin logs for details.")
        else:
            # Side-effects run only after the auth code is successfully
            # exchanged. If switch_page (or any later call) raises, the
            # verified identity stays set so the admin can navigate manually
            # rather than retrying OAuth with a now-consumed auth code.
            set_admin_identity(signed_identity)
            _clear_callback_params()
            st.success("Admin login successful.")
            st.switch_page("pages/admin.py")
        return

    st.link_button(
        "Sign in with EVE",
        url=_build_authorization_url(service),
        width="stretch",
    )


if __name__ == "__main__":
    main()
