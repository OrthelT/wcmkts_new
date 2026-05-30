"""EVE SSO wrapper for the POC.

This deliberately REUSES your existing `services.eve_sso_service.EveSSOService`
verbatim — the same class the Streamlit admin flow uses. The only thing we
replace is the *factory*: instead of reading `st.secrets`, we build the config
from environment variables. That is the whole thesis of the migration in one
file: business logic ports unchanged; only the Streamlit-coupled glue is swapped.

Two modes:
  * CONFIGURED  — real EVE OAuth via your EveSSOService (set the env vars below).
  * DEMO        — if env vars are absent, a clearly-labeled mock identity so the
                  per-user session features still demo without registering a
                  CCP application.

Env vars (CONFIGURED mode):
  EVE_SSO_CLIENT_ID, EVE_SSO_CLIENT_SECRET
  EVE_SSO_CALLBACK_URL          (default http://localhost:8080/auth/callback)
  EVE_SSO_ALLOWED_CHARACTER_IDS (comma-separated)
  POC_SESSION_SECRET            (>= 32 chars)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

logger = logging.getLogger("poc.auth")

# Scopes you'd request for the real use case (user assets + market orders).
# Note: the existing EveSSOService.create_authorization_url does NOT add scopes
# (it's an identity-only admin login). For ESI asset access you append these —
# shown here to make the gap explicit.
ESI_SCOPES = (
    "esi-assets.read_assets.v1 "
    "esi-markets.read_character_orders.v1"
)


def build_sso_service():
    """Return (service, mode). mode is 'configured' or 'demo'."""
    client_id = os.getenv("EVE_SSO_CLIENT_ID")
    client_secret = os.getenv("EVE_SSO_CLIENT_SECRET")
    allowed = os.getenv("EVE_SSO_ALLOWED_CHARACTER_IDS", "")
    session_secret = os.getenv("POC_SESSION_SECRET", "")

    if not (client_id and client_secret and allowed and len(session_secret) >= 32):
        logger.info("EVE SSO env not fully set — running in DEMO (mock) mode.")
        return None, "demo"

    from services.eve_sso_service import EveSSOConfig, EveSSOService

    config = EveSSOConfig(
        client_id=client_id,
        client_secret=client_secret,
        callback_url=os.getenv(
            "EVE_SSO_CALLBACK_URL", "http://localhost:8080/auth/callback"
        ),
        allowed_character_ids=tuple(
            int(x) for x in allowed.split(",") if x.strip()
        ),
        session_secret=session_secret,
        session_ttl_minutes=int(os.getenv("POC_SESSION_TTL_MIN", "120")),
    )
    return EveSSOService(config), "configured"


def authorization_url(service, state: str) -> str:
    """Build the EVE authorize URL, adding ESI scopes the base method omits."""
    base = service.create_authorization_url(state)
    sep = "&" if "?" in base else "?"
    from urllib.parse import quote

    return f"{base}{sep}scope={quote(ESI_SCOPES)}"
