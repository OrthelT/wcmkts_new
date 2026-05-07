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
        assert row["fit_count"] == 2

    def test_fit_count_single_fit(self):
        from pages.components.dashboard_components import _compute_module_targets

        fits_df = pd.DataFrame({
            "type_id": [100],
            "ship_id": [999],
            "fit_id": [1],
            "fit_qty": [2],
            "fits_on_mkt": [10],
            "category_id": [7],
        })
        targets_df = pd.DataFrame({"fit_id": [1], "ship_target": [20]})
        repo = self._make_repo(fits_df, targets_df)
        result = _compute_module_targets(repo)
        assert result.iloc[0]["fit_count"] == 1

    def test_fit_count_uses_distinct_not_row_count(self):
        # Same module appearing twice in the same fit_id (e.g. low + mid slot)
        # should count as 1 distinct fit, not 2.
        from pages.components.dashboard_components import _compute_module_targets

        fits_df = pd.DataFrame({
            "type_id": [100, 100],
            "ship_id": [999, 999],
            "fit_id": [1, 1],
            "fit_qty": [1, 1],
            "fits_on_mkt": [10, 10],
            "category_id": [7, 7],
        })
        targets_df = pd.DataFrame({"fit_id": [1], "ship_target": [20]})
        repo = self._make_repo(fits_df, targets_df)
        result = _compute_module_targets(repo)
        assert result.iloc[0]["fit_count"] == 1

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
    """Tests for doctrine status cell styling helper.

    Asserts the behavior contract (good=no style, attention/critical=styled)
    rather than exact RGBA strings — color tweaks shouldn't break tests.
    """

    def test_good_status_has_no_background(self):
        from pages.components.dashboard_components import _status_cell_style

        assert _status_cell_style("🟢 Good") == ""

    def test_needs_attention_status_is_styled(self):
        from pages.components.dashboard_components import _status_cell_style

        result = _status_cell_style("🟡 Needs Attention")
        assert result.startswith("background-color:")

    def test_critical_status_is_styled(self):
        from pages.components.dashboard_components import _status_cell_style

        result = _status_cell_style("🔴 Critical")
        assert result.startswith("background-color:")


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


class TestComputeShipTargetPct:
    """Tests for _compute_ship_target_pct() — the per-ship progress helper."""

    def test_zero_target_returns_zero(self):
        from pages.components.dashboard_components import _compute_ship_target_pct

        assert _compute_ship_target_pct(5, 0) == 0

    def test_negative_target_returns_zero(self):
        from pages.components.dashboard_components import _compute_ship_target_pct

        assert _compute_ship_target_pct(5, -3) == 0

    def test_exact_match_returns_100(self):
        from pages.components.dashboard_components import _compute_ship_target_pct

        assert _compute_ship_target_pct(20, 20) == 100

    def test_overstock_capped_at_100(self):
        from pages.components.dashboard_components import _compute_ship_target_pct

        assert _compute_ship_target_pct(50, 10) == 100

    def test_partial_progress_rounds(self):
        from pages.components.dashboard_components import _compute_ship_target_pct

        # 7/9 = 77.77...% -> 78
        assert _compute_ship_target_pct(7, 9) == 78

    def test_zero_stock_returns_zero(self):
        from pages.components.dashboard_components import _compute_ship_target_pct

        assert _compute_ship_target_pct(0, 20) == 0


class TestDoctrineModulesColumnConfig:
    """Verify the doctrine modules column config is properly defined."""

    @patch("ui.column_definitions.st")
    def test_returns_expected_keys(self, mock_st):
        mock_st.column_config = MagicMock()
        from ui.column_definitions import get_doctrine_modules_column_config
        config = get_doctrine_modules_column_config("en")
        expected_keys = {
            "type_id", "image_url", "type_name", "target_pct", "order_volume",
            "fit_count", "qty_needed", "current_sell_price", "jita_sell_price",
            "jita_buy_price", "pct_diff_vs_jita_sell", "_mkt", "_doc",
        }
        assert set(config.keys()) == expected_keys


class TestComputeModuleTargetsMissingTargets:
    """Tests for null-target error handling in _compute_module_targets()."""

    def _make_repo(self, fits_df, targets_df):
        repo = MagicMock()
        repo.get_all_fits.return_value = fits_df
        repo.get_all_targets.return_value = targets_df
        return repo

    def test_raises_when_fit_has_no_target_row(self):
        from pages.components.dashboard_components import _compute_module_targets

        # fit_id=2 has no row in targets_df
        fits_df = pd.DataFrame({
            "type_id": [100, 101],
            "ship_id": [999, 998],
            "fit_id": [1, 2],
            "fit_qty": [2, 3],
            "fits_on_mkt": [10, 5],
            "category_id": [7, 7],
        })
        targets_df = pd.DataFrame({"fit_id": [1], "ship_target": [20]})
        repo = self._make_repo(fits_df, targets_df)
        with pytest.raises(ValueError, match=r"Missing ship_targets.*\[2\]"):
            _compute_module_targets(repo)

    def test_lists_all_missing_fit_ids(self):
        from pages.components.dashboard_components import _compute_module_targets

        fits_df = pd.DataFrame({
            "type_id": [100, 101, 102],
            "ship_id": [999, 998, 997],
            "fit_id": [1, 2, 3],
            "fit_qty": [1, 1, 1],
            "fits_on_mkt": [5, 5, 5],
            "category_id": [7, 7, 7],
        })
        targets_df = pd.DataFrame({"fit_id": [1], "ship_target": [10]})
        repo = self._make_repo(fits_df, targets_df)
        with pytest.raises(ValueError, match=r"\[2, 3\]"):
            _compute_module_targets(repo)


class TestResolveTableSelection:
    """Regression tests for `_resolve_table_selection`.

    Guards the bug where iloc-based row resolution returned the wrong type_id
    when display_df was filtered (low-stock filter dropped rows from source_df).
    """

    def _source_df(self):
        # Source uses non-contiguous index to simulate a row-filter result;
        # the bugfix relies on edited_df.index aligning with source_df.index.
        return pd.DataFrame(
            {"type_id": [11, 22, 33, 44]},
            index=[0, 1, 2, 3],
        )

    def test_returns_market_stats_target_for_correct_row(self):
        from pages.components.dashboard_components import _resolve_table_selection

        source_df = self._source_df()
        # Filtered display kept only rows at index 2 and 3 (low-stock subset)
        edited_df = pd.DataFrame(
            {"_mkt": [False, True], "_doc": [False, False], "type_id": [33, 44]},
            index=[2, 3],
        )
        # iloc[1] → type_id 44, the correct answer.
        # Pre-fix code did `source_df.iloc[1]` which would have returned 22.
        assert _resolve_table_selection(edited_df, source_df) == (44, "market_stats")

    def test_returns_doctrine_status_target(self):
        from pages.components.dashboard_components import _resolve_table_selection

        source_df = self._source_df()
        edited_df = pd.DataFrame(
            {"_mkt": [False, False], "_doc": [True, False], "type_id": [33, 44]},
            index=[2, 3],
        )
        assert _resolve_table_selection(edited_df, source_df) == (33, "doctrine_status")

    def test_returns_none_none_when_no_checkbox_set(self):
        from pages.components.dashboard_components import _resolve_table_selection

        source_df = self._source_df()
        edited_df = pd.DataFrame(
            {"_mkt": [False, False], "_doc": [False, False], "type_id": [11, 22]},
            index=[0, 1],
        )
        assert _resolve_table_selection(edited_df, source_df) == (None, None)

    def test_skips_rows_with_missing_source_index(self):
        # Latent guard: future refactor that resets indices shouldn't crash.
        from pages.components.dashboard_components import _resolve_table_selection

        source_df = self._source_df()
        # Index 99 is not in source_df — should be skipped, falling through
        # to None, None rather than raising KeyError.
        edited_df = pd.DataFrame(
            {"_mkt": [True], "_doc": [False], "type_id": [99]},
            index=[99],
        )
        assert _resolve_table_selection(edited_df, source_df) == (None, None)


# =========================================================================
# render_popular_modules_table — early exit contract
# =========================================================================


class TestRenderPopularModulesTableEarlyExits:
    """The function must return a (None, None) tuple — not bare None — on
    every early-exit path so the caller's tuple-unpacking never crashes.
    """

    def _kwargs(self):
        return {
            "market_service": MagicMock(),
            "price_service": MagicMock(),
            "doctrine_repo": MagicMock(),
            "sde_repo": MagicMock(),
            "language_code": "en",
            "dataframe_key": "test_key",
        }

    def test_value_error_returns_none_none(self):
        from pages.components import dashboard_components as dc

        with patch.object(dc, "_compute_module_targets", side_effect=ValueError("missing")):
            with patch.object(dc.st, "error"):
                result = dc.render_popular_modules_table(**self._kwargs())
        assert result == (None, None)

    def test_empty_module_targets_returns_none_none(self):
        from pages.components import dashboard_components as dc

        with patch.object(dc, "_compute_module_targets", return_value=pd.DataFrame()):
            result = dc.render_popular_modules_table(**self._kwargs())
        assert result == (None, None)

    def test_empty_snapshot_returns_none_none(self):
        from pages.components import dashboard_components as dc

        targets = pd.DataFrame({"type_id": [100], "qty_needed": [1], "target_pct": [50], "fit_count": [1]})
        kwargs = self._kwargs()
        kwargs["market_service"].get_current_market_snapshot.return_value = pd.DataFrame()

        with patch.object(dc, "_compute_module_targets", return_value=targets):
            result = dc.render_popular_modules_table(**kwargs)
        assert result == (None, None)
