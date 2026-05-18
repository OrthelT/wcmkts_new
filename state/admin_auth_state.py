"""Admin auth state helpers for Streamlit session state."""

from __future__ import annotations

import streamlit as st

ADMIN_IDENTITY_STATE_KEY = "admin_identity"
ADMIN_STATE_PREFIX = "admin_"


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
    """Remove all admin-scoped session state (identity + pending edits + notices).

    Sweeps every key prefixed ``admin_`` so a logout from Admin A on a shared
    workstation cannot leave pending watchlist adds/removes or doctrine-fit
    drafts queued for Admin B — which would otherwise be attributed to B in
    the audit log on the next Save click.
    """
    stale_keys = [
        key
        for key in list(st.session_state.keys())
        if isinstance(key, str) and key.startswith(ADMIN_STATE_PREFIX)
    ]
    for key in stale_keys:
        st.session_state.pop(key, None)
