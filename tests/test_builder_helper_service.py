"""Tests for BuilderHelperService."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.builder_helper_service import BuilderHelperService


def _mock_engine():
    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = None
    return engine


class TestBuilderHelperService:
    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_get_builder_data_uses_all_local_builder_cost_rows(self, mock_async_client):
        first_type_id = 24698
        second_type_id = 999_999

        market_repo = MagicMock()
        market_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [
                {
                    "type_id": first_type_id,
                    "type_name": "Included Item",
                    "group_id": 1,
                    "group_name": "Included Group",
                    "category_id": 2,
                    "category_name": "Included Category",
                    "total_cost_per_unit": 12_500_000.0,
                    "time_per_unit": 900.0,
                    "me": 8,
                    "runs": 3,
                    "fetched_at": "2026-05-04 09:15:00",
                },
                {
                    "type_id": second_type_id,
                    "type_name": "Excluded Item",
                    "group_id": 1,
                    "group_name": "Excluded Group",
                    "category_id": 2,
                    "category_name": "Excluded Category",
                    "total_cost_per_unit": 99_999_999.0,
                    "time_per_unit": 900.0,
                    "me": 8,
                    "runs": 3,
                    "fetched_at": "2026-05-04 09:15:00",
                },
            ]
        )
        market_repo.get_all_stats.return_value = pd.DataFrame(
            [
                {"type_id": first_type_id, "price": 15_000_000.0},
                {"type_id": second_type_id, "price": 20_000_000.0},
            ]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [
                {"type_id": first_type_id, "volume_30d": 20.0},
                {"type_id": second_type_id, "volume_30d": 10.0},
            ]
        )
        market_repo.db = MagicMock(engine=_mock_engine())

        jita_prices = pd.DataFrame(
            [
                {"type_id": first_type_id, "sell_price": 10_000_000.0},
                {"type_id": second_type_id, "sell_price": 12_000_000.0},
            ]
        )
        with patch("services.builder_helper_service.pd.read_sql_query", return_value=jita_prices) as mock_read_sql:
            service = BuilderHelperService(market_repo)
            result = service.get_builder_data()

        assert list(result["type_id"]) == [first_type_id, second_type_id]
        first_row = result.iloc[0]
        second_row = result.iloc[1]
        assert first_row["item_name"] == "Included Item"
        assert first_row["market_sell_price"] == 15_000_000.0
        assert first_row["jita_sell_price"] == 10_000_000.0
        assert first_row["build_cost"] == 12_500_000.0
        assert first_row["cap_utils"] == pytest.approx((15_000_000.0 - 12_500_000.0) / 15_000_000.0)
        assert first_row["profit_30d"] == pytest.approx(50_000_000.0)
        assert first_row["turnover_30d"] == pytest.approx(200_000_000.0)
        assert first_row["volume_30d"] == 20.0

        assert second_row["item_name"] == "Excluded Item"
        assert second_row["market_sell_price"] == 20_000_000.0
        assert second_row["jita_sell_price"] == 12_000_000.0
        assert second_row["build_cost"] == 99_999_999.0
        assert second_row["profit_30d"] == pytest.approx((20_000_000.0 - 99_999_999.0) * 10.0)
        assert second_row["turnover_30d"] == pytest.approx(120_000_000.0)
        assert second_row["volume_30d"] == 10.0

        market_repo.get_builder_cost_catalog.assert_called_once()
        market_repo.get_all_stats.assert_called_once()
        market_repo.get_30day_volume_metrics.assert_called_once_with([first_type_id, second_type_id])
        market_repo.get_sde_info.assert_not_called()
        mock_read_sql.assert_called_once()
        assert mock_async_client.call_count == 0

    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_get_builder_data_returns_empty_when_local_catalog_missing(self, mock_async_client):
        market_repo = MagicMock()
        market_repo.get_builder_cost_catalog.return_value = pd.DataFrame()

        service = BuilderHelperService(market_repo)

        with patch("services.builder_helper_service.pd.read_sql_query") as mock_read_sql:
            result = service.get_builder_data()

        assert result.empty
        market_repo.get_all_stats.assert_not_called()
        market_repo.get_30day_volume_metrics.assert_not_called()
        market_repo.get_sde_info.assert_not_called()
        mock_read_sql.assert_not_called()
        assert mock_async_client.call_count == 0
