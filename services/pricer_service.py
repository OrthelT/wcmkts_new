"""
Pricer Service

Main orchestration service for the Pricer feature.
Handles parsing, SDE resolution, and price lookups from multiple sources.

Data Flow:
1. Parse user input (EFT or multibuy) -> RawParsedItem list
2. Resolve items in SDE -> ParsedItem list with type_ids
3. Fetch Jita prices (buy + sell) from Fuzzwork/Janice
4. Fetch local 4-HWWF prices from marketorders
5. Combine into PricedItem list and PricerResult
"""

from dataclasses import dataclass
from typing import Optional
import logging
import requests
import pandas as pd
from sqlalchemy import text

from config import DatabaseConfig
from domain.pricer import (
    InputFormat,
    SlotType,
    ParsedItem,
    PricedItem,
    PricerResult,
    LocalPriceData,
)
from services.parser_utils import (
    parse_input,
    RawParsedItem,
)
from repositories.market_orders_repo import MarketOrdersRepository, get_market_orders_repository
from logging_config import setup_logging
import streamlit as st
from ui.formatters import get_image_url

logger = setup_logging(__name__, log_file="pricer_service.log")


# =============================================================================
# Jita Price Data
# =============================================================================

@dataclass
class JitaPriceData:
    """
    Jita price data for an item (both buy and sell).
    """
    type_id: int
    sell_price: float = 0.0
    buy_price: float = 0.0

    @property
    def spread(self) -> float:
        """Price spread (sell - buy)."""
        return self.sell_price - self.buy_price

    @property
    def spread_percentage(self) -> Optional[float]:
        """Spread as percentage of sell price."""
        if self.sell_price > 0:
            return (self.spread / self.sell_price) * 100
        return None


# =============================================================================
# Jita Price Provider (handles both buy and sell)
# =============================================================================

class JitaPriceProvider:
    """
    Fetches both buy and sell prices from Jita via Fuzzwork API.

    Falls back to Janice API if Fuzzwork fails.
    """

    FUZZWORK_URL = "https://market.fuzzwork.co.uk/aggregates/"
    REGION_JITA = 10000002
    TIMEOUT = 30

    JANICE_URL = "https://janice.e-351.com/api/rest/v2/pricer"
    JANICE_MARKET = 2

    def __init__(self, janice_api_key: Optional[str] = None, logger_instance: Optional[logging.Logger] = None):
        self._janice_key = janice_api_key
        self._logger = logger_instance or logger

    def get_prices(self, type_ids: list[int]) -> dict[int, JitaPriceData]:
        """
        Get Jita buy and sell prices for multiple type IDs.

        Tries Fuzzwork first, falls back to Janice if available.

        Args:
            type_ids: List of EVE type IDs

        Returns:
            Dictionary mapping type_id to JitaPriceData
        """
        if not type_ids:
            return {}

        # Try Fuzzwork first
        result = self._fetch_fuzzwork(type_ids)

        # Check for missing items
        missing = [tid for tid in type_ids if tid not in result or result[tid].sell_price == 0]

        # Fallback to Janice for missing items
        if missing and self._janice_key:
            self._logger.debug(f"Falling back to Janice for {len(missing)} items")
            janice_result = self._fetch_janice(missing)
            result.update(janice_result)

        # Ensure all requested IDs have an entry
        for tid in type_ids:
            if tid not in result:
                result[tid] = JitaPriceData(type_id=tid)

        return result

    def _fetch_fuzzwork(self, type_ids: list[int]) -> dict[int, JitaPriceData]:
        """Fetch prices from Fuzzwork API."""
        try:
            type_ids_str = ','.join(map(str, type_ids))
            url = f"{self.FUZZWORK_URL}?region={self.REGION_JITA}&types={type_ids_str}"

            response = requests.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()

            data = response.json()
            return self._parse_fuzzwork_response(data, type_ids)

        except requests.exceptions.Timeout:
            self._logger.error("Fuzzwork API timeout")
            return {}
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Fuzzwork API error: {e}")
            return {}

    def _parse_fuzzwork_response(self, data: dict, type_ids: list[int]) -> dict[int, JitaPriceData]:
        """Parse Fuzzwork JSON response."""
        result = {}

        for type_id in type_ids:
            type_id_str = str(type_id)

            if type_id_str not in data:
                continue

            item_data = data[type_id_str]
            sell_data = item_data.get('sell', {})
            buy_data = item_data.get('buy', {})

            sell_price = sell_data.get('percentile', 0) or 0
            buy_price = buy_data.get('percentile', 0) or 0

            if sell_price or buy_price:
                result[type_id] = JitaPriceData(
                    type_id=type_id,
                    sell_price=float(sell_price),
                    buy_price=float(buy_price),
                )

        return result

    def _fetch_janice(self, type_ids: list[int]) -> dict[int, JitaPriceData]:
        """Fetch prices from Janice API."""
        if not self._janice_key:
            return {}

        try:
            body = '\n'.join(map(str, type_ids))
            headers = {
                'X-ApiKey': self._janice_key,
                'accept': 'application/json',
                'Content-Type': 'text/plain'
            }
            params = {'market': str(self.JANICE_MARKET)}

            response = requests.post(
                self.JANICE_URL,
                data=body,
                headers=headers,
                params=params,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()

            return self._parse_janice_response(response.json())

        except Exception as e:
            self._logger.error(f"Janice API error: {e}")
            return {}

    def _parse_janice_response(self, data: dict) -> dict[int, JitaPriceData]:
        """Parse Janice JSON response."""
        result = {}

        for item in data.get('appraisalItems', []):
            type_id = item.get('typeID')
            if type_id is None:
                continue

            prices = item.get('prices', {}).get('top5AveragePrices', {})
            sell_price = prices.get('sellPrice', 0) or 0
            buy_price = prices.get('buyPrice', 0) or 0

            if sell_price or buy_price:
                result[type_id] = JitaPriceData(
                    type_id=type_id,
                    sell_price=float(sell_price),
                    buy_price=float(buy_price),
                )

        return result


# =============================================================================
# SDE Lookup Service
# =============================================================================

class SDELookupService:
    """
    Service for resolving item names to type IDs using SDE database.
    """

    def __init__(self, db: DatabaseConfig, logger_instance: Optional[logging.Logger] = None):
        self._db = db
        self._logger = logger_instance or logger

    def resolve_item(self, type_name: str) -> Optional[dict]:
        """
        Resolve a single item name to SDE data.

        Args:
            type_name: Item name to look up

        Returns:
            Dict with typeID, typeName, groupName, categoryName, volume
            or None if not found
        """
        query = """
            SELECT typeID, typeName, groupName, categoryName, volume
            FROM sdetypes
            WHERE typeName = :type_name COLLATE NOCASE
            LIMIT 1
        """

        try:
            with self._db.engine.connect() as conn:
                result = conn.execute(text(query), {"type_name": type_name.strip()}).fetchone()

                if result:
                    return {
                        "type_id": result[0],
                        "type_name": result[1],
                        "group_name": result[2] or "",
                        "category_name": result[3] or "",
                        "volume": result[4] or 0.0,
                    }

            # Try fuzzy match if exact match fails
            return self._fuzzy_match(type_name)

        except Exception as e:
            self._logger.error(f"SDE lookup error for '{type_name}': {e}")
            return None

    def _fuzzy_match(self, type_name: str) -> Optional[dict]:
        """Attempt fuzzy matching for item name."""
        # Try with wildcards
        query = """
            SELECT typeID, typeName, groupName, categoryName, volume
            FROM sdetypes
            WHERE typeName LIKE :pattern COLLATE NOCASE
            ORDER BY LENGTH(typeName)
            LIMIT 1
        """

        try:
            with self._db.engine.connect() as conn:
                # Try exact prefix match first
                result = conn.execute(
                    text(query),
                    {"pattern": f"{type_name.strip()}%"}
                ).fetchone()

                if result:
                    self._logger.debug(f"Fuzzy matched '{type_name}' to '{result[1]}'")
                    return {
                        "type_id": result[0],
                        "type_name": result[1],
                        "group_name": result[2] or "",
                        "category_name": result[3] or "",
                        "volume": result[4] or 0.0,
                    }

        except Exception as e:
            self._logger.error(f"Fuzzy match error: {e}")

        return None

    def resolve_items(self, type_names: list[str]) -> dict[str, Optional[dict]]:
        """
        Resolve multiple item names.

        Args:
            type_names: List of item names

        Returns:
            Dict mapping original name to SDE data (or None)
        """
        return {name: self.resolve_item(name) for name in type_names}


# =============================================================================
# Main Pricer Service
# =============================================================================

class PricerService:
    """
    Main service for the Pricer feature.

    Orchestrates:
    1. Parsing input (EFT or multibuy)
    2. Resolving items in SDE
    3. Fetching Jita prices (buy + sell)
    4. Fetching local 4-HWWF prices
    5. Fetching market stats (avg volume, days remaining)
    6. Fetching doctrine information
    7. Combining into final result
    """

    def __init__(
        self,
        sde_db: DatabaseConfig,
        mkt_db: DatabaseConfig,
        market_repo: MarketOrdersRepository,
        jita_provider: JitaPriceProvider,
        logger_instance: Optional[logging.Logger] = None
    ):
        self._sde_lookup = SDELookupService(sde_db, logger_instance)
        self._sde_db = sde_db
        self._mkt_db = mkt_db
        self._market_repo = market_repo
        self._jita_provider = jita_provider
        self._logger = logger_instance or logger

    @classmethod
    def create_default(cls) -> "PricerService":
        """
        Factory method to create service with default configuration.
        """
        sde_db = DatabaseConfig("sde")
        mkt_db = DatabaseConfig("wcmkt")
        market_repo = get_market_orders_repository()

        # Get Janice API key from secrets
        janice_key = None
        try:
            janice_key = st.secrets.janice.api_key
        except Exception:
            logger.warning("Janice API key not found in secrets")

        jita_provider = JitaPriceProvider(janice_key)

        return cls(sde_db, mkt_db, market_repo, jita_provider)

    def get_market_stats(self, type_ids: list[int]) -> dict[int, dict]:
        """
        Get market stats (avg_volume, days_remaining) for type IDs.

        Args:
            type_ids: List of EVE type IDs

        Returns:
            Dict mapping type_id to dict with avg_volume and days_remaining
        """
        if not type_ids:
            return {}

        placeholders = ','.join([':id' + str(i) for i in range(len(type_ids))])
        query = f"""
            SELECT type_id, avg_volume, days_remaining, total_volume_remain
            FROM marketstats
            WHERE type_id IN ({placeholders})
        """
        params = {f'id{i}': tid for i, tid in enumerate(type_ids)}

        try:
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(text(query), conn, params=params)

            result = {}
            for _, row in df.iterrows():
                type_id = int(row['type_id'])
                avg_vol = float(row['avg_volume']) if pd.notna(row['avg_volume']) else 0.0
                days = float(row['days_remaining']) if pd.notna(row['days_remaining']) else 0.0
                result[type_id] = {
                    'avg_volume': avg_vol,
                    'days_remaining': days,
                    'total_volume_remain': int(row['total_volume_remain']) if pd.notna(row['total_volume_remain']) else 0
                }

            return result

        except Exception as e:
            self._logger.error(f"Error fetching market stats: {e}")
            return {}

    def get_doctrine_info(self, type_ids: list[int]) -> dict[int, dict]:
        """
        Get doctrine information for type IDs.

        Args:
            type_ids: List of EVE type IDs

        Returns:
            Dict mapping type_id to dict with is_doctrine and ships list
        """
        if not type_ids:
            return {}

        placeholders = ','.join([':id' + str(i) for i in range(len(type_ids))])
        query = f"""
            SELECT DISTINCT type_id, ship_name, fits_on_mkt
            FROM doctrines
            WHERE type_id IN ({placeholders})
        """
        params = {f'id{i}': tid for i, tid in enumerate(type_ids)}

        try:
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(text(query), conn, params=params)

            # Group ships by type_id
            result = {}
            for type_id in type_ids:
                result[type_id] = {'is_doctrine': False, 'ships': []}

            for _, row in df.iterrows():
                type_id = int(row['type_id'])
                ship_name = row['ship_name']
                fits = int(row['fits_on_mkt']) if pd.notna(row['fits_on_mkt']) else 0

                if type_id not in result:
                    result[type_id] = {'is_doctrine': False, 'ships': []}

                result[type_id]['is_doctrine'] = True
                if ship_name and pd.notna(ship_name):
                    result[type_id]['ships'].append(f"{ship_name} ({fits})")

            return result

        except Exception as e:
            self._logger.error(f"Error fetching doctrine info: {e}")
            return {tid: {'is_doctrine': False, 'ships': []} for tid in type_ids}

    def price_input(self, text: str) -> PricerResult:
        """
        Main entry point: parse input and return priced results.

        Args:
            text: User input (EFT fitting or multibuy list)

        Returns:
            PricerResult with priced items and metadata
        """
        if not text or not text.strip():
            return PricerResult(
                parse_errors=["Empty input"],
                input_type=InputFormat.UNKNOWN
            )

        # Step 1: Parse input
        raw_items, input_format, ship_name, fit_name, parse_errors = parse_input(text)

        if not raw_items:
            return PricerResult(
                parse_errors=parse_errors or ["No items found in input"],
                input_type=input_format,
                ship_name=ship_name,
                fit_name=fit_name,
            )

        # Step 2: Resolve items in SDE
        parsed_items = self._resolve_items(raw_items)

        # Separate resolved and unresolved
        resolved = [item for item in parsed_items if item.is_resolved]
        unresolved = [item for item in parsed_items if not item.is_resolved]

        # Add unresolved items to errors
        for item in unresolved:
            parse_errors.append(f"Item not found: {item.type_name}")

        if not resolved:
            return PricerResult(
                parse_errors=parse_errors,
                input_type=input_format,
                ship_name=ship_name,
                fit_name=fit_name,
            )

        # Step 3: Get type IDs for price lookup
        type_ids = [item.type_id for item in resolved if item.type_id]

        # Step 4: Fetch prices
        jita_prices = self._jita_provider.get_prices(type_ids)
        local_prices = self._market_repo.get_local_prices(type_ids)

        # Step 5: Fetch market stats (avg volume, days remaining)
        market_stats = self.get_market_stats(type_ids)

        # Step 6: Fetch doctrine information
        doctrine_info = self.get_doctrine_info(type_ids)

        # Step 7: Combine into PricedItems
        priced_items = []
        for item in resolved:
            if not item.type_id:
                continue

            # Type assertion: after the check above, item.type_id is guaranteed to be int
            type_id: int = item.type_id

            jita_data = jita_prices.get(type_id, JitaPriceData(type_id=type_id))
            local_data = local_prices.get(type_id, LocalPriceData(type_id=type_id))
            stats = market_stats.get(type_id, {'avg_volume': 0.0, 'days_remaining': 0.0})
            doctrine = doctrine_info.get(type_id, {'is_doctrine': False, 'ships': []})

            category_name = item.category_name
            isship = True if category_name == "Ship" else False

            priced_items.append(PricedItem(
                item=item,
                image_url=get_image_url(type_id, size=64, isship=isship),
                jita_sell=jita_data.sell_price,
                jita_buy=jita_data.buy_price,
                local_sell=local_data.min_sell_price,
                local_buy=local_data.max_buy_price,
                local_sell_volume=local_data.total_sell_volume,
                local_buy_volume=local_data.total_buy_volume,
                avg_daily_volume=stats['avg_volume'],
                days_of_stock=stats['days_remaining'],
                is_doctrine=doctrine['is_doctrine'],
                doctrine_ships=tuple(doctrine['ships']),
            ))

        self._logger.info(
            f"Priced {len(priced_items)} items "
            f"({input_format.value} format, {len(parse_errors)} errors)"
        )

        return PricerResult(
            items=priced_items,
            parse_errors=parse_errors,
            input_type=input_format,
            ship_name=ship_name,
            fit_name=fit_name,
        )

    def _resolve_items(self, raw_items: list[RawParsedItem]) -> list[ParsedItem]:
        """
        Resolve raw parsed items to ParsedItem with SDE data.
        """
        parsed_items = []

        for raw in raw_items:
            sde_data = self._sde_lookup.resolve_item(raw.name)

            if sde_data:
                parsed_items.append(ParsedItem(
                    type_name=raw.name,
                    quantity=raw.quantity,
                    type_id=sde_data["type_id"],
                    resolved_name=sde_data["type_name"],
                    volume=sde_data["volume"],
                    group_name=sde_data["group_name"],
                    category_name=sde_data["category_name"],
                    slot_type=raw.slot_type,
                ))
            else:
                parsed_items.append(ParsedItem(
                    type_name=raw.name,
                    quantity=raw.quantity,
                    parse_error=f"Not found in SDE: {raw.name}",
                ))

        return parsed_items


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_pricer_service() -> PricerService:
    """
    Get or create a PricerService instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.

    Returns:
        PricerService instance
    """
    try:
        from state import get_service
        return get_service('pricer_service', PricerService.create_default)
    except ImportError:
        logger.debug("state module unavailable, creating new PricerService instance")
        return PricerService.create_default()
