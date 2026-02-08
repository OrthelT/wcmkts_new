"""
Tests for MarketService

Tests pure calculation functions, chart creation, and data orchestration
in the market service layer. Uses synthetic DataFrames to avoid DB dependencies.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import plotly.graph_objects as go


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_history_df():
    """30+ days of market history data for testing."""
    dates = pd.date_range(end=datetime.now(), periods=40, freq="D")
    return pd.DataFrame({
        "type_id": [34] * 40,
        "type_name": ["Tritanium"] * 40,
        "date": dates,
        "average": [5.0 + i * 0.1 for i in range(40)],
        "volume": [1000 + i * 10 for i in range(40)],
    })


@pytest.fixture
def sample_orders_df():
    """Market orders with both buy and sell orders."""
    return pd.DataFrame({
        "order_id": [1, 2, 3, 4],
        "type_id": [34, 34, 35, 35],
        "type_name": ["Tritanium", "Tritanium", "Pyerite", "Pyerite"],
        "typeID": [34, 34, 35, 35],
        "typeName": ["Tritanium", "Tritanium", "Pyerite", "Pyerite"],
        "price": [5.0, 4.5, 10.0, 9.5],
        "volume_remain": [1000, 500, 200, 300],
        "is_buy_order": [0, 1, 0, 1],
        "duration": [90, 90, 90, 90],
        "issued": pd.to_datetime(["2026-01-01"] * 4),
    })


@pytest.fixture
def mock_repo():
    """Mock MarketRepository for service tests."""
    repo = Mock()
    repo.get_all_orders.return_value = pd.DataFrame()
    repo.get_all_stats.return_value = pd.DataFrame()
    repo.get_all_history.return_value = pd.DataFrame()
    repo.get_category_type_ids.return_value = []
    repo.get_history_by_type_ids.return_value = pd.DataFrame()
    return repo


# ---------------------------------------------------------------------------
# Test: calculate_30day_metrics
# ---------------------------------------------------------------------------

class TestCalculate30dayMetrics:
    """Test 30-day market metric calculations."""

    def test_returns_correct_tuple_structure(self, sample_history_df, mock_repo):
        """Should return (avg_vol, avg_isk, vol_delta, isk_delta, df_30, df_7)."""
        mock_repo.get_all_history.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        result = service.calculate_30day_metrics()

        assert isinstance(result, tuple)
        assert len(result) == 6
        avg_vol, avg_isk, vol_delta, isk_delta, df_30, df_7 = result
        assert avg_vol > 0
        assert avg_isk > 0
        assert isinstance(df_30, pd.DataFrame)
        assert isinstance(df_7, pd.DataFrame)

    def test_empty_history_returns_zeros(self, mock_repo):
        """Empty history should return all zeros."""
        mock_repo.get_all_history.return_value = pd.DataFrame()

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        result = service.calculate_30day_metrics()

        assert result == (0, 0, 0, 0, 0, 0)

    def test_category_filter(self, sample_history_df, mock_repo):
        """Filtering by category should use category type_ids."""
        mock_repo.get_category_type_ids.return_value = [34]
        mock_repo.get_history_by_type_ids.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        result = service.calculate_30day_metrics(selected_category="Ship")

        mock_repo.get_category_type_ids.assert_called_once_with("Ship")
        assert result[0] > 0  # avg_vol

    def test_item_filter(self, mock_repo):
        """Filtering by item_id should query by specific type_id."""
        item_df = pd.DataFrame({
            "type_id": [34] * 10,
            "date": pd.date_range(end=datetime.now(), periods=10, freq="D"),
            "average": [5.0] * 10,
            "volume": [100] * 10,
        })
        mock_repo.get_history_by_type_ids.return_value = item_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        result = service.calculate_30day_metrics(selected_item_id=34)

        assert result[0] > 0


# ---------------------------------------------------------------------------
# Test: calculate_isk_volume_by_period
# ---------------------------------------------------------------------------

class TestCalculateISKVolumeByPeriod:
    """Test ISK volume period aggregation."""

    def test_daily_aggregation(self, sample_history_df, mock_repo):
        mock_repo.get_all_history.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        result = service.calculate_isk_volume_by_period("daily")

        assert isinstance(result, pd.Series)
        assert len(result) > 0

    def test_weekly_aggregation(self, sample_history_df, mock_repo):
        mock_repo.get_all_history.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        result = service.calculate_isk_volume_by_period("weekly")

        assert isinstance(result, pd.Series)
        # Weekly should have fewer entries than daily
        daily = service.calculate_isk_volume_by_period("daily")
        assert len(result) <= len(daily)

    def test_monthly_aggregation(self, sample_history_df, mock_repo):
        mock_repo.get_all_history.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        result = service.calculate_isk_volume_by_period("monthly")

        assert isinstance(result, pd.Series)

    def test_date_range_filter(self, sample_history_df, mock_repo):
        mock_repo.get_all_history.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        start = datetime.now() - timedelta(days=10)
        end = datetime.now()
        result = service.calculate_isk_volume_by_period(
            "daily", start_date=start, end_date=end
        )

        assert len(result) <= 11  # 10 days + possible boundary


# ---------------------------------------------------------------------------
# Test: detect_outliers
# ---------------------------------------------------------------------------

class TestDetectOutliers:
    """Test outlier detection (static method)."""

    def test_iqr_detects_outlier(self):
        from services.market_service import MarketService
        series = pd.Series([1, 2, 3, 4, 5, 100])
        mask = MarketService.detect_outliers(series, method="iqr", threshold=1.5)

        assert isinstance(mask, pd.Series)
        assert mask.iloc[-1] is True or mask.iloc[-1] == True  # 100 is outlier

    def test_zscore_detects_outlier(self):
        from services.market_service import MarketService
        series = pd.Series([1, 2, 3, 4, 5, 100])
        mask = MarketService.detect_outliers(series, method="zscore", threshold=2.0)

        assert isinstance(mask, pd.Series)
        assert mask.iloc[-1]  # 100 is outlier

    def test_invalid_method_raises(self):
        from services.market_service import MarketService
        with pytest.raises(ValueError, match="Method must be"):
            MarketService.detect_outliers(pd.Series([1, 2, 3]), method="invalid")


# ---------------------------------------------------------------------------
# Test: handle_outliers
# ---------------------------------------------------------------------------

class TestHandleOutliers:
    """Test outlier handling methods."""

    def test_remove_outliers(self):
        from services.market_service import MarketService
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = MarketService.handle_outliers(series, method="remove")

        assert len(result) < len(series)
        assert 100 not in result.values

    def test_cap_outliers(self):
        from services.market_service import MarketService
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = MarketService.handle_outliers(series, method="cap", cap_percentile=95)

        assert len(result) == len(series)
        assert result.max() < 100

    def test_none_method_returns_unchanged(self):
        from services.market_service import MarketService
        series = pd.Series([1, 2, 3, 4, 5, 100])
        result = MarketService.handle_outliers(series, method="none")

        pd.testing.assert_series_equal(result, series)

    def test_invalid_method_raises(self):
        from services.market_service import MarketService
        with pytest.raises(ValueError):
            MarketService.handle_outliers(pd.Series([1, 2]), method="invalid")


# ---------------------------------------------------------------------------
# Test: create_isk_volume_chart
# ---------------------------------------------------------------------------

class TestCreateISKVolumeChart:
    """Test ISK volume chart creation."""

    def test_returns_plotly_figure(self, sample_history_df, mock_repo):
        mock_repo.get_all_history.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        fig = service.create_isk_volume_chart()

        assert isinstance(fig, go.Figure)
        assert len(fig.data) >= 2  # Bar + moving average line

    def test_chart_with_outlier_cap(self, sample_history_df, mock_repo):
        mock_repo.get_all_history.return_value = sample_history_df

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        fig = service.create_isk_volume_chart(outlier_method="cap")

        assert isinstance(fig, go.Figure)


# ---------------------------------------------------------------------------
# Test: get_top_n_items
# ---------------------------------------------------------------------------

class TestGetTopNItems:
    """Test top N items sorting and limiting."""

    def test_returns_correct_count(self):
        from services.market_service import MarketService
        df = pd.DataFrame({
            "type_name": ["A", "B", "C", "A", "B", "C"],
            "daily_isk_volume": [100, 200, 300, 150, 250, 350],
            "volume": [10, 20, 30, 15, 25, 35],
        })

        result = MarketService.get_top_n_items(
            df, df, period_idx=0, agg_idx=0, sort_idx=0, count=2
        )

        assert result is not None
        assert len(result) == 2

    def test_sort_by_isk(self):
        from services.market_service import MarketService
        df = pd.DataFrame({
            "type_name": ["A", "B", "C"],
            "daily_isk_volume": [300, 100, 200],
            "volume": [10, 30, 20],
        })

        result = MarketService.get_top_n_items(
            df, df, period_idx=0, agg_idx=0, sort_idx=0, count=3
        )

        assert result.index[0] == "A"  # Highest ISK

    def test_sort_by_volume(self):
        from services.market_service import MarketService
        df = pd.DataFrame({
            "type_name": ["A", "B", "C"],
            "daily_isk_volume": [300, 100, 200],
            "volume": [10, 30, 20],
        })

        result = MarketService.get_top_n_items(
            df, df, period_idx=0, agg_idx=0, sort_idx=1, count=3
        )

        assert result.index[0] == "B"  # Highest volume

    def test_empty_df_returns_none(self):
        from services.market_service import MarketService
        empty = pd.DataFrame()
        result = MarketService.get_top_n_items(
            empty, empty, period_idx=0, agg_idx=0, sort_idx=0, count=5
        )

        assert result is None


# ---------------------------------------------------------------------------
# Test: clean_order_data
# ---------------------------------------------------------------------------

class TestCleanOrderData:
    """Test order data cleaning (column renaming, expiry calculation)."""

    def test_renames_columns(self):
        from services.market_service import MarketService
        df = pd.DataFrame({
            "order_id": [1],
            "is_buy_order": [0],
            "type_id": [34],
            "typeID": [34],
            "typeName": ["Tritanium"],
            "type_name": ["Tritanium"],
            "price": [5.0],
            "volume_remain": [100],
            "duration": [90],
            "issued": [pd.Timestamp("2026-01-01")],
        })
        result = MarketService.clean_order_data(df)

        assert "type_name" in result.columns
        assert "expiry" in result.columns
        assert "days_remaining" in result.columns

    def test_calculates_expiry(self):
        from services.market_service import MarketService
        df = pd.DataFrame({
            "order_id": [1],
            "is_buy_order": [0],
            "type_id": [34],
            "typeID": [34],
            "typeName": ["Tritanium"],
            "type_name": ["Tritanium"],
            "price": [5.0],
            "volume_remain": [100],
            "duration": [90],
            "issued": [pd.Timestamp("2026-01-01")],
        })
        result = MarketService.clean_order_data(df)

        assert result["days_remaining"].iloc[0] >= 0


# ---------------------------------------------------------------------------
# Test: get_market_data
# ---------------------------------------------------------------------------

class TestGetMarketData:
    """Test market data retrieval and splitting."""

    def test_returns_sell_buy_stats(self, sample_orders_df, mock_repo):
        mock_repo.get_all_orders.return_value = sample_orders_df
        mock_repo.get_all_stats.return_value = pd.DataFrame({
            "type_id": [34, 35],
            "price": [5.0, 10.0],
            "type_name": ["Tritanium", "Pyerite"],
        })

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        sell, buy, stats = service.get_market_data(show_all=True)

        assert isinstance(sell, pd.DataFrame)
        assert isinstance(buy, pd.DataFrame)
        assert isinstance(stats, pd.DataFrame)

    def test_filters_by_item_id(self, sample_orders_df, mock_repo):
        mock_repo.get_all_orders.return_value = sample_orders_df
        mock_repo.get_all_stats.return_value = pd.DataFrame({
            "type_id": [34, 35],
            "price": [5.0, 10.0],
            "type_name": ["Tritanium", "Pyerite"],
        })

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        sell, buy, stats = service.get_market_data(
            show_all=False, selected_item_id=34
        )

        if not sell.empty:
            assert all(sell["type_id"] == 34)

    def test_empty_orders(self, mock_repo):
        mock_repo.get_all_orders.return_value = pd.DataFrame()
        mock_repo.get_all_stats.return_value = pd.DataFrame()

        from services.market_service import MarketService
        service = MarketService(mock_repo)
        sell, buy, stats = service.get_market_data(show_all=True)

        assert sell.empty
        assert buy.empty
