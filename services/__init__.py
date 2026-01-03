"""
Services Package

This package contains service modules that implement business logic
using clean architecture patterns.

Each service module follows these principles:
1. Single Responsibility - one domain per service
2. Dependency Injection - dependencies passed in, not created
3. Protocol/ABC - interfaces for testability
4. Dataclasses - structured domain models
"""

from services.price_service import (
    # Main service
    PriceService,
    get_price_service,

    # Domain models
    PriceResult,
    BatchPriceResult,
    FitCostAnalysis,
    PriceSource,

    # Providers (for custom configuration)
    FuzzworkProvider,
    JaniceProvider,
    LocalMarketProvider,
    FallbackPriceProvider,

    # Backwards compatibility
    get_jita_price,
    get_multi_item_jita_price,
    calculate_jita_fit_cost_and_delta,
)

__all__ = [
    # Main service
    'PriceService',
    'get_price_service',

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
