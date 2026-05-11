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

from settings_service import SettingsService

SSO_METADATA_URL = "https://login.eveonline.com/.well-known/oauth-authorization-server"
SSO_VERIFY_URL = "https://login.eveonline.com/v2/oauth/verify"
OAUTH_STATE_TTL_MINUTES = 15


@dataclass(frozen=True)
class EveSSOConfig:
    client_id: str
    client_secret: str
    callback_url: str
    allowed_character_ids: tuple[int, ...]
    session_secret: str
    session_ttl_minutes: int


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

        expires_at = issued_at + timedelta(minutes=OAUTH_STATE_TTL_MINUTES)
        return expires_at > self._now()

    def complete_login(self, *, code: str, returned_state: str, expected_state: str) -> dict:
        """Exchange an auth code, verify identity, and return a signed admin session."""
        if not returned_state or returned_state != expected_state:
            raise ValueError("Invalid OAuth state")

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
        """Validate a signed admin identity payload."""
        if not identity or "payload" not in identity or "signature" not in identity:
            return None

        payload = identity["payload"]
        expected_signature = self._sign_payload(payload)
        if not hmac.compare_digest(str(identity["signature"]), expected_signature):
            return None

        try:
            expires_at = datetime.fromisoformat(payload["expires_at"])
        except (KeyError, TypeError, ValueError):
            return None

        if expires_at <= self._now():
            return None

        try:
            character_id = int(payload["character_id"])
        except (KeyError, TypeError, ValueError):
            return None

        if character_id not in self._config.allowed_character_ids:
            return None

        return payload

    def _get_metadata(self) -> dict:
        if self._metadata is None:
            response = self._http.get(SSO_METADATA_URL, timeout=15)
            response.raise_for_status()
            self._metadata = response.json()
        return self._metadata

    def _exchange_code(self, code: str) -> str:
        metadata = self._get_metadata()
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
        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError("EVE SSO token response did not include an access token")
        return access_token

    def _verify_access_token(self, access_token: str) -> dict:
        response = self._http.get(
            SSO_VERIFY_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if "CharacterID" not in payload or "CharacterName" not in payload:
            raise ValueError("EVE SSO verify response did not include character identity")
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
    )
    return EveSSOService(config)
