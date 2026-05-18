"""Tests for EVE SSO service behavior."""

from datetime import datetime, timedelta, timezone

import pytest

from services.eve_sso_service import (
    EveSSOConfig,
    EveSSOService,
    InvalidOAuthStateError,
    SSONetworkError,
)


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
    # session_secret must be ≥32 chars (enforced by EveSSOConfig.__post_init__).
    base = EveSSOConfig(
        client_id="client-id",
        client_secret="client-secret",
        callback_url="http://localhost:8501/admin_login",
        allowed_character_ids=(2122333361,),
        session_secret="test-session-secret-32-chars-min!",
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


def test_complete_login_rejects_tampered_state():
    """complete_login now validates state via HMAC internally — no separate guard needed."""
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=DummySession(), now_provider=lambda: now)

    state = service.build_oauth_state()
    tampered = f"{state[:-1]}x"

    with pytest.raises(InvalidOAuthStateError, match="invalid"):
        service.complete_login(code="auth-code", state=tampered)


def test_complete_login_rejects_empty_state():
    """An empty state must be rejected — defends against malformed callback URLs."""
    service = EveSSOService(make_config(), http_client=DummySession())

    with pytest.raises(InvalidOAuthStateError):
        service.complete_login(code="auth-code", state="")


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
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
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
    service = EveSSOService(make_config(), http_client=session, now_provider=lambda: now)
    state = service.build_oauth_state()

    with pytest.raises(PermissionError, match="not authorized"):
        service.complete_login(code="auth-code", state=state)


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


# --- EveSSOConfig invariant tests -----------------------------------------------------


def test_evesso_config_rejects_empty_allow_list():
    """An empty allow-list silently disables admin access — must fail fast at deploy."""
    with pytest.raises(ValueError, match="allowed_character_ids"):
        make_config(allowed_character_ids=())


def test_evesso_config_rejects_empty_session_secret():
    """An empty session_secret produces deterministic HMACs — must fail fast."""
    with pytest.raises(ValueError, match="session_secret"):
        make_config(session_secret="")


def test_evesso_config_rejects_short_session_secret():
    """A too-short session_secret weakens HMAC tamper-resistance — must fail fast."""
    with pytest.raises(ValueError, match="session_secret"):
        make_config(session_secret="short")


def test_evesso_config_rejects_non_positive_session_ttl():
    """A non-positive TTL makes every issued token instantly expired."""
    with pytest.raises(ValueError, match="session_ttl_minutes"):
        make_config(session_ttl_minutes=0)


def test_evesso_config_rejects_non_positive_oauth_state_ttl():
    """A non-positive OAuth state TTL rejects every callback — must fail fast."""
    with pytest.raises(ValueError, match="oauth_state_ttl_minutes"):
        make_config(oauth_state_ttl_minutes=0)


def test_evesso_config_rejects_empty_client_id():
    with pytest.raises(ValueError, match="client_id"):
        make_config(client_id="")


def test_evesso_config_rejects_empty_callback_url():
    with pytest.raises(ValueError, match="callback_url"):
        make_config(callback_url="")


def test_oauth_state_ttl_uses_configured_value():
    """The OAuth state TTL must come from config, not a hardcoded module constant."""
    now = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    # 1-minute TTL — a state issued at t=0 is invalid at t=2 min
    short_ttl_config = make_config(oauth_state_ttl_minutes=1)
    service = EveSSOService(short_ttl_config, http_client=DummySession(), now_provider=lambda: now)
    state = service.build_oauth_state()
    assert service.verify_oauth_state(state) is True

    later = now + timedelta(minutes=2)
    expired_service = EveSSOService(
        short_ttl_config, http_client=DummySession(), now_provider=lambda: later
    )
    assert expired_service.verify_oauth_state(state) is False


# --- HTTP / OAuth error-path tests ---------------------------------------------------

import json

import requests


class FailingResponse:
    """Response that raises HTTPError on raise_for_status().

    Mirrors real ``requests.Response.raise_for_status()`` by attaching ``self`` to
    the raised ``HTTPError`` so callers (and our SSONetworkError wrapper) can
    extract the status code via ``exc.response.status_code``.
    """

    def __init__(self, status_code: int = 500):
        self.status_code = status_code

    def raise_for_status(self):
        raise requests.HTTPError(f"{self.status_code} server error", response=self)

    def json(self):
        raise AssertionError("json() should not be called when raise_for_status raises")


class MalformedJSONResponse:
    """Response that raises JSONDecodeError when .json() is called."""

    def raise_for_status(self):
        return None

    def json(self):
        raise json.JSONDecodeError("expecting value", "<html>...", 0)


def _service_with_valid_state(session, now=None):
    """Build a service with a valid (non-tampered, non-expired) HMAC state.

    Returns (service, state) so HTTP-failure tests can exercise the
    post-state-check branches without state errors confusing the outcome.
    """
    now = now or datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    service = EveSSOService(make_config(), http_client=session, now_provider=lambda: now)
    return service, service.build_oauth_state()


def test_get_metadata_propagates_http_error():
    """A 5xx from EVE SSO metadata endpoint must surface as SSONetworkError, not silent."""
    session = DummySession()
    session.get = lambda url, **kwargs: FailingResponse(503)
    service = EveSSOService(make_config(), http_client=session)

    with pytest.raises(SSONetworkError) as excinfo:
        service.create_authorization_url("state-token")
    assert excinfo.value.status_code == 503


def test_exchange_code_propagates_http_error():
    """A 5xx from the token endpoint must surface as SSONetworkError carrying status."""
    session = DummySession()
    session.post = lambda url, **kwargs: FailingResponse(502)
    service, state = _service_with_valid_state(session)

    with pytest.raises(SSONetworkError) as excinfo:
        service.complete_login(code="auth-code", state=state)
    assert excinfo.value.status_code == 502


def test_exchange_code_raises_on_missing_access_token():
    """A 200 OK with no access_token field must surface as SSONetworkError."""
    session = DummySession()
    session.post = lambda url, **kwargs: DummyResponse({"error": "invalid_grant"})
    service, state = _service_with_valid_state(session)

    with pytest.raises(SSONetworkError, match="access token"):
        service.complete_login(code="auth-code", state=state)


def test_exchange_code_propagates_json_decode_error():
    """Malformed token-endpoint body (e.g. HTML during EVE incident) must surface as SSONetworkError."""
    session = DummySession()
    session.post = lambda url, **kwargs: MalformedJSONResponse()
    service, state = _service_with_valid_state(session)

    with pytest.raises(SSONetworkError, match="JSON"):
        service.complete_login(code="auth-code", state=state)


def test_exchange_code_401_carries_credential_status_code():
    """A 401 from the token endpoint signals bad client_secret — status must surface."""
    session = DummySession()
    session.post = lambda url, **kwargs: FailingResponse(401)
    service, state = _service_with_valid_state(session)

    with pytest.raises(SSONetworkError) as excinfo:
        service.complete_login(code="auth-code", state=state)
    assert excinfo.value.status_code == 401


def test_verify_access_token_propagates_http_error():
    """A 5xx from the verify endpoint must surface as SSONetworkError."""
    session = DummySession()
    original_get = session.get

    def get_router(url, **kwargs):
        if url.endswith("/v2/oauth/verify"):
            return FailingResponse(500)
        return original_get(url, **kwargs)

    session.get = get_router
    service, state = _service_with_valid_state(session)

    with pytest.raises(SSONetworkError) as excinfo:
        service.complete_login(code="auth-code", state=state)
    assert excinfo.value.status_code == 500


def test_verify_access_token_raises_on_missing_character_id():
    """A 200 OK with no CharacterID must surface as SSONetworkError."""
    session = DummySession()
    original_get = session.get

    def get_router(url, **kwargs):
        if url.endswith("/v2/oauth/verify"):
            return DummyResponse({"CharacterName": "Orthel"})
        return original_get(url, **kwargs)

    session.get = get_router
    service, state = _service_with_valid_state(session)

    with pytest.raises(SSONetworkError, match="character identity"):
        service.complete_login(code="auth-code", state=state)


def test_complete_login_invokes_token_exchange_before_verify():
    """Guard against a regression that skips the token POST."""
    session = DummySession()
    service, state = _service_with_valid_state(session)

    service.complete_login(code="auth-code", state=state)

    call_methods = [call[0] for call in session.calls]
    assert call_methods == ["GET", "POST", "GET"], (
        f"Expected metadata GET, token POST, verify GET; got {call_methods}"
    )
