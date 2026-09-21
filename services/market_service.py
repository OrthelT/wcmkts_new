"""
Market Service

Pure business logic for market data analysis: metric calculations, ISK volume
aggregation and chart creation. No Streamlit imports.

Design Principles:
1. Dependency Injection - MarketRepository passed in, not created
2. Pure Functions - No session state, no UI, no caching (caching is in repo layer)
3. Testable - All methods work with plain DataFrames and return plain objects
4. Chart creation returns Plotly Figures (not rendered) for page layer to display
"""

from typing import Optional
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

from logging_config import setup_logging

logger = setup_logging(__name__)

# SDE category id for ships. The 30-day panel scopes the "Ship" category the
# same way the "Ships" pill does — shuttles excluded — by routing through the
# pill resolver instead of the shuttle-inclusive category resolver.
SHIP_CATEGORY_ID = 6


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

        # Clean order data. Sort so the tables open on the prices that matter:
        # cheapest sell first, highest buy first, grouped per item when the
        # view spans more than one type.
        if not sell_df.empty:
            sell_df = self._sort_orders(self.clean_order_data(sell_df), ascending=True)
        if not buy_df.empty:
            buy_df = self._sort_orders(self.clean_order_data(buy_df), ascending=False)

        return sell_df, buy_df, stats_df

    @staticmethod
    def _sort_orders(df: pd.DataFrame, ascending: bool) -> pd.DataFrame:
        """Sort orders by price, keeping each item's orders together."""
        if "price" not in df.columns:
            return df
        sort_cols = ["price"]
        order = [ascending]
        if "type_name" in df.columns and df["type_name"].nunique() > 1:
            sort_cols.insert(0, "type_name")
            order.insert(0, True)
        return df.sort_values(sort_cols, ascending=order).reset_index(drop=True)

    def get_current_market_snapshot(self, type_ids: list[int]) -> pd.DataFrame:
        """Get current local sell price and sell-order volume for specific type IDs."""
        if not type_ids:
            return pd.DataFrame(
                columns=["type_id", "type_name", "current_sell_price", "order_volume"]
            )

        requested_ids = [int(type_id) for type_id in dict.fromkeys(type_ids)]
        base_df = pd.DataFrame({"type_id": requested_ids})

        # Fetch only the requested rows — filtering and (for orders) the sell
        # aggregation happen in SQL via the repository, so the full
        # marketstats / marketorders tables are never loaded into pandas.
        stats_df = self._repo.get_stats_for_type_ids(requested_ids)
        if stats_df is None or stats_df.empty:
            stats_df = pd.DataFrame(
                columns=["type_id", "type_name", "min_price", "total_volume_remain"]
            )
        else:
            stats_df = (
                stats_df[["type_id", "type_name", "min_price", "total_volume_remain"]]
                .drop_duplicates(subset=["type_id"])
                .copy()
            )
            stats_df["min_price"] = pd.to_numeric(stats_df["min_price"], errors="coerce")
            stats_df["total_volume_remain"] = pd.to_numeric(
                stats_df["total_volume_remain"],
                errors="coerce",
            )

        sell_summary = self._repo.get_sell_order_summary(requested_ids)
        if sell_summary is None or sell_summary.empty:
            sell_summary = pd.DataFrame(
                columns=["type_id", "order_type_name", "sell_order_price", "sell_order_volume"]
            )
        else:
            sell_summary = sell_summary.copy()
            sell_summary["sell_order_price"] = pd.to_numeric(
                sell_summary["sell_order_price"], errors="coerce"
            )
            sell_summary["sell_order_volume"] = pd.to_numeric(
                sell_summary["sell_order_volume"], errors="coerce"
            )

        result = base_df.merge(stats_df, on="type_id", how="left").merge(
            sell_summary,
            on="type_id",
            how="left",
        )
        result["type_name"] = result["type_name"].combine_first(result["order_type_name"])
        result["current_sell_price"] = result["sell_order_price"].where(
            result["sell_order_price"].notna(),
            result["min_price"],
        )
        result["order_volume"] = result["sell_order_volume"].where(
            result["sell_order_volume"].notna(),
            result["total_volume_remain"],
        )
        result["current_sell_price"] = (
            pd.to_numeric(result["current_sell_price"], errors="coerce").fillna(0.0)
        )
        result["order_volume"] = pd.to_numeric(result["order_volume"], errors="coerce").fillna(0.0)
        return result[["type_id", "type_name", "current_sell_price", "order_volume"]]

    def get_market_overview_kpis(self) -> dict:
        """Aggregate market-wide KPI totals from the live order book.

        total_market_value and items_listed come from marketorders (sell side)
        so the dashboard matches the Market Stats page's all-items "Sell Orders
        Value" (both are SUM(price * volume_remain) over sell orders; the
        Market Stats figure only differs when a category filter is active
        there) — see _get_order_book_summary_impl for why marketstats is
        deliberately not used here.

        Returns:
            Dict with keys: total_market_value, active_sell_orders,
            active_buy_orders, items_listed, last_updated.
        """
        summary = self._repo.get_order_book_summary()
        return {
            "total_market_value": float(summary.get("sell_order_value", 0.0)),
            "active_sell_orders": int(summary.get("active_sell_orders", 0)),
            "active_buy_orders": int(summary.get("active_buy_orders", 0)),
            "items_listed": int(summary.get("sell_types_listed", 0)),
            "last_updated": self._repo.get_update_time(),
        }

    def get_30day_filter_type_ids(self, filter_key: str) -> list:
        """Resolve a 30-day stats pill filter key to type_ids."""
        return self._repo.get_30day_filter_type_ids(filter_key)

    # =====================================================================
    # Pure Calculations
    # =====================================================================

    def calculate_30day_metrics(
        self,
        selected_category: str = None,
        selected_category_id: int | None = None,
        selected_item_id: int = None,
        selected_type_ids: list[int] | None = None,
    ) -> tuple:
        """Calculate 30-day and 7-day market metrics.

        Scope precedence: selected_item_id > selected_type_ids >
        category > all items. selected_type_ids=[] is an empty scope and
        returns zeros without querying (never widens to all items).

        Returns:
            (avg_daily_volume, avg_daily_isk_value, vol_delta, isk_delta,
             df_30days, df_7days)
            All zeros and zeros tuple on error or empty data.
        """
        try:
            if selected_item_id:
                df = self._repo.get_history_by_type_ids([selected_item_id])
            elif selected_type_ids is not None:
                if not selected_type_ids:
                    return 0, 0, 0, 0, 0, 0
                df = self._repo.get_history_by_type_ids(selected_type_ids)
            elif selected_category_id is not None or selected_category:
                if selected_category_id == SHIP_CATEGORY_ID or selected_category == "Ship":
                    # Ship scope excludes shuttles here (matches the Ships pill),
                    # so route through the pill resolver, not the shuttle-
                    # inclusive category resolver used by the main table.
                    type_ids = self._repo.get_30day_filter_type_ids("ships")
                else:
                    type_ids = self._repo.get_category_type_ids(
                        selected_category,
                        category_id=selected_category_id,
                    )
                if not type_ids:
                    return 0, 0, 0, 0, 0, 0
                df = self._repo.get_history_by_type_ids(type_ids)
            else:
                # Unfiltered scope: fetch the window this method reports on
                # rather than the whole table. The pandas cutoffs below still
                # apply -- they carve the 7-day slice out of the same frame.
                df = self._repo.get_history_window(30)

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

            # Divide totals by the fixed window size, not by traded-day count.
            # An item traded on 17 of 30 days still has a 30-day denominator.
            avg_vol = daily_30["volume"].sum() / 30
            avg_isk = daily_30["daily_isk_volume"].sum() / 30
            avg_vol_7 = daily_7["volume"].sum() / 7 if not daily_7.empty else 0
            avg_isk_7 = daily_7["daily_isk_volume"].sum() / 7 if not daily_7.empty else 0

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

    def create_30day_activity_chart(self, df_30days) -> Optional[go.Figure]:
        """Create the daily ISK value (bars) + units traded (line) chart.

        Args:
            df_30days: the 30-day history slice from calculate_30day_metrics()
                with date, volume, and daily_isk_volume columns. Error paths
                return the int 0 sentinel instead of a DataFrame, so guard on
                type, not just emptiness.

        Returns:
            Plotly Figure, or None when there is nothing to chart.
        """
        if not isinstance(df_30days, pd.DataFrame) or df_30days.empty:
            return None

        daily = (
            df_30days.groupby("date")
            .agg(volume=("volume", "sum"), isk_value=("daily_isk_volume", "sum"))
            .reset_index()
            .sort_values("date")
        )

        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(
            go.Bar(
                x=daily["date"],
                y=daily["isk_value"],
                name="ISK Value",
                hovertemplate="<b>%{x}</b><br>ISK: %{y:,.0f}<extra></extra>",
            ),
            secondary_y=False,
        )
        fig.add_trace(
            go.Scatter(
                x=daily["date"],
                y=daily["volume"],
                name="Units Traded",
                line=dict(color="#FF69B4", width=2),
                hovertemplate="<b>%{x}</b><br>Units: %{y:,.0f}<extra></extra>",
            ),
            secondary_y=True,
        )
        fig.update_layout(
            height=350,
            margin=dict(t=30, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        )
        fig.update_yaxes(title_text="ISK Value", secondary_y=False)
        fig.update_yaxes(title_text="Units Traded", secondary_y=True, showgrid=False)
        return fig

    def calculate_isk_volume_by_period(
        self,
        period: str = "daily",
        days: int | None = 30,
        category: str = None,
        category_id: int | None = None,
    ) -> pd.Series:
        """Calculate ISK volume aggregated by time period.

        The per-date sum is done in SQL (see
        ``MarketRepository.get_isk_volume_by_date``); this only re-groups the
        daily series into weeks, months, or years.

        Args:
            period: 'daily', 'weekly', 'monthly', or 'yearly'
            days: window size in days; None for the whole history
            category: Optional SDE category name filter
            category_id: Optional SDE category ID filter

        Returns:
            Series indexed by date/period with ISK volume values.
        """
        type_ids = None
        if category is not None or category_id is not None:
            type_ids = self._repo.get_category_type_ids(
                category, category_id=category_id
            )
            if not type_ids:
                return pd.Series(dtype=float)

        df = self._repo.get_isk_volume_by_date(days=days, type_ids=type_ids)
        if df.empty:
            return pd.Series(dtype=float)

        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])

        if period == "weekly":
            grouped = df.groupby(df["date"].dt.to_period("W"))["total_isk_volume"].sum()
            grouped.index = grouped.index.to_timestamp()
        elif period == "monthly":
            grouped = df.groupby(df["date"].dt.to_period("M"))["total_isk_volume"].sum()
            grouped.index = grouped.index.to_timestamp()
        elif period == "yearly":
            grouped = df.groupby(df["date"].dt.to_period("Y"))["total_isk_volume"].sum()
            grouped.index = grouped.index.to_timestamp()
        else:
            grouped = df.set_index("date")["total_isk_volume"]

        grouped.index.name = "date"
        return grouped

    def get_available_date_range(
        self,
        category: str = None,
        category_id: int | None = None,
    ) -> tuple:
        """Get min and max dates from market history.

        Aggregated in SQL rather than reduced from a loaded frame: this only
        needs two dates, and the unfiltered history is ~890 k rows.

        Returns:
            (min_date, max_date) as pandas Timestamps, or (None, None).
        """
        if category is None and category_id is None:
            return self._repo.get_history_date_range(None)

        type_ids = self._repo.get_category_type_ids(category, category_id=category_id)
        if not type_ids:
            return None, None
        return self._repo.get_history_date_range(type_ids)

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
        # A source frame carrying both spellings ends up with two identically
        # named columns after the rename; keep the first so later lookups
        # return a Series rather than a DataFrame.
        df = df.loc[:, ~df.columns.duplicated()]

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
        days: int | None = 30,
        selected_category: str = None,
        selected_category_id: int | None = None,
    ) -> go.Figure:
        """Create ISK volume bar chart with moving average.

        Returns:
            Plotly Figure with bars and moving average line.
        """
        df = self.calculate_isk_volume_by_period(
            date_period,
            days,
            selected_category,
            selected_category_id,
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

        cat_suffix = f" - {selected_category}" if selected_category else ""

        fig.update_layout(
            title=f"{label} ISK Volume with {moving_avg_period}-Period Moving Average{cat_suffix}",
            xaxis_title="Date",
            yaxis_title="ISK Volume",
        )
        return fig

    def create_isk_volume_table(
        self,
        date_period: str = "daily",
        days: int | None = 30,
        selected_category: str = None,
        selected_category_id: int | None = None,
    ) -> pd.DataFrame:
        """Create ISK volume table matching chart filters.

        Returns:
            DataFrame with Date and ISK Volume columns, sorted descending.
        """
        df = self.calculate_isk_volume_by_period(
            date_period,
            days,
            selected_category,
            selected_category_id,
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



# =============================================================================
# Factory Function
# =============================================================================

def get_market_service() -> MarketService:
    """Get or create a MarketService instance for the active market.

    Uses state.get_service for session persistence. Falls back to
    direct instantiation if state module is unavailable.
    """
    def _create() -> MarketService:
        from repositories.market_repo import get_market_repository
        repo = get_market_repository()
        return MarketService(repo)

    try:
        from state import get_service
        from state.market_state import get_active_market_key
        return get_service(f"market_service_{get_active_market_key()}", _create)
    except ImportError:
        logger.debug("state module unavailable, creating new MarketService instance")
        return _create()
