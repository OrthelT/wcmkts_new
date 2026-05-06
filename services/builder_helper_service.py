"""Builder Helper Service.

Combines stored builder-cost catalog data with local market and Jita pricing.

No Streamlit imports - pure business logic.
"""

from typing import Optional

import pandas as pd

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
    "isk_per_hour",
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


_METADATA_FIELDS = ("type_name", "group_name", "category_name")


def _build_metadata_index(
    watchlist_df: pd.DataFrame,
    stats_df: pd.DataFrame,
) -> dict[int, dict[str, str]]:
    """Build {type_id: {type_name, group_name, category_name}} preferring watchlist over marketstats."""
    index: dict[int, dict[str, str]] = {}

    # Stats first (lower priority).
    for source in (stats_df, watchlist_df):
        if source is None or source.empty or "type_id" not in source.columns:
            continue
        for _, row in source.iterrows():
            type_id = _to_int(row.get("type_id"))
            if type_id is None:
                continue
            entry = index.setdefault(type_id, {})
            for field in _METADATA_FIELDS:
                value = row.get(field) if field in source.columns else None
                if value is not None and not pd.isna(value) and str(value):
                    entry[field] = str(value)
    return index


# =============================================================================
# Service
# =============================================================================

class BuilderHelperService:
    """Aggregates stored build cost, market price, and Jita price data."""

    def __init__(self, market_repo, price_service, build_cost_repo, sde_repo=None):
        self._market_repo = market_repo
        self._price_service = price_service
        self._build_cost_repo = build_cost_repo
        self._sde_repo = sde_repo

    def get_builder_data(
        self,
        language_code: str = "en",
        price_basis: str = "avg",
    ) -> pd.DataFrame:
        """Fetch and combine all builder helper data into a single DataFrame.

        Catalog rows come from buildcost.db.builder_costs (the backend's
        synced source of truth). Type-name/group/category metadata is
        enriched in pandas by joining against wcmkt watchlist (preferred)
        with marketstats as a fallback.

        price_basis selects which local-market price feeds the profitability
        columns (cap_utils, isk_per_hour, profit_30d):
          - "avg":     marketstats.avg_price (30-day mean) — default
          - "current": marketstats.price (current best sell)
        """
        if price_basis not in ("avg", "current"):
            logger.warning("Unknown price_basis %r, falling back to 'avg'", price_basis)
            price_basis = "avg"

        builder_df = self._build_cost_repo.get_builder_cost_catalog()
        if builder_df.empty or "type_id" not in builder_df.columns:
            logger.warning("No builder costs available in the local catalog")
            return _empty_builder_frame()

        type_ids = [
            type_id
            for type_id in (_to_int(value) for value in builder_df["type_id"].tolist())
            if type_id is not None
        ]
        if not type_ids:
            logger.warning("Builder helper catalog rows are missing type IDs")
            return _empty_builder_frame()

        jita_prices_map = self._fetch_jita_prices(type_ids)
        stats_df = self._market_repo.get_all_stats()
        price_column = "avg_price" if price_basis == "avg" else "price"
        local_prices = _build_numeric_map(stats_df, "type_id", price_column)
        volume_index = _build_numeric_map(
            self._market_repo.get_30day_volume_metrics(type_ids),
            "type_id",
            "volume_30d",
        )
        metadata_index = _build_metadata_index(
            self._market_repo.get_watchlist(),
            stats_df,
        )

        rows = []
        for _, row in builder_df.iterrows():
            type_id = _to_int(row.get("type_id"))
            if type_id is None:
                continue

            jita_sell_price = jita_prices_map.get(type_id)
            market_sell_price = local_prices.get(type_id)
            build_cost = _to_float(row.get("total_cost_per_unit"))
            time_per_unit = _to_float(row.get("time_per_unit"))
            volume_30d = volume_index.get(type_id)

            cap_utils = None
            if (
                market_sell_price is not None
                and build_cost is not None
                and build_cost != 0
            ):
                cap_utils = (market_sell_price - build_cost) / build_cost

            isk_per_hour = None
            if (
                market_sell_price is not None
                and build_cost is not None
                and time_per_unit is not None
                and time_per_unit > 0
            ):
                isk_per_hour = (market_sell_price - build_cost) / time_per_unit * 3600

            profit_30d = None
            if market_sell_price is not None and build_cost is not None and volume_30d is not None:
                profit_30d = (market_sell_price - build_cost) * volume_30d

            turnover_30d = None
            if jita_sell_price is not None and volume_30d is not None:
                turnover_30d = jita_sell_price * volume_30d

            metadata = metadata_index.get(type_id, {})
            rows.append(
                {
                    "type_id": type_id,
                    "item_name": metadata.get("type_name") or f"Unknown ({type_id})",
                    "category": metadata.get("category_name") or "—",
                    "group": metadata.get("group_name") or "—",
                    "market_sell_price": market_sell_price,
                    "jita_sell_price": jita_sell_price,
                    "build_cost": build_cost,
                    "cap_utils": cap_utils,
                    "isk_per_hour": isk_per_hour,
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
        """Resolve Jita sell prices via the shared PriceService.

        Delegates to PriceService so this page uses the same provider chain
        (local jita_prices cache → Fuzzwork → Janice) and shared in-memory
        cache as the rest of the app. Items without a positive sell price
        are omitted from the returned map.
        """
        if not type_ids:
            return {}

        price_map = self._price_service.get_jita_price_data_map(type_ids)
        return {
            tid: result.sell_price
            for tid, result in price_map.items()
            if result.has_sell_price
        }


# =============================================================================
# Factory Function
# =============================================================================

def get_builder_helper_service() -> BuilderHelperService:
    """Get or create a BuilderHelperService instance."""

    def _create() -> BuilderHelperService:
        from repositories.build_cost_repo import get_build_cost_repository
        from repositories.market_repo import get_market_repository
        from repositories.sde_repo import get_sde_repository
        from services.price_service import get_price_service

        return BuilderHelperService(
            market_repo=get_market_repository(),
            price_service=get_price_service(),
            build_cost_repo=get_build_cost_repository(),
            sde_repo=get_sde_repository(),
        )

    try:
        from state import get_service
        from state.market_state import get_active_market_key

        return get_service(f"builder_helper_service_{get_active_market_key()}", _create)
    except ImportError:
        return _create()
