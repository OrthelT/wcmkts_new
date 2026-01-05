"""
Services Package

This package contains service modules that implement business logic
using clean architecture patterns.

Each service module follows these principles:
1. Single Responsibility - one domain per service
2. Dependency Injection - dependencies passed in, not created
3. Protocol/ABC - interfaces for testability
4. Dataclasses - structured domain models

Streamlit Caching Pattern:
- Module-level functions with @st.cache_data (stateless, hashable args)
- Service classes coordinate cached functions
- Services cached with @st.cache_resource
"""

from services.price_service import (
    # Main services (use CachedPriceService for Streamlit apps)
    PriceService,
    CachedPriceService,
    get_price_service,

    # Cached functions (can be used directly if needed)
    fetch_jita_prices_cached,
    fetch_janice_prices_cached,
    fetch_local_prices_cached,

    # Domain models
    PriceResult,
    BatchPriceResult,
    FitCostAnalysis,
    PriceSource,

    # Providers (for custom configuration or testing)
    FuzzworkProvider,
    JaniceProvider,
    LocalMarketProvider,
    FallbackPriceProvider,

    # Backwards compatibility wrappers
    get_jita_price,
    get_multi_item_jita_price,
    calculate_jita_fit_cost_and_delta,
)

__all__ = [
    # Main services
    'PriceService',
    'CachedPriceService',
    'get_price_service',

    # Cached functions
    'fetch_jita_prices_cached',
    'fetch_janice_prices_cached',
    'fetch_local_prices_cached',

    # Domain models
    'PriceResult',
    'BatchPriceResult',
    'FitCostAnalysis',
    'PriceSource',

    # Providers
    'FuzzworkProvider',
    'JaniceProvider',
    'LocalMarketProvider',
    'FallbackPriceProvider',

    # Backwards compatibility
    'get_jita_price',
    'get_multi_item_jita_price',
    'calculate_jita_fit_cost_and_delta',
]
