"""
Tests for pages/downloads.py

Verifies that download functions respect the active market context
by passing the correct database alias through to repositories.
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, PropertyMock, MagicMock


class TestMarketDownloadsCsv:
    """Test that market CSV functions use the provided db_alias."""

    def _mock_db_and_repo(self, df: pd.DataFrame):
        """Create mocked DatabaseConfig and MarketRepository returning df."""
        mock_db = Mock()
        mock_db.alias = "test_alias"
        mock_repo = Mock()
        mock_repo.get_all_orders.return_value = df
        mock_repo.get_all_stats.return_value = df
        mock_repo.get_all_history.return_value = df
        return mock_db, mock_repo

    @patch("pages.downloads.MarketRepository")
    @patch("pages.downloads.DatabaseConfig")
    def test_market_orders_csv_uses_provided_alias(self, mock_db_cls, mock_repo_cls):
        """_get_market_orders_csv passes db_alias to DatabaseConfig."""
        df = pd.DataFrame({"type_id": [34], "price": [10.0]})
        mock_db, mock_repo = self._mock_db_and_repo(df)
        mock_db_cls.return_value = mock_db
        mock_repo_cls.return_value = mock_repo

        from pages.downloads import _get_market_orders_csv
        _get_market_orders_csv.clear()
        result = _get_market_orders_csv("wcmktprod")

        mock_db_cls.assert_called_once_with("wcmktprod")
        mock_repo_cls.assert_called_once_with(mock_db)
        assert b"type_id" in result
        assert b"34" in result

    @patch("pages.downloads.MarketRepository")
    @patch("pages.downloads.DatabaseConfig")
    def test_market_orders_csv_different_alias(self, mock_db_cls, mock_repo_cls):
        """Different db_alias produces a different DatabaseConfig call."""
        df = pd.DataFrame({"type_id": [99], "price": [5.0]})
        mock_db, mock_repo = self._mock_db_and_repo(df)
        mock_db_cls.return_value = mock_db
        mock_repo_cls.return_value = mock_repo

        from pages.downloads import _get_market_orders_csv
        _get_market_orders_csv.clear()
        _get_market_orders_csv("wcmktnorth")

        mock_db_cls.assert_called_once_with("wcmktnorth")

    @patch("pages.downloads.MarketRepository")
    @patch("pages.downloads.DatabaseConfig")
    def test_market_stats_csv_uses_provided_alias(self, mock_db_cls, mock_repo_cls):
        """_get_market_stats_csv passes db_alias to DatabaseConfig."""
        df = pd.DataFrame({"type_id": [34], "sell_volume": [100]})
        mock_db, mock_repo = self._mock_db_and_repo(df)
        mock_db_cls.return_value = mock_db
        mock_repo_cls.return_value = mock_repo

        from pages.downloads import _get_market_stats_csv
        _get_market_stats_csv.clear()
        _get_market_stats_csv("wcmktnorth")

        mock_db_cls.assert_called_once_with("wcmktnorth")

    @patch("pages.downloads.MarketRepository")
    @patch("pages.downloads.DatabaseConfig")
    def test_market_history_csv_uses_provided_alias(self, mock_db_cls, mock_repo_cls):
        """_get_market_history_csv passes db_alias to DatabaseConfig."""
        df = pd.DataFrame({"type_id": [34], "date": ["2024-01-01"]})
        mock_db, mock_repo = self._mock_db_and_repo(df)
        mock_db_cls.return_value = mock_db
        mock_repo_cls.return_value = mock_repo

        from pages.downloads import _get_market_history_csv
        _get_market_history_csv.clear()
        _get_market_history_csv("wcmktprod")

        mock_db_cls.assert_called_once_with("wcmktprod")


class TestLowStockCsvMarketContext:
    """Test that low stock CSV function uses the provided db_alias."""

    @patch("pages.downloads.BaseRepository")
    @patch("pages.downloads.DatabaseConfig")
    def test_low_stock_csv_uses_provided_alias(self, mock_db_cls, mock_base_repo_cls):
        """_get_low_stock_csv passes db_alias to DatabaseConfig, not hardcoded."""
        mock_db = Mock()
        mock_db_cls.return_value = mock_db

        df = pd.DataFrame({
            "type_id": [34],
            "days_remaining": [3.0],
            "is_doctrine": [0],
            "ship_name": [None],
            "fits_on_mkt": [None],
        })
        mock_repo = Mock()
        mock_repo.read_df.return_value = df
        mock_base_repo_cls.return_value = mock_repo

        from pages.downloads import _get_low_stock_csv
        _get_low_stock_csv.clear()
        _get_low_stock_csv("wcmktnorth", 7.0, False, False)

        mock_db_cls.assert_called_once_with("wcmktnorth")

    @patch("pages.downloads.BaseRepository")
    @patch("pages.downloads.DatabaseConfig")
    def test_low_stock_csv_primary_alias(self, mock_db_cls, mock_base_repo_cls):
        """Verify primary market alias is passed through correctly."""
        mock_db = Mock()
        mock_db_cls.return_value = mock_db

        df = pd.DataFrame({
            "type_id": [34],
            "days_remaining": [3.0],
            "is_doctrine": [0],
            "ship_name": [None],
            "fits_on_mkt": [None],
        })
        mock_repo = Mock()
        mock_repo.read_df.return_value = df
        mock_base_repo_cls.return_value = mock_repo

        from pages.downloads import _get_low_stock_csv
        _get_low_stock_csv.clear()
        _get_low_stock_csv("wcmktprod", 7.0, False, False)

        mock_db_cls.assert_called_once_with("wcmktprod")


class TestDoctrineDownloadsCsv:
    """Test that doctrine CSV functions use the provided db_alias."""

    @patch("pages.downloads.DoctrineService")
    def test_all_doctrine_fits_csv_uses_provided_alias(self, mock_svc_cls):
        """_get_all_doctrine_fits_csv passes db_alias to DoctrineService.create_default."""
        mock_service = Mock()
        mock_service.build_fit_data.return_value.raw_df = pd.DataFrame({
            "fit_id": [1], "type_id": [34], "fit_qty": [1],
            "fits_on_mkt": [2], "ship_name": ["Osprey"], "type_name": ["Tritanium"],
        })
        mock_service.repository.get_all_targets.return_value = pd.DataFrame({
            "fit_id": [1], "fit_name": ["Logi"], "ship_target": [10]
        })
        mock_svc_cls.create_default.return_value = mock_service

        from pages.downloads import _get_all_doctrine_fits_csv
        _get_all_doctrine_fits_csv.clear()
        result = _get_all_doctrine_fits_csv("wcmktnorth")

        mock_svc_cls.create_default.assert_called_once_with("wcmktnorth")
        assert b"fit_id" in result

    @patch("pages.downloads.DoctrineService")
    def test_fit_options_uses_provided_alias(self, mock_svc_cls):
        """_get_fit_options passes db_alias to DoctrineService.create_default."""
        mock_summary = Mock()
        mock_summary.fit_id = 1
        mock_summary.ship_name = "Osprey"
        mock_summary.fit_name = "Logi"
        mock_service = Mock()
        mock_service.get_all_fit_summaries.return_value = [mock_summary]
        mock_svc_cls.create_default.return_value = mock_service

        from pages.downloads import _get_fit_options
        _get_fit_options.clear()
        result = _get_fit_options("wcmktnorth")

        mock_svc_cls.create_default.assert_called_once_with("wcmktnorth")
        assert len(result) == 1
        assert result[0]["ship_name"] == "Osprey"

    @patch("pages.downloads.DoctrineService")
    def test_single_fit_csv_uses_provided_alias(self, mock_svc_cls):
        """_get_single_fit_csv passes db_alias to DoctrineService.create_default."""
        mock_service = Mock()
        mock_service.repository.get_fit_by_id.return_value = pd.DataFrame({
            "fit_id": [1], "type_id": [34]
        })
        mock_svc_cls.create_default.return_value = mock_service

        from pages.downloads import _get_single_fit_csv
        _get_single_fit_csv.clear()
        result = _get_single_fit_csv("wcmktprod", 1)

        mock_svc_cls.create_default.assert_called_once_with("wcmktprod")
        assert b"fit_id" in result

    @patch("pages.downloads.DoctrineService")
    def test_filtered_doctrine_csv_uses_provided_alias(self, mock_svc_cls):
        """_get_filtered_doctrine_csv passes db_alias to DoctrineService.create_default."""
        mock_service = Mock()
        mock_service.build_fit_data.return_value.raw_df = pd.DataFrame({
            "fit_id": [1, 2], "type_id": [34, 35], "qty": [1, 2]
        })
        mock_service.repository.get_all_targets.return_value = pd.DataFrame({
            "fit_id": [1, 2], "target": [10, 20]
        })
        mock_svc_cls.create_default.return_value = mock_service

        from pages.downloads import _get_filtered_doctrine_csv
        _get_filtered_doctrine_csv.clear()
        result = _get_filtered_doctrine_csv("wcmktnorth", (1,))

        mock_svc_cls.create_default.assert_called_once_with("wcmktnorth")
        assert b"fit_id" in result


class TestGetTableListReturnType:
    """Test that get_table_list returns list[str]."""

    @patch("config.DatabaseConfig.engine", new_callable=PropertyMock)
    def test_get_table_list_returns_list_of_strings(self, mock_engine_prop):
        """get_table_list should return list[str], not list[tuple]."""
        mock_conn = MagicMock()
        mock_row1 = Mock()
        mock_row1.name = "marketstats"
        mock_row2 = Mock()
        mock_row2.name = "marketorders"
        mock_row3 = Mock()
        mock_row3.name = "sqlite_stat1"
        mock_conn.execute.return_value.fetchall.return_value = [
            mock_row1, mock_row2, mock_row3
        ]
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn
        mock_engine_prop.return_value = mock_engine

        from config import DatabaseConfig
        with patch.object(DatabaseConfig, '__init__', lambda self, *a, **kw: None):
            db = DatabaseConfig.__new__(DatabaseConfig)
            db._engine = mock_engine
            # Manually set engine property to return our mock
            with patch.object(type(db), 'engine', new_callable=PropertyMock, return_value=mock_engine):
                result = db.get_table_list()

        assert isinstance(result, list)
        assert all(isinstance(t, str) for t in result)
        assert "marketstats" in result
        assert "marketorders" in result
        assert "sqlite_stat1" not in result
