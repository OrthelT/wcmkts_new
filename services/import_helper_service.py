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
from repositories import get_sde_repository
from repositories.sde_repo import SDERepository
from services.price_service import PriceResult, PriceService, get_price_service
from services.type_name_localization import apply_localized_type_names
from settings_service import SettingsService

logger = setup_logging(__name__, log_file="import_helper_service.log")

_settings = SettingsService()
SHIPPING_COST_PER_M3: float = _settings.default_shipping_cost

# Ship shipping costs must use packaged volume instead of raw assembled hull volume.
PACKAGED_SHIP_VOLUMES_M3: dict[str, float] = {
    "Capsule": 500.0,
    "Shuttle": 500.0,
    "Corvette": 2500.0,
    "Frigate": 2500.0,
    "Assault Frigate": 2500.0,
    "Covert Ops": 2500.0,
    "Electronic Attack Ship": 2500.0,
    "Expedition Frigate": 2500.0,
    "Interceptor": 2500.0,
    "Logistics Frigate": 2500.0,
    "Prototype Exploration Ship": 2500.0,
    "Stealth Bomber": 2500.0,
    "Command Destroyer": 5000.0,
    "Destroyer": 5000.0,
    "Interdictor": 5000.0,
    "Tactical Destroyer": 5000.0,
    "Strategic Cruiser": 5000.0,
    "Combat Recon Ship": 10000.0,
    "Cruiser": 10000.0,
    "Flag Cruiser": 10000.0,
    "Force Recon Ship": 10000.0,
    "Heavy Assault Cruiser": 10000.0,
    "Heavy Interdiction Cruiser": 10000.0,
    "Logistics": 10000.0,
    "Attack Battlecruiser": 15000.0,
    "Combat Battlecruiser": 15000.0,
    "Command Ship": 15000.0,
    "Blockade Runner": 20000.0,
    "Deep Space Transport": 20000.0,
    "Hauler": 20000.0,
    "Exhumer": 3750.0,
    "Mining Barge": 3750.0,
    "Battleship": 50000.0,
    "Black Ops": 50000.0,
    "Expedition Command Ship": 50000.0,
    "Marauder": 50000.0,
    "Industrial Command Ship": 500000.0,
    "Capital Industrial Ship": 1300000.0,
    "Carrier": 1300000.0,
    "Dreadnought": 1300000.0,
    "Force Auxiliary": 1300000.0,
    "Freighter": 1300000.0,
    "Jump Freighter": 1300000.0,
    "Lancer Dreadnought": 1300000.0,
    "Supercarrier": 1300000.0,
    "Titan": 10000000.0,
}


def _get_jita_sell_price(jita_prices: dict, type_id) -> float:
    """Safely extract Jita sell price from a provider result map."""
    if pd.isna(type_id):
        return 0.0
    result: Optional[PriceResult] = jita_prices.get(int(type_id))
    return result.sell_price if result else 0.0


def _get_jita_buy_price(jita_prices: dict, type_id) -> float:
    """Safely extract Jita buy price from a provider result map."""
    if pd.isna(type_id):
        return 0.0
    result: Optional[PriceResult] = jita_prices.get(int(type_id))
    return result.buy_price if result else 0.0


def _apply_packaged_ship_volumes(
    volume_df: pd.DataFrame,
    logger_instance: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """Replace ship volumes with packaged volumes for shipping-cost calculations."""
    if volume_df.empty:
        return volume_df

    result = volume_df.copy()
    if "raw_volume_m3" not in result.columns:
        if logger_instance is not None:
            logger_instance.warning("raw_volume_m3 column missing; defaulting to 0.0")
        result["raw_volume_m3"] = 0.0
    else:
        result["raw_volume_m3"] = (
            pd.to_numeric(result["raw_volume_m3"], errors="coerce").fillna(0.0)
        )

    if "category_name" not in result.columns or "group_name" not in result.columns:
        if logger_instance is not None:
            logger_instance.warning(
                "category_name/group_name columns missing; skipping packaged volume logic"
            )
        result["volume_m3"] = result["raw_volume_m3"]
        return result

    ship_mask = result["category_name"].eq("Ship")
    if ship_mask.any():
        mapped_ship_volumes = result.loc[ship_mask, "group_name"].map(PACKAGED_SHIP_VOLUMES_M3)
        if logger_instance is not None:
            missing_groups = (
                result.loc[ship_mask & mapped_ship_volumes.isna(), "group_name"]
                .dropna()
                .unique()
                .tolist()
            )
            if missing_groups:
                logger_instance.warning(
                    "Using raw volume for ship groups without packaged overrides: %s",
                    ", ".join(sorted(missing_groups)),
                )
        result.loc[ship_mask, "raw_volume_m3"] = mapped_ship_volumes.fillna(
            result.loc[ship_mask, "raw_volume_m3"]
        )

    result["volume_m3"] = result["raw_volume_m3"]
    return result.drop(
        columns=["raw_volume_m3", "group_name", "category_name"],
        errors="ignore",
    )


@dataclass(frozen=True)
class ImportHelperFilters:
    """Filter configuration for Import Helper data."""

    category_ids: list[int] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    search_text: str = ""
    doctrine_only: bool = False
    tech2_only: bool = False
    faction_only: bool = False
    profitable_only: bool = True
    min_capital_utilis: Optional[float] = None
    min_turnover_30d: Optional[float] = None
    markup_margin: float = 0.2
    shipping_cost_per_m3: float = SHIPPING_COST_PER_M3


class ImportHelperService:
    """Business logic for Import Helper market analysis."""

    def __init__(
        self,
        mkt_db: DatabaseConfig,
        sde_repo: SDERepository,
        price_service: PriceService,
        logger_instance: Optional[logging.Logger] = None,
    ):
        self._mkt_db = mkt_db
        self._sde_repo = sde_repo
        self._price_service = price_service
        self._logger = logger_instance or logger

    @classmethod
    def create_default(
        cls,
        db_alias: Optional[str] = None,
        janice_api_key: Optional[str] = None,
    ) -> "ImportHelperService":
        """Create the default service for the active market."""
        if db_alias is None:
            try:
                from state.market_state import get_active_market

                db_alias = get_active_market().database_alias
            except ImportError:
                db_alias = "wcmkt"
            except Exception as e:
                logger.error(f"Failed to get active market, falling back to 'wcmkt': {e}")
                db_alias = "wcmkt"

        if janice_api_key is None:
            try:
                janice_api_key = st.secrets.janice.api_key
            except (KeyError, AttributeError):
                janice_api_key = None
            except Exception as e:
                logger.warning(f"Unexpected error reading Janice API key: {e}")
                janice_api_key = None

        market_db = DatabaseConfig(db_alias)
        sde_repo = get_sde_repository()
        price_service = get_price_service(
            db_alias=db_alias,
            janice_api_key=janice_api_key,
        )
        return cls(market_db, sde_repo, price_service)

    def _get_import_candidates(self) -> pd.DataFrame:
        """Fetch marketstats rows merged with SDE item volume.

        Raises:
            RuntimeError: If the market database query fails.
        """
        market_query = text(
            """
            SELECT
                ms.type_id,
                ms.type_name,
                ms.price,
                ms.avg_volume,
                ms.category_id,
                ms.category_name,
                ms.group_id,
                ms.group_name,
                CASE WHEN d.type_id IS NOT NULL THEN 1 ELSE 0 END AS is_doctrine
            FROM marketstats ms
            LEFT JOIN (
                SELECT DISTINCT type_id
                FROM doctrines
            ) d ON ms.type_id = d.type_id
            """
        )

        with self._mkt_db.engine.connect() as conn:
            market_df = pd.read_sql_query(market_query, conn)

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
                groupName AS group_name,
                categoryName AS category_name,
                COALESCE(volume, 0) AS raw_volume_m3
            FROM sdetypes
            WHERE typeID IN :type_ids
            """
        ).bindparams(bindparam("type_ids", expanding=True))

        try:
            with self._sde_repo.db.engine.connect() as conn:
                volume_df = pd.read_sql_query(sde_query, conn, params={"type_ids": type_ids})
        except Exception as e:
            self._logger.warning(f"Failed to fetch SDE volume data (shipping costs unavailable): {e}")
            volume_df = pd.DataFrame(columns=["type_id", "volume_m3"])

        if volume_df.empty:
            result = market_df.copy()
            result["volume_m3"] = 0.0
            return result

        volume_df = _apply_packaged_ship_volumes(volume_df, self._logger)
        return market_df.merge(volume_df, on="type_id", how="left").fillna({"volume_m3": 0.0})

    def get_category_options(self) -> pd.DataFrame:
        """Return category options for sidebar filtering."""
        try:
            query = (
                "SELECT DISTINCT category_id, category_name "
                "FROM marketstats "
                "WHERE category_id IS NOT NULL AND category_name IS NOT NULL "
                "ORDER BY category_name"
            )
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn)
            return df.reset_index(drop=True)
        except Exception as e:
            self._logger.error(f"Failed to get import-helper category options: {e}")
            return pd.DataFrame(columns=["category_id", "category_name"])

    def fetch_base_data(self) -> pd.DataFrame:
        """Fetch candidates from DB and Jita prices. Jita Price caching is handled inside PriceService.

        Returns a DataFrame with all computed columns (jita prices, shipping,
        profit, capital_utilis) but no filters applied.

        Raises:
            RuntimeError: If Jita price fetch fails.
        """
        df = self._get_import_candidates().copy()
        if df.empty:
            return df

        df["type_id"] = pd.to_numeric(df["type_id"], errors="coerce").astype("Int64")
        df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)
        df["avg_volume"] = pd.to_numeric(df.get("avg_volume"), errors="coerce").fillna(0.0)
        df["volume_m3"] = pd.to_numeric(df.get("volume_m3"), errors="coerce").fillna(0.0)

        type_ids = df["type_id"].dropna().astype(int).tolist()
        try:
            jita_prices = self._price_service.get_jita_price_data_map(type_ids)
        except Exception as e:
            self._logger.error(f"Jita price fetch failed: {e}")
            raise RuntimeError(f"Failed to fetch Jita prices: {e}") from e

        df["jita_sell_price"] = df["type_id"].map(
            lambda tid: _get_jita_sell_price(jita_prices, tid)
        )
        df["jita_buy_price"] = df["type_id"].map(
            lambda tid: _get_jita_buy_price(jita_prices, tid)
        )

        df["shipping_cost"] = df["volume_m3"] * SHIPPING_COST_PER_M3
        df["profit_jita_sell"] = df["price"] - (df["jita_sell_price"] + df["shipping_cost"])
        df["profit_jita_sell_30d"] = df["profit_jita_sell"] * 30 * df["avg_volume"]
        df["turnover_30d"] = df["avg_volume"] * 30 * df["jita_sell_price"]
        df["volume_30d"] = df["avg_volume"] * 30

        df["capital_utilis"] = 0.0
        nonzero_jita = df["jita_sell_price"] > 0
        df.loc[nonzero_jita, "capital_utilis"] = (
            df.loc[nonzero_jita, "profit_jita_sell"]
            / df.loc[nonzero_jita, "jita_sell_price"]
        )

        return df

    def get_import_items(
        self,
        base_df: Optional[pd.DataFrame] = None,
        filters: Optional[ImportHelperFilters] = None,
        language_code: str = "en",
    ) -> pd.DataFrame:
        """Apply localization and filters to import-helper data.

        Accepts either a pre-fetched base dataframe or, for backwards
        compatibility, an ImportHelperFilters instance as the first argument.
        """
        if isinstance(base_df, ImportHelperFilters):
            filters = base_df
            base_df = None

        filters = filters or ImportHelperFilters()
        if base_df is None:
            base_df = self.fetch_base_data()

        df = base_df.copy()
        if df.empty:
            return df

        df = apply_localized_type_names(df, self._sde_repo, language_code, self._logger)
        df["shipping_cost"] = df["volume_m3"] * filters.shipping_cost_per_m3
        df["profit_jita_sell"] = df["price"] - (df["jita_sell_price"] + df["shipping_cost"])
        df["profit_jita_sell_30d"] = df["profit_jita_sell"] * 30 * df["avg_volume"]
        df["capital_utilis"] = 0.0
        nonzero_jita = df["jita_sell_price"] > 0
        df.loc[nonzero_jita, "capital_utilis"] = (
            df.loc[nonzero_jita, "profit_jita_sell"]
            / df.loc[nonzero_jita, "jita_sell_price"]
        )
        df["rrp"] = df["jita_sell_price"] * (1 + filters.markup_margin) + df["shipping_cost"]

        df = df[df["avg_volume"] > 0]

        if filters.doctrine_only:
            df = df[df.get("is_doctrine", 0) == 1]

        if filters.tech2_only:
            tech2_type_ids = self._sde_repo.get_tech2_type_ids()
            df = df[df["type_id"].isin(tech2_type_ids)]

        if filters.faction_only:
            faction_type_ids = self._sde_repo.get_faction_type_ids()
            df = df[df["type_id"].isin(faction_type_ids)]

        if filters.category_ids:
            df = df[df["category_id"].isin(filters.category_ids)]
        elif filters.categories:
            df = df[df["category_name"].isin(filters.categories)]

        if filters.search_text:
            search = filters.search_text.strip().lower()
            search_series = df["type_name"].fillna("")
            if "type_name_en" in df.columns:
                search_series = search_series + " " + df["type_name_en"].fillna("")
            df = df[search_series.str.lower().str.contains(search, na=False)]

        if filters.profitable_only:
            df = df[df["profit_jita_sell"] > 0]

        # Treat the default 0.0 as "no filter" so disabling
        # profitable_only can still surface negative-profit items.
        if filters.min_capital_utilis not in (None, 0, 0.0):
            df = df[df["capital_utilis"] >= filters.min_capital_utilis]

        if filters.min_turnover_30d is not None:
            df = df[df["turnover_30d"] >= filters.min_turnover_30d]

        if df.empty:
            return df

        return df.sort_values(
            by=["capital_utilis", "profit_jita_sell", "turnover_30d"],
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
    try:
        from state import get_service
        from state.market_state import get_active_market_key
        return get_service(
            f"import_helper_service_{get_active_market_key()}",
            ImportHelperService.create_default,
        )
    except ImportError:
        return ImportHelperService.create_default()
