"""Tests for market dashboard components and service methods."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# =========================================================================
# MarketService.get_market_overview_kpis
# =========================================================================


class TestGetMarketOverviewKpis:
    """Tests for MarketService.get_market_overview_kpis()."""

    def _make_service(self, stats_df=None, orders_df=None, update_time="12:00 UTC"):
        from services.market_service import MarketService

        repo = MagicMock()
        repo.get_all_stats.return_value = stats_df
        repo.get_all_orders.return_value = orders_df
        repo.get_update_time.return_value = update_time
        return MarketService(repo)

    def test_basic_aggregation(self):
        stats = pd.DataFrame({
            "type_id": [34, 35],
            "min_price": [10.0, 20.0],
            "total_volume_remain": [100, 200],
        })
        orders = pd.DataFrame({
            "is_buy_order": [0, 0, 1],
        })
        service = self._make_service(stats_df=stats, orders_df=orders)
        kpis = service.get_market_overview_kpis()

        assert kpis["total_market_value"] == pytest.approx(10.0 * 100 + 20.0 * 200)
        assert kpis["items_listed"] == 2
        assert kpis["active_sell_orders"] == 2
        assert kpis["active_buy_orders"] == 1
        assert kpis["last_updated"] == "12:00 UTC"

    def test_empty_data_returns_zeros(self):
        service = self._make_service(
            stats_df=pd.DataFrame(), orders_df=pd.DataFrame(), update_time=None,
        )
        kpis = service.get_market_overview_kpis()

        assert kpis["total_market_value"] == 0.0
        assert kpis["items_listed"] == 0
        assert kpis["active_sell_orders"] == 0
        assert kpis["active_buy_orders"] == 0
        assert kpis["last_updated"] is None

    def test_none_dataframes(self):
        service = self._make_service(stats_df=None, orders_df=None)
        kpis = service.get_market_overview_kpis()

        assert kpis["total_market_value"] == 0.0
        assert kpis["items_listed"] == 0
        assert kpis["active_sell_orders"] == 0
        assert kpis["active_buy_orders"] == 0

    def test_non_numeric_values_coerced(self):
        stats = pd.DataFrame({
            "type_id": [34],
            "min_price": ["not_a_number"],
            "total_volume_remain": [100],
        })
        service = self._make_service(stats_df=stats, orders_df=pd.DataFrame())
        kpis = service.get_market_overview_kpis()

        assert kpis["total_market_value"] == 0.0
        assert kpis["items_listed"] == 1


# =========================================================================
# _compute_module_targets
# =========================================================================


class TestComputeModuleTargets:
    """Tests for _compute_module_targets()."""

    def _make_repo(self, fits_df, targets_df):
        repo = MagicMock()
        repo.get_all_fits.return_value = fits_df
        repo.get_all_targets.return_value = targets_df
        return repo

    def test_excludes_ship_hulls(self):
        from pages.components.dashboard_components import _compute_module_targets

        fits_df = pd.DataFrame({
            "type_id": [100, 200],
            "ship_id": [200, 200],
            "fit_id": [1, 1],
            "fit_qty": [2, 1],
            "fits_on_mkt": [10, 10],
            "category_id": [7, 6],
        })
        targets_df = pd.DataFrame({"fit_id": [1], "ship_target": [20]})
        repo = self._make_repo(fits_df, targets_df)
        result = _compute_module_targets(repo)
        # Only type_id 100 (module), not 200 (ship hull)
        assert list(result["type_id"]) == [100]

    def test_qty_needed_and_target_pct(self):
        from pages.components.dashboard_components import _compute_module_targets

        fits_df = pd.DataFrame({
            "type_id": [100],
            "ship_id": [999],
            "fit_id": [1],
            "fit_qty": [3],
            "fits_on_mkt": [8],
            "category_id": [7],
        })
        targets_df = pd.DataFrame({"fit_id": [1], "ship_target": [20]})
        repo = self._make_repo(fits_df, targets_df)
        result = _compute_module_targets(repo)
        row = result.iloc[0]
        # qty_needed = (20 - 8) * 3 = 36
        assert row["qty_needed"] == 36
        # target_pct = round((8 / 20) * 100) = 40
        assert row["target_pct"] == 40

    def test_no_shortfall_means_zero_qty_needed(self):
        from pages.components.dashboard_components import _compute_module_targets

        fits_df = pd.DataFrame({
            "type_id": [100],
            "ship_id": [999],
            "fit_id": [1],
            "fit_qty": [2],
            "fits_on_mkt": [25],
            "category_id": [7],
        })
        targets_df = pd.DataFrame({"fit_id": [1], "ship_target": [20]})
        repo = self._make_repo(fits_df, targets_df)
        result = _compute_module_targets(repo)
        assert result.iloc[0]["qty_needed"] == 0
        # target_pct capped at 100
        assert result.iloc[0]["target_pct"] == 100

    def test_aggregates_across_fits(self):
        from pages.components.dashboard_components import _compute_module_targets

        # Module 100 appears in two fits with different shortfall levels
        fits_df = pd.DataFrame({
            "type_id": [100, 100],
            "ship_id": [999, 998],
            "fit_id": [1, 2],
            "fit_qty": [2, 4],
            "fits_on_mkt": [15, 5],
            "category_id": [7, 7],
        })
        targets_df = pd.DataFrame({
            "fit_id": [1, 2],
            "ship_target": [20, 10],
        })
        repo = self._make_repo(fits_df, targets_df)
        result = _compute_module_targets(repo)
        assert len(result) == 1
        row = result.iloc[0]
        # Fit 1: qty_needed = (20-15)*2 = 10, target_pct = round(15/20*100) = 75
        # Fit 2: qty_needed = (10-5)*4 = 20, target_pct = round(5/10*100) = 50
        # MAX(qty_needed) = 20, MIN(target_pct) = 50
        assert row["qty_needed"] == 20
        assert row["target_pct"] == 50

    def test_empty_fits(self):
        from pages.components.dashboard_components import _compute_module_targets

        repo = self._make_repo(pd.DataFrame(), pd.DataFrame())
        result = _compute_module_targets(repo)
        assert result.empty


# =========================================================================
# Extraction smoke tests
# =========================================================================


class TestDashboardComponentImports:
    """Smoke tests to verify the extraction didn't break imports."""

    def test_constants_importable(self):
        from pages.components.dashboard_components import (
            MINERAL_TYPE_IDS,
            ISOTOPE_AND_FUEL_BLOCK_TYPE_IDS,
        )
        assert len(MINERAL_TYPE_IDS) == 9
        assert len(ISOTOPE_AND_FUEL_BLOCK_TYPE_IDS) == 10

    def test_render_comparison_table_importable(self):
        from pages.components.dashboard_components import render_comparison_table
        assert callable(render_comparison_table)

    def test_doctrine_ships_table_importable(self):
        from pages.components.dashboard_components import render_doctrine_ships_table
        assert callable(render_doctrine_ships_table)

    def test_popular_modules_table_importable(self):
        from pages.components.dashboard_components import render_popular_modules_table
        assert callable(render_popular_modules_table)


# =========================================================================
# Column config smoke test
# =========================================================================


class TestDoctrineShipsColumnConfig:
    """Verify the new column config is properly defined."""

    @patch("ui.column_definitions.st")
    def test_returns_expected_keys(self, mock_st):
        mock_st.column_config = MagicMock()
        from ui.column_definitions import get_doctrine_ships_column_config
        config = get_doctrine_ships_column_config("en")
        expected_keys = {
            "image_url", "fit_id", "type_name", "target_pct",
            "current_sell_price", "order_volume",
            "jita_sell_price", "ship_target", "fits_on_mkt",
            "_mkt", "_doc",
        }
        assert set(config.keys()) == expected_keys


class TestDoctrineStatusCellStyle:
    """Tests for doctrine status cell styling helper."""

    def test_good_status_has_no_background(self):
        from pages.components.dashboard_components import _status_cell_style

        assert _status_cell_style("🟢 Good") == ""

    def test_needs_attention_status_gets_yellow_background(self):
        from pages.components.dashboard_components import _status_cell_style

        assert _status_cell_style("🟡 Needs Attention") == "background-color: rgba(220, 250, 60, 0.25)"

    def test_critical_status_gets_red_background(self):
        from pages.components.dashboard_components import _status_cell_style

        assert _status_cell_style("🔴 Critical") == "background-color: rgba(239, 83, 80, 0.28)"

    def test_fits_avail_style_applies_only_to_fits_column(self):
        from pages.components.dashboard_components import _fits_avail_column_style

        fits_column = pd.Series([10, 5, 1], name="fits_on_mkt", index=[0, 1, 2])
        status_labels = pd.Series(["🟢 Good", "🟡 Needs Attention", "🔴 Critical"], index=[0, 1, 2])
        styles = _fits_avail_column_style(fits_column, status_labels)
        assert styles == ["", "background-color: rgba(220, 250, 60, 0.25)", "background-color: rgba(239, 83, 80, 0.28)"]

        other_column = pd.Series(["A", "B", "C"], name="type_name", index=[0, 1, 2])
        assert _fits_avail_column_style(other_column, status_labels) == ["", "", ""]


class TestJitaDiffCellStyle:
    """Tests for % vs Jita conditional styling helper."""

    def test_greater_than_five_is_green(self):
        from pages.components.dashboard_components import _jita_diff_cell_style

        assert _jita_diff_cell_style(5.01) == "color: #66bb6a"

    def test_positive_below_threshold_is_neutral(self):
        from pages.components.dashboard_components import _jita_diff_cell_style

        assert _jita_diff_cell_style(4.99) == "color: #728049"

    def test_negative_is_red(self):
        from pages.components.dashboard_components import _jita_diff_cell_style

        assert _jita_diff_cell_style(-0.01) == "color: #ef5350"

    def test_exactly_zero_is_neutral(self):
        from pages.components.dashboard_components import _jita_diff_cell_style

        assert _jita_diff_cell_style(0.0) == "color: #728049"
