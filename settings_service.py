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
