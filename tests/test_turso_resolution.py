"""Tests for DatabaseConfig Turso secret-section resolution.

Market hubs declare their secrets.toml section via
``[markets.*].turso_secret_key``; DatabaseConfig must resolve credentials from
that single source so the config the app reasons about and the config that
drives sync can never drift. Non-market utility DBs fall back to
``[db_turso_keys]`` overrides, then the ``{alias}_turso`` convention.
"""
import unittest


class TestTursoSecretResolution(unittest.TestCase):
    """Unit tests for the pure secret-section resolution helper."""

    def test_market_alias_resolves_to_market_config_secret_key(self):
        """A market hub's section comes from MarketConfig.turso_secret_key,
        not the {alias}_turso convention. This is the regression guard for the
        case where secrets.toml has no {alias}_turso section (e.g. wcmktprod
        reached via [market3_turso])."""
        from config import _resolve_turso_section

        market_secret_keys = {
            "wcmktprod": "market3_turso",
            "market3": "wcmktnorth_turso",
        }
        overrides = {"sde": "sdelite_turso"}
        self.assertEqual(
            _resolve_turso_section("wcmktprod", market_secret_keys, overrides),
            "market3_turso",
        )

    def test_override_used_when_not_a_market_alias(self):
        """Utility DBs without a market config use their [db_turso_keys] override."""
        from config import _resolve_turso_section

        self.assertEqual(
            _resolve_turso_section("sde", {}, {"sde": "sdelite_turso"}),
            "sdelite_turso",
        )

    def test_convention_used_when_no_market_or_override(self):
        """An alias with neither a market config nor an override falls back to
        the {alias}_turso convention."""
        from config import _resolve_turso_section

        self.assertEqual(
            _resolve_turso_section("wcmkttest", {}, {}),
            "wcmkttest_turso",
        )

    def test_market_config_takes_precedence_over_override(self):
        """When an alias is both a market alias and has an override, the market
        config wins — it is the single source of truth for market hubs."""
        from config import _resolve_turso_section

        self.assertEqual(
            _resolve_turso_section("x", {"x": "from_market"}, {"x": "from_override"}),
            "from_market",
        )


if __name__ == "__main__":
    unittest.main()
