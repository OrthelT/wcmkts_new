"""Tests for BuilderHelperService."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from services.builder_helper_service import BuilderHelperService, _compute_need
from services.price_service import BatchPriceResult, PriceResult, PriceSource


def _make_price_service(jita_sell_prices: dict[int, float]):
    """Build a price-service stub returning the supplied sell prices."""
    price_service = MagicMock()
    prices = {
        tid: PriceResult.success_result(
            type_id=tid,
            sell_price=price,
            source=PriceSource.JITA_DATABASE,
        )
        for tid, price in jita_sell_prices.items()
    }
    price_service.get_jita_prices.return_value = BatchPriceResult(
        prices=prices,
        source=PriceSource.JITA_DATABASE,
        failed_ids=[],
    )
    return price_service


def _catalog_row(type_id: int, total_cost: float, time_per_unit: float = 900.0) -> dict:
    return {
        "type_id": type_id,
        "total_cost_per_unit": total_cost,
        "time_per_unit": time_per_unit,
        "me": 10,
        "runs": 10,
        "fetched_at": "2026-05-04 09:15:00",
    }


def _watchlist_row(
    type_id: int,
    type_name: str,
    group_name: str = "Group",
    category_name: str = "Category",
) -> dict:
    return {
        "type_id": type_id,
        "type_name": type_name,
        "group_id": 1,
        "group_name": group_name,
        "category_id": 2,
        "category_name": category_name,
    }


class TestBuilderHelperService:
    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_get_builder_data_uses_all_local_builder_cost_rows(self, mock_async_client):
        first_type_id = 24698
        second_type_id = 999_999

        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [
                _catalog_row(first_type_id, 12_500_000.0),
                _catalog_row(second_type_id, 99_999_999.0),
            ]
        )
        market_repo.get_watchlist.return_value = pd.DataFrame(
            [
                _watchlist_row(first_type_id, "Included Item", "Included Group", "Included Category"),
                _watchlist_row(second_type_id, "Excluded Item", "Excluded Group", "Excluded Category"),
            ]
        )
        market_repo.get_all_stats.return_value = pd.DataFrame(
            [
                {"type_id": first_type_id, "price": 15_000_000.0, "avg_price": 14_000_000.0},
                {"type_id": second_type_id, "price": 20_000_000.0, "avg_price": 19_000_000.0},
            ]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [
                {"type_id": first_type_id, "volume_30d": 20.0},
                {"type_id": second_type_id, "volume_30d": 10.0},
            ]
        )

        price_service = _make_price_service({
            first_type_id: 10_000_000.0,
            second_type_id: 12_000_000.0,
        })

        service = BuilderHelperService(market_repo, price_service, build_cost_repo)
        result = service.get_builder_data()

        assert list(result["type_id"]) == [first_type_id, second_type_id]
        first_row = result.iloc[0]
        second_row = result.iloc[1]
        assert first_row["item_name"] == "Included Item"
        assert first_row["category"] == "Included Category"
        assert first_row["group"] == "Included Group"
        assert first_row["market_sell_price"] == 14_000_000.0
        assert first_row["jita_sell_price"] == 10_000_000.0
        assert first_row["build_cost"] == 12_500_000.0
        assert first_row["cap_utils"] == pytest.approx((14_000_000.0 - 12_500_000.0) / 12_500_000.0)
        assert first_row["isk_per_hour"] == pytest.approx((14_000_000.0 - 12_500_000.0) / 900.0 * 3600)
        assert first_row["profit_30d"] == pytest.approx((14_000_000.0 - 12_500_000.0) * 20.0)
        assert first_row["turnover_30d"] == pytest.approx(200_000_000.0)
        assert first_row["volume_30d"] == 20.0

        assert second_row["item_name"] == "Excluded Item"
        assert second_row["market_sell_price"] == 19_000_000.0
        assert second_row["jita_sell_price"] == 12_000_000.0
        assert second_row["build_cost"] == 99_999_999.0
        assert second_row["profit_30d"] == pytest.approx((19_000_000.0 - 99_999_999.0) * 10.0)
        assert second_row["turnover_30d"] == pytest.approx(120_000_000.0)
        assert second_row["volume_30d"] == 10.0

        build_cost_repo.get_builder_cost_catalog.assert_called_once()
        market_repo.get_watchlist.assert_called_once()
        market_repo.get_all_stats.assert_called_once()
        market_repo.get_30day_volume_metrics.assert_called_once_with([first_type_id, second_type_id])
        market_repo.get_sde_info.assert_not_called()
        price_service.get_jita_prices.assert_called_once_with([first_type_id, second_type_id])
        assert mock_async_client.call_count == 0

    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_get_builder_data_returns_empty_when_local_catalog_missing(self, mock_async_client):
        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame()
        price_service = _make_price_service({})

        service = BuilderHelperService(market_repo, price_service, build_cost_repo)
        result = service.get_builder_data()

        assert result.empty
        market_repo.get_all_stats.assert_not_called()
        market_repo.get_watchlist.assert_not_called()
        market_repo.get_30day_volume_metrics.assert_not_called()
        market_repo.get_sde_info.assert_not_called()
        price_service.get_jita_prices.assert_not_called()
        assert mock_async_client.call_count == 0

    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_missing_local_market_price_leaves_market_sell_price_none(self, mock_async_client):
        """When no local marketstats row exists, market_sell_price must stay None
        and dependent metrics (cap_utils, isk_per_hour, profit_30d) must also be
        None — no synthesized fallback is allowed."""
        type_id = 24698

        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [_catalog_row(type_id, 12_500_000.0)]
        )
        market_repo.get_watchlist.return_value = pd.DataFrame(
            [_watchlist_row(type_id, "Item")]
        )
        market_repo.get_all_stats.return_value = pd.DataFrame(
            columns=["type_id", "price", "avg_price"]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [{"type_id": type_id, "volume_30d": 20.0}]
        )

        price_service = _make_price_service({type_id: 10_000_000.0})

        service = BuilderHelperService(market_repo, price_service, build_cost_repo)
        result = service.get_builder_data()

        row = result.iloc[0]
        assert row["item_name"] == "Item"
        assert row["jita_sell_price"] == 10_000_000.0
        assert row["market_sell_price"] is None
        assert row["cap_utils"] is None
        assert row["isk_per_hour"] is None
        assert row["profit_30d"] is None
        # turnover_30d uses jita * volume so it should still resolve.
        assert row["turnover_30d"] == pytest.approx(200_000_000.0)
        assert mock_async_client.call_count == 0

    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_price_basis_current_uses_marketstats_price(self, mock_async_client):
        """price_basis='current' must source market_sell_price from marketstats.price
        (current best sell), not avg_price."""
        type_id = 24698

        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [_catalog_row(type_id, 12_500_000.0)]
        )
        market_repo.get_watchlist.return_value = pd.DataFrame(
            [_watchlist_row(type_id, "Item")]
        )
        market_repo.get_all_stats.return_value = pd.DataFrame(
            [{"type_id": type_id, "price": 15_000_000.0, "avg_price": 14_000_000.0}]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [{"type_id": type_id, "volume_30d": 20.0}]
        )

        price_service = _make_price_service({type_id: 10_000_000.0})

        service = BuilderHelperService(market_repo, price_service, build_cost_repo)
        result = service.get_builder_data(price_basis="current")

        row = result.iloc[0]
        assert row["market_sell_price"] == 15_000_000.0
        assert row["cap_utils"] == pytest.approx((15_000_000.0 - 12_500_000.0) / 12_500_000.0)
        assert row["isk_per_hour"] == pytest.approx((15_000_000.0 - 12_500_000.0) / 900.0 * 3600)
        assert row["profit_30d"] == pytest.approx((15_000_000.0 - 12_500_000.0) * 20.0)
        assert mock_async_client.call_count == 0

    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_watchlist_metadata_takes_precedence_over_marketstats(self, mock_async_client):
        """When both watchlist and marketstats supply metadata, watchlist wins."""
        type_id = 24698

        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [_catalog_row(type_id, 12_500_000.0)]
        )
        market_repo.get_watchlist.return_value = pd.DataFrame(
            [_watchlist_row(type_id, "Watchlist Name", "Watchlist Group", "Watchlist Cat")]
        )
        market_repo.get_all_stats.return_value = pd.DataFrame(
            [
                {
                    "type_id": type_id,
                    "type_name": "Stats Name",
                    "group_name": "Stats Group",
                    "category_name": "Stats Cat",
                    "price": 15_000_000.0,
                    "avg_price": 14_000_000.0,
                }
            ]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [{"type_id": type_id, "volume_30d": 20.0}]
        )

        price_service = _make_price_service({type_id: 10_000_000.0})
        service = BuilderHelperService(market_repo, price_service, build_cost_repo)
        result = service.get_builder_data()

        row = result.iloc[0]
        assert row["item_name"] == "Watchlist Name"
        assert row["group"] == "Watchlist Group"
        assert row["category"] == "Watchlist Cat"
        assert mock_async_client.call_count == 0

    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_marketstats_metadata_used_when_watchlist_missing_type(self, mock_async_client):
        """An item missing from watchlist but present in marketstats falls back to
        marketstats metadata rather than 'Unknown'."""
        type_id = 24698

        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [_catalog_row(type_id, 12_500_000.0)]
        )
        market_repo.get_watchlist.return_value = pd.DataFrame(
            columns=["type_id", "type_name", "group_id", "group_name", "category_id", "category_name"]
        )
        market_repo.get_all_stats.return_value = pd.DataFrame(
            [
                {
                    "type_id": type_id,
                    "type_name": "Stats Name",
                    "group_name": "Stats Group",
                    "category_name": "Stats Cat",
                    "price": 15_000_000.0,
                    "avg_price": 14_000_000.0,
                }
            ]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [{"type_id": type_id, "volume_30d": 20.0}]
        )

        price_service = _make_price_service({type_id: 10_000_000.0})
        service = BuilderHelperService(market_repo, price_service, build_cost_repo)
        result = service.get_builder_data()

        row = result.iloc[0]
        assert row["item_name"] == "Stats Name"
        assert row["group"] == "Stats Group"
        assert row["category"] == "Stats Cat"
        assert mock_async_client.call_count == 0


class TestComputeNeed:
    def test_doctrine_item_below_target_returns_shortfall(self):
        # current_stock < target_qty -> build the shortfall.
        assert _compute_need(current_stock=30, target_qty=100, avg_daily=3.0, min_days=7) == 70

    def test_doctrine_item_at_or_above_target_returns_zero(self):
        assert _compute_need(current_stock=80, target_qty=50, avg_daily=8.0, min_days=7) == 0

    def test_non_doctrine_item_covers_min_days(self):
        # target_qty == 0 -> build enough to cover min_days of sales, net of stock.
        # round(5 * 7) - 10 == 25
        assert _compute_need(current_stock=10, target_qty=0, avg_daily=5.0, min_days=7) == 25

    def test_non_doctrine_item_already_covered_returns_zero(self):
        assert _compute_need(current_stock=100, target_qty=0, avg_daily=5.0, min_days=7) == 0

    def test_non_doctrine_with_zero_min_days_returns_zero(self):
        assert _compute_need(current_stock=0, target_qty=0, avg_daily=5.0, min_days=0) == 0


class TestBuilderDataSupplyColumns:
    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_supply_columns_populated_for_each_scenario(self, mock_async_client):
        doctrine_short = 100
        doctrine_met = 200
        non_doctrine = 300

        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        doctrine_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [
                _catalog_row(doctrine_short, 1_000_000.0),
                _catalog_row(doctrine_met, 1_000_000.0),
                _catalog_row(non_doctrine, 1_000_000.0),
            ]
        )
        market_repo.get_watchlist.return_value = pd.DataFrame(
            [
                _watchlist_row(doctrine_short, "Short"),
                _watchlist_row(doctrine_met, "Met"),
                _watchlist_row(non_doctrine, "Other"),
            ]
        )
        market_repo.get_all_stats.return_value = pd.DataFrame(
            [
                {"type_id": doctrine_short, "price": 2_000_000.0, "avg_price": 2_000_000.0, "total_volume_remain": 30},
                {"type_id": doctrine_met, "price": 2_000_000.0, "avg_price": 2_000_000.0, "total_volume_remain": 80},
                {"type_id": non_doctrine, "price": 2_000_000.0, "avg_price": 2_000_000.0, "total_volume_remain": 10},
            ]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [
                {"type_id": doctrine_short, "volume_30d": 90.0, "avg_volume_30d": 3.0},
                {"type_id": doctrine_met, "volume_30d": 240.0, "avg_volume_30d": 8.0},
                {"type_id": non_doctrine, "volume_30d": 150.0, "avg_volume_30d": 5.0},
            ]
        )
        doctrine_repo.get_target_quantities.return_value = pd.DataFrame(
            [
                {"type_id": doctrine_short, "target_qty": 100},
                {"type_id": doctrine_met, "target_qty": 50},
            ]
        )

        price_service = _make_price_service({
            doctrine_short: 1_500_000.0,
            doctrine_met: 1_500_000.0,
            non_doctrine: 1_500_000.0,
        })

        service = BuilderHelperService(
            market_repo, price_service, build_cost_repo, doctrine_repo=doctrine_repo
        )
        result = service.get_builder_data(min_days=7).set_index("type_id")

        # Doctrine item below target -> need = 100 - 30.
        short = result.loc[doctrine_short]
        assert short["current_stock"] == 30
        assert short["target_qty"] == 100
        assert short["days"] == pytest.approx(10.0)  # 30 / 3.0
        assert short["need"] == 70

        # Doctrine item at/above target -> need = 0.
        met = result.loc[doctrine_met]
        assert met["current_stock"] == 80
        assert met["target_qty"] == 50
        assert met["need"] == 0

        # Non-doctrine item -> cover min_days: round(5 * 7) - 10 = 25.
        other = result.loc[non_doctrine]
        assert other["current_stock"] == 10
        assert other["target_qty"] == 0
        assert other["days"] == pytest.approx(2.0)  # 10 / 5.0
        assert other["need"] == 25

        assert mock_async_client.call_count == 0

    @patch("httpx.AsyncClient", side_effect=AssertionError("EverRef must not be called"))
    def test_days_blank_without_recent_sales(self, mock_async_client):
        type_id = 24698
        market_repo = MagicMock()
        build_cost_repo = MagicMock()
        build_cost_repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [_catalog_row(type_id, 1_000_000.0)]
        )
        market_repo.get_watchlist.return_value = pd.DataFrame([_watchlist_row(type_id, "Item")])
        market_repo.get_all_stats.return_value = pd.DataFrame(
            [{"type_id": type_id, "price": 2_000_000.0, "avg_price": 2_000_000.0, "total_volume_remain": 40}]
        )
        market_repo.get_30day_volume_metrics.return_value = pd.DataFrame(
            [{"type_id": type_id, "volume_30d": 0.0, "avg_volume_30d": 0.0}]
        )
        price_service = _make_price_service({type_id: 1_500_000.0})

        service = BuilderHelperService(market_repo, price_service, build_cost_repo)
        row = service.get_builder_data(min_days=7).iloc[0]

        assert row["current_stock"] == 40
        assert row["days"] is None  # no avg daily volume -> undefined cover, not 0
        assert mock_async_client.call_count == 0
