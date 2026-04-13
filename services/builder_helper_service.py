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
from sqlalchemy import bindparam, text

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

# EverRef API
EVEREF_BASE_URL = "https://api.everef.net/v1/industry/cost"
EVEREF_STATIC_PARAMS = (
    "structure_type_id=35826"
    "&security=NULL_SEC"
    "&system_cost_bonus=0&manufacturing_cost=0&facility_tax=0"
)

API_TIMEOUT = 20.0
MAX_CONCURRENCY = 6
USER_AGENT = (
    "WCMKTS-BuilderHelper/1.0 "
    "(https://github.com/OrthelT/wcmkts_new; orthel.toralen@gmail.com)"
)

# --- API param resolution rules ---
TECH_I_META_GROUP_ID = 1
TECH_II_META_GROUP_ID = 2
TECH_III_META_GROUP_ID = 14
MANUFACTURABLE_META_GROUPS = frozenset({
    TECH_I_META_GROUP_ID, TECH_II_META_GROUP_ID, TECH_III_META_GROUP_ID
})

EXCLUDED_GROUPS = frozenset({
    "Interdiction Nullifier",
    "Exotic Plasma Charge",
    "Condenser Pack",
})
EXCLUDED_NAMES = frozenset({
    "Vedmak", "Leshak", "Damavik", "Zirnitra",
})

MODULE_CATEGORY_ID = 7
DRONE_CATEGORY_ID = 18
CHARGE_CATEGORY_ID = 8
SHIP_CATEGORY_ID = 6
FIGHTER_CATEGORY_ID = 87
DEPLOYABLE_CATEGORY_ID = 22
SUBSYSTEM_CATEGORY_ID = 32
HIGH_VALUE_THRESHOLD = 40_000_000

ALLOWED_CATEGORIES = frozenset({
    MODULE_CATEGORY_ID,
    DRONE_CATEGORY_ID,
    CHARGE_CATEGORY_ID,
    SHIP_CATEGORY_ID,
    FIGHTER_CATEGORY_ID,
    DEPLOYABLE_CATEGORY_ID,
    SUBSYSTEM_CATEGORY_ID,
})


# =============================================================================
# Helpers
# =============================================================================

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


def _resolve_api_params(
    sde_info: dict, jita_price: Optional[float]
) -> Optional[tuple[int, int]]:
    """Determine (me, runs) for the EverRef API call for a single item.

    Returns None if the item should be skipped entirely (not manufacturable
    under the current rules, or explicitly excluded).
    """
    meta_group_id = sde_info.get("meta_group_id")
    group_name = sde_info.get("group_name") or ""
    category_id = sde_info.get("category_id")
    type_name = sde_info.get("type_name") or ""

    # Skip items not in a manufacturable tech tier
    if meta_group_id not in MANUFACTURABLE_META_GROUPS:
        return None

    # Skip items outside the allowed categories
    if category_id not in ALLOWED_CATEGORIES:
        return None

    # Skip explicitly excluded groups/names (regardless of tier)
    if group_name in EXCLUDED_GROUPS or type_name in EXCLUDED_NAMES:
        return None

    if meta_group_id == TECH_I_META_GROUP_ID:
        return (10, 10)

    if meta_group_id == TECH_II_META_GROUP_ID:
        if category_id in (MODULE_CATEGORY_ID, DRONE_CATEGORY_ID, CHARGE_CATEGORY_ID):
            if jita_price is not None and jita_price > HIGH_VALUE_THRESHOLD:
                return (4, 5)
            return (0, 10)
        if category_id == SHIP_CATEGORY_ID:
            return (3, 3)

    # T3 or unmatched T2 categories
    return (0, 1)


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
        market_repo: MarketRepository for local prices, SDE info, and Jita prices.
        sde_repo: SDERepository for type name localization.
    """

    def __init__(self, market_repo, sde_repo=None):
        self._market_repo = market_repo
        self._sde_repo = sde_repo

    def get_builder_data(self, language_code: str = "en") -> pd.DataFrame:
        """Fetch and combine all builder helper data into a single DataFrame.

        Only items that are manufacturable under the current rules are included.
        Skipped items (wrong meta group, excluded name/group) do not appear.

        Args:
            language_code: Language code for localizing item names (default "en").

        Returns:
            DataFrame with columns:
                type_id, item_name, category, group,
                market_sell_price, jita_sell_price, build_cost, cap_utils,
                profit_30d, turnover_30d, volume_30d
        """
        all_type_ids = BUILDER_ITEM_IDS

        # 1. SDE info (name, group, category, meta group)
        sde_df = self._market_repo.get_sde_info(all_type_ids)
        sde_index: dict[int, dict] = {}
        if not sde_df.empty:
            for _, row in sde_df.iterrows():
                sde_index[int(row["type_id"])] = row.to_dict()

        # 2. Jita sell prices from local jita_prices table
        jita_prices_map = self._fetch_jita_prices(all_type_ids)

        # 3. Resolve per-item API params; collect only manufacturable items
        params_map: dict[int, tuple[int, int]] = {}
        for type_id in all_type_ids:
            sde = sde_index.get(type_id, {})
            params = _resolve_api_params(sde, jita_prices_map.get(type_id))
            if params is not None:
                params_map[type_id] = params

        manufacturable_ids = list(params_map.keys())
        if not manufacturable_ids:
            logger.warning("No manufacturable items found for builder helper")
            return pd.DataFrame()

        logger.info(
            "Builder helper: %d/%d items are manufacturable",
            len(manufacturable_ids),
            len(all_type_ids),
        )

        # 4. Fetch manufacture costs from EverRef API (only for manufacturable items)
        build_costs: dict[int, BuildCostResult] = asyncio.run(
            self._fetch_all_build_costs(params_map)
        )

        # 5. Local market sell price
        stats_df = self._market_repo.get_all_stats()
        local_prices: dict[int, float] = {}
        if not stats_df.empty and "type_id" in stats_df.columns and "price" in stats_df.columns:
            subset = stats_df[stats_df["type_id"].isin(manufacturable_ids)][["type_id", "price"]]
            local_prices = {
                int(tid): _to_float(price)
                for tid, price in zip(subset["type_id"], subset["price"])
                if _to_float(price) is not None
            }

        # 6. 30-day volume metrics
        volume_metrics = self._market_repo.get_30day_volume_metrics(manufacturable_ids)
        volume_index: dict[int, float] = {}
        if not volume_metrics.empty and "type_id" in volume_metrics.columns:
            for _, row in volume_metrics.iterrows():
                v = _to_float(row.get("volume_30d"))
                if v is not None:
                    volume_index[int(row["type_id"])] = v

        # 7. Build result rows (only for manufacturable items)
        rows = []
        for type_id in manufacturable_ids:
            sde = sde_index.get(type_id, {})
            item_name = sde.get("type_name") or f"Unknown ({type_id})"
            category = sde.get("category_name") or "—"
            group = sde.get("group_name") or "—"

            jita_sell_price: Optional[float] = jita_prices_map.get(type_id)

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
            loc_ids = pd.to_numeric(df["type_id"], errors="coerce").dropna().astype(int).unique().tolist()
            localized_names = get_localized_name_map(loc_ids, self._sde_repo, language_code, logger)
            if localized_names:
                df["item_name"] = df["type_id"].map(
                    lambda value: localized_names.get(int(value))
                    if pd.notna(value) and int(value) in localized_names
                    else None
                ).fillna(df["item_name"])

        return df

    # ------------------------------------------------------------------
    # Jita price lookup (local DB)
    # ------------------------------------------------------------------

    def _fetch_jita_prices(self, type_ids: list[int]) -> dict[int, float]:
        """Read Jita sell prices from the local jita_prices table.

        Returns an empty dict if the table is unavailable (e.g. local dev
        environment where the DB hasn't been synced from Turso yet).
        """
        if not type_ids:
            return {}
        query = text(
            "SELECT type_id, sell_price FROM jita_prices WHERE type_id IN :type_ids"
        ).bindparams(bindparam("type_ids", expanding=True))
        try:
            with self._market_repo.db.engine.connect() as conn:
                df = pd.read_sql_query(
                    query, conn, params={"type_ids": [int(t) for t in type_ids]}
                )
        except Exception as exc:
            logger.warning("jita_prices unavailable: %s", exc)
            return {}
        if df.empty:
            return {}
        return {
            int(row["type_id"]): float(row["sell_price"])
            for _, row in df.iterrows()
            if row["sell_price"] is not None
        }

    # ------------------------------------------------------------------
    # Async EverRef fetching
    # ------------------------------------------------------------------

    async def _fetch_all_build_costs(
        self, params_map: dict[int, tuple[int, int]]
    ) -> dict[int, BuildCostResult]:
        """Fetch build costs for all items concurrently using per-item me/runs."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        limits = httpx.Limits(
            max_connections=MAX_CONCURRENCY,
            max_keepalive_connections=MAX_CONCURRENCY,
        )
        headers = {"User-Agent": USER_AGENT}
        results: dict[int, BuildCostResult] = {}

        async with httpx.AsyncClient(http2=True, limits=limits, headers=headers) as client:
            tasks = [
                self._fetch_one(client, semaphore, tid, me, runs)
                for tid, (me, runs) in params_map.items()
            ]
            for coro in asyncio.as_completed(tasks):
                item = await coro
                results[item.type_id] = item

        successes = sum(1 for r in results.values() if r.error is None)
        errors = len(results) - successes
        logger.info(
            "EverRef fetch complete: %d succeeded, %d failed out of %d items",
            successes,
            errors,
            len(params_map),
        )
        return results

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        type_id: int,
        me: int,
        runs: int,
    ) -> BuildCostResult:
        """Fetch build cost for a single item from EverRef."""
        async with semaphore:
            url = (
                f"{EVEREF_BASE_URL}?product_id={type_id}"
                f"&{EVEREF_STATIC_PARAMS}&me={me}&runs={runs}"
            )
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

        return BuilderHelperService(
            market_repo=get_market_repository(),
            sde_repo=get_sde_repository(),
        )

    try:
        from state import get_service

        return get_service("builder_helper_service", _create)
    except ImportError:
        return _create()
