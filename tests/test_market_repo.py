"""
Tests for MarketRepository

Tests the market data repository with:
- Cached data fetchers (stats, orders, history)
- Per-type history queries
- Update time retrieval
- Targeted cache invalidation
- Factory function integration
- Malformed DB recovery paths via BaseRepository.read_df()
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, PropertyMock, MagicMock


class TestMarketRepositoryCachedFunctions:
    """Test the module-level cached functions that back MarketRepository methods."""

    def _mock_engine(self):
        """Create a mock engine with context-manager connect()."""
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn
        return mock_engine, mock_conn

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_get_all_stats_returns_dataframe(self, mock_read_sql, mock_db_cls):
        """_get_all_stats returns a DataFrame from the marketstats table."""
        expected = pd.DataFrame({"type_id": [34, 35], "price": [10.0, 20.0]})
        mock_read_sql.return_value = expected
        mock_engine, _ = self._mock_engine()
        mock_db = Mock()
        type(mock_db).engine = PropertyMock(return_value=mock_engine)
        mock_db_cls.return_value = mock_db

        from repositories.market_repo import _get_all_stats_impl
        result = _get_all_stats_impl()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        assert "type_id" in result.columns

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_get_all_orders_returns_dataframe(self, mock_read_sql, mock_db_cls):
        """_get_all_orders returns a DataFrame from the marketorders table."""
        expected = pd.DataFrame({
            "order_id": [1, 2],
            "type_id": [34, 35],
            "price": [10.0, 20.0],
            "is_buy_order": [0, 1],
        })
        mock_read_sql.return_value = expected
        mock_engine, _ = self._mock_engine()
        mock_db = Mock()
        type(mock_db).engine = PropertyMock(return_value=mock_engine)
        mock_db_cls.return_value = mock_db

        from repositories.market_repo import _get_all_orders_impl
        result = _get_all_orders_impl()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_get_all_history_returns_dataframe(self, mock_read_sql, mock_db_cls):
        """_get_all_history returns a DataFrame from the market_history table."""
        expected = pd.DataFrame({
            "type_id": [34], "date": ["2026-01-01"],
            "average": [10.0], "volume": [1000],
        })
        mock_read_sql.return_value = expected
        mock_engine, _ = self._mock_engine()
        mock_db = Mock()
        type(mock_db).engine = PropertyMock(return_value=mock_engine)
        mock_db_cls.return_value = mock_db

        from repositories.market_repo import _get_all_history_impl
        result = _get_all_history_impl()

        assert isinstance(result, pd.DataFrame)
        assert "type_id" in result.columns

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_get_history_by_type_returns_filtered(self, mock_read_sql, mock_db_cls):
        """_get_history_by_type returns history for a specific type_id."""
        expected = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-02"],
            "average": [10.0, 11.0],
            "volume": [1000, 1200],
        })
        mock_read_sql.return_value = expected
        mock_engine, _ = self._mock_engine()
        mock_db = Mock()
        type(mock_db).engine = PropertyMock(return_value=mock_engine)
        mock_db_cls.return_value = mock_db

        from repositories.market_repo import _get_history_by_type_impl
        result = _get_history_by_type_impl(34)

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2
        # Verify the query was called with type_id param
        call_args = mock_read_sql.call_args
        assert call_args[1]["params"]["type_id"] == 34


class TestMarketRepositoryMalformedRecovery:
    """Test malformed DB recovery in cached functions."""

    def _mock_engine(self):
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn
        return mock_engine, mock_conn

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_stats_recovery_on_malformed_db(self, mock_read_sql, mock_db_cls):
        """Stats function recovers from malformed DB by syncing and retrying."""
        expected = pd.DataFrame({"type_id": [34], "price": [10.0]})
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("database disk image is malformed")
            return expected

        mock_read_sql.side_effect = side_effect
        mock_engine, _ = self._mock_engine()
        mock_db = Mock()
        type(mock_db).engine = PropertyMock(return_value=mock_engine)
        mock_db_cls.return_value = mock_db

        from repositories.market_repo import _get_all_stats_impl
        result = _get_all_stats_impl()

        assert isinstance(result, pd.DataFrame)
        mock_db.sync.assert_called_once()

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_orders_remote_fallback_on_persistent_error(self, mock_read_sql, mock_db_cls):
        """Orders function falls back to remote when local stays broken after sync."""
        expected = pd.DataFrame({"order_id": [1], "type_id": [34], "price": [10.0]})
        mock_engine, _ = self._mock_engine()
        mock_remote_engine, _ = self._mock_engine()
        mock_db = Mock()
        type(mock_db).engine = PropertyMock(return_value=mock_engine)
        type(mock_db).remote_engine = PropertyMock(return_value=mock_remote_engine)
        mock_db_cls.return_value = mock_db

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First two calls (local) fail, third call (remote) succeeds
            if call_count <= 2:
                raise Exception("database disk image is malformed")
            return expected

        mock_read_sql.side_effect = side_effect

        from repositories.market_repo import _get_all_orders_impl
        result = _get_all_orders_impl()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        mock_db.sync.assert_called_once()


class TestMarketRepositoryClass:
    """Test the MarketRepository class methods."""

    @patch("repositories.market_repo._get_all_stats_cached")
    def test_get_all_stats_delegates(self, mock_cached):
        """Class method delegates to cached function."""
        expected = pd.DataFrame({"type_id": [34]})
        mock_cached.return_value = expected

        from repositories.market_repo import MarketRepository
        mock_db = Mock()
        repo = MarketRepository(mock_db)
        result = repo.get_all_stats()

        assert result is expected
        mock_cached.assert_called_once()

    @patch("repositories.market_repo._get_all_orders_cached")
    def test_get_all_orders_delegates(self, mock_cached):
        expected = pd.DataFrame({"order_id": [1]})
        mock_cached.return_value = expected

        from repositories.market_repo import MarketRepository
        mock_db = Mock()
        repo = MarketRepository(mock_db)
        result = repo.get_all_orders()

        assert result is expected

    @patch("repositories.market_repo._get_all_history_cached")
    def test_get_all_history_delegates(self, mock_cached):
        expected = pd.DataFrame({"date": ["2026-01-01"]})
        mock_cached.return_value = expected

        from repositories.market_repo import MarketRepository
        mock_db = Mock()
        repo = MarketRepository(mock_db)
        result = repo.get_all_history()

        assert result is expected

    @patch("repositories.market_repo._get_history_by_type_cached")
    def test_get_history_by_type_delegates(self, mock_cached):
        expected = pd.DataFrame({"date": ["2026-01-01"], "average": [10.0]})
        mock_cached.return_value = expected

        from repositories.market_repo import MarketRepository
        mock_db = Mock()
        repo = MarketRepository(mock_db)
        result = repo.get_history_by_type(34)

        assert result is expected
        mock_cached.assert_called_once_with(34, mock_db.alias)


class TestGetUpdateTime:
    """Test get_update_time utility."""

    def test_returns_formatted_time_from_dict(self):
        from datetime import datetime, timezone
        from repositories.market_repo import get_update_time

        update_time = datetime(2026, 1, 15, 14, 30, 0, tzinfo=timezone.utc)
        status = {"updated": update_time, "needs_update": False}
        result = get_update_time(status)

        assert result == "2026-01-15 | 14:30 UTC"

    def test_returns_none_for_none_status(self):
        from repositories.market_repo import get_update_time
        assert get_update_time(None) is None

    def test_returns_none_for_empty_dict(self):
        from repositories.market_repo import get_update_time
        assert get_update_time({}) is None

    def test_returns_none_for_bool_status(self):
        from repositories.market_repo import get_update_time
        assert get_update_time(True) is None


class TestInvalidateMarketCaches:
    """Test targeted cache invalidation."""

    @patch("repositories.market_repo._get_all_stats_cached")
    @patch("repositories.market_repo._get_all_orders_cached")
    @patch("repositories.market_repo._get_all_history_cached")
    @patch("repositories.market_repo._get_history_by_type_cached")
    def test_invalidate_clears_all_market_caches(
        self, mock_history_type, mock_history, mock_orders, mock_stats
    ):
        """invalidate_market_caches clears all four market cache functions."""
        from repositories.market_repo import invalidate_market_caches

        invalidate_market_caches()

        mock_stats.clear.assert_called_once()
        mock_orders.clear.assert_called_once()
        mock_history.clear.assert_called_once()
        mock_history_type.clear.assert_called_once()


class TestGetLocalPrice:
    """Test the get_local_price impl function."""

    def _mock_engine(self):
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn
        return mock_engine, mock_conn

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_returns_price_when_found(self, mock_read_sql, mock_db_cls):
        expected = pd.DataFrame({"price": [125.50]})
        mock_read_sql.return_value = expected
        mock_engine, _ = self._mock_engine()
        mock_db = Mock()
        mock_db.engine = mock_engine
        mock_db_cls.return_value = mock_db

        from repositories.market_repo import _get_local_price_impl
        result = _get_local_price_impl(34)

        assert result == 125.50

    @patch("repositories.market_repo.DatabaseConfig")
    @patch("pandas.read_sql_query")
    def test_returns_none_when_not_found(self, mock_read_sql, mock_db_cls):
        mock_read_sql.return_value = pd.DataFrame({"price": []})
        mock_engine, _ = self._mock_engine()
        mock_db = Mock()
        mock_db.engine = mock_engine
        mock_db_cls.return_value = mock_db

        from repositories.market_repo import _get_local_price_impl
        result = _get_local_price_impl(99999999)

        assert result is None


class TestMarketRepositoryFactory:
    """Test get_market_repository factory function."""

    @patch("repositories.market_repo.DatabaseConfig")
    def test_factory_creates_repository(self, mock_db_cls):
        """Factory creates a MarketRepository instance."""
        from repositories.market_repo import MarketRepository

        mock_db = Mock()
        mock_db_cls.return_value = mock_db

        # Test the fallback path (no state module)
        with patch.dict("sys.modules", {"state": None}):
            from repositories.market_repo import get_market_repository
            repo = get_market_repository()
            assert isinstance(repo, MarketRepository)
