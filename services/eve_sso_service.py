"""EVE SSO login helpers for the admin flow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import json
import secrets
from typing import Callable
from urllib.parse import urlencode

import requests
import streamlit as st

from logging_config import setup_logging
from settings_service import SettingsService

logger = setup_logging(__name__, log_file="eve_sso_service.log")

SSO_METADATA_URL = "https://login.eveonline.com/.well-known/oauth-authorization-server"
SSO_VERIFY_URL = "https://login.eveonline.com/v2/oauth/verify"

# Minimum session-secret length. 32 chars of urlsafe_b64 ≈ 192 bits of entropy,
# the floor at which HMAC-SHA256 can be considered tamper-resistant for a tiny
# in-circle admin allow-list. Shorter secrets in production are a deploy bug.
_MIN_SESSION_SECRET_LENGTH = 32


class EveSSOError(Exception):
    """Base class for EVE SSO failures the admin login page can map to user messages."""


class InvalidOAuthStateError(EveSSOError):
    """OAuth state failed HMAC/TTL verification (tampered, malformed, or expired)."""


class SSONetworkError(EveSSOError):
    """EVE SSO endpoint was unreachable, returned a non-2xx status, or gave malformed data.

    Distinguishes "EVE is temporarily down / having an incident" from "this character is
    not allowed" (PermissionError) and from "your state is bad" (InvalidOAuthStateError).
    Carries the HTTP ``status_code`` when one is available so the caller can decide
    whether to suggest "try again in a few minutes" (5xx) vs "credentials misconfigured"
    (401/403 from the token endpoint).
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        upstream_message: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.upstream_message = upstream_message


@dataclass(frozen=True)
class EveSSOConfig:
    """Frozen config for the EVE SSO admin login flow.

    Invariants enforced on construction so deploy-time mistakes (empty allow-list,
    short secret, non-positive TTL) fail loudly rather than silently disabling
    admin access or producing deterministic HMACs.
    """

    client_id: str
    client_secret: str
    callback_url: str
    allowed_character_ids: tuple[int, ...]
    session_secret: str
    session_ttl_minutes: int
    oauth_state_ttl_minutes: int = 15

    def __post_init__(self) -> None:
        if not self.client_id:
            raise ValueError("eve_sso.client_id must be a non-empty string")
        if not self.client_secret:
            raise ValueError("eve_sso.client_secret must be a non-empty string")
        if not self.callback_url:
            raise ValueError("eve_sso.callback_url must be a non-empty string")
        if not self.allowed_character_ids:
            raise ValueError(
                "eve_sso.allowed_character_ids must not be empty — an empty allow-list "
                "silently locks all admins out"
            )
        if not self.session_secret:
            raise ValueError("admin.session_secret must be a non-empty string")
        if len(self.session_secret) < _MIN_SESSION_SECRET_LENGTH:
            raise ValueError(
                f"admin.session_secret must be at least {_MIN_SESSION_SECRET_LENGTH} "
                "characters — short secrets weaken HMAC tamper-resistance"
            )
        if self.session_ttl_minutes <= 0:
            raise ValueError(
                "admin.session_ttl_minutes must be positive — non-positive TTL makes "
                "every issued token instantly expired"
            )
        if self.oauth_state_ttl_minutes <= 0:
            raise ValueError("admin.oauth_state_ttl_minutes must be positive")


class EveSSOService:
    """Handle EVE OAuth login and signed internal admin sessions."""

    def __init__(
        self,
        config: EveSSOConfig,
        *,
        http_client=None,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self._config = config
        self._http = http_client or requests.Session()
        self._now = now_provider or (lambda: datetime.now(timezone.utc))
        self._metadata: dict | None = None

    def create_authorization_url(self, state: str) -> str:
        """Return the EVE authorization URL for the admin login flow."""
        metadata = self._get_metadata()
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._config.client_id,
                "redirect_uri": self._config.callback_url,
                "state": state,
            }
        )
        return f"{metadata['authorization_endpoint']}?{query}"

    def build_oauth_state(self) -> str:
        """Create a signed, time-limited OAuth state token."""
        payload = {
            "nonce": secrets.token_urlsafe(24),
            "issued_at": self._now().isoformat(),
        }
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        signature = self._sign_string(payload_json)
        return ".".join(
            [
                self._urlsafe_b64encode(payload_json.encode("utf-8")),
                signature,
            ]
        )

    def verify_oauth_state(self, state: str | None) -> bool:
        """Validate a signed OAuth state token without relying on session memory."""
        if not state or "." not in state:
            return False

        encoded_payload, signature = state.split(".", 1)
        try:
            payload_json = self._urlsafe_b64decode(encoded_payload).decode("utf-8")
            payload = json.loads(payload_json)
            issued_at = datetime.fromisoformat(payload["issued_at"])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False

        expected_signature = self._sign_string(payload_json)
        if not hmac.compare_digest(signature, expected_signature):
            return False

        expires_at = issued_at + timedelta(minutes=self._config.oauth_state_ttl_minutes)
        return expires_at > self._now()

    def complete_login(self, *, code: str, state: str) -> dict:
        """Exchange an auth code, verify identity, and return a signed admin session.

        State validation is performed here via :meth:`verify_oauth_state` (HMAC + TTL).
        The previous ``expected_state`` parameter was always called with the same value
        as ``returned_state``, making the equality check a no-op — the real guard has
        always been the HMAC. Centralising the check here means no caller can forget
        it.

        Raises:
            InvalidOAuthStateError: state failed HMAC/TTL verification.
            SSONetworkError: EVE SSO endpoint unreachable or returned bad data.
            PermissionError: character authenticated but is not in the admin allow-list.
        """
        if not self.verify_oauth_state(state):
            raise InvalidOAuthStateError(
                "OAuth state is invalid (tampered, malformed, or expired)"
            )

        access_token = self._exchange_code(code)
        character = self._verify_access_token(access_token)
        character_id = int(character["CharacterID"])

        if character_id not in self._config.allowed_character_ids:
            raise PermissionError(f"Character {character_id} is not authorized")

        return self.build_signed_admin_identity(character_id, character["CharacterName"])

    def build_signed_admin_identity(self, character_id: int, character_name: str) -> dict:
        """Create a signed internal admin identity payload."""
        issued_at = self._now()
        payload = {
            "character_id": int(character_id),
            "character_name": character_name,
            "issued_at": issued_at.isoformat(),
            "expires_at": (
                issued_at + timedelta(minutes=self._config.session_ttl_minutes)
            ).isoformat(),
        }
        return {"payload": payload, "signature": self._sign_payload(payload)}

    def verify_signed_admin_identity(self, identity: dict | None) -> dict | None:
        """Validate a signed admin identity payload.

        Returns the verified payload on success or ``None`` for any failure mode.
        Each failure mode is logged at ERROR with a distinct event tag so ops can
        distinguish benign expirations from security-relevant tampering or revocation.
        """
        if not identity or "payload" not in identity or "signature" not in identity:
            logger.error("admin_identity_verify_failed: missing payload or signature envelope")
            return None

        payload = identity["payload"]
        expected_signature = self._sign_payload(payload)
        if not hmac.compare_digest(str(identity["signature"]), expected_signature):
            logger.error(
                "admin_identity_verify_failed: signature mismatch — possible tampering"
            )
            return None

        try:
            expires_at = datetime.fromisoformat(payload["expires_at"])
        except (KeyError, TypeError, ValueError):
            logger.error(
                "admin_identity_verify_failed: malformed expires_at in signed payload"
            )
            return None

        if expires_at <= self._now():
            logger.error("admin_identity_verify_failed: session expired (expected re-login)")
            return None

        try:
            character_id = int(payload["character_id"])
        except (KeyError, TypeError, ValueError):
            logger.error(
                "admin_identity_verify_failed: malformed character_id in signed payload"
            )
            return None

        if character_id not in self._config.allowed_character_ids:
            logger.error(
                "admin_identity_verify_failed: character_id=%s not in allow-list (revoked)",
                character_id,
            )
            return None

        return payload

    def _get_metadata(self) -> dict:
        if self._metadata is None:
            try:
                response = self._http.get(SSO_METADATA_URL, timeout=15)
                response.raise_for_status()
                self._metadata = response.json()
            except requests.HTTPError as exc:
                raise SSONetworkError(
                    "EVE SSO metadata endpoint returned an HTTP error",
                    status_code=_status_code_from(exc),
                ) from exc
            except requests.RequestException as exc:
                raise SSONetworkError("EVE SSO metadata endpoint unreachable") from exc
            except (ValueError, json.JSONDecodeError) as exc:
                raise SSONetworkError("EVE SSO metadata response was not valid JSON") from exc
        return self._metadata

    def _exchange_code(self, code: str) -> str:
        metadata = self._get_metadata()
        try:
            response = self._http.post(
                metadata["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                },
                auth=(self._config.client_id, self._config.client_secret),
                headers={"Accept": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.HTTPError as exc:
            raise SSONetworkError(
                "EVE SSO token endpoint returned an HTTP error",
                status_code=_status_code_from(exc),
            ) from exc
        except requests.RequestException as exc:
            raise SSONetworkError("EVE SSO token endpoint unreachable") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise SSONetworkError("EVE SSO token response was not valid JSON") from exc
        access_token = payload.get("access_token")
        if not access_token:
            raise SSONetworkError(
                "EVE SSO token response did not include an access token",
                upstream_message=str(payload.get("error_description") or payload.get("error") or ""),
            )
        return access_token

    def _verify_access_token(self, access_token: str) -> dict:
        try:
            response = self._http.get(
                SSO_VERIFY_URL,
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.HTTPError as exc:
            raise SSONetworkError(
                "EVE SSO verify endpoint returned an HTTP error",
                status_code=_status_code_from(exc),
            ) from exc
        except requests.RequestException as exc:
            raise SSONetworkError("EVE SSO verify endpoint unreachable") from exc
        except (ValueError, json.JSONDecodeError) as exc:
            raise SSONetworkError("EVE SSO verify response was not valid JSON") from exc
        if "CharacterID" not in payload or "CharacterName" not in payload:
            raise SSONetworkError("EVE SSO verify response did not include character identity")
        return payload

    def _sign_payload(self, payload: dict) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self._sign_bytes(encoded)

    def _sign_string(self, value: str) -> str:
        return self._sign_bytes(value.encode("utf-8"))

    def _sign_bytes(self, value: bytes) -> str:
        secret = self._config.session_secret.encode("utf-8")
        return hmac.new(secret, value, hashlib.sha256).hexdigest()

    @staticmethod
    def _urlsafe_b64encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    @staticmethod
    def _urlsafe_b64decode(value: str) -> bytes:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}")


def _status_code_from(exc: requests.HTTPError) -> int | None:
    """Best-effort HTTP status code extraction from a requests HTTPError."""
    response = getattr(exc, "response", None)
    return getattr(response, "status_code", None)


def get_eve_sso_service() -> EveSSOService:
    """Create an EVE SSO service from settings and secrets."""
    settings = SettingsService()
    config = EveSSOConfig(
        client_id=settings.eve_sso_client_id,
        client_secret=st.secrets["eve_sso"]["client_secret"],
        callback_url=settings.eve_sso_callback_url,
        allowed_character_ids=settings.eve_sso_allowed_character_ids,
        session_secret=st.secrets["admin"]["session_secret"],
        session_ttl_minutes=settings.admin_session_ttl_minutes,
        oauth_state_ttl_minutes=settings.admin_oauth_state_ttl_minutes,
    )
    return EveSSOService(config)
