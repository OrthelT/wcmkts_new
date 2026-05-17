"""Tests for admin login OAuth callback handling."""

import pytest

from pages import admin_login


class StubSSOService:
    def __init__(self, *, verify_returns: bool = True):
        self.completed = None
        self._verify_returns = verify_returns

    def build_oauth_state(self):
        return "fresh-state"

    def create_authorization_url(self, state):
        return f"https://login.example.test?state={state}"

    def verify_oauth_state(self, state):
        return self._verify_returns

    def complete_login(self, *, code, returned_state, expected_state):
        self.completed = {
            "code": code,
            "returned_state": returned_state,
            "expected_state": expected_state,
        }
        return {"payload": {"character_id": 1}, "signature": "signed"}


def test_build_authorization_url_does_not_touch_session_state():
    """HMAC-signed state is self-validating; nothing should be stored in session."""
    url = admin_login._build_authorization_url(StubSSOService())

    assert url == "https://login.example.test?state=fresh-state"


def test_complete_callback_succeeds_when_hmac_verifies():
    service = StubSSOService(verify_returns=True)

    identity = admin_login._complete_callback_login(service, "auth-code", "signed-state")

    assert identity == {"payload": {"character_id": 1}, "signature": "signed"}
    assert service.completed == {
        "code": "auth-code",
        "returned_state": "signed-state",
        "expected_state": "signed-state",
    }


def test_complete_callback_rejects_when_hmac_fails():
    service = StubSSOService(verify_returns=False)

    with pytest.raises(ValueError, match="Invalid OAuth state"):
        admin_login._complete_callback_login(service, "auth-code", "tampered-state")
    assert service.completed is None
