"""Tests for admin login OAuth state handling."""

from pages import admin_login


class StubSSOService:
    def __init__(self):
        self.completed = None

    def build_oauth_state(self):
        return "pending-state"

    def create_authorization_url(self, state):
        return f"https://login.example.test?state={state}"

    def verify_oauth_state(self, state):
        return state == "returned-state"

    def complete_login(self, *, code, returned_state, expected_state):
        self.completed = {
            "code": code,
            "returned_state": returned_state,
            "expected_state": expected_state,
        }
        return {"payload": {"character_id": 1}, "signature": "signed"}


def test_build_authorization_url_stores_pending_state(monkeypatch):
    stored = {}
    monkeypatch.setattr(
        admin_login,
        "set_pending_oauth_state",
        lambda state: stored.__setitem__("state", state),
    )

    url = admin_login._build_authorization_url(StubSSOService())

    assert stored["state"] == "pending-state"
    assert url == "https://login.example.test?state=pending-state"


def test_complete_callback_uses_consumed_pending_state(monkeypatch):
    service = StubSSOService()
    monkeypatch.setattr(admin_login, "consume_pending_oauth_state", lambda: "returned-state")

    identity = admin_login._complete_callback_login(service, "auth-code", "returned-state")

    assert identity == {"payload": {"character_id": 1}, "signature": "signed"}
    assert service.completed == {
        "code": "auth-code",
        "returned_state": "returned-state",
        "expected_state": "returned-state",
    }


def test_complete_callback_rejects_state_not_pending_for_session(monkeypatch):
    service = StubSSOService()
    monkeypatch.setattr(admin_login, "consume_pending_oauth_state", lambda: "other-session-state")

    try:
        admin_login._complete_callback_login(service, "auth-code", "returned-state")
    except ValueError as exc:
        assert "Invalid OAuth state" in str(exc)
    else:
        raise AssertionError("Expected invalid OAuth state")
    assert service.completed is None
