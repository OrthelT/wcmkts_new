"""Tests for LowStockService."""

import pandas as pd
from unittest.mock import Mock, patch


def _mock_db():
    mock_conn = Mock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)
    mock_engine = Mock()
    mock_engine.connect.return_value = mock_conn
    mock_db = Mock()
    type(mock_db).engine = mock_engine
    return mock_db


def _mock_market_repo(volume_map: dict[int, tuple[float, float]] | None = None):
    """Create a mock MarketRepository.

    Args:
        volume_map: {type_id: (volume_30d, avg_volume_30d)} mapping.
    """
    mock_repo = Mock()
    volume_map = volume_map or {}
    rows = [
        {"type_id": tid, "volume_30d": v30, "avg_volume_30d": avg}
        for tid, (v30, avg) in volume_map.items()
    ]
    mock_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
        rows or [], columns=["type_id", "volume_30d", "avg_volume_30d"]
    )
    return mock_repo


class TestLowStockService:
    @patch("services.low_stock_service.apply_localized_type_names")
    @patch("pandas.read_sql_query")
    def test_get_low_stock_items_hides_zero_volume_items_by_default(
        self,
        mock_read_sql,
        mock_localize,
    ):
        from services.low_stock_service import LowStockFilters, LowStockService

        mock_read_sql.return_value = pd.DataFrame(
            {
                "type_id": [34, 35, 36],
                "total_volume_remain": [12, 20, 8],
                "min_price": [29.0, 19.0, 9.0],
                "price": [30.0, 20.0, 10.0],
                "avg_price": [31.0, 21.0, 11.0],
                "avg_volume": [1.0, 1.0, 1.0],
                "group_id": [18, 18, 18],
                "type_name": ["Tritanium", "Pyerite", "Mexallon"],
                "group_name": ["Mineral", "Mineral", "Mineral"],
                "category_id": [4, 4, 4],
                "category_name": ["Mineral", "Mineral", "Mineral"],
                "days_remaining": [12.0, 12.0, 12.0],
                "last_update": [None, None, None],
                "is_doctrine": [0, 0, 0],
                "ship_name": [None, None, None],
                "fits_on_mkt": [None, None, None],
            }
        )
        mock_localize.side_effect = lambda df, *_args, **_kwargs: df

        market_repo = Mock()
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            {
                "type_id": [34, 36],
                "volume_30d": [15.0, 1.5],
                "avg_volume_30d": [0.5, 0.04],
            }
        )

        with patch("settings_service.SettingsService") as mock_settings_service:
            mock_settings_service.return_value.use_equivalents = False
            service = LowStockService(_mock_db(), Mock(), market_repo)
            hidden_result = service.get_low_stock_items(language_code="en")
            shown_result = service.get_low_stock_items(
                LowStockFilters(show_zero_volume_items=True),
                language_code="en",
            )

        assert hidden_result["type_id"].tolist() == [34]
        assert shown_result["type_id"].tolist() == [34, 35, 36]

    @patch("services.low_stock_service.apply_localized_type_names")
    @patch("pandas.read_sql_query")
    def test_get_low_stock_items_uses_history_based_avg_volume_and_recalculates_days(
        self,
        mock_read_sql,
        mock_localize,
    ):
        from services.low_stock_service import LowStockService

        mock_read_sql.return_value = pd.DataFrame(
            {
                "type_id": [34],
                "total_volume_remain": [12],
                "min_price": [29.0],
                "price": [30.0],
                "avg_price": [31.0],
                "avg_volume": [1.0],
                "group_id": [18],
                "type_name": ["Tritanium"],
                "group_name": ["Mineral"],
                "category_id": [4],
                "category_name": ["Mineral"],
                "days_remaining": [12.0],
                "last_update": [None],
                "is_doctrine": [0],
                "ship_name": [None],
                "fits_on_mkt": [None],
            }
        )
        mock_localize.side_effect = lambda df, *_args, **_kwargs: df

        market_repo = Mock()
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            {
                "type_id": [34],
                "volume_30d": [15.0],
                "avg_volume_30d": [0.5],
            }
        )

        with patch("settings_service.SettingsService") as mock_settings_service:
            mock_settings_service.return_value.use_equivalents = False
            service = LowStockService(_mock_db(), Mock(), market_repo)
            result = service.get_low_stock_items(language_code="en")

        assert len(result) == 1
        assert result.iloc[0]["avg_volume"] == 0.5
        assert result.iloc[0]["days_remaining"] == 24.0

    @patch("services.low_stock_service.apply_localized_type_names")
    @patch("pandas.read_sql_query")
    def test_get_low_stock_items_applies_localized_names(
        self,
        mock_read_sql,
        mock_localize,
    ):
        from services.low_stock_service import LowStockService

        mock_read_sql.return_value = pd.DataFrame(
            {
                "type_id": [34],
                "total_volume_remain": [1200],
                "min_price": [29.0],
                "price": [30.0],
                "avg_price": [31.0],
                "avg_volume": [10.0],
                "group_id": [18],
                "type_name": ["Tritanium"],
                "group_name": ["Mineral"],
                "category_id": [4],
                "category_name": ["Mineral"],
                "days_remaining": [2.5],
                "last_update": [None],
                "is_doctrine": [1],
                "ship_name": ["Ferox"],
                "fits_on_mkt": [12],
            }
        )
        mock_localize.return_value = pd.DataFrame(
            {
                "type_id": [34],
                "total_volume_remain": [1200],
                "min_price": [29.0],
                "price": [30.0],
                "avg_price": [31.0],
                "avg_volume": [10.0],
                "group_id": [18],
                "type_name": ["三钛合金"],
                "type_name_en": ["Tritanium"],
                "group_name": ["Mineral"],
                "category_id": [4],
                "category_name": ["Mineral"],
                "days_remaining": [2.5],
                "last_update": [None],
                "is_doctrine": [1],
                "ship_name": ["Ferox"],
                "fits_on_mkt": [12],
                "ships": [["Ferox (12)"]],
            }
        )

        market_repo = Mock()
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            {
                "type_id": [34],
                "volume_30d": [300.0],
                "avg_volume_30d": [10.0],
            }
        )

        with patch("settings_service.SettingsService") as mock_settings_service:
            mock_settings_service.return_value.use_equivalents = False
            service = LowStockService(_mock_db(), Mock(), market_repo)
            result = service.get_low_stock_items(language_code="zh")

        assert len(result) == 1
        assert result.iloc[0]["type_name"] == "三钛合金"
        mock_localize.assert_called_once()
