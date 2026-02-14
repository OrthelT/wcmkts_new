"""
Tests for DatabaseConfig alias resolution and cache keying.

Validates the critical behavior: when code uses the virtual "wcmkt" alias,
DatabaseConfig resolves it to the concrete alias of the active market
(e.g. "wcmktprod" or "wcmktnorth"), and repository methods pass that
resolved alias to cached functions — giving each market its own cache entry.
"""

import pytest
from unittest.mock import patch, Mock, PropertyMock, MagicMock


# ---------------------------------------------------------------------------
# DatabaseConfig alias resolution
# ---------------------------------------------------------------------------

class TestAliasResolution:
    """DatabaseConfig("wcmkt") resolves to the active market's database_alias."""

    @patch("config.DatabaseConfig._resolve_active_market_alias", return_value="wcmktprod")
    def test_wcmkt_resolves_to_active_market(self, mock_resolve):
        """'wcmkt' resolves to whatever _resolve_active_market_alias returns."""
        from config import DatabaseConfig
        db = DatabaseConfig("wcmkt")
        assert db.alias == "wcmktprod"

    @patch("config.DatabaseConfig._resolve_active_market_alias", return_value="wcmktnorth")
    def test_wcmkt_resolves_to_deployment_market(self, mock_resolve):
        """'wcmkt' resolves to deployment alias when that market is active."""
        from config import DatabaseConfig
        db = DatabaseConfig("wcmkt")
        assert db.alias == "wcmktnorth"

    @patch("config.DatabaseConfig._resolve_active_market_alias", return_value=None)
    def test_wcmkt_falls_back_to_wcdbmap(self, mock_resolve):
        """'wcmkt' falls back to static wcdbmap when outside Streamlit."""
        from config import DatabaseConfig
        db = DatabaseConfig("wcmkt")
        assert db.alias == DatabaseConfig.wcdbmap

    def test_concrete_alias_unchanged(self):
        """Concrete aliases like 'sde' are not resolved."""
        from config import DatabaseConfig
        db = DatabaseConfig("sde")
        assert db.alias == "sde"

    @patch("config.DatabaseConfig._resolve_active_market_alias", return_value="wcmktprod")
    def test_deprecated_wcmkt2_resolves_same_as_wcmkt(self, mock_resolve):
        """Deprecated 'wcmkt2' alias still resolves via the same path."""
        from config import DatabaseConfig
        db = DatabaseConfig("wcmkt2")
        assert db.alias == "wcmktprod"

    @patch("config.DatabaseConfig._resolve_active_market_alias", return_value="wcmktprod")
    def test_deprecated_wcmkt3_resolves_same_as_wcmkt(self, mock_resolve):
        """Deprecated 'wcmkt3' alias still resolves via the same path."""
        from config import DatabaseConfig
        db = DatabaseConfig("wcmkt3")
        assert db.alias == "wcmktprod"

    def test_unknown_alias_raises(self):
        """Unknown alias raises ValueError."""
        from config import DatabaseConfig
        with pytest.raises(ValueError, match="Unknown database alias"):
            DatabaseConfig("nonexistent_db")


# ---------------------------------------------------------------------------
# Resolved alias produces distinct objects per market
# ---------------------------------------------------------------------------

class TestAliasDistinctness:
    """Different active markets produce DatabaseConfig instances with different aliases."""

    def test_two_markets_have_different_aliases(self):
        """Switching the active market changes the resolved alias."""
        from config import DatabaseConfig

        with patch.object(
            DatabaseConfig, "_resolve_active_market_alias", return_value="wcmktprod"
        ):
            db_primary = DatabaseConfig("wcmkt")

        with patch.object(
            DatabaseConfig, "_resolve_active_market_alias", return_value="wcmktnorth"
        ):
            db_deploy = DatabaseConfig("wcmkt")

        assert db_primary.alias != db_deploy.alias
        assert db_primary.alias == "wcmktprod"
        assert db_deploy.alias == "wcmktnorth"

    def test_two_markets_have_different_paths(self):
        """Different resolved aliases point to different database files."""
        from config import DatabaseConfig

        with patch.object(
            DatabaseConfig, "_resolve_active_market_alias", return_value="wcmktprod"
        ):
            db_primary = DatabaseConfig("wcmkt")

        with patch.object(
            DatabaseConfig, "_resolve_active_market_alias", return_value="wcmktnorth"
        ):
            db_deploy = DatabaseConfig("wcmkt")

        assert db_primary.path != db_deploy.path


# ---------------------------------------------------------------------------
# Repository passes resolved alias (not "wcmkt") to cached functions
# ---------------------------------------------------------------------------

class TestRepositoryCacheKeying:
    """MarketRepository delegates to cached functions with the resolved alias."""

    @patch("repositories.market_repo._get_all_stats_cached")
    def test_get_all_stats_passes_resolved_alias(self, mock_cached):
        """get_all_stats() passes db.alias, not the literal 'wcmkt'."""
        mock_cached.return_value = MagicMock()
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db.alias = "wcmktprod"
        repo = MarketRepository(mock_db)
        repo.get_all_stats()

        mock_cached.assert_called_once_with("wcmktprod")

    @patch("repositories.market_repo._get_all_orders_cached")
    def test_get_all_orders_passes_resolved_alias(self, mock_cached):
        mock_cached.return_value = MagicMock()
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db.alias = "wcmktnorth"
        repo = MarketRepository(mock_db)
        repo.get_all_orders()

        mock_cached.assert_called_once_with("wcmktnorth")

    @patch("repositories.market_repo._get_all_history_cached")
    def test_get_all_history_passes_resolved_alias(self, mock_cached):
        mock_cached.return_value = MagicMock()
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db.alias = "wcmktprod"
        repo = MarketRepository(mock_db)
        repo.get_all_history()

        mock_cached.assert_called_once_with("wcmktprod")

    @patch("repositories.market_repo._get_history_by_type_cached")
    def test_get_history_by_type_passes_resolved_alias(self, mock_cached):
        mock_cached.return_value = MagicMock()
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db.alias = "wcmktnorth"
        repo = MarketRepository(mock_db)
        repo.get_history_by_type(34)

        mock_cached.assert_called_once_with(34, "wcmktnorth")

    @patch("repositories.market_repo._get_local_price_cached")
    def test_get_local_price_passes_resolved_alias(self, mock_cached):
        mock_cached.return_value = 100.0
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db.alias = "wcmktprod"
        repo = MarketRepository(mock_db)
        repo.get_local_price(34)

        mock_cached.assert_called_once_with(34, "wcmktprod")

    @patch("repositories.market_repo._get_watchlist_type_ids_cached")
    def test_get_watchlist_passes_resolved_alias(self, mock_cached):
        mock_cached.return_value = [34, 35]
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db.alias = "wcmktnorth"
        repo = MarketRepository(mock_db)
        repo.get_watchlist_type_ids()

        mock_cached.assert_called_once_with("wcmktnorth")

    @patch("repositories.market_repo._get_market_type_ids_cached")
    def test_get_market_type_ids_passes_resolved_alias(self, mock_cached):
        mock_cached.return_value = [34, 35, 36]
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db.alias = "wcmktprod"
        repo = MarketRepository(mock_db)
        repo.get_market_type_ids()

        mock_cached.assert_called_once_with("wcmktprod")


# ---------------------------------------------------------------------------
# Two markets get separate cache keys (integration-style)
# ---------------------------------------------------------------------------

class TestCacheKeyIsolation:
    """Different markets produce different cache key arguments."""

    @patch("repositories.market_repo._get_all_stats_cached")
    def test_two_repos_produce_different_cache_keys(self, mock_cached):
        """Repos for different markets call cached func with different aliases."""
        mock_cached.return_value = MagicMock()
        from repositories.market_repo import MarketRepository

        db_prod = Mock()
        db_prod.alias = "wcmktprod"
        db_north = Mock()
        db_north.alias = "wcmktnorth"

        repo_prod = MarketRepository(db_prod)
        repo_north = MarketRepository(db_north)

        repo_prod.get_all_stats()
        repo_north.get_all_stats()

        calls = mock_cached.call_args_list
        assert len(calls) == 2
        assert calls[0].args == ("wcmktprod",)
        assert calls[1].args == ("wcmktnorth",)

    @patch("repositories.market_repo._get_history_by_type_cached")
    def test_same_type_different_markets_different_keys(self, mock_cached):
        """Same type_id on different markets produces distinct cache calls."""
        mock_cached.return_value = MagicMock()
        from repositories.market_repo import MarketRepository

        db_prod = Mock()
        db_prod.alias = "wcmktprod"
        db_north = Mock()
        db_north.alias = "wcmktnorth"

        MarketRepository(db_prod).get_history_by_type(34)
        MarketRepository(db_north).get_history_by_type(34)

        calls = mock_cached.call_args_list
        assert len(calls) == 2
        assert calls[0].args == (34, "wcmktprod")
        assert calls[1].args == (34, "wcmktnorth")
