"""
Price Service Module

This module demonstrates several advanced Python patterns:
1. Protocol/ABC for provider abstraction (Strategy Pattern)
2. Dataclasses for structured results
3. Dependency Injection for testability
4. Chain of Responsibility for fallback logic
5. Caching with proper invalidation

Consolidates price logic from:
- utils.py (get_jita_price, get_multi_item_jita_price, etc.)
- doctrines.py (calculate_jita_fit_cost_and_delta, null price handling)
- doctrine_status.py (fetch_jita_prices_for_types)
"""

from dataclasses import dataclass, field
from typing import Protocol, Optional
from enum import Enum, auto
import logging
import threading
import time
import requests
import pandas as pd
import streamlit as st
from config import DatabaseConfig
from logging_config import setup_logging

logger = setup_logging(__name__, log_file="price_service.log")

# Type alias for clarity
TypeID = int
Price = float

_PRICE_SERVICE_LOCK = threading.Lock()
_PRICE_SERVICES: dict[str, "PriceService"] = {}
_PRICE_CACHE_LOCK = threading.Lock()
_SHARED_JITA_PRICE_CACHE: dict[TypeID, "CachedPriceEntry"] = {}


# =============================================================================
# Domain Models (Dataclasses)
# =============================================================================

class PriceSource(Enum):
    """Enum for price data sources."""
    LOCAL_MARKET = auto()
    JITA_FUZZWORK = auto()
    JITA_JANICE = auto()
    MARKET_AVERAGE = auto()
    FALLBACK_ZERO = auto()


@dataclass(frozen=True)
class PriceResult:
    """
    Immutable result of a price lookup.

    frozen=True makes this hashable and safe for caching.
    """
    type_id: TypeID
    sell_price: Price
    buy_price: Price
    source: PriceSource
    success: bool = True
    error_message: Optional[str] = None

    @property
    def price(self) -> Price:
        """Backward-compatible alias for sell price."""
        return self.sell_price

    @property
    def has_sell_price(self) -> bool:
        """True when a sell price is available."""
        return self.sell_price > 0

    @property
    def has_buy_price(self) -> bool:
        """True when a buy price is available."""
        return self.buy_price > 0

    @property
    def has_any_price(self) -> bool:
        """True when either a sell or buy price is available."""
        return self.has_sell_price or self.has_buy_price

    @classmethod
    def success_result(
        cls,
        type_id: TypeID,
        sell_price: Price,
        source: PriceSource,
        buy_price: Price = 0.0,
    ) -> "PriceResult":
        """Factory for successful price lookups."""
        return cls(
            type_id=type_id,
            sell_price=sell_price,
            buy_price=buy_price,
            source=source,
            success=sell_price > 0,
        )

    @classmethod
    def failure_result(cls, type_id: TypeID, error: str) -> "PriceResult":
        """Factory for failed price lookups."""
        return cls(
            type_id=type_id,
            sell_price=0.0,
            buy_price=0.0,
            source=PriceSource.FALLBACK_ZERO,
            success=False,
            error_message=error
        )


@dataclass
class BatchPriceResult:
    """Result of a batch price lookup."""
    prices: dict[TypeID, PriceResult] = field(default_factory=dict)
    source: PriceSource = PriceSource.JITA_FUZZWORK
    failed_ids: list[TypeID] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for p in self.prices.values() if p.success)

    @property
    def failure_count(self) -> int:
        return len(self.failed_ids)

    def get_price(self, type_id: TypeID, default: Price = 0.0) -> Price:
        """Get price for a type_id, with default fallback."""
        result = self.prices.get(type_id)
        return result.price if result and result.success else default

    def get_buy_price(self, type_id: TypeID, default: Price = 0.0) -> Price:
        """Get buy price for a type_id, with default fallback."""
        result = self.prices.get(type_id)
        return result.buy_price if result and result.has_buy_price else default

    def to_dict(self) -> dict[TypeID, Price]:
        """Convert to simple type_id -> price mapping."""
        return {tid: r.price for tid, r in self.prices.items() if r.has_sell_price}

    def to_buy_dict(self) -> dict[TypeID, Price]:
        """Convert to simple type_id -> buy price mapping."""
        return {tid: r.buy_price for tid, r in self.prices.items() if r.has_buy_price}


@dataclass
class FitCostAnalysis:
    """
    Analysis of a fit's cost compared to Jita prices.

    Encapsulates the logic that was in calculate_jita_fit_cost_and_delta().
    """
    fit_id: int
    local_cost: Price
    jita_cost: Price
    missing_prices: list[TypeID] = field(default_factory=list)

    @property
    def delta_absolute(self) -> Price:
        """Absolute difference: local - jita."""
        return self.local_cost - self.jita_cost

    @property
    def delta_percentage(self) -> Optional[float]:
        """Percentage difference from Jita. None if Jita cost is 0."""
        if self.jita_cost <= 0:
            return None
        return ((self.local_cost - self.jita_cost) / self.jita_cost) * 100

    @property
    def is_cheaper_than_jita(self) -> bool:
        """True if local price is cheaper than Jita."""
        return self.delta_absolute < 0

    @property
    def has_missing_data(self) -> bool:
        """True if some items couldn't be priced."""
        return len(self.missing_prices) > 0


@dataclass(frozen=True)
class CachedPriceEntry:
    """Cached price entry with a per-record timestamp."""
    result: PriceResult
    cached_at: float


# =============================================================================
# Provider Protocol (Strategy Pattern)
# =============================================================================

class PriceProvider(Protocol):
    """
    Protocol defining what a price provider must implement.

    Using Protocol instead of ABC allows structural subtyping -
    any class with these methods works, no inheritance required.
    """

    def get_price(self, type_id: TypeID) -> PriceResult:
        """Get price for a single item."""
        ...

    def get_prices(self, type_ids: list[TypeID]) -> BatchPriceResult:
        """Get prices for multiple items."""
        ...

    @property
    def name(self) -> str:
        """Provider name for logging."""
        ...


# =============================================================================
# Concrete Providers
# =============================================================================

class FuzzworkProvider:
    """
    Price provider using Fuzzwork API.

    This is the primary Jita price source.
    """

    BASE_URL = "https://market.fuzzwork.co.uk/aggregates/"
    REGION_JITA = 10000002
    TIMEOUT = 30

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return "Fuzzwork"

    def get_price(self, type_id: TypeID) -> PriceResult:
        """Get price for a single item from Fuzzwork."""
        result = self.get_prices([type_id])
        return result.prices.get(type_id, PriceResult.failure_result(type_id, "Not found"))

    def get_prices(self, type_ids: list[TypeID]) -> BatchPriceResult:
        """Batch fetch prices from Fuzzwork API."""
        if not type_ids:
            return BatchPriceResult()

        try:
            type_ids_str = ','.join(map(str, type_ids))
            url = f"{self.BASE_URL}?region={self.REGION_JITA}&types={type_ids_str}"
            self._logger.info(
                "Price API call: Fuzzwork batch lookup for %s item(s)",
                len(type_ids),
            )

            response = requests.get(url, timeout=self.TIMEOUT)
            response.raise_for_status()

            data = response.json()
            return self._parse_response(data, type_ids)

        except requests.exceptions.Timeout:
            self._logger.error("Fuzzwork API timeout")
            return BatchPriceResult(failed_ids=type_ids)
        except requests.exceptions.RequestException as e:
            self._logger.error(f"Fuzzwork API error: {e}")
            return BatchPriceResult(failed_ids=type_ids)

    def _parse_response(self, data: dict, requested_ids: list[TypeID]) -> BatchPriceResult:
        """Parse Fuzzwork JSON response into BatchPriceResult."""
        prices = {}
        failed = []

        for type_id in requested_ids:
            type_id_str = str(type_id)

            if type_id_str not in data:
                failed.append(type_id)
                continue

            sell_data = data[type_id_str].get('sell', {})
            buy_data = data[type_id_str].get('buy', {})
            sell_price = sell_data.get('percentile')
            buy_price = buy_data.get('percentile')

            if sell_price is not None or buy_price is not None:
                prices[type_id] = PriceResult.success_result(
                    type_id=type_id,
                    sell_price=float(sell_price or 0.0),
                    buy_price=float(buy_price or 0.0),
                    source=PriceSource.JITA_FUZZWORK,
                )
            else:
                failed.append(type_id)
                self._logger.warning(f"No buy/sell percentile price for type_id {type_id}")

        return BatchPriceResult(
            prices=prices,
            source=PriceSource.JITA_FUZZWORK,
            failed_ids=failed
        )


class JaniceProvider:
    """
    Price provider using Janice API.

    Used as fallback when Fuzzwork fails.
    """

    BASE_URL = "https://janice.e-351.com/api/rest/v2/pricer"
    MARKET_JITA = 2
    TIMEOUT = 30

    def __init__(self, api_key: str, logger: Optional[logging.Logger] = None):
        self._api_key = api_key
        self._logger = logger or logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return "Janice"

    def get_price(self, type_id: TypeID) -> PriceResult:
        """Get price for a single item from Janice."""
        try:
            url = f"{self.BASE_URL}/{type_id}?market={self.MARKET_JITA}"
            headers = {'X-ApiKey': self._api_key, 'accept': 'application/json'}
            self._logger.info("Price API call: Janice single lookup for type_id %s", type_id)

            response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
            response.raise_for_status()

            data = response.json()
            prices = data.get('top5AveragePrices', {})
            sell_price = prices.get('sellPrice')
            buy_price = prices.get('buyPrice')

            if sell_price is not None or buy_price is not None:
                return PriceResult.success_result(
                    type_id=type_id,
                    sell_price=float(sell_price or 0.0),
                    buy_price=float(buy_price or 0.0),
                    source=PriceSource.JITA_JANICE,
                )
            return PriceResult.failure_result(type_id, "No buy/sell price in response")

        except Exception as e:
            self._logger.error(f"Janice API error for {type_id}: {e}")
            return PriceResult.failure_result(type_id, str(e))

    def get_prices(self, type_ids: list[TypeID]) -> BatchPriceResult:
        """Batch fetch prices from Janice API."""
        if not type_ids:
            return BatchPriceResult()

        try:
            body = '\n'.join(map(str, type_ids))
            headers = {
                'X-ApiKey': self._api_key,
                'accept': 'application/json',
                'Content-Type': 'text/plain'
            }
            params = {'market': str(self.MARKET_JITA)}
            self._logger.info(
                "Price API call: Janice batch lookup for %s item(s)",
                len(type_ids),
            )

            response = requests.post(
                self.BASE_URL,
                data=body,
                headers=headers,
                params=params,
                timeout=self.TIMEOUT
            )
            response.raise_for_status()

            return self._parse_response(response.json(), type_ids)

        except Exception as e:
            self._logger.error(f"Janice batch API error: {e}")
            return BatchPriceResult(failed_ids=type_ids)

    def _parse_response(self, data: dict, requested_ids: list[TypeID]) -> BatchPriceResult:
        """Parse Janice JSON response."""
        prices = {}
        found_ids = set()

        for item in data.get('appraisalItems', []):
            type_id = item.get('typeID')
            if type_id is None:
                continue

            found_ids.add(type_id)
            prices_data = item.get('prices', {}).get('top5AveragePrices', {})
            sell_price = prices_data.get('sellPrice')
            buy_price = prices_data.get('buyPrice')

            if sell_price is not None or buy_price is not None:
                prices[type_id] = PriceResult.success_result(
                    type_id=type_id,
                    sell_price=float(sell_price or 0.0),
                    buy_price=float(buy_price or 0.0),
                    source=PriceSource.JITA_JANICE,
                )

        failed = [tid for tid in requested_ids if tid not in found_ids or tid not in prices]

        return BatchPriceResult(
            prices=prices,
            source=PriceSource.JITA_JANICE,
            failed_ids=failed
        )


class LocalMarketProvider:
    """
    Price provider using local market database.

    Fetches prices from the local marketstats table.
    """

    def __init__(self, db_config, logger: Optional[logging.Logger] = None):
        self._db = db_config
        self._logger = logger or logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return "LocalMarket"

    def get_price(self, type_id: TypeID) -> PriceResult:
        """Get price from local market data."""
        result = self.get_prices([type_id])
        return result.prices.get(type_id, PriceResult.failure_result(type_id, "Not found"))

    def get_prices(self, type_ids: list[TypeID]) -> BatchPriceResult:
        """Batch fetch from local marketstats table."""
        if not type_ids:
            return BatchPriceResult(source=PriceSource.LOCAL_MARKET)

        try:
            placeholders = ','.join(['?'] * len(type_ids))
            query = f"SELECT type_id, price, avg_price FROM marketstats WHERE type_id IN ({placeholders})"

            with self._db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn, params=tuple(type_ids))

            return self._parse_dataframe(df, type_ids)

        except Exception as e:
            self._logger.error(f"Local market query error: {e}")
            return BatchPriceResult(failed_ids=type_ids, source=PriceSource.LOCAL_MARKET)

    def _parse_dataframe(self, df: pd.DataFrame, requested_ids: list[TypeID]) -> BatchPriceResult:
        """Parse DataFrame into BatchPriceResult."""
        prices = {}
        found_ids = set()

        for _, row in df.iterrows():
            type_id = int(row['type_id'])
            found_ids.add(type_id)

            # Prefer price, fall back to avg_price
            price = row.get('price') if pd.notna(row.get('price')) else row.get('avg_price')

            if pd.notna(price) and price > 0:
                prices[type_id] = PriceResult.success_result(
                    type_id=type_id,
                    sell_price=float(price),
                    buy_price=0.0,
                    source=PriceSource.LOCAL_MARKET,
                )

        failed = [tid for tid in requested_ids if tid not in prices]

        return BatchPriceResult(
            prices=prices,
            source=PriceSource.LOCAL_MARKET,
            failed_ids=failed
        )


# =============================================================================
# Chain of Responsibility - Fallback Provider
# =============================================================================

class FallbackPriceProvider:
    """
    Price provider that tries multiple providers in order.

    Implements Chain of Responsibility pattern - if one provider fails,
    it automatically tries the next one.
    """

    def __init__(
        self,
        providers: list[PriceProvider],
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize with ordered list of providers.

        Args:
            providers: List of providers to try, in order of preference
        """
        self._providers = providers
        self._logger = logger or logging.getLogger(__name__)

    @property
    def name(self) -> str:
        names = [p.name for p in self._providers]
        return f"Fallback({' -> '.join(names)})"

    def get_price(self, type_id: TypeID) -> PriceResult:
        """Try each provider until one yields a sell price."""
        result = self.get_prices([type_id])
        return result.prices.get(type_id, PriceResult.failure_result(type_id, "All providers failed"))

    def get_prices(self, type_ids: list[TypeID]) -> BatchPriceResult:
        """
        Try each provider for remaining items.

        More efficient than individual lookups - tracks which IDs
        still need pricing and only queries those.
        """
        all_prices: dict[TypeID, PriceResult] = {}
        remaining_ids = set(type_ids)

        for provider in self._providers:
            if not remaining_ids:
                break

            try:
                result = provider.get_prices(list(remaining_ids))

                for type_id, price_result in result.prices.items():
                    merged_result = self._merge_price_results(
                        existing=all_prices.get(type_id),
                        new_result=price_result,
                    )
                    if merged_result is not None:
                        all_prices[type_id] = merged_result
                    if merged_result and merged_result.has_sell_price:
                        remaining_ids.discard(type_id)

                self._logger.debug(
                    f"{provider.name}: got {result.success_count} prices, "
                    f"{len(remaining_ids)} remaining"
                )

            except Exception as e:
                self._logger.warning(f"{provider.name} batch failed: {e}")
                continue

        failed_ids = list(remaining_ids)
        for type_id in failed_ids:
            if type_id not in all_prices:
                all_prices[type_id] = PriceResult.failure_result(type_id, "All providers failed")

        return BatchPriceResult(
            prices=all_prices,
            source=PriceSource.JITA_FUZZWORK,  # Primary source
            failed_ids=failed_ids
        )

    @staticmethod
    def _merge_price_results(
        existing: Optional[PriceResult],
        new_result: PriceResult,
    ) -> Optional[PriceResult]:
        """Merge partial buy/sell data from multiple providers."""
        if existing is None:
            return new_result if new_result.has_any_price or new_result.success else None
        if not new_result.has_any_price:
            return existing

        sell_price = existing.sell_price if existing.has_sell_price else new_result.sell_price
        buy_price = existing.buy_price if existing.has_buy_price else new_result.buy_price
        source = existing.source if existing.has_sell_price else new_result.source
        success = sell_price > 0
        error_message = existing.error_message if success else new_result.error_message

        return PriceResult(
            type_id=existing.type_id,
            sell_price=sell_price,
            buy_price=buy_price,
            source=source,
            success=success,
            error_message=error_message,
        )


# =============================================================================
# Main Price Service (Facade)
# =============================================================================

class PriceService:
    """
    Main price service - facade for all price operations.

    This is the primary interface that Streamlit pages should use.
    It hides the complexity of providers, caching, and fallback logic.

    Example usage:
        service = PriceService.create_default()

        # Single price
        result = service.get_jita_price(34)  # Tritanium

        # Batch prices
        prices = service.get_jita_prices([34, 35, 36])

        # Fit cost analysis
        analysis = service.analyze_fit_cost(fit_df, local_cost=1_000_000)
    """

    def __init__(
        self,
        jita_provider: PriceProvider,
        local_provider: Optional[PriceProvider] = None,
        logger: Optional[logging.Logger] = None,
        cache_ttl: int = 3600,
        price_cache: Optional[dict[TypeID, CachedPriceEntry]] = None,
    ):
        """
        Initialize price service with providers.

        Args:
            jita_provider: Provider for Jita prices (usually FallbackProvider)
            local_provider: Provider for local market prices (optional)
            logger: Logger instance
            cache_ttl: Cache time-to-live in seconds
            price_cache: Shared cache store for Jita prices
        """
        self._jita_provider = jita_provider
        self._local_provider = local_provider
        self._logger = logger or logging.getLogger(__name__)
        self._cache_ttl = cache_ttl

        self._price_cache = price_cache if price_cache is not None else {}

    @classmethod
    def create_default(cls, db_config=None, janice_api_key: str = None) -> "PriceService":
        """
        Factory method to create service with default configuration.

        This is the recommended way to instantiate the service.
        """
        logger = logging.getLogger(__name__)

        # Build provider chain: Fuzzwork -> Janice
        providers = [FuzzworkProvider(logger)]

        if janice_api_key:
            providers.append(JaniceProvider(janice_api_key, logger))

        jita_provider = FallbackPriceProvider(providers, logger)

        # Optional local provider
        local_provider = None
        if db_config:
            local_provider = LocalMarketProvider(db_config, logger)

        return cls(
            jita_provider=jita_provider,
            local_provider=local_provider,
            logger=logger,
            price_cache=_SHARED_JITA_PRICE_CACHE,
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_jita_price(self, type_id: TypeID) -> PriceResult:
        """
        Get Jita price for a single item.

        Uses cache if available, otherwise fetches from providers.
        """
        cached_result = self._get_cached_result(type_id)
        if cached_result is not None:
            return cached_result

        result = self._jita_provider.get_price(type_id)
        self._cache_result(type_id, result)
        return result

    def get_jita_prices(self, type_ids: list[TypeID]) -> BatchPriceResult:
        """
        Get Jita prices for multiple items.

        Optimizes by only fetching uncached items.
        """
        # Separate cached and uncached
        cached: dict[TypeID, PriceResult] = {}
        uncached = []

        for type_id in type_ids:
            cached_result = self._get_cached_result(type_id)
            if cached_result is None:
                uncached.append(type_id)
                continue
            cached[type_id] = cached_result

        # Fetch uncached
        if uncached:
            result = self._jita_provider.get_prices(uncached)
            for type_id, price_result in result.prices.items():
                self._cache_result(type_id, price_result)
            cached.update(result.prices)

        return BatchPriceResult(
            prices=cached,
            source=PriceSource.JITA_FUZZWORK,
            failed_ids=[tid for tid in type_ids if tid not in cached or not cached[tid].success]
        )

    def get_jita_prices_as_dict(self, type_ids: list[TypeID]) -> dict[TypeID, Price]:
        """
        Convenience method returning simple type_id -> price dict.

        This is the format expected by existing code like
        calculate_jita_fit_cost_and_delta().
        """
        return self.get_jita_prices(type_ids).to_dict()

    def get_jita_buy_prices_as_dict(self, type_ids: list[TypeID]) -> dict[TypeID, Price]:
        """Convenience method returning simple type_id -> buy price dict."""
        return self.get_jita_prices(type_ids).to_buy_dict()

    def get_jita_price_data_map(self, type_ids: list[TypeID]) -> dict[TypeID, PriceResult]:
        """Return full price records including sell and buy values."""
        return dict(self.get_jita_prices(type_ids).prices)

    def analyze_fit_cost(
        self,
        fit_data: pd.DataFrame,
        local_cost: Price,
        jita_price_map: Optional[dict[TypeID, Price]] = None
    ) -> FitCostAnalysis:
        """
        Analyze fit cost compared to Jita prices.

        Replaces calculate_jita_fit_cost_and_delta() from doctrines.py.

        Args:
            fit_data: DataFrame with columns: type_id, fit_qty
            local_cost: Current local market cost of the fit
            jita_price_map: Optional pre-fetched Jita prices

        Returns:
            FitCostAnalysis with cost comparison data
        """
        if fit_data.empty:
            return FitCostAnalysis(fit_id=0, local_cost=local_cost, jita_cost=0.0)

        fit_id = int(fit_data['fit_id'].iloc[0]) if 'fit_id' in fit_data.columns else 0

        # Get Jita prices (use provided map or fetch)
        type_ids = fit_data['type_id'].unique().tolist()
        jita_prices = jita_price_map or self.get_jita_prices_as_dict(type_ids)

        # Calculate Jita cost
        jita_cost = 0.0
        missing = []

        for _, row in fit_data.iterrows():
            type_id = int(row['type_id'])
            fit_qty = int(row['fit_qty'])

            if type_id in jita_prices and jita_prices[type_id] > 0:
                jita_cost += fit_qty * jita_prices[type_id]
            else:
                missing.append(type_id)

        return FitCostAnalysis(
            fit_id=fit_id,
            local_cost=local_cost,
            jita_cost=jita_cost,
            missing_prices=missing
        )

    def fill_null_prices(
        self,
        df: pd.DataFrame,
        price_column: str = 'price',
        type_id_column: str = 'type_id'
    ) -> pd.DataFrame:
        """
        Fill null prices in a DataFrame with Jita prices.

        Replaces the null price handling logic in create_fit_df().

        Args:
            df: DataFrame with price and type_id columns
            price_column: Name of the price column
            type_id_column: Name of the type_id column

        Returns:
            DataFrame with null prices filled
        """
        df = df.copy()

        null_mask = df[price_column].isna()
        if not null_mask.any():
            return df

        null_type_ids = df.loc[null_mask, type_id_column].unique().tolist()
        self._logger.info(f"Filling {len(null_type_ids)} null prices")

        # Try local market first
        if self._local_provider:
            local_result = self._local_provider.get_prices(null_type_ids)
            for type_id, price_result in local_result.prices.items():
                if price_result.success:
                    mask = (df[type_id_column] == type_id) & df[price_column].isna()
                    df.loc[mask, price_column] = price_result.price
                    self._logger.debug(f"Filled {type_id} with local price: {price_result.price}")

        # Then try Jita for remaining nulls
        still_null = df[price_column].isna()
        if still_null.any():
            remaining_ids = df.loc[still_null, type_id_column].unique().tolist()
            jita_result = self.get_jita_prices(remaining_ids)

            for type_id, price_result in jita_result.prices.items():
                if price_result.success:
                    mask = (df[type_id_column] == type_id) & df[price_column].isna()
                    df.loc[mask, price_column] = price_result.price
                    self._logger.debug(f"Filled {type_id} with Jita price: {price_result.price}")

        # Final fallback: fill remaining with 0
        remaining_nulls = df[price_column].isna().sum()
        if remaining_nulls > 0:
            self._logger.warning(f"Filling {remaining_nulls} prices with 0")
            df[price_column] = df[price_column].fillna(0)

        return df

    def clear_cache(self):
        """Clear the price cache."""
        with _PRICE_CACHE_LOCK:
            self._price_cache.clear()
        self._logger.info("Price cache cleared")

    def get_cache_stats(self) -> dict:
        """Get cache statistics for debugging."""
        with _PRICE_CACHE_LOCK:
            self._prune_expired_cache_entries()
            return {
                'cached_items': len(self._price_cache),
                'successful': sum(1 for entry in self._price_cache.values() if entry.result.success),
                'failed': sum(1 for entry in self._price_cache.values() if not entry.result.success),
                'cache_ttl_seconds': self._cache_ttl,
            }

    def _cache_result(self, type_id: TypeID, result: PriceResult) -> None:
        """Store a price result with its cache timestamp."""
        with _PRICE_CACHE_LOCK:
            self._price_cache[type_id] = CachedPriceEntry(
                result=result,
                cached_at=time.monotonic(),
            )

    def _get_cached_result(self, type_id: TypeID) -> Optional[PriceResult]:
        """Return a cached result if it has not expired."""
        with _PRICE_CACHE_LOCK:
            cached_entry = self._price_cache.get(type_id)
            if cached_entry is None:
                return None
            if self._is_cache_entry_expired(cached_entry):
                self._price_cache.pop(type_id, None)
                return None
            return cached_entry.result

    def _is_cache_entry_expired(self, cached_entry: CachedPriceEntry) -> bool:
        """Check whether a cached entry is older than the configured TTL."""
        return (time.monotonic() - cached_entry.cached_at) >= self._cache_ttl

    def _prune_expired_cache_entries(self) -> None:
        """Remove expired items from the in-memory cache."""
        expired_ids = [
            type_id
            for type_id, entry in self._price_cache.items()
            if self._is_cache_entry_expired(entry)
        ]
        for type_id in expired_ids:
            self._price_cache.pop(type_id, None)


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_price_service(
    db_alias: Optional[str] = None,
    janice_api_key: Optional[str] = None,
    market_key: Optional[str] = None,
) -> PriceService:
    """
    Get or create a PriceService instance.

    Reuses one process-wide service instance per market key so the
    in-memory price cache survives across Streamlit sessions.

    Example:
        from services.price_service import get_price_service

        service = get_price_service()
        prices = service.get_jita_prices([34, 35, 36])
    """
    resolved_db_alias = db_alias
    resolved_market_key = market_key

    if resolved_db_alias is None:
        try:
            from state.market_state import get_active_market
            resolved_db_alias = get_active_market().database_alias
        except (ImportError, Exception):
            resolved_db_alias = "wcmkt"

    if resolved_market_key is None:
        try:
            from state.market_state import get_active_market_key
            resolved_market_key = get_active_market_key()
        except (ImportError, Exception):
            resolved_market_key = resolved_db_alias

    service_key = f"price_service_{resolved_market_key}"

    def _create_price_service() -> PriceService:
        janice_key = janice_api_key
        if janice_key is None:
            try:
                janice_key = st.secrets.janice.api_key
            except Exception:
                janice_key = None

        db_config = DatabaseConfig(resolved_db_alias)
        return PriceService.create_default(
            db_config=db_config,
            janice_api_key=janice_key
        )

    with _PRICE_SERVICE_LOCK:
        service = _PRICE_SERVICES.get(service_key)
        if service is None:
            service = _create_price_service()
            _PRICE_SERVICES[service_key] = service
        return service


# =============================================================================
# Backwards Compatibility
# =============================================================================

def get_jita_price(type_id: int) -> float:
    """Backwards-compatible wrapper for get_jita_price."""
    service = get_price_service()
    result = service.get_jita_price(type_id)
    return result.price if result.success else 0.0
