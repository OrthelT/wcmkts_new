"""
Import Helper Service

Calculates local-vs-Jita import opportunities for market items.
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

import pandas as pd
import streamlit as st
from sqlalchemy import bindparam, text

from config import DatabaseConfig
from logging_config import setup_logging
from services.pricer_service import JitaPriceProvider

logger = setup_logging(__name__, log_file="import_helper_service.log")

SHIPPING_COST_PER_M3 = 500.0


def _get_jita_sell_price(jita_prices: dict, type_id) -> float:
    """Safely extract Jita sell price from a provider result map."""
    if pd.isna(type_id):
        return 0.0
    result = jita_prices.get(int(type_id))
    return result.sell_price if result else 0.0


def _get_jita_buy_price(jita_prices: dict, type_id) -> float:
    """Safely extract Jita buy price from a provider result map."""
    if pd.isna(type_id):
        return 0.0
    result = jita_prices.get(int(type_id))
    return result.buy_price if result else 0.0


@dataclass(frozen=True)
class ImportHelperFilters:
    """Filter configuration for Import Helper data."""

    categories: list[str] = field(default_factory=list)
    search_text: str = ""
    profitable_only: bool = True
    min_capital_utilis: Optional[float] = None


class ImportHelperService:
    """Business logic for Import Helper market analysis."""

    def __init__(
        self,
        mkt_db: DatabaseConfig,
        sde_db: DatabaseConfig,
        jita_provider: JitaPriceProvider,
        logger_instance: Optional[logging.Logger] = None,
    ):
        self._mkt_db = mkt_db
        self._sde_db = sde_db
        self._jita_provider = jita_provider
        self._logger = logger_instance or logger

    @classmethod
    def create_default(
        cls,
        db_alias: str = None,
        janice_api_key: str = None,
    ) -> "ImportHelperService":
        """Create the default service for the active market."""
        if db_alias is None:
            try:
                from state.market_state import get_active_market

                db_alias = get_active_market().database_alias
            except (ImportError, Exception):
                db_alias = "wcmkt"

        if janice_api_key is None:
            try:
                janice_api_key = st.secrets.janice.api_key
            except Exception:
                janice_api_key = None

        market_db = DatabaseConfig(db_alias)
        sde_db = DatabaseConfig("sde")
        jita_provider = JitaPriceProvider(janice_api_key)
        return cls(market_db, sde_db, jita_provider)

    def _get_import_candidates(self) -> pd.DataFrame:
        """Fetch marketstats rows merged with SDE item volume."""
        market_query = text(
            """
            SELECT
                type_id,
                type_name,
                price,
                avg_volume,
                category_name,
                group_name
            FROM marketstats
            """
        )

        try:
            with self._mkt_db.engine.connect() as conn:
                market_df = pd.read_sql_query(market_query, conn)
        except Exception as e:
            self._logger.error(f"Failed to fetch import-helper market data: {e}")
            return pd.DataFrame()

        if market_df.empty:
            return market_df

        type_ids = market_df["type_id"].dropna().astype(int).tolist()
        if not type_ids:
            result = market_df.copy()
            result["volume_m3"] = 0.0
            return result

        sde_query = text(
            """
            SELECT
                typeID AS type_id,
                COALESCE(volume, 0) AS volume_m3
            FROM sdetypes
            WHERE typeID IN :type_ids
            """
        ).bindparams(bindparam("type_ids", expanding=True))

        try:
            with self._sde_db.engine.connect() as conn:
                volume_df = pd.read_sql_query(sde_query, conn, params={"type_ids": type_ids})
        except Exception as e:
            self._logger.error(f"Failed to fetch SDE volume data: {e}")
            volume_df = pd.DataFrame(columns=["type_id", "volume_m3"])

        if volume_df.empty:
            result = market_df.copy()
            result["volume_m3"] = 0.0
            return result

        return market_df.merge(volume_df, on="type_id", how="left").fillna({"volume_m3": 0.0})

    def get_category_options(self) -> list[str]:
        """Return category options for sidebar filtering."""
        try:
            query = "SELECT DISTINCT category_name FROM marketstats ORDER BY category_name"
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn)
            return df["category_name"].dropna().tolist()
        except Exception as e:
            self._logger.error(f"Failed to get import-helper category options: {e}")
            return []

    def get_import_items(
        self,
        filters: Optional[ImportHelperFilters] = None,
    ) -> pd.DataFrame:
        """Return import-helper rows with calculated profitability metrics."""
        filters = filters or ImportHelperFilters()
        df = self._get_import_candidates().copy()
        if df.empty:
            return df

        df["type_id"] = pd.to_numeric(df["type_id"], errors="coerce").astype("Int64")
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
        df["avg_volume"] = pd.to_numeric(df.get("avg_volume"), errors="coerce").fillna(0.0)
        df["volume_m3"] = pd.to_numeric(df.get("volume_m3"), errors="coerce").fillna(0.0)

        type_ids = df["type_id"].dropna().astype(int).tolist()
        jita_prices = self._jita_provider.get_prices(type_ids)

        df["jita_sell_price"] = df["type_id"].map(
            lambda tid: _get_jita_sell_price(jita_prices, tid)
        )
        df["jita_buy_price"] = df["type_id"].map(
            lambda tid: _get_jita_buy_price(jita_prices, tid)
        )

        df["shipping_cost"] = df["volume_m3"] * SHIPPING_COST_PER_M3
        df["profit_jita_sell"] = df["jita_sell_price"] - df["price"]
        df["volume_30d"] = df["avg_volume"] * 30 * df["jita_sell_price"]

        df["capital_utilis"] = 0.0
        nonzero_jita = df["jita_sell_price"] > 0
        df.loc[nonzero_jita, "capital_utilis"] = (
            df.loc[nonzero_jita, "profit_jita_sell"] - df.loc[nonzero_jita, "shipping_cost"]
        ) / df.loc[nonzero_jita, "jita_sell_price"]

        if filters.categories:
            df = df[df["category_name"].isin(filters.categories)]

        if filters.search_text:
            search = filters.search_text.strip().lower()
            df = df[df["type_name"].str.lower().str.contains(search, na=False)]

        if filters.profitable_only:
            df = df[df["profit_jita_sell"] > 0]

        if filters.min_capital_utilis is not None:
            df = df[df["capital_utilis"] >= filters.min_capital_utilis]

        if df.empty:
            return df

        return df.sort_values(
            by=["capital_utilis", "profit_jita_sell", "volume_30d"],
            ascending=[False, False, False],
        ).reset_index(drop=True)

    def get_summary_stats(self, df: pd.DataFrame) -> dict[str, float]:
        """Return top-level summary stats for display."""
        if df.empty:
            return {
                "total_items": 0,
                "profitable_items": 0,
                "avg_capital_utilis": 0.0,
            }

        profitable_items = int((df["profit_jita_sell"] > 0).sum())
        avg_capital_utilis = float(df["capital_utilis"].mean())
        return {
            "total_items": int(len(df)),
            "profitable_items": profitable_items,
            "avg_capital_utilis": avg_capital_utilis,
        }


def get_import_helper_service() -> ImportHelperService:
    """Get or create the ImportHelperService for the active market."""

    def _create() -> ImportHelperService:
        janice_key = None
        try:
            janice_key = st.secrets.janice.api_key
        except Exception:
            pass
        return ImportHelperService.create_default(janice_api_key=janice_key)

    try:
        from state import get_service
        from state.market_state import get_active_market_key

        return get_service(
            f"import_helper_service_{get_active_market_key()}",
            _create,
        )
    except ImportError:
        logger.debug("state module unavailable, creating new ImportHelperService")
        return _create()
