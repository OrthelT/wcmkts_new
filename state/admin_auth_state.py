"""Admin auth state helpers for Streamlit session state."""

from __future__ import annotations

import streamlit as st

PENDING_OAUTH_STATE_KEY = "admin_pending_oauth_state"
ADMIN_IDENTITY_STATE_KEY = "admin_identity"


def get_pending_oauth_state() -> str | None:
    """Return the pending OAuth state token, if any."""
    return st.session_state.get(PENDING_OAUTH_STATE_KEY)


def set_pending_oauth_state(state: str) -> None:
    """Persist the pending OAuth state token."""
    st.session_state[PENDING_OAUTH_STATE_KEY] = state


def consume_pending_oauth_state() -> str | None:
    """Return and remove the pending OAuth state token."""
    value = get_pending_oauth_state()
    st.session_state.pop(PENDING_OAUTH_STATE_KEY, None)
    return value


def get_admin_identity() -> dict | None:
    """Return the signed admin identity payload, if any."""
    return st.session_state.get(ADMIN_IDENTITY_STATE_KEY)


def set_admin_identity(identity: dict) -> None:
    """Persist the signed admin identity payload."""
    st.session_state[ADMIN_IDENTITY_STATE_KEY] = identity


def clear_admin_identity() -> None:
    """Remove the signed admin identity payload."""
    st.session_state.pop(ADMIN_IDENTITY_STATE_KEY, None)


def clear_admin_auth_state() -> None:
    """Remove all admin-auth state from the session."""
    clear_admin_identity()
    st.session_state.pop(PENDING_OAUTH_STATE_KEY, None)
