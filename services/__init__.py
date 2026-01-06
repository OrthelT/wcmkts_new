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

Available Services:
- PriceService / CachedPriceService: Jita and local market prices
- DoctrineService: Doctrine fits, summaries, and ship categorization
"""

# -----------------------------------------------------------------------------
# Price Service
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# Doctrine Service
# -----------------------------------------------------------------------------
from services.doctrine_service import (
    # Main service
    DoctrineService,
    get_doctrine_service,

    # Cached functions
    fetch_all_doctrines_cached,
    fetch_ship_targets_cached,
    fetch_doctrine_fits_cached,
    build_fit_summary_cached,

    # Domain models
    FitItem,
    FitSummary,
    DoctrineData,
    FitStatus,
    ShipRole,

    # Ship categorization
    ShipRoleCategorizer,

    # Backwards compatibility
    create_fit_df,
    get_all_fit_data,
    get_target_from_fit_id,
)

__all__ = [
    # === Price Service ===
    'PriceService',
    'CachedPriceService',
    'get_price_service',

    # Price cached functions
    'fetch_jita_prices_cached',
    'fetch_janice_prices_cached',
    'fetch_local_prices_cached',

    # Price domain models
    'PriceResult',
    'BatchPriceResult',
    'FitCostAnalysis',
    'PriceSource',

    # Price providers
    'FuzzworkProvider',
    'JaniceProvider',
    'LocalMarketProvider',
    'FallbackPriceProvider',

    # Price backwards compatibility
    'get_jita_price',
    'get_multi_item_jita_price',
    'calculate_jita_fit_cost_and_delta',

    # === Doctrine Service ===
    'DoctrineService',
    'get_doctrine_service',

    # Doctrine cached functions
    'fetch_all_doctrines_cached',
    'fetch_ship_targets_cached',
    'fetch_doctrine_fits_cached',
    'build_fit_summary_cached',

    # Doctrine domain models
    'FitItem',
    'FitSummary',
    'DoctrineData',
    'FitStatus',
    'ShipRole',

    # Ship categorization
    'ShipRoleCategorizer',

    # Doctrine backwards compatibility
    'create_fit_df',
    'get_all_fit_data',
    'get_target_from_fit_id',
]
