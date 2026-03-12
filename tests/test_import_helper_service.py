"""Tests for ImportHelperService."""

import pandas as pd
from unittest.mock import Mock, patch

from services.price_service import PriceResult, PriceSource


class DummyPriceService:
    def __init__(self, prices: dict[int, PriceResult]):
        self._prices = prices

    def get_jita_price_data_map(self, type_ids: list[int]) -> dict[int, PriceResult]:
        return {
            type_id: self._prices.get(type_id, PriceResult.failure_result(type_id, "Not found"))
            for type_id in type_ids
        }


class TestImportHelperService:
    def test_fetch_base_data_recomputes_each_call(self):
        from services.import_helper_service import ImportHelperService

        provider = DummyPriceService(
            {
                34: PriceResult.success_result(
                    type_id=34,
                    sell_price=20.0,
                    buy_price=18.0,
                    source=PriceSource.JITA_FUZZWORK,
                )
            }
        )
        candidate_df = pd.DataFrame(
            {
                "type_id": [34],
                "type_name": ["Tritanium"],
                "price": [30.0],
                "avg_volume": [5.0],
                "volume_m3": [0.01],
                "category_name": ["Mineral"],
                "group_name": ["Mineral"],
            }
        )

        first_market_db = Mock()
        first_market_db.alias = "wcmkt"
        first_service = ImportHelperService(first_market_db, Mock(), provider)
        with patch.object(first_service, "_get_import_candidates", return_value=candidate_df) as fetch_candidates:
            first_service.fetch_base_data()
            first_service.fetch_base_data()

        assert fetch_candidates.call_count == 2

    def test_get_import_items_calculates_requested_metrics(self):
        from services.import_helper_service import ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))
        provider = DummyPriceService(
            {
                34: PriceResult.success_result(
                    type_id=34,
                    sell_price=20.0,
                    buy_price=18.0,
                    source=PriceSource.JITA_FUZZWORK,
                )
            }
        )
        service._price_service = provider

        with patch.object(
            service,
            "_get_import_candidates",
            return_value=pd.DataFrame(
                {
                    "type_id": [34],
                    "type_name": ["Tritanium"],
                    "price": [30.0],
                    "avg_volume": [5.0],
                    "volume_m3": [0.01],
                    "category_name": ["Mineral"],
                    "group_name": ["Mineral"],
                }
            ),
        ):
            base_df = service.fetch_base_data()
            result = service.get_import_items(base_df)

        from services.import_helper_service import SHIPPING_COST_PER_M3

        expected_shipping = 0.01 * SHIPPING_COST_PER_M3
        expected_profit = 10.0 - expected_shipping  # price(30) - (jita(20) + shipping)
        row = result.iloc[0]
        assert row["shipping_cost"] == expected_shipping
        assert abs(row["profit_jita_sell"] - expected_profit) < 1e-9
        assert abs(row["profit_jita_sell_30d"] - expected_profit * 30 * 5.0) < 1e-9
        assert row["turnover_30d"] == 3000.0
        assert row["volume_30d"] == 150.0
        expected_rrp = 20.0 * 1.2 + expected_shipping  # jita * (1 + margin) + shipping
        assert abs(row["rrp"] - expected_rrp) < 1e-9
        expected_cap_utilis = expected_profit / 20.0
        assert abs(row["capital_utilis"] - expected_cap_utilis) < 1e-9

    def test_get_import_items_calculates_rrp_with_custom_markup_margin(self):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))
        provider = DummyPriceService(
            {
                34: PriceResult.success_result(
                    type_id=34,
                    sell_price=20.0,
                    buy_price=18.0,
                    source=PriceSource.JITA_FUZZWORK,
                )
            }
        )
        service._price_service = provider

        filters = ImportHelperFilters(markup_margin=0.5)

        with patch.object(
            service,
            "_get_import_candidates",
            return_value=pd.DataFrame(
                {
                    "type_id": [34],
                    "type_name": ["Tritanium"],
                    "price": [30.0],
                    "avg_volume": [5.0],
                    "volume_m3": [0.01],
                    "category_name": ["Mineral"],
                    "group_name": ["Mineral"],
                }
            ),
        ):
            base_df = service.fetch_base_data()
            result = service.get_import_items(base_df, filters)

        from services.import_helper_service import SHIPPING_COST_PER_M3

        expected_shipping = 0.01 * SHIPPING_COST_PER_M3
        expected_rrp = 20.0 * 1.5 + expected_shipping  # jita * (1 + 0.5) + shipping
        row = result.iloc[0]
        assert abs(row["rrp"] - expected_rrp) < 1e-9

    def test_get_import_items_uses_custom_shipping_cost_per_m3(self):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))
        base_df = pd.DataFrame(
            {
                "type_id": [34],
                "type_name": ["Tritanium"],
                "price": [30.0],
                "avg_volume": [5.0],
                "volume_m3": [2.0],
                "jita_sell_price": [20.0],
                "jita_buy_price": [18.0],
                "turnover_30d": [3000.0],
                "volume_30d": [150.0],
                "category_name": ["Mineral"],
                "group_name": ["Mineral"],
            }
        )

        result = service.get_import_items(
            base_df,
            ImportHelperFilters(
                profitable_only=False,
                shipping_cost_per_m3=100.0,
            ),
        )

        row = result.iloc[0]
        assert row["shipping_cost"] == 200.0
        assert row["profit_jita_sell"] == -190.0
        assert row["profit_jita_sell_30d"] == -28_500.0
        assert row["turnover_30d"] == 3000.0
        assert row["volume_30d"] == 150.0
        assert row["capital_utilis"] == -9.5
        assert row["rrp"] == 224.0

    def test_get_import_items_applies_filters_using_avg_volume(self):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))
        provider = DummyPriceService(
            {
                34: PriceResult.success_result(
                    type_id=34,
                    sell_price=20.0,
                    buy_price=18.0,
                    source=PriceSource.JITA_FUZZWORK,
                ),
                35: PriceResult.success_result(
                    type_id=35,
                    sell_price=20.0,
                    buy_price=19.0,
                    source=PriceSource.JITA_FUZZWORK,
                ),
            }
        )
        service._price_service = provider

        filters = ImportHelperFilters(
            categories=["Mineral"],
            search_text="trit",
            profitable_only=True,
            min_capital_utilis=0.2,
        )

        with patch.object(
            service,
            "_get_import_candidates",
            return_value=pd.DataFrame(
                {
                    "type_id": [34, 35],
                    "type_name": ["Tritanium", "Pyerite"],
                    "price": [30.0, 15.0],
                    "avg_volume": [4.0, 2.0],
                    "volume_m3": [0.01, 0.02],
                    "category_name": ["Mineral", "Mineral"],
                    "group_name": ["Mineral", "Mineral"],
                }
            ),
        ):
            base_df = service.fetch_base_data()
            result = service.get_import_items(base_df, filters)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["type_id"] == 34
        assert row["turnover_30d"] == 2400.0
        assert row["volume_30d"] == 120.0

    def test_get_import_items_filters_by_minimum_30d_turnover(self):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))
        provider = DummyPriceService(
            {
                34: PriceResult.success_result(
                    type_id=34,
                    sell_price=20.0,
                    buy_price=18.0,
                    source=PriceSource.JITA_FUZZWORK,
                ),
                35: PriceResult.success_result(
                    type_id=35,
                    sell_price=20.0,
                    buy_price=19.0,
                    source=PriceSource.JITA_FUZZWORK,
                ),
            }
        )
        service._price_service = provider

        filters = ImportHelperFilters(
            profitable_only=False,
            min_turnover_30d=2500.0,
        )

        with patch.object(
            service,
            "_get_import_candidates",
            return_value=pd.DataFrame(
                {
                    "type_id": [34, 35],
                    "type_name": ["Tritanium", "Pyerite"],
                    "price": [30.0, 25.0],
                    "avg_volume": [5.0, 2.0],
                    "volume_m3": [0.01, 0.02],
                    "category_name": ["Mineral", "Mineral"],
                    "group_name": ["Mineral", "Mineral"],
                }
            ),
        ):
            base_df = service.fetch_base_data()
            result = service.get_import_items(base_df, filters)

        assert len(result) == 1
        row = result.iloc[0]
        assert row["type_id"] == 34
        assert row["turnover_30d"] == 3000.0
        assert row["volume_30d"] == 150.0

    def test_get_import_items_applies_item_type_filters(self):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        mock_sde_repo = Mock()
        mock_sde_repo.get_tech2_type_ids.return_value = [35]
        mock_sde_repo.get_faction_type_ids.return_value = {36}

        service = ImportHelperService(Mock(), mock_sde_repo, DummyPriceService({}))
        base_df = pd.DataFrame(
            {
                "type_id": [34, 35, 36],
                "type_name": ["Tritanium", "Tech Item", "Faction Item"],
                "price": [30.0, 40.0, 50.0],
                "avg_volume": [5.0, 5.0, 5.0],
                "volume_m3": [0.01, 0.01, 0.01],
                "jita_sell_price": [20.0, 20.0, 20.0],
                "jita_buy_price": [18.0, 18.0, 18.0],
                "shipping_cost": [1.0, 1.0, 1.0],
                "profit_jita_sell": [9.0, 19.0, 29.0],
                "profit_jita_sell_30d": [1350.0, 2850.0, 4350.0],
                "turnover_30d": [3000.0, 3000.0, 3000.0],
                "volume_30d": [150.0, 150.0, 150.0],
                "capital_utilis": [0.45, 0.95, 1.45],
                "category_name": ["Mineral", "Module", "Module"],
                "group_name": ["Mineral", "Module", "Module"],
                "is_doctrine": [0, 1, 0],
            }
        )

        doctrine_result = service.get_import_items(
            base_df,
            ImportHelperFilters(doctrine_only=True, profitable_only=False),
        )
        tech2_result = service.get_import_items(
            base_df,
            ImportHelperFilters(tech2_only=True, profitable_only=False),
        )
        faction_result = service.get_import_items(
            base_df,
            ImportHelperFilters(faction_only=True, profitable_only=False),
        )

        assert doctrine_result["type_id"].tolist() == [35]
        assert tech2_result["type_id"].tolist() == [35]
        assert faction_result["type_id"].tolist() == [36]

    @patch("services.import_helper_service.apply_localized_type_names")
    def test_get_import_items_uses_localized_names_and_preserves_english_search(
        self,
        mock_localize,
    ):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))

        base_df = pd.DataFrame(
            {
                "type_id": [34],
                "type_name": ["Tritanium"],
                "price": [30.0],
                "avg_volume": [5.0],
                "volume_m3": [0.01],
                "jita_sell_price": [20.0],
                "jita_buy_price": [18.0],
                "shipping_cost": [1.0],
                "profit_jita_sell": [9.0],
                "profit_jita_sell_30d": [1350.0],
                "turnover_30d": [3000.0],
                "volume_30d": [150.0],
                "capital_utilis": [0.45],
                "category_name": ["Mineral"],
                "group_name": ["Mineral"],
            }
        )

        def _localize(df, *_args, **_kwargs):
            localized_df = df.copy()
            localized_df["type_name"] = "三钛合金"
            localized_df["type_name_en"] = "Tritanium"
            return localized_df

        mock_localize.side_effect = _localize

        filters = ImportHelperFilters(search_text="trit")
        result = service.get_import_items(base_df, filters, language_code="zh")

        assert len(result) == 1
        assert result.iloc[0]["type_name"] == "三钛合金"
        mock_localize.assert_called_once()

    def test_get_summary_stats_returns_counts_and_average(self):
        from services.import_helper_service import ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))
        df = pd.DataFrame(
            {
                "profit_jita_sell": [10.0, -1.0, 5.0],
                "capital_utilis": [0.2, -0.1, 0.3],
            }
        )

        result = service.get_summary_stats(df)

        assert result["total_items"] == 3
        assert result["profitable_items"] == 2
        assert result["avg_capital_utilis"] == 0.13333333333333333

    def test_fetch_base_data_returns_empty_when_no_candidates(self):
        from services.import_helper_service import ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyPriceService({}))
        with patch.object(service, "_get_import_candidates", return_value=pd.DataFrame()):
            result = service.fetch_base_data()
            assert result.empty

    @patch("pandas.read_sql_query")
    def test_get_category_options_reads_marketstats(self, mock_read_sql):
        from services.import_helper_service import ImportHelperService

        mock_read_sql.return_value = pd.DataFrame(
            {
                "category_id": [4, 7],
                "category_name": ["Mineral", "Ship Equipment"],
            }
        )
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn
        mkt_db = Mock()
        type(mkt_db).engine = mock_engine

        service = ImportHelperService(mkt_db, Mock(), DummyPriceService({}))
        result = service.get_category_options()

        assert result["category_id"].tolist() == [4, 7]
        assert result["category_name"].tolist() == ["Mineral", "Ship Equipment"]
