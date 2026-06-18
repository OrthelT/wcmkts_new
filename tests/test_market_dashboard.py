"""Tests for market dashboard components and service methods."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# =========================================================================
# MarketService.get_market_overview_kpis
# =========================================================================


class TestGetMarketOverviewKpis:
    """Tests for MarketService.get_market_overview_kpis()."""

    def _make_service(
        self, stats_df=None, order_counts=None, update_time="12:00 UTC",
    ):
        from services.market_service import MarketService

        repo = MagicMock()
        repo.get_all_stats.return_value = stats_df
        # Order counts now come from a SQL GROUP BY in the repository, not a
        # full-table pandas load. Default to zeros when not provided.
        repo.get_order_counts.return_value = order_counts or {
            "active_sell_orders": 0,
            "active_buy_orders": 0,
        }
        repo.get_update_time.return_value = update_time
        return MarketService(repo)

    def test_basic_aggregation(self):
        stats = pd.DataFrame({
            "type_id": [34, 35],
            "min_price": [10.0, 20.0],
            "total_volume_remain": [100, 200],
        })
        service = self._make_service(
            stats_df=stats,
            order_counts={"active_sell_orders": 2, "active_buy_orders": 1},
        )
        kpis = service.get_market_overview_kpis()

        assert kpis["total_market_value"] == pytest.approx(10.0 * 100 + 20.0 * 200)
        assert kpis["items_listed"] == 2
        assert kpis["active_sell_orders"] == 2
        assert kpis["active_buy_orders"] == 1
        assert kpis["last_updated"] == "12:00 UTC"

    def test_empty_data_returns_zeros(self):
        service = self._make_service(
            stats_df=pd.DataFrame(), order_counts=None, update_time=None,
        )
        kpis = service.get_market_overview_kpis()

        assert kpis["total_market_value"] == 0.0
        assert kpis["items_listed"] == 0
        assert kpis["active_sell_orders"] == 0
        assert kpis["active_buy_orders"] == 0
        assert kpis["last_updated"] is None

    def test_none_dataframes(self):
        service = self._make_service(stats_df=None, order_counts=None)
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
        service = self._make_service(stats_df=stats, order_counts=None)
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

    def test_nan_returns_empty(self):
        """A missing % vs Jita (NaN) gets no color — the cell renders blank."""
        from pages.components.dashboard_components import _jita_diff_cell_style

        assert _jita_diff_cell_style(float("nan")) == ""


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
            "jita_buy_price", "pct_diff_vs_jita_sell",
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


# =========================================================================
# Jita price NA handling (missing Jita price must render blank, never 0)
# =========================================================================


class TestJitaPriceOrNa:
    """_jita_price_or_na: a missing/failed Jita result is NaN, not a fake 0."""

    def test_none_returns_nan(self):
        from pages.components.dashboard_components import _jita_price_or_na

        assert pd.isna(_jita_price_or_na(None, "sell_price"))

    def test_failed_result_returns_nan(self):
        from types import SimpleNamespace
        from pages.components.dashboard_components import _jita_price_or_na

        failed = SimpleNamespace(success=False, sell_price=0.0, buy_price=0.0)
        assert pd.isna(_jita_price_or_na(failed, "sell_price"))
        assert pd.isna(_jita_price_or_na(failed, "buy_price"))

    def test_successful_result_returns_value(self):
        from types import SimpleNamespace
        from pages.components.dashboard_components import _jita_price_or_na

        ok = SimpleNamespace(success=True, sell_price=8.0, buy_price=7.0)
        assert _jita_price_or_na(ok, "sell_price") == 8.0
        assert _jita_price_or_na(ok, "buy_price") == 7.0


class TestAddJitaPrices:
    """_add_jita_prices: missing/failed prices stay NaN so they render '—'."""

    def test_missing_or_failed_prices_render_as_nan_not_zero(self):
        from types import SimpleNamespace
        from pages.components.dashboard_components import _add_jita_prices

        df = pd.DataFrame({
            "type_id": [34, 35, 36],
            "current_sell_price": [10.0, 20.0, 30.0],
        })
        price_map = {
            34: SimpleNamespace(success=True, sell_price=8.0, buy_price=7.0),
            # 35: a backfilled failure result (success False, price 0)
            35: SimpleNamespace(success=False, sell_price=0.0, buy_price=0.0),
            # 36: absent from the map entirely
        }

        result = _add_jita_prices(df, price_map).set_index("type_id")

        # Priced item keeps real values and a computed % diff
        assert result.loc[34, "jita_sell_price"] == 8.0
        assert result.loc[34, "pct_diff_vs_jita_sell"] == pytest.approx(
            (10.0 - 8.0) / 8.0 * 100
        )
        # A missing Jita price is NOT "free at Jita" — must be NaN, never 0
        for missing_tid in (35, 36):
            assert pd.isna(result.loc[missing_tid, "jita_sell_price"])
            assert pd.isna(result.loc[missing_tid, "jita_buy_price"])
            assert pd.isna(result.loc[missing_tid, "pct_diff_vs_jita_sell"])


class TestCoerceNumericFillValue:
    """_coerce_numeric: fill_value=None preserves NaN (for Jita columns)."""

    def test_default_fills_nan_with_zero(self):
        from pages.components.dashboard_components import _coerce_numeric

        df = pd.DataFrame({"x": [1.0, None]})
        out = _coerce_numeric(df, ["x"])
        assert out["x"].tolist() == [1.0, 0.0]

    def test_fill_value_none_preserves_nan(self):
        from pages.components.dashboard_components import _coerce_numeric

        df = pd.DataFrame({"x": [1.0, None]})
        out = _coerce_numeric(df, ["x"], fill_value=None)
        assert out["x"].iloc[0] == 1.0
        assert pd.isna(out["x"].iloc[1])


# =========================================================================
# _apply_equivalents_to_fits (vectorized) — regression lock vs the old loop
# =========================================================================


class TestApplyEquivalentsToFits:
    """The vectorized update must reproduce the original per-row loop:
    fit_qty > 0 -> total_stock // fit_qty; fit_qty <= 0 -> total_stock;
    type_id with no aggregated stock -> left untouched.
    """

    def test_vectorized_update_matches_loop_semantics(self):
        from pages.components import dashboard_components as dc

        fits_df = pd.DataFrame({
            "type_id": [100, 101, 102, 999],
            "fit_qty": [3, 1, 0, 2],
            "fits_on_mkt": [-1, -1, -1, 7],  # 999 has no equivalent -> stays 7
        })
        aggregated = {100: 10, 101: 5, 102: 8}  # 999 absent

        equiv = MagicMock()
        equiv.get_type_ids_with_equivalents.return_value = [100, 101, 102]
        equiv.get_aggregated_stock.return_value = aggregated

        with patch("settings_service.SettingsService") as mock_settings, patch(
            "services.module_equivalents_service.get_module_equivalents_service",
            return_value=equiv,
        ):
            mock_settings.return_value.use_equivalents = True
            result = dc._apply_equivalents_to_fits(fits_df).set_index("type_id")

        assert result.loc[100, "fits_on_mkt"] == 10 // 3  # floor division -> 3
        assert result.loc[101, "fits_on_mkt"] == 5 // 1   # -> 5
        assert result.loc[102, "fits_on_mkt"] == 8        # fit_qty 0 -> total_stock
        assert result.loc[999, "fits_on_mkt"] == 7        # untouched


# =========================================================================
# _require_jita_prices — total-outage guard (data-integrity)
# =========================================================================


class TestRequireJitaPrices:
    """Bails (None + st.error) only on a TOTAL outage; passes the map through
    when at least one item is priced; an empty request is not an outage.
    """

    def _price_service(self, prices):
        ps = MagicMock()
        ps.get_jita_prices.return_value.prices = prices
        return ps

    def test_total_outage_returns_none_and_surfaces_error(self):
        from types import SimpleNamespace
        from pages.components import dashboard_components as dc

        prices = {
            34: SimpleNamespace(success=False, sell_price=0.0),
            35: SimpleNamespace(success=False, sell_price=0.0),
        }
        ps = self._price_service(prices)
        with patch.object(dc, "st") as mock_st:
            result = dc._require_jita_prices(ps, [34, 35])

        assert result is None
        mock_st.error.assert_called_once()

    def test_partial_availability_returns_map_without_error(self):
        from types import SimpleNamespace
        from pages.components import dashboard_components as dc

        prices = {
            34: SimpleNamespace(success=True, sell_price=8.0),
            35: SimpleNamespace(success=False, sell_price=0.0),
        }
        ps = self._price_service(prices)
        with patch.object(dc, "st") as mock_st:
            result = dc._require_jita_prices(ps, [34, 35])

        assert result is prices
        mock_st.error.assert_not_called()

    def test_empty_type_ids_is_not_an_outage(self):
        from pages.components import dashboard_components as dc

        ps = self._price_service({})
        with patch.object(dc, "st") as mock_st:
            result = dc._require_jita_prices(ps, [])

        assert result == {}
        mock_st.error.assert_not_called()


class TestGetSelectedTypeId:
    """Lock the on_select extraction contract reused by the doctrine tables."""

    def _df(self):
        return pd.DataFrame({"type_id": [11, 22, 33]})

    def _event(self, rows):
        from types import SimpleNamespace
        return SimpleNamespace(selection={"rows": rows})

    def test_none_event_returns_none(self):
        from pages.components.dashboard_components import _get_selected_type_id
        assert _get_selected_type_id(None, self._df()) is None

    def test_empty_selection_returns_none(self):
        from pages.components.dashboard_components import _get_selected_type_id
        assert _get_selected_type_id(self._event([]), self._df()) is None

    def test_valid_row_returns_positional_type_id(self):
        from pages.components.dashboard_components import _get_selected_type_id
        # row index 1 → second row → type_id 22 (positional, index-label agnostic)
        assert _get_selected_type_id(self._event([1]), self._df()) == 22

    def test_out_of_range_row_returns_none(self):
        from pages.components.dashboard_components import _get_selected_type_id
        assert _get_selected_type_id(self._event([99]), self._df()) is None

    def test_negative_row_returns_none(self):
        # Streamlit never emits a negative on_select index, but the guard must
        # reject it rather than letting iloc[-1] silently wrap to the last row.
        from pages.components.dashboard_components import _get_selected_type_id
        assert _get_selected_type_id(self._event([-1]), self._df()) is None

    def test_out_of_range_row_logs_error(self):
        # An out-of-range index means realignment drift (a legit click cannot
        # produce one), so it must be logged loudly, not swallowed.
        from pages.components import dashboard_components as dc
        with patch.object(dc.logger, "error") as mock_err:
            assert dc._get_selected_type_id(self._event([99]), self._df()) is None
        mock_err.assert_called_once()

    def test_normal_no_selection_does_not_log(self):
        # None-event and empty-rows are normal "nothing selected" states — silent.
        from pages.components import dashboard_components as dc
        with patch.object(dc.logger, "error") as mock_err:
            assert dc._get_selected_type_id(None, self._df()) is None
            assert dc._get_selected_type_id(self._event([]), self._df()) is None
        mock_err.assert_not_called()


class TestResolveSelection:
    """Realignment guard for the doctrine tables' on_select handling.

    on_select returns a POSITIONAL index into the *displayed* (possibly
    low-stock-filtered, alphabetically-sorted) rows, but the source frame is the
    full unfiltered frame. _resolve_selection must realign source -> display
    order before positional extraction. Restores the protection of the deleted
    TestResolveTableSelection, which guarded the same off-by-row navigation bug.
    """

    def _event(self, rows):
        from types import SimpleNamespace
        return SimpleNamespace(selection={"rows": rows})

    def test_filtered_frame_maps_position_to_displayed_row(self):
        from pages.components.dashboard_components import _resolve_selection

        # Full source: 4 rows. Low-stock filter kept only labels 2 and 3.
        source_df = pd.DataFrame({"type_id": [11, 22, 33, 44]}, index=[0, 1, 2, 3])
        display_df = source_df.loc[[2, 3]]
        # Displayed position 1 -> label 3 -> type_id 44.
        # The pre-fix bug (source_df.iloc[1] on the full frame) would return 22.
        assert _resolve_selection(
            self._event([1]), source_df, display_df, "market_stats",
        ) == (44, "market_stats")

    def test_reordered_display_maps_by_position_not_label(self):
        from pages.components.dashboard_components import _resolve_selection

        # Alphabetical sort can leave labels non-monotonic in display order.
        source_df = pd.DataFrame({"type_id": [11, 22, 33]}, index=[0, 1, 2])
        display_df = source_df.loc[[2, 0, 1]]  # display order: 33, 11, 22
        assert _resolve_selection(
            self._event([0]), source_df, display_df, "doctrine_status",
        ) == (33, "doctrine_status")

    def test_returns_destination_passed_through(self):
        from pages.components.dashboard_components import _resolve_selection

        source_df = pd.DataFrame({"type_id": [11, 22]}, index=[0, 1])
        assert _resolve_selection(
            self._event([0]), source_df, source_df, "doctrine_status",
        ) == (11, "doctrine_status")

    def test_no_selection_returns_none_none(self):
        from pages.components.dashboard_components import _resolve_selection

        source_df = pd.DataFrame({"type_id": [11, 22]}, index=[0, 1])
        assert _resolve_selection(
            self._event([]), source_df, source_df, "market_stats",
        ) == (None, None)


class TestDestinationToggle:
    def test_returns_choice_when_segment_selected(self):
        from pages.components import dashboard_components as dc
        with patch.object(dc, "st") as mock_st:
            mock_st.columns.return_value = (MagicMock(), MagicMock())
            mock_st.segmented_control.return_value = "market_stats"
            assert dc._render_destination_toggle("k", "en") == "market_stats"

    def test_falls_back_to_doctrine_status_when_none(self):
        from pages.components import dashboard_components as dc
        with patch.object(dc, "st") as mock_st:
            mock_st.columns.return_value = (MagicMock(), MagicMock())
            mock_st.segmented_control.return_value = None
            assert dc._render_destination_toggle("k", "en") == "doctrine_status"


class TestTableFunctionsDropDestinationParam:
    def test_ships_table_has_no_destination_param(self):
        import inspect
        from pages.components.dashboard_components import render_doctrine_ships_table
        assert "destination" not in inspect.signature(render_doctrine_ships_table).parameters

    def test_modules_table_has_no_destination_param(self):
        import inspect
        from pages.components.dashboard_components import render_popular_modules_table
        assert "destination" not in inspect.signature(render_popular_modules_table).parameters


class TestCommodityGridNoGlobalToggle:
    def test_grid_source_has_no_global_destination_toggle(self):
        # Read the source directly to avoid triggering main() at import time
        import pathlib
        source_path = pathlib.Path(__file__).parent.parent / "pages" / "market_dashboard.py"
        source = source_path.read_text()

        # Extract the _render_commodity_grid function body
        # Find from "def _render_commodity_grid" to the next "def " at same indentation
        import re
        match = re.search(
            r"def _render_commodity_grid\(.*?\):\n(.*?)(?=\ndef )",
            source,
            re.DOTALL
        )
        if not match:
            pytest.fail("Could not find _render_commodity_grid function")

        func_body = match.group(1)
        assert "dash_row_destination" not in func_body, "Orphaned dash_row_destination key found"
        assert "segmented_control" not in func_body, "Orphaned segmented_control found"
        assert "destination=dest" not in func_body, "Orphaned destination=dest kwarg found"
