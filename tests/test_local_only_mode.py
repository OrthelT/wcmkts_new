"""Tests for local-only mode feature.

Validates that the is_local_only() gate works correctly and that
sync() respects local-only mode.
"""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestIsLocalOnly(unittest.TestCase):
    """Test the is_local_only() function and SettingsService.local_only property."""

    def _make_service(self, env_settings: dict):
        """Create a SettingsService with mocked settings."""
        import settings_service

        settings = {"env": env_settings}
        with patch.object(settings_service, "_cached_settings", settings):
            return settings_service.SettingsService()

    def test_local_only_true(self):
        import settings_service

        settings = {"env": {"local_only": True}}
        with patch.object(settings_service, "_cached_settings", settings):
            self.assertTrue(settings_service.is_local_only())

    def test_local_only_false(self):
        import settings_service

        settings = {"env": {"local_only": False}}
        with patch.object(settings_service, "_cached_settings", settings):
            self.assertFalse(settings_service.is_local_only())

    def test_local_only_missing_key_defaults_false(self):
        import settings_service

        settings = {"env": {"log_level": "DEBUG"}}
        with patch.object(settings_service, "_cached_settings", settings):
            self.assertFalse(settings_service.is_local_only())

    def test_local_only_missing_env_section_defaults_false(self):
        import settings_service

        settings = {}
        with patch.object(settings_service, "_cached_settings", settings):
            self.assertFalse(settings_service.is_local_only())

    def test_property_matches_function(self):
        import settings_service

        for value in (True, False):
            settings = {"env": {"local_only": value}}
            with patch.object(settings_service, "_cached_settings", settings):
                svc = settings_service.SettingsService()
                self.assertEqual(svc.local_only, settings_service.is_local_only())


class TestSettingsTomlLocalOnlyDefault(unittest.TestCase):
    """Ensure the committed settings.toml has local_only = false.

    Prevents accidental deployment with sync disabled.
    """

    def test_local_only_is_false_in_committed_settings(self):
        import tomllib

        settings_path = Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        self.assertFalse(
            settings.get("env", {}).get("local_only", False),
            "settings.toml must have local_only = false to prevent "
            "accidental production deployment without sync",
        )


class TestSyncLocalOnlyMode(unittest.TestCase):
    """Test DatabaseConfig.sync() behavior in local-only mode."""

    @patch("settings_service.is_local_only", return_value=True)
    @patch("init_db.verify_db_content", return_value=True)
    def test_sync_returns_true_when_db_has_content(self, mock_verify, mock_local):
        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = "wcmktprod"
        db.path = "/fake/wcmktprod.db"
        db.turso_url = None
        db.token = None

        result = db.sync()

        self.assertTrue(result)
        mock_verify.assert_called_once_with("/fake/wcmktprod.db")

    @patch("settings_service.is_local_only", return_value=True)
    @patch("init_db.verify_db_content", return_value=False)
    def test_sync_returns_false_when_db_empty(self, mock_verify, mock_local):
        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = "wcmktprod"
        db.path = "/fake/wcmktprod.db"
        db.turso_url = None
        db.token = None

        result = db.sync()

        self.assertFalse(result)

    @patch("settings_service.is_local_only", return_value=False)
    def test_sync_raises_without_credentials_when_not_local_only(self, mock_local):
        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = "wcmktprod"
        db.path = "/fake/wcmktprod.db"
        db.turso_url = None
        db.token = None

        with self.assertRaises(ValueError):
            db.sync()


if __name__ == "__main__":
    unittest.main()
