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

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol, Optional, Callable
from enum import Enum, auto
from functools import lru_cache
import logging
import requests
import pandas as pd
import streamlit as st
from config import DatabaseConfig

# Type alias for clarity
TypeID = int
Price = float


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
    price: Price
    source: PriceSource
    success: bool = True
    error_message: Optional[str] = None

    @classmethod
    def success_result(cls, type_id: TypeID, price: Price, source: PriceSource) -> "PriceResult":
        """Factory for successful price lookups."""
        return cls(type_id=type_id, price=price, source=source, success=True)

    @classmethod
    def failure_result(cls, type_id: TypeID, error: str) -> "PriceResult":
        """Factory for failed price lookups."""
        return cls(
            type_id=type_id,
            price=0.0,
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

    def to_dict(self) -> dict[TypeID, Price]:
        """Convert to simple type_id -> price mapping."""
        return {tid: r.price for tid, r in self.prices.items() if r.success}


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
            percentile = sell_data.get('percentile')

            if percentile is not None:
                prices[type_id] = PriceResult.success_result(
                    type_id=type_id,
                    price=float(percentile),
                    source=PriceSource.JITA_FUZZWORK
                )
            else:
                failed.append(type_id)
                self._logger.warning(f"No percentile price for type_id {type_id}")

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

            response = requests.get(url, headers=headers, timeout=self.TIMEOUT)
            response.raise_for_status()

            data = response.json()
            price = data.get('top5AveragePrices', {}).get('sellPrice')

            if price is not None:
                return PriceResult.success_result(type_id, float(price), PriceSource.JITA_JANICE)
            return PriceResult.failure_result(type_id, "No sell price in response")

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
            sell_price = item.get('prices', {}).get('top5AveragePrices', {}).get('sellPrice')

            if sell_price is not None:
                prices[type_id] = PriceResult.success_result(
                    type_id=type_id,
                    price=float(sell_price),
                    source=PriceSource.JITA_JANICE
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

            with self._db.local_access():
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
                    price=float(price),
                    source=PriceSource.LOCAL_MARKET
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
        """Try each provider until one succeeds."""
        for provider in self._providers:
            try:
                result = provider.get_price(type_id)
                if result.success:
                    self._logger.debug(f"Got price for {type_id} from {provider.name}")
                    return result
            except Exception as e:
                self._logger.warning(f"{provider.name} failed for {type_id}: {e}")
                continue

        return PriceResult.failure_result(type_id, "All providers failed")

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

                # Add successful results
                for type_id, price_result in result.prices.items():
                    if price_result.success:
                        all_prices[type_id] = price_result
                        remaining_ids.discard(type_id)

                self._logger.debug(
                    f"{provider.name}: got {result.success_count} prices, "
                    f"{len(remaining_ids)} remaining"
                )

            except Exception as e:
                self._logger.warning(f"{provider.name} batch failed: {e}")
                continue

        # Mark remaining as failures
        failed_ids = list(remaining_ids)
        for type_id in failed_ids:
            all_prices[type_id] = PriceResult.failure_result(type_id, "All providers failed")

        return BatchPriceResult(
            prices=all_prices,
            source=PriceSource.JITA_FUZZWORK,  # Primary source
            failed_ids=failed_ids
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
        cache_ttl: int = 3600
    ):
        """
        Initialize price service with providers.

        Args:
            jita_provider: Provider for Jita prices (usually FallbackProvider)
            local_provider: Provider for local market prices (optional)
            logger: Logger instance
            cache_ttl: Cache time-to-live in seconds
        """
        self._jita_provider = jita_provider
        self._local_provider = local_provider
        self._logger = logger or logging.getLogger(__name__)
        self._cache_ttl = cache_ttl

        # In-memory cache (could be replaced with Redis, etc.)
        self._price_cache: dict[TypeID, PriceResult] = {}

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
            logger=logger
        )

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def get_jita_price(self, type_id: TypeID) -> PriceResult:
        """
        Get Jita price for a single item.

        Uses cache if available, otherwise fetches from providers.
        """
        if type_id in self._price_cache:
            return self._price_cache[type_id]

        result = self._jita_provider.get_price(type_id)
        self._price_cache[type_id] = result
        return result

    def get_jita_prices(self, type_ids: list[TypeID]) -> BatchPriceResult:
        """
        Get Jita prices for multiple items.

        Optimizes by only fetching uncached items.
        """
        # Separate cached and uncached
        cached = {}
        uncached = []

        for type_id in type_ids:
            if type_id in self._price_cache:
                cached[type_id] = self._price_cache[type_id]
            else:
                uncached.append(type_id)

        # Fetch uncached
        if uncached:
            result = self._jita_provider.get_prices(uncached)
            # Update cache
            for type_id, price_result in result.prices.items():
                self._price_cache[type_id] = price_result
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
        self._price_cache.clear()
        self._logger.info("Price cache cleared")

    def get_cache_stats(self) -> dict:
        """Get cache statistics for debugging."""
        return {
            'cached_items': len(self._price_cache),
            'successful': sum(1 for r in self._price_cache.values() if r.success),
            'failed': sum(1 for r in self._price_cache.values() if not r.success),
        }


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_price_service() -> PriceService:
    """
    Get or create a PriceService instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.

    Example:
        from services.price_service import get_price_service

        service = get_price_service()
        prices = service.get_jita_prices([34, 35, 36])
    """
    def _create_price_service() -> PriceService:
        # Get API key from secrets if available
        janice_key = None
        try:
            janice_key = st.secrets.janice.api_key
        except Exception:
            pass

        db_config = DatabaseConfig("wcmkt")
        return PriceService.create_default(
            db_config=db_config,
            janice_api_key=janice_key
        )

    try:
        from state import get_service
        return get_service('price_service', _create_price_service)
    except ImportError:
        # Fallback for non-Streamlit contexts or missing state module
        return _create_price_service()


# =============================================================================
# Backwards Compatibility
# =============================================================================

# These functions maintain API compatibility with existing code
# They delegate to the PriceService under the hood

def get_jita_price(type_id: int) -> float:
    """Backwards-compatible wrapper for get_jita_price."""
    service = get_price_service()
    result = service.get_jita_price(type_id)
    return result.price if result.success else 0.0


def get_multi_item_jita_price(type_ids: list[int]) -> dict[int, float]:
    """Backwards-compatible wrapper for batch Jita prices."""
    service = get_price_service()
    return service.get_jita_prices_as_dict(type_ids)


def calculate_jita_fit_cost_and_delta(
    fit_data: pd.DataFrame,
    current_fit_cost: float,
    jita_price_map: dict[int, float] | None = None
) -> tuple[float, float | None]:
    """
    Backwards-compatible wrapper for fit cost analysis.

    Returns (jita_fit_cost, percentage_delta) tuple for compatibility
    with existing code.
    """
    service = get_price_service()
    analysis = service.analyze_fit_cost(fit_data, current_fit_cost, jita_price_map)
    return analysis.jita_cost, analysis.delta_percentage
