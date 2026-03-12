"""Tests for LowStockService localization behavior."""

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


class TestLowStockService:
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

        with patch("settings_service.SettingsService") as mock_settings_service:
            mock_settings_service.return_value.use_equivalents = False
            service = LowStockService(_mock_db(), Mock())
            result = service.get_low_stock_items(language_code="zh")

        assert len(result) == 1
        assert result.iloc[0]["type_name"] == "三钛合金"
        mock_localize.assert_called_once()
