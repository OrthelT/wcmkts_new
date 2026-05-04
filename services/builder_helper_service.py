"""Builder Helper Service.

Combines stored builder-cost catalog data with local market and Jita pricing.

No Streamlit imports - pure business logic.
"""

from typing import Optional

import pandas as pd
from sqlalchemy import bindparam, text

from logging_config import setup_logging
from services.type_name_localization import get_localized_name_map

logger = setup_logging(__name__, log_file="builder_helper_service.log")


# =============================================================================
# Constants
# =============================================================================

BUILDER_HELPER_COLUMNS = [
    "type_id",
    "item_name",
    "category",
    "group",
    "market_sell_price",
    "jita_sell_price",
    "build_cost",
    "cap_utils",
    "profit_30d",
    "turnover_30d",
    "volume_30d",
]


# =============================================================================
# Helpers
# =============================================================================

def _to_float(value) -> Optional[float]:
    """Safely convert a value to float, returning None on failure."""
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> Optional[int]:
    """Safely convert a value to int, returning None on failure."""
    if value is None or pd.isna(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_str(value, default: str) -> str:
    """Safely convert a value to a non-empty string, falling back to default."""
    if value is None or pd.isna(value):
        return default
    text_value = str(value)
    return text_value if text_value else default


def _empty_builder_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=BUILDER_HELPER_COLUMNS)


def _build_numeric_map(
    df: pd.DataFrame,
    key_column: str,
    value_column: str,
) -> dict[int, float]:
    """Convert a two-column DataFrame into an int-to-float mapping."""
    if df.empty or key_column not in df.columns or value_column not in df.columns:
        return {}

    result: dict[int, float] = {}
    for _, row in df[[key_column, value_column]].iterrows():
        key = _to_int(row.get(key_column))
        value = _to_float(row.get(value_column))
        if key is not None and value is not None:
            result[key] = value
    return result


# =============================================================================
# Service
# =============================================================================

class BuilderHelperService:
    """Aggregates stored build cost, market price, and Jita price data."""

    def __init__(self, market_repo, sde_repo=None):
        self._market_repo = market_repo
        self._sde_repo = sde_repo

    def get_builder_data(self, language_code: str = "en") -> pd.DataFrame:
        """Fetch and combine all builder helper data into a single DataFrame."""
        builder_df = self._market_repo.get_builder_cost_catalog()
        if builder_df.empty or "type_id" not in builder_df.columns:
            logger.warning("No builder costs available in the local catalog")
            return _empty_builder_frame()

        builder_df = builder_df.drop_duplicates(subset=["type_id"], keep="first")
        type_ids = [
            type_id
            for type_id in (_to_int(value) for value in builder_df["type_id"].tolist())
            if type_id is not None
        ]
        if not type_ids:
            logger.warning("Builder helper catalog rows are missing type IDs")
            return _empty_builder_frame()

        jita_prices_map = self._fetch_jita_prices(type_ids)
        local_prices = _build_numeric_map(
            self._market_repo.get_all_stats(),
            "type_id",
            "price",
        )
        volume_index = _build_numeric_map(
            self._market_repo.get_30day_volume_metrics(type_ids),
            "type_id",
            "volume_30d",
        )

        rows = []
        for _, row in builder_df.iterrows():
            type_id = _to_int(row.get("type_id"))
            if type_id is None:
                continue

            jita_sell_price = jita_prices_map.get(type_id)
            market_sell_price = local_prices.get(type_id)
            if market_sell_price is None and jita_sell_price is not None:
                market_sell_price = jita_sell_price * 1.4

            build_cost = _to_float(row.get("total_cost_per_unit"))
            volume_30d = volume_index.get(type_id)

            cap_utils = None
            if (
                market_sell_price is not None
                and build_cost is not None
                and market_sell_price != 0
            ):
                cap_utils = (market_sell_price - build_cost) / market_sell_price

            profit_30d = None
            if market_sell_price is not None and build_cost is not None and volume_30d is not None:
                profit_30d = (market_sell_price - build_cost) * volume_30d

            turnover_30d = None
            if jita_sell_price is not None and volume_30d is not None:
                turnover_30d = jita_sell_price * volume_30d

            rows.append(
                {
                    "type_id": type_id,
                    "item_name": _to_str(row.get("type_name"), f"Unknown ({type_id})"),
                    "category": _to_str(row.get("category_name"), "—"),
                    "group": _to_str(row.get("group_name"), "—"),
                    "market_sell_price": market_sell_price,
                    "jita_sell_price": jita_sell_price,
                    "build_cost": build_cost,
                    "cap_utils": cap_utils,
                    "profit_30d": profit_30d,
                    "turnover_30d": turnover_30d,
                    "volume_30d": volume_30d,
                }
            )

        df = pd.DataFrame(rows, columns=BUILDER_HELPER_COLUMNS)

        if self._sde_repo is not None and language_code != "en" and not df.empty:
            loc_ids = df["type_id"].dropna().astype(int).tolist()
            localized_names = get_localized_name_map(
                loc_ids,
                self._sde_repo,
                language_code,
                logger,
            )
            if localized_names:
                df["item_name"] = df["type_id"].map(
                    lambda value: localized_names.get(int(value))
                    if pd.notna(value) and int(value) in localized_names
                    else None
                ).fillna(df["item_name"])

        return df

    def _fetch_jita_prices(self, type_ids: list[int]) -> dict[int, float]:
        """Read Jita sell prices from the local jita_prices table."""
        if not type_ids:
            return {}

        db = getattr(self._market_repo, "db", None)
        engine = getattr(db, "engine", None)
        if engine is None:
            logger.warning("jita_prices unavailable: market repository has no database engine")
            return {}

        query = text(
            "SELECT type_id, sell_price FROM jita_prices WHERE type_id IN :type_ids"
        ).bindparams(bindparam("type_ids", expanding=True))

        try:
            with engine.connect() as conn:
                df = pd.read_sql_query(
                    query,
                    conn,
                    params={"type_ids": [int(t) for t in type_ids]},
                )
        except Exception as exc:
            logger.warning("jita_prices unavailable: %s", exc)
            return {}

        if df.empty or "type_id" not in df.columns or "sell_price" not in df.columns:
            return {}

        result: dict[int, float] = {}
        for _, row in df.iterrows():
            type_id = _to_int(row.get("type_id"))
            sell_price = _to_float(row.get("sell_price"))
            if type_id is not None and sell_price is not None:
                result[type_id] = sell_price
        return result


# =============================================================================
# Factory Function
# =============================================================================

def get_builder_helper_service() -> BuilderHelperService:
    """Get or create a BuilderHelperService instance."""

    def _create() -> BuilderHelperService:
        from repositories.market_repo import get_market_repository
        from repositories.sde_repo import get_sde_repository

        return BuilderHelperService(
            market_repo=get_market_repository(),
            sde_repo=get_sde_repository(),
        )

    try:
        from state import get_service

        return get_service("builder_helper_service", _create)
    except ImportError:
        return _create()
