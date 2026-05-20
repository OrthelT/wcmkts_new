"""Centralized settings loader for the application.

Infrastructure-level module — must not import from services/, repositories/,
config.py, or logging_config.py to avoid circular imports.
"""

import tomllib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_cached_settings: dict | None = None


def _load_settings(settings_path: Path = Path("settings.toml")) -> dict:
    """Load and cache settings from the TOML file."""
    global _cached_settings
    if _cached_settings is not None:
        return _cached_settings
    try:
        with open(settings_path, "rb") as f:
            _cached_settings = tomllib.load(f)
            return _cached_settings
    except Exception as e:
        logger.error("Failed to load settings from %s: %s", settings_path, e)
        raise


def get_freshness_probe_aliases() -> list[str]:
    """Return database aliases configured for post-sync freshness probes.

    Source of truth for "which DBs participate in periodic staleness
    checking" — driven by ``[freshness_probes]`` in settings.toml.
    """
    settings = _load_settings()
    return list(settings.get("freshness_probes", {}).keys())


def get_doctrine_override(market_alias: str) -> str | None:
    """Return the extra ``market_flag`` value to merge for ``market_alias``, or None.

    Reads ``[doctrine_override]`` from settings.toml. Returns None when the override
    is absent, disabled, or targets a different alias — those are legitimate
    "no override" states.

    Raises ValueError when the override IS configured for this alias but
    ``use_market_key`` is missing or malformed. Per the project Data Integrity Rule,
    silently dropping a configured override would surface fits from the wrong market.
    """
    settings = _load_settings()
    override = settings.get("doctrine_override", {})
    if not override.get("doctrine_override_enabled"):
        return None
    if override.get("override_market_alias") != market_alias:
        return None

    market_key = override.get("use_market_key")
    if not isinstance(market_key, str) or not market_key:
        raise ValueError(
            f"doctrine_override is configured for {market_alias!r} but use_market_key "
            f"is missing or invalid: {market_key!r}"
        )
    return market_key


def get_all_market_configs() -> dict:
    """Return a dict of MarketConfig keyed by market key (e.g. 'primary').

    Module-level convenience function so callers don't need SettingsService.
    """
    from domain.market_config import MarketConfig

    settings = _load_settings()
    markets_raw = settings.get("markets", {})
    configs: dict = {}
    for key, vals in markets_raw.items():
        configs[key] = MarketConfig(
            key=key,
            name=vals["name"],
            short_name=vals["short_name"],
            region_id=vals["region_id"],
            system_id=vals["system_id"],
            structure_id=vals["structure_id"],
            database_alias=vals["database_alias"],
            database_file=vals["database_file"],
            turso_secret_key=vals["turso_secret_key"],
        )
    return configs


class SettingsService:
    """Read-only accessor for application settings.

    Settings are cached at module level after the first read.
    """

    def __init__(self, settings_path: str | Path = Path("settings.toml")):
        self.settings = _load_settings(Path(settings_path))

    @property
    def settings_dict(self) -> dict:
        """Return the full settings dictionary (backwards compat with get_settings())."""
        return self.settings

    @property
    def log_level(self) -> str:
        return self.settings["env"]["log_level"]

    @property
    def env(self) -> str:
        return self.settings["env"]["env"]

    @property
    def use_equivalents(self) -> bool:
        return self.settings["module_strategy"]["use_equivalent"]

    @property
    def default_shipping_cost(self) -> float:
        return float(self.settings.get("import_helper", {}).get("default_shipping_cost", 445))

    @property
    def default_language(self) -> str:
        return self.settings.get("i18n", {}).get("default_language", "en")

    @property
    def eve_sso_client_id(self) -> str:
        return str(self.settings.get("eve_sso", {}).get("client_id", ""))

    @property
    def eve_sso_callback_url(self) -> str:
        return str(self.settings.get("eve_sso", {}).get("callback_url", ""))

    @property
    def eve_sso_allowed_character_ids(self) -> tuple[int, ...]:
        values = self.settings.get("eve_sso", {}).get("allowed_character_ids", [])
        return tuple(int(value) for value in values)

    @property
    def admin_write_target(self) -> str:
        target = str(self.settings.get("admin", {}).get("write_target", "local")).strip().lower()
        if target not in {"local", "remote"}:
            raise ValueError("admin.write_target must be 'local' or 'remote'")
        return target

    @property
    def admin_session_ttl_minutes(self) -> int:
        return int(self.settings.get("admin", {}).get("session_ttl_minutes", 480))

    @property
    def admin_oauth_state_ttl_minutes(self) -> int:
        """How long an OAuth state token remains valid after generation (default 15).

        Source of truth lives in ``[admin]`` so ops can tune the window without
        a code change. Below 5 minutes risks racing tab-restore flows; above 60
        minutes weakens replay resistance during incident rollback windows.
        """
        return int(self.settings.get("admin", {}).get("oauth_state_ttl_minutes", 15))

def resolve_db_alias(db_alias: str | None = None, fallback: str = "wcmkt") -> str:
    """Resolve a database alias, falling back to the active market hub.

    Shared helper for service factory methods that all need the same
    "use active market if no alias given, fall back to a safe default" logic.
    """
    if db_alias is not None:
        return db_alias
    try:
        from state.market_state import get_active_market
        return get_active_market().database_alias
    except (ImportError, Exception):
        return fallback
