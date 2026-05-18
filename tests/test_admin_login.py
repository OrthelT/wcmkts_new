"""Tests for admin login OAuth callback handling."""

import pytest

from pages import admin_login
from services.eve_sso_service import InvalidOAuthStateError


class StubSSOService:
    def __init__(self, *, complete_raises: Exception | None = None):
        self.completed = None
        self._complete_raises = complete_raises

    def build_oauth_state(self):
        return "fresh-state"

    def create_authorization_url(self, state):
        return f"https://login.example.test?state={state}"

    def complete_login(self, *, code, state):
        if self._complete_raises is not None:
            raise self._complete_raises
        self.completed = {"code": code, "state": state}
        return {"payload": {"character_id": 1}, "signature": "signed"}


def test_build_authorization_url_does_not_touch_session_state():
    """HMAC-signed state is self-validating; nothing should be stored in session."""
    url = admin_login._build_authorization_url(StubSSOService())

    assert url == "https://login.example.test?state=fresh-state"


def test_complete_callback_passes_code_and_state_to_service():
    """The page should forward the callback params verbatim to the service."""
    service = StubSSOService()

    identity = admin_login._complete_callback_login(service, "auth-code", "signed-state")

    assert identity == {"payload": {"character_id": 1}, "signature": "signed"}
    assert service.completed == {"code": "auth-code", "state": "signed-state"}


def test_complete_callback_propagates_invalid_state_error():
    """State-verification failure raised by the service must propagate unchanged."""
    service = StubSSOService(complete_raises=InvalidOAuthStateError("bad state"))

    with pytest.raises(InvalidOAuthStateError):
        admin_login._complete_callback_login(service, "auth-code", "tampered-state")
    assert service.completed is None
