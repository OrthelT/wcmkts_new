import tomllib
import logging
from pathlib import Path

logger = logging.basicConfig()
root_dir = Path.cwd()
settings_path = Path(__file__).resolve().parent.parent / "settings.toml"


class SettingsService:
    def __init__(self, settings_path: Path = "settings.toml"):
        self.settings_path = settings_path
        self.settings_dict = self.get_settings()
        self.settings = self.settings_dict

    def get_settings(self) -> dict:
        """Get the settings from the settings.toml file."""
        try:
            with open(self.settings_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            logger.error(f"Failed to load settings from settings.toml: {e}")
            raise e

    def get_settings_keys(self) -> str:
        return self.settings.keys()

    @property
    def log_level(self):
        ll = self.settings["env"]["log_level"]
        return ll

    @property
    def env(self):
        return self.settings["env"]["env"]

    @property
    def use_equivalents(self):
        equivelents_strategy = self.settings["module_strategy"]["use_equivelent"]
        print(f"\n equivelents_strategy: {equivelents_strategy}\n")
        return equivelents_strategy


if __name__ == "__main__":
    pass
