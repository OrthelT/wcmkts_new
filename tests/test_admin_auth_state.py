"""Tests for admin auth session state helpers."""

from state import admin_auth_state


def test_admin_identity_round_trip(monkeypatch):
    monkeypatch.setattr(admin_auth_state.st, "session_state", {}, raising=False)
    identity = {
        "payload": {"character_id": 2122333361, "character_name": "Orthel"},
        "signature": "signed",
    }

    admin_auth_state.set_admin_identity(identity)

    assert admin_auth_state.get_admin_identity() == identity


def test_clear_admin_auth_state(monkeypatch):
    monkeypatch.setattr(
        admin_auth_state.st,
        "session_state",
        {
            admin_auth_state.ADMIN_IDENTITY_STATE_KEY: {"payload": {}, "signature": "x"},
        },
        raising=False,
    )

    admin_auth_state.clear_admin_auth_state()

    assert admin_auth_state.get_admin_identity() is None


def test_clear_admin_auth_state_sweeps_pending_admin_keys(monkeypatch):
    """Logout must clear pending watchlist + doctrine edits — not just the identity.

    Regression guard for the shared-workstation handoff: Admin A's pending adds
    must not be attributed to Admin B on the next Save click.
    """
    session = {
        admin_auth_state.ADMIN_IDENTITY_STATE_KEY: {"payload": {}, "signature": "x"},
        "admin_watchlist_pending_adds": [{"type_id": 34}],
        "admin_watchlist_pending_removes": [{"type_id": 35}],
        "admin_watchlist_remove_editor": {"some": "widget state"},
        "admin_watchlist_notice": "Saved 5 items",
        "admin_doctrine_eft_text": "[Vedmak, Old Fit]",
        "admin_doctrine_loaded_fit_id": 99,
        "admin_doctrine_notice": "Saved doctrine",
        "unrelated_user_pref": "keep me",
    }
    monkeypatch.setattr(admin_auth_state.st, "session_state", session, raising=False)

    admin_auth_state.clear_admin_auth_state()

    assert admin_auth_state.get_admin_identity() is None
    for key in (
        "admin_watchlist_pending_adds",
        "admin_watchlist_pending_removes",
        "admin_watchlist_remove_editor",
        "admin_watchlist_notice",
        "admin_doctrine_eft_text",
        "admin_doctrine_loaded_fit_id",
        "admin_doctrine_notice",
    ):
        assert key not in session, f"{key} should be cleared on logout"
    assert session.get("unrelated_user_pref") == "keep me"
