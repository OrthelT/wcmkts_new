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
