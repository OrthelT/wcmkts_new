"""Admin auth state helpers for Streamlit session state."""

from __future__ import annotations

import streamlit as st

ADMIN_IDENTITY_STATE_KEY = "admin_identity"


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
