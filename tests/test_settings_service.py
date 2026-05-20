"""Tests for application settings accessors."""

import pytest

import settings_service


def test_admin_write_target_defaults_to_local_without_admin_section(monkeypatch):
    """Safe default: an unset admin.write_target must not route writes to prod."""
    monkeypatch.setattr(settings_service, "_cached_settings", {}, raising=False)

    settings = settings_service.SettingsService()

    assert settings.admin_write_target == "local"


def test_doctrine_override_returns_none_when_section_absent(monkeypatch):
    monkeypatch.setattr(settings_service, "_cached_settings", {}, raising=False)
    assert settings_service.get_doctrine_override("wcmktnewkeep") is None


def test_doctrine_override_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "_cached_settings",
        {
            "doctrine_override": {
                "doctrine_override_enabled": False,
                "override_market_alias": "wcmktnewkeep",
                "use_market_key": "primary",
            }
        },
        raising=False,
    )
    assert settings_service.get_doctrine_override("wcmktnewkeep") is None


def test_doctrine_override_returns_none_for_alias_mismatch(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "_cached_settings",
        {
            "doctrine_override": {
                "doctrine_override_enabled": True,
                "override_market_alias": "wcmktnewkeep",
                "use_market_key": "primary",
            }
        },
        raising=False,
    )
    assert settings_service.get_doctrine_override("wcmktprod") is None


def test_doctrine_override_returns_market_key_for_matching_alias(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "_cached_settings",
        {
            "doctrine_override": {
                "doctrine_override_enabled": True,
                "override_market_alias": "wcmktnewkeep",
                "use_market_key": "primary",
            }
        },
        raising=False,
    )
    assert settings_service.get_doctrine_override("wcmktnewkeep") == "primary"


def test_doctrine_override_raises_when_configured_but_missing_market_key(monkeypatch):
    """Data Integrity Rule: configured-but-malformed must fail loud, not silently drop."""
    monkeypatch.setattr(
        settings_service,
        "_cached_settings",
        {
            "doctrine_override": {
                "doctrine_override_enabled": True,
                "override_market_alias": "wcmktnewkeep",
            }
        },
        raising=False,
    )
    with pytest.raises(ValueError, match="use_market_key"):
        settings_service.get_doctrine_override("wcmktnewkeep")


def test_doctrine_override_raises_when_market_key_is_wrong_type(monkeypatch):
    monkeypatch.setattr(
        settings_service,
        "_cached_settings",
        {
            "doctrine_override": {
                "doctrine_override_enabled": True,
                "override_market_alias": "wcmktnewkeep",
                "use_market_key": 42,
            }
        },
        raising=False,
    )
    with pytest.raises(ValueError, match="use_market_key"):
        settings_service.get_doctrine_override("wcmktnewkeep")
