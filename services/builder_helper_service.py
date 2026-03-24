"""
Builder Helper Service

Fetches manufacture costs from the EverRef API for a fixed prototype list of
items and combines with local market and Jita pricing data.

No Streamlit imports — pure business logic.
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Optional

import httpx
import pandas as pd

from logging_config import setup_logging
from services.type_name_localization import get_localized_name_map

logger = setup_logging(__name__, log_file="builder_helper_service.log")

# =============================================================================
# Constants
# =============================================================================

# Prototype item list — fixed for this iteration
BUILDER_ITEM_IDS: list[int] = [
    2945, 32039, 31368, 31003, 4399, 11239, 482, 40571, 2038, 3162,
    2539, 1183, 28211, 28209, 4260, 26420, 3033, 11184, 47911, 22436,
    21888, 37298, 40351, 31165, 12565, 21640, 28213, 12005, 2195, 1541,
    41415, 3995, 4258, 26374, 60301, 22442, 47918, 12729, 12013, 2547,
    20125, 54786, 2436, 12743, 37296,
]

# EverRef API — fixed structure/rig config for prototype
EVEREF_BASE_URL = "https://api.everef.net/v1/industry/cost"
EVEREF_PARAMS = (
    "structure_type_id=35826"
    "&security=NULL_SEC"
    "&system_cost_bonus=-0.5&manufacturing_cost=0.04&facility_tax=0"
)

API_TIMEOUT = 20.0
MAX_CONCURRENCY = 6
USER_AGENT = (
    "WCMKTS-BuilderHelper/1.0 "
    "(https://github.com/OrthelT/wcmkts_new; orthel.toralen@gmail.com)"
)

# EverRef returns time in seconds; 3600 converts to hours
def _to_float(value) -> Optional[float]:
    """Safely convert an API value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# Matches ISO 8601 duration strings of the form PT[nH][nM][nS], e.g. PT24H20M48.1S
_DURATION_RE = re.compile(
    r"^PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?$"
)


def _parse_duration_to_seconds(value) -> Optional[float]:
    """Parse an ISO 8601 duration string (e.g. PT24H20M48.1S) to total seconds.

    Returns None if the value is absent or unparseable.
    """
    if not value:
        return None
    # Fast path: plain numeric string or number
    try:
        return float(value)
    except (TypeError, ValueError):
        pass
    m = _DURATION_RE.match(str(value).strip())
    if not m:
        logger.warning("Cannot parse duration: %r", value)
        return None
    hours = float(m.group(1) or 0)
    minutes = float(m.group(2) or 0)
    seconds = float(m.group(3) or 0)
    return hours * 3600.0 + minutes * 60.0 + seconds


# =============================================================================
# Domain Model
# =============================================================================

@dataclass
class BuildCostResult:
    """Build cost data for a single manufactured item."""

    type_id: int
    total_cost_per_unit: Optional[float] = None
    time_per_unit: Optional[float] = None
    error: Optional[str] = None


# =============================================================================
# Service
# =============================================================================

class BuilderHelperService:
    """Aggregates manufacture cost, local market price, and Jita price data.

    Args:
        market_repo: MarketRepository for local prices and SDE info.
        price_service: PriceService for Jita price lookups.
        sde_repo: SDERepository for type name localization.
    """

    def __init__(self, market_repo, price_service, sde_repo=None):
        self._market_repo = market_repo
        self._price_service = price_service
        self._sde_repo = sde_repo

    def get_builder_data(self, language_code: str = "en") -> pd.DataFrame:
        """Fetch and combine all builder helper data into a single DataFrame.

        Args:
            language_code: Language code for localizing item names (default "en").

        Returns:
            DataFrame with columns:
                type_id, item_name, category, group,
                market_sell_price, jita_sell_price, build_cost, cap_utils,
                profit_30d, turnover_30d, volume_30d
        """
        type_ids = BUILDER_ITEM_IDS

        # 1. Fetch manufacture costs from EverRef API
        build_costs: dict[int, BuildCostResult] = asyncio.run(
            self._fetch_all_build_costs(type_ids)
        )

        # 2. SDE info (name, group, category) — from market_repo which joins SDE
        sde_df = self._market_repo.get_sde_info(type_ids)

        # 3. Local market sell price — use `price` column from marketstats
        stats_df = self._market_repo.get_all_stats()
        local_prices: dict[int, float] = {}
        if not stats_df.empty and "type_id" in stats_df.columns and "price" in stats_df.columns:
            subset = stats_df[stats_df["type_id"].isin(type_ids)][["type_id", "price"]]
            local_prices = {
                int(tid): _to_float(price)
                for tid, price in zip(subset["type_id"], subset["price"])
                if _to_float(price) is not None
            }

        # 4. Jita sell prices
        jita_map = self._price_service.get_jita_price_data_map(type_ids)

        # 5. 30-day volume metrics
        volume_metrics = self._market_repo.get_30day_volume_metrics(type_ids)
        volume_index: dict[int, float] = {}
        if not volume_metrics.empty and "type_id" in volume_metrics.columns:
            for _, row in volume_metrics.iterrows():
                v = _to_float(row.get("volume_30d"))
                if v is not None:
                    volume_index[int(row["type_id"])] = v

        # 6. Build result rows
        sde_index: dict[int, dict] = {}
        if not sde_df.empty:
            for _, row in sde_df.iterrows():
                sde_index[int(row["type_id"])] = row.to_dict()

        rows = []
        for type_id in type_ids:
            sde = sde_index.get(type_id, {})
            item_name = sde.get("type_name") or f"Unknown ({type_id})"
            category = sde.get("category_name") or "—"
            group = sde.get("group_name") or "—"

            jita_result = jita_map.get(type_id)
            jita_sell_price: Optional[float] = (
                jita_result.sell_price if jita_result and jita_result.has_sell_price else None
            )

            market_sell_price: Optional[float] = local_prices.get(type_id)
            if market_sell_price is None and jita_sell_price is not None:
                market_sell_price = jita_sell_price * 1.4

            bc = build_costs.get(type_id)
            build_cost: Optional[float] = bc.total_cost_per_unit if bc else None

            volume_30d: Optional[float] = volume_index.get(type_id)

            cap_utils: Optional[float] = None
            if market_sell_price is not None and build_cost is not None and market_sell_price != 0:
                cap_utils = (market_sell_price - build_cost) / market_sell_price

            profit_30d: Optional[float] = None
            if market_sell_price is not None and build_cost is not None and volume_30d is not None:
                profit_30d = (market_sell_price - build_cost) * volume_30d

            turnover_30d: Optional[float] = None
            if jita_sell_price is not None and volume_30d is not None:
                turnover_30d = jita_sell_price * volume_30d

            rows.append(
                {
                    "type_id": type_id,
                    "item_name": item_name,
                    "category": category,
                    "group": group,
                    "market_sell_price": market_sell_price,
                    "jita_sell_price": jita_sell_price,
                    "build_cost": build_cost,
                    "cap_utils": cap_utils,
                    "profit_30d": profit_30d,
                    "turnover_30d": turnover_30d,
                    "volume_30d": volume_30d,
                }
            )

        df = pd.DataFrame(rows)

        # Apply item name localization if SDE repo is available and not English
        if self._sde_repo is not None and language_code != "en" and not df.empty:
            type_ids = pd.to_numeric(df["type_id"], errors="coerce").dropna().astype(int).unique().tolist()
            localized_names = get_localized_name_map(type_ids, self._sde_repo, language_code, logger)
            if localized_names:
                df["item_name"] = df["type_id"].map(
                    lambda value: localized_names.get(int(value))
                    if pd.notna(value) and int(value) in localized_names
                    else None
                ).fillna(df["item_name"])

        return df

    # ------------------------------------------------------------------
    # Async EverRef fetching
    # ------------------------------------------------------------------

    async def _fetch_all_build_costs(
        self, type_ids: list[int]
    ) -> dict[int, BuildCostResult]:
        """Fetch build costs for all items concurrently."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        limits = httpx.Limits(
            max_connections=MAX_CONCURRENCY,
            max_keepalive_connections=MAX_CONCURRENCY,
        )
        headers = {"User-Agent": USER_AGENT}
        results: dict[int, BuildCostResult] = {}

        async with httpx.AsyncClient(http2=True, limits=limits, headers=headers) as client:
            tasks = [self._fetch_one(client, semaphore, tid) for tid in type_ids]
            for coro in asyncio.as_completed(tasks):
                item = await coro
                results[item.type_id] = item

        successes = sum(1 for r in results.values() if r.error is None)
        errors = len(results) - successes
        logger.info(
            "EverRef fetch complete: %d succeeded, %d failed out of %d items",
            successes,
            errors,
            len(type_ids),
        )
        return results

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        type_id: int,
    ) -> BuildCostResult:
        """Fetch build cost for a single item from EverRef."""
        async with semaphore:
            url = f"{EVEREF_BASE_URL}?product_id={type_id}&{EVEREF_PARAMS}"
            try:
                r = await client.get(url, timeout=API_TIMEOUT)

                # 400 means this item is not manufacturable (e.g. dropped/non-craftable)
                if r.status_code == 400:
                    logger.warning(
                        "type_id=%d is not manufacturable (400 from EverRef)", type_id
                    )
                    return BuildCostResult(type_id=type_id, error="not_manufacturable")

                r.raise_for_status()
                data = r.json()
                try:
                    item_data = data["manufacturing"][str(type_id)]
                except KeyError:
                    logger.warning("No manufacturing data for type_id=%d", type_id)
                    return BuildCostResult(type_id=type_id, error="no_manufacturing_data")

                return BuildCostResult(
                    type_id=type_id,
                    total_cost_per_unit=_to_float(item_data.get("total_cost_per_unit")),
                    time_per_unit=_parse_duration_to_seconds(item_data.get("time_per_unit")),
                )
            except httpx.HTTPStatusError as exc:
                logger.error(
                    "HTTP error fetching build cost for type_id=%d: %s", type_id, exc
                )
                return BuildCostResult(type_id=type_id, error=str(exc))
            except Exception as exc:
                logger.error("Error fetching build cost for type_id=%d: %s", type_id, exc)
                return BuildCostResult(type_id=type_id, error=str(exc))


# =============================================================================
# Factory Function
# =============================================================================

def get_builder_helper_service() -> BuilderHelperService:
    """Get or create a BuilderHelperService instance.

    Uses state.get_service for session persistence when running inside
    Streamlit. Falls back to direct instantiation for tests.
    """

    def _create() -> BuilderHelperService:
        from repositories.market_repo import get_market_repository
        from repositories.sde_repo import get_sde_repository
        from services.price_service import get_price_service

        return BuilderHelperService(
            market_repo=get_market_repository(),
            price_service=get_price_service(),
            sde_repo=get_sde_repository(),
        )

    try:
        from state import get_service

        return get_service("builder_helper_service", _create)
    except ImportError:
        return _create()
