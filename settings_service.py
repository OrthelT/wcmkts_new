"""Centralized settings loader for the application.

Infrastructure-level module — must not import from services/, repositories/,
config.py, or logging_config.py to avoid circular imports.
"""

import tomllib
import logging
from datetime import datetime, timedelta, timezone
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


def get_db_update_schedule() -> tuple[int, int]:
    """Return the (frequency_hours, minutes_after_hour) schedule for DB updates.

    Values come from the ``[db_update]`` section of settings.toml:
      - ``frequency``: hours between scheduled updates (1 = hourly)
      - ``time``: minutes after the hour when the update runs

    Defaults to (1, 0) if the section is missing so callers always get a
    valid schedule.
    """
    settings = _load_settings()
    cfg = settings.get("db_update", {})
    frequency = int(cfg.get("frequency", 1))
    minute = int(cfg.get("time", 0))
    if frequency < 1:
        frequency = 1
    minute = max(0, min(59, minute))
    return frequency, minute


def time_until_next_db_update(now: datetime | None = None) -> timedelta:
    """Return the ``timedelta`` from ``now`` until the next scheduled DB update.

    The schedule is midnight-UTC anchored: updates run every ``frequency``
    hours at ``minute`` past the hour (e.g. 00:20, 01:20, 02:20 for
    frequency=1, minute=20). If every slot today has already passed, this
    rolls over to the first slot of the following day.

    Note: "every ``frequency`` hours" only holds cleanly when ``frequency``
    divides 24 (1, 2, 3, 4, 6, 8, 12, 24). For non-divisors (e.g. 5), the
    last daily slot lands before 24h and the rollover resets at 00:``minute``
    tomorrow — producing a short gap between the last slot of today and the
    first slot of tomorrow. Use divisor values to keep the cadence uniform.

    Args:
        now: Reference time (assumed UTC if naive). Defaults to ``datetime.now(tz=UTC)``.
    """
    frequency, minute = get_db_update_schedule()
    if now is None:
        now = datetime.now(tz=timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        # Schedule is UTC-anchored; convert any other tz so the midnight
        # boundary below lands on UTC midnight, not the caller's local one.
        now = now.astimezone(timezone.utc)

    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Iterate candidate slots for today, then fall through to tomorrow.
    slots_per_day = max(1, 24 // frequency)
    for k in range(slots_per_day):
        candidate = midnight + timedelta(hours=k * frequency, minutes=minute)
        if candidate > now:
            return candidate - now
    tomorrow_midnight = midnight + timedelta(days=1)
    return (tomorrow_midnight + timedelta(minutes=minute)) - now


def minutes_until_next_db_update(now: datetime | None = None) -> int:
    """Return the whole-minute countdown until the next scheduled DB update.

    Convenience wrapper around :func:`time_until_next_db_update` for UI
    callers that just want an integer. Rounds up so a countdown of 0s
    becomes 1 minute (never report "0 minutes" to the user).
    """
    delta = time_until_next_db_update(now)
    total_seconds = max(0, int(delta.total_seconds()))
    # Round up to at least 1 so we never render "0 minutes".
    minutes = (total_seconds + 59) // 60
    return max(1, minutes)


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
