"""Tests for EVE SSO service behavior."""

from datetime import datetime, timedelta, timezone

import pytest

from services.eve_sso_service import EveSSOConfig, EveSSOService


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummySession:
    def __init__(self):
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/.well-known/oauth-authorization-server"):
            return DummyResponse(
                {
                    "authorization_endpoint": "https://login.eveonline.com/v2/oauth/authorize",
                    "token_endpoint": "https://login.eveonline.com/v2/oauth/token",
                }
            )
        if url.endswith("/v2/oauth/verify"):
            return DummyResponse(
                {
                    "CharacterID": 2122333361,
                    "CharacterName": "Orthel",
                }
            )
        raise AssertionError(f"Unexpected GET {url}")

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        if url.endswith("/v2/oauth/token"):
            return DummyResponse({"access_token": "access-token"})
        raise AssertionError(f"Unexpected POST {url}")


def make_config(**overrides):
    base = EveSSOConfig(
        client_id="client-id",
        client_secret="client-secret",
        callback_url="http://localhost:8501/admin_login",
        allowed_character_ids=(2122333361,),
        session_secret="session-secret",
        session_ttl_minutes=60,
    )
    values = base.__dict__ | overrides
    return EveSSOConfig(**values)


def test_create_authorization_url_contains_required_params():
    session = DummySession()
    service = EveSSOService(make_config(), http_client=session)

    url = service.create_authorization_url("state-token")

    assert "response_type=code" in url
    assert "client_id=client-id" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8501%2Fadmin_login" in url
    assert "state=state-token" in url
    assert "scope=" not in url


def test_complete_login_rejects_mismatched_state():
    service = EveSSOService(make_config(), http_client=DummySession())

    with pytest.raises(ValueError, match="Invalid OAuth state"):
        service.complete_login(code="auth-code", returned_state="wrong", expected_state="right")


def test_build_and_verify_oauth_state_round_trip():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: now)

    state = service.build_oauth_state()

    assert service.verify_oauth_state(state) is True


def test_verify_oauth_state_rejects_tampering():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: now)

    state = service.build_oauth_state()
    tampered = f"{state[:-1]}x"

    assert service.verify_oauth_state(tampered) is False


def test_verify_oauth_state_rejects_expired_token():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: now)
    state = service.build_oauth_state()

    later = now + timedelta(minutes=16)
    expired_service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: later)

    assert expired_service.verify_oauth_state(state) is False


def test_complete_login_rejects_non_allow_listed_character():
    session = DummySession()

    def denied_verify(*args, **kwargs):
        return DummyResponse({"CharacterID": 99, "CharacterName": "Denied"})

    session.get = lambda url, **kwargs: (
        DummyResponse(
            {
                "authorization_endpoint": "https://login.eveonline.com/v2/oauth/authorize",
                "token_endpoint": "https://login.eveonline.com/v2/oauth/token",
            }
        )
        if url.endswith("/.well-known/oauth-authorization-server")
        else denied_verify(url, **kwargs)
    )
    service = EveSSOService(make_config(), http_client=session)

    with pytest.raises(PermissionError, match="not authorized"):
        service.complete_login(code="auth-code", returned_state="state", expected_state="state")


def test_signed_admin_identity_round_trip():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: now)

    identity = service.build_signed_admin_identity(2122333361, "Orthel")
    verified = service.verify_signed_admin_identity(identity)

    assert verified["character_id"] == 2122333361
    assert verified["character_name"] == "Orthel"


def test_signed_admin_identity_rejects_tampering():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: now)

    identity = service.build_signed_admin_identity(2122333361, "Orthel")
    identity["payload"]["character_id"] = 7

    assert service.verify_signed_admin_identity(identity) is None


def test_signed_admin_identity_rejects_expired_session():
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: now)
    identity = service.build_signed_admin_identity(2122333361, "Orthel")

    later = now + timedelta(minutes=61)
    expired_service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: later)

    assert expired_service.verify_signed_admin_identity(identity) is None
