"""
Market Service

Pure business logic for market data analysis: metric calculations, ISK volume
aggregation, outlier handling, and chart creation. No Streamlit imports.

Design Principles:
1. Dependency Injection - MarketRepository passed in, not created
2. Pure Functions - No session state, no UI, no caching (caching is in repo layer)
3. Testable - All methods work with plain DataFrames and return plain objects
4. Chart creation returns Plotly Figures (not rendered) for page layer to display
"""

from typing import Optional
from datetime import datetime, timedelta

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from config import get_settings
from logging_config import setup_logging

logger = setup_logging(__name__)


class MarketService:
    """Market analysis service with pure calculation and chart creation logic.

    Args:
        market_repo: MarketRepository instance for data access.
    """

    def __init__(self, market_repo):
        self._repo = market_repo

    # =====================================================================
    # Data Access Orchestration
    # =====================================================================

    def get_history_by_category(self, category: str = None) -> pd.DataFrame:
        """Get market history, optionally filtered by SDE category.

        Args:
            category: SDE category name (e.g. 'Ship'). None for all history.

        Returns:
            DataFrame with market history rows.
        """
        if category is None:
            return self._repo.get_all_history()

        type_ids = self._repo.get_category_type_ids(category)
        if not type_ids:
            return pd.DataFrame()

        df = self._repo.get_history_by_type_ids(type_ids)
        return df if not df.empty else pd.DataFrame()

    def get_market_data(
        self,
        show_all: bool,
        category_info: Optional[dict] = None,
        selected_item_id: Optional[int] = None,
    ) -> tuple:
        """Get filtered market data split into sell/buy orders + stats.

        Args:
            show_all: If True, return all orders unfiltered.
            category_info: Optional dict with 'type_ids' key for category filter.
            selected_item_id: Optional type_id for single-item filter.

        Returns:
            (sell_df, buy_df, stats_df) tuple of DataFrames.
        """
        df = self._repo.get_all_orders()
        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        # Apply filters
        if selected_item_id:
            orders_df = df[df["type_id"] == selected_item_id]
        elif category_info and "type_ids" in category_info:
            orders_df = df[df["type_id"].isin(category_info["type_ids"])]
        else:
            orders_df = df

        # Get stats filtered to matching type_ids
        stats_df = self._repo.get_all_stats()
        if not stats_df.empty and not orders_df.empty:
            stats_df = stats_df[
                stats_df["type_id"].isin(orders_df["type_id"].unique())
            ].reset_index(drop=True)

        # Split into sell/buy
        sell_df = orders_df[orders_df["is_buy_order"] == 0].reset_index(drop=True)
        buy_df = orders_df[orders_df["is_buy_order"] == 1].reset_index(drop=True)

        # Clean order data
        if not sell_df.empty:
            sell_df = self.clean_order_data(sell_df)
        if not buy_df.empty:
            buy_df = self.clean_order_data(buy_df)

        return sell_df, buy_df, stats_df

    # =====================================================================
    # Pure Calculations
    # =====================================================================

    def calculate_30day_metrics(
        self,
        selected_category: str = None,
        selected_item_id: int = None,
    ) -> tuple:
        """Calculate 30-day and 7-day market metrics.

        Returns:
            (avg_daily_volume, avg_daily_isk_value, vol_delta, isk_delta,
             df_30days, df_7days)
            All zeros and zeros tuple on error or empty data.
        """
        try:
            if selected_item_id:
                df = self._repo.get_history_by_type_ids([selected_item_id])
            elif selected_category:
                type_ids = self._repo.get_category_type_ids(selected_category)
                if not type_ids:
                    return 0, 0, 0, 0, 0, 0
                df = self._repo.get_history_by_type_ids(type_ids)
            else:
                df = self._repo.get_all_history()

            if df.empty:
                return 0, 0, 0, 0, 0, 0

            df["date"] = pd.to_datetime(df["date"])

            month_cutoff = datetime.now() - timedelta(days=30)
            week_cutoff = datetime.now() - timedelta(days=7)
            df_30days = df[df["date"] >= month_cutoff].copy()
            df_7days = df[df["date"] >= week_cutoff].copy()

            if df_30days.empty:
                return 0, 0, 0, 0, 0, 0

            df_30days["daily_isk_volume"] = df_30days["average"] * df_30days["volume"]
            df_7days["daily_isk_volume"] = df_7days["average"] * df_7days["volume"]

            daily_30 = df_30days.groupby("date").agg(
                {"volume": "sum", "daily_isk_volume": "sum"}
            ).reset_index()
            daily_7 = df_7days.groupby("date").agg(
                {"volume": "sum", "daily_isk_volume": "sum"}
            ).reset_index()

            avg_vol = daily_30["volume"].mean()
            avg_isk = daily_30["daily_isk_volume"].mean()
            avg_vol_7 = daily_7["volume"].mean() if not daily_7.empty else 0
            avg_isk_7 = daily_7["daily_isk_volume"].mean() if not daily_7.empty else 0

            vol_delta = round(
                ((avg_vol_7 - avg_vol) / avg_vol * 100) if avg_vol > 0 else 0, 1
            )
            isk_delta = round(
                ((avg_isk_7 - avg_isk) / avg_isk * 100) if avg_isk > 0 else 0, 1
            )

            return avg_vol, avg_isk, vol_delta, isk_delta, df_30days, df_7days

        except Exception as e:
            logger.error(f"Error calculating 30-day metrics: {e}")
            return 0, 0, 0, 0, 0, 0

    def calculate_isk_volume_by_period(
        self,
        period: str = "daily",
        start_date=None,
        end_date=None,
        category: str = None,
    ) -> pd.Series:
        """Calculate ISK volume aggregated by time period.

        Args:
            period: 'daily', 'weekly', 'monthly', or 'yearly'
            start_date: Optional start date filter
            end_date: Optional end date filter
            category: Optional SDE category name filter

        Returns:
            Series indexed by date/period with ISK volume values.
        """
        df = self.get_history_by_category(category)
        if df.empty:
            return pd.Series(dtype=float)

        df["date"] = pd.to_datetime(df["date"])

        if start_date is not None:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date is not None:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        df["total_isk_volume"] = df["average"] * df["volume"]

        if period == "weekly":
            df["week"] = df["date"].dt.to_period("W")
            grouped = df.groupby("week")["total_isk_volume"].sum()
            grouped.index = grouped.index.to_timestamp()
        elif period == "monthly":
            df["month"] = df["date"].dt.to_period("M")
            grouped = df.groupby("month")["total_isk_volume"].sum()
            grouped.index = grouped.index.to_timestamp()
        elif period == "yearly":
            df["year"] = df["date"].dt.to_period("Y")
            grouped = df.groupby("year")["total_isk_volume"].sum()
            grouped.index = grouped.index.to_timestamp()
        else:
            grouped = df.groupby("date")["total_isk_volume"].sum()

        return grouped

    def get_available_date_range(
        self, category: str = None
    ) -> tuple:
        """Get min and max dates from market history.

        Returns:
            (min_date, max_date) as pandas Timestamps, or (None, None).
        """
        df = self.get_history_by_category(category)
        if df.empty:
            return None, None
        df["date"] = pd.to_datetime(df["date"])
        return df["date"].min(), df["date"].max()

    @staticmethod
    def get_top_n_items(
        df_7days: pd.DataFrame,
        df_30days: pd.DataFrame,
        period_idx: int,
        agg_idx: int,
        sort_idx: int,
        count: int,
    ) -> Optional[pd.DataFrame]:
        """Get top N items by ISK volume or quantity.

        Args:
            df_7days: 7-day history with 'type_name', 'daily_isk_volume', 'volume'
            df_30days: 30-day history with same columns
            period_idx: 0=week, 1=month
            agg_idx: 0=daily average, 1=total
            sort_idx: 0=by ISK, 1=by volume
            count: Number of items to return

        Returns:
            DataFrame with top items, or None if empty.
        """
        if df_7days.empty or df_30days.empty:
            return None

        source = df_7days.copy() if period_idx == 0 else df_30days.copy()

        agg_func = "mean" if agg_idx == 0 else "sum"
        grouped = source.groupby("type_name").agg(
            {"daily_isk_volume": agg_func, "volume": agg_func}
        )

        sort_col = "daily_isk_volume" if sort_idx == 0 else "volume"
        return grouped.sort_values(sort_col, ascending=False).head(count)

    # =====================================================================
    # Static Utilities
    # =====================================================================

    @staticmethod
    def detect_outliers(
        series: pd.Series, method: str = "iqr", threshold: float = 1.5
    ) -> pd.Series:
        """Detect outliers in a numeric Series.

        Args:
            series: Numeric data
            method: 'iqr' or 'zscore'
            threshold: Sensitivity (1.5 for IQR, 2-3 for z-score)

        Returns:
            Boolean Series where True = outlier.
        """
        if method == "iqr":
            q1 = series.quantile(0.25)
            q3 = series.quantile(0.75)
            iqr = q3 - q1
            return (series < q1 - threshold * iqr) | (series > q3 + threshold * iqr)
        elif method == "zscore":
            z = np.abs((series - series.mean()) / series.std())
            return z > threshold
        else:
            raise ValueError("Method must be 'iqr' or 'zscore'")

    @staticmethod
    def handle_outliers(
        series: pd.Series,
        method: str = "none",
        outlier_threshold: float = 1.5,
        cap_percentile: int = 95,
    ) -> pd.Series:
        """Handle outliers by removing, capping, or leaving unchanged.

        Args:
            series: Numeric data
            method: 'remove', 'cap', or 'none'
            outlier_threshold: Detection threshold
            cap_percentile: Percentile for capping (when method='cap')

        Returns:
            Series with outliers handled.
        """
        if method == "none":
            return series

        outliers = MarketService.detect_outliers(
            series, threshold=outlier_threshold
        )

        if method == "remove":
            return series[~outliers]
        elif method == "cap":
            cap_value = series.quantile(cap_percentile / 100)
            result = series.astype(float).copy()
            result[outliers] = cap_value
            return result
        else:
            raise ValueError("Method must be 'remove', 'cap', or 'none'")

    @staticmethod
    def clean_order_data(df: pd.DataFrame) -> pd.DataFrame:
        """Clean market order data: rename columns, calculate expiry.

        Args:
            df: Raw order DataFrame from marketorders table.

        Returns:
            Cleaned DataFrame with standardized columns and expiry dates.
        """
        df = df.copy().reset_index(drop=True)
        df.rename(
            columns={"typeID": "type_id", "typeName": "type_name"}, inplace=True
        )

        cols = [
            "order_id", "is_buy_order", "type_id", "type_name",
            "price", "volume_remain", "duration", "issued",
        ]
        available_cols = [c for c in cols if c in df.columns]
        df = df[available_cols]

        if not pd.api.types.is_datetime64_any_dtype(df["issued"]):
            df["issued"] = pd.to_datetime(df["issued"])

        df["expiry"] = df.apply(
            lambda r: r["issued"] + pd.Timedelta(days=r["duration"]), axis=1
        )
        df["days_remaining"] = (df["expiry"] - pd.Timestamp.now()).dt.days
        df["days_remaining"] = df["days_remaining"].apply(lambda x: max(x, 0)).astype(int)
        df["issued"] = df["issued"].dt.date
        df["expiry"] = df["expiry"].dt.date

        return df.reset_index(drop=True)

    # =====================================================================
    # Chart Creation (returns Plotly Figures)
    # =====================================================================

    def create_isk_volume_chart(
        self,
        moving_avg_period: int = 14,
        date_period: str = "daily",
        start_date=None,
        end_date=None,
        outlier_method: str = None,
        outlier_threshold: float = 1.5,
        cap_percentile: int = 95,
        selected_category: str = None,
    ) -> go.Figure:
        """Create ISK volume bar chart with moving average.

        Returns:
            Plotly Figure with bars and moving average line.
        """
        if outlier_method is None:
            outlier_method = _get_default_outlier_method()

        df = self.calculate_isk_volume_by_period(
            date_period, start_date, end_date, selected_category
        )

        if outlier_method != "none":
            df = self.handle_outliers(
                df,
                method=outlier_method,
                outlier_threshold=outlier_threshold,
                cap_percentile=cap_percentile,
            )

        period_labels = {
            "daily": "Daily",
            "weekly": "Weekly",
            "monthly": "Monthly",
            "yearly": "Yearly",
        }
        label = period_labels.get(date_period, "Daily")

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df.index,
            y=df.values,
            name=f"{label} ISK Volume",
            hovertemplate="<b>%{x}</b><br>ISK: %{y:,.0f}<extra></extra>",
        ))

        moving_avg = df.rolling(window=moving_avg_period, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=df.index,
            y=moving_avg.values,
            name=f"{moving_avg_period}-Period Moving Average",
            line=dict(color="#FF69B4", width=2),
            hovertemplate="<b>%{x}</b><br>Mov Avg: %{y:,.0f}<extra></extra>",
        ))

        title_suffix = ""
        if outlier_method == "cap":
            title_suffix = f" (Outliers capped at {cap_percentile}th percentile)"
        elif outlier_method == "remove":
            title_suffix = " (Outliers removed)"

        cat_suffix = f" - {selected_category}" if selected_category else ""

        fig.update_layout(
            title=f"{label} ISK Volume with {moving_avg_period}-Period Moving Average{cat_suffix}{title_suffix}",
            xaxis_title="Date",
            yaxis_title="ISK Volume",
        )
        return fig

    def create_isk_volume_table(
        self,
        date_period: str = "daily",
        start_date=None,
        end_date=None,
        selected_category: str = None,
    ) -> pd.DataFrame:
        """Create ISK volume table matching chart filters.

        Returns:
            DataFrame with Date and ISK Volume columns, sorted descending.
        """
        df = self.calculate_isk_volume_by_period(
            date_period, start_date, end_date, selected_category
        )
        table = df.reset_index()
        table.columns = ["Date", "ISK Volume"]
        table["ISK Volume"] = table["ISK Volume"].apply(lambda x: f"{x:,.0f}")
        return table.sort_values("Date", ascending=False)

    def create_history_chart(self, type_id: int) -> Optional[go.Figure]:
        """Create price+volume history chart for a specific item.

        Args:
            type_id: EVE type ID

        Returns:
            Plotly Figure with price and volume subplots, or None if no data.
        """
        df = self._repo.get_history_by_type(type_id)
        if df.empty:
            return None

        df["ma_14"] = df["average"].rolling(window=14).mean()

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.7, 0.3],
        )

        fig.add_trace(
            go.Scatter(
                x=df["date"], y=df["average"],
                name="Average Price",
                line=dict(color="#FF69B4", width=2),
            ),
            row=1, col=1,
        )

        fig.add_trace(
            go.Scatter(
                x=df["date"], y=df["ma_14"],
                name="14-Day MA",
                line=dict(color="#b87fe3", width=2, dash="dot"),
            ),
            row=1, col=1,
        )

        fig.add_trace(
            go.Bar(
                x=df["date"], y=df["volume"],
                name="Volume",
                opacity=0.5,
                marker_color="#00B5F7",
            ),
            row=2, col=1,
        )

        fig.update_layout(
            paper_bgcolor="#0F1117",
            plot_bgcolor="#0F1117",
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1,
                xanchor="right", x=1,
                font=dict(color="white"),
                bgcolor="rgba(10,10,10,0)",
            ),
            title_font_color="white",
            hovermode="x unified",
            autosize=True,
        )

        fig.update_yaxes(
            title=dict(text="Price (ISK)", font=dict(color="white", size=10), standoff=5),
            gridcolor="rgba(128,128,128,0.2)",
            tickfont=dict(color="white"),
            tickformat=",",
            row=1, col=1,
            automargin=True,
        )
        fig.update_yaxes(
            title=dict(text="Volume", font=dict(color="white", size=10), standoff=5),
            gridcolor="rgba(128,128,128,0.2)",
            tickfont=dict(color="white"),
            tickformat=",",
            row=2, col=1,
            automargin=True,
            color="white",
        )
        fig.update_xaxes(
            gridcolor="rgba(128,128,128,0.2)",
            tickfont=dict(color="white"),
            row=2, col=1,
        )
        fig.update_xaxes(showticklabels=False, row=1, col=1)

        fig.add_shape(
            type="rect",
            xref="paper", yref="paper",
            x0=0, y0=0, x1=1, y1=0.3,
            fillcolor="#1a1a2e",
            layer="below",
            line_width=0,
        )
        return fig

    def create_price_volume_chart(self, df: pd.DataFrame) -> go.Figure:
        """Create price-volume histogram for sell orders.

        Args:
            df: DataFrame with 'price' and 'volume_remain' columns.

        Returns:
            Plotly Figure with histogram.
        """
        fig = px.histogram(
            df,
            x="price",
            y="volume_remain",
            histfunc="sum",
            nbins=50,
            title="Market Orders Distribution",
            labels={"price": "Price (ISK)", "volume_remain": "Volume Available"},
        )
        fig.update_layout(
            bargap=0.1,
            xaxis_title="Price (ISK)",
            yaxis_title="Volume Available",
            showlegend=False,
        )
        fig.update_xaxes(tickformat=",")
        return fig


# =============================================================================
# Module-level Helpers
# =============================================================================

def _get_default_outlier_method() -> str:
    """Get default outlier method from settings.toml."""
    settings = get_settings()
    return settings["outliers"]["default_method"]


# =============================================================================
# Factory Function
# =============================================================================

def get_market_service() -> MarketService:
    """Get or create a MarketService instance.

    Uses state.get_service for session persistence. Falls back to
    direct instantiation if state module is unavailable.
    """
    def _create() -> MarketService:
        from repositories.market_repo import get_market_repository
        repo = get_market_repository()
        return MarketService(repo)

    try:
        from state import get_service
        return get_service("market_service", _create)
    except ImportError:
        logger.debug("state module unavailable, creating new MarketService instance")
        return _create()
