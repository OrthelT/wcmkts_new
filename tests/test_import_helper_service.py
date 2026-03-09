"""Tests for ImportHelperService."""

import pandas as pd
from unittest.mock import Mock, patch

from services.pricer_service import JitaPriceData


class DummyJitaProvider:
    def __init__(self, prices: dict[int, JitaPriceData]):
        self._prices = prices

    def get_prices(self, type_ids: list[int]) -> dict[int, JitaPriceData]:
        return {
            type_id: self._prices.get(type_id, JitaPriceData(type_id=type_id))
            for type_id in type_ids
        }


class TestImportHelperService:
    def test_get_import_items_calculates_requested_metrics(self):
        from services.import_helper_service import ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyJitaProvider({}))
        provider = DummyJitaProvider(
            {34: JitaPriceData(type_id=34, sell_price=20.0, buy_price=18.0)}
        )
        service._jita_provider = provider

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

        row = result.iloc[0]
        assert row["shipping_cost"] == 5.0
        assert row["profit_jita_sell"] == 10.0
        assert row["profit_jita_sell_30d"] == 1500.0
        assert row["turnover_30d"] == 3000.0
        assert row["volume_30d"] == 150.0
        assert row["rrp"] == 24.0
        assert row["capital_utilis"] == 0.25

    def test_get_import_items_calculates_rrp_with_custom_markup_margin(self):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyJitaProvider({}))
        provider = DummyJitaProvider(
            {34: JitaPriceData(type_id=34, sell_price=20.0, buy_price=18.0)}
        )
        service._jita_provider = provider

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

        row = result.iloc[0]
        assert row["rrp"] == 30.0

    def test_get_import_items_applies_filters_using_avg_volume(self):
        from services.import_helper_service import ImportHelperFilters, ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyJitaProvider({}))
        provider = DummyJitaProvider(
            {
                34: JitaPriceData(type_id=34, sell_price=20.0, buy_price=18.0),
                35: JitaPriceData(type_id=35, sell_price=20.0, buy_price=19.0),
            }
        )
        service._jita_provider = provider

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

        service = ImportHelperService(Mock(), Mock(), DummyJitaProvider({}))
        provider = DummyJitaProvider(
            {
                34: JitaPriceData(type_id=34, sell_price=20.0, buy_price=18.0),
                35: JitaPriceData(type_id=35, sell_price=20.0, buy_price=19.0),
            }
        )
        service._jita_provider = provider

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

    def test_get_summary_stats_returns_counts_and_average(self):
        from services.import_helper_service import ImportHelperService

        service = ImportHelperService(Mock(), Mock(), DummyJitaProvider({}))
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

    @patch("pandas.read_sql_query")
    def test_get_category_options_reads_marketstats(self, mock_read_sql):
        from services.import_helper_service import ImportHelperService

        mock_read_sql.return_value = pd.DataFrame(
            {"category_name": ["Mineral", "Ship Equipment"]}
        )
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn
        mkt_db = Mock()
        type(mkt_db).engine = mock_engine

        service = ImportHelperService(mkt_db, Mock(), DummyJitaProvider({}))
        result = service.get_category_options()

        assert result == ["Mineral", "Ship Equipment"]
