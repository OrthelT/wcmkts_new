"""Tests for application settings accessors."""

import settings_service


def test_admin_write_target_defaults_to_local_without_admin_section(monkeypatch):
    """Safe default: an unset admin.write_target must not route writes to prod."""
    monkeypatch.setattr(settings_service, "_cached_settings", {}, raising=False)

    settings = settings_service.SettingsService()

    assert settings.admin_write_target == "local"
