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

from services.doctrine_service import (
    # Main service
    DoctrineService,
    get_doctrine_service,

    # Builder
    FitDataBuilder,
    FitBuildResult,
    BuildMetadata,

    # Backwards compatibility
    create_fit_df,
)

from services.categorization import (
    # Main service
    ConfigBasedCategorizer,
    get_ship_role_categorizer,

    # Configuration
    ShipRoleConfig,

    # Backwards compatibility
    categorize_ship_by_role,
)

__all__ = [
    # Price Service
    'PriceService',
    'get_price_service',
    'PriceResult',
    'BatchPriceResult',
    'FitCostAnalysis',
    'PriceSource',
    'FuzzworkProvider',
    'JaniceProvider',
    'LocalMarketProvider',
    'FallbackPriceProvider',
    'get_jita_price',
    'get_multi_item_jita_price',
    'calculate_jita_fit_cost_and_delta',

    # Doctrine Service
    'DoctrineService',
    'get_doctrine_service',
    'FitDataBuilder',
    'FitBuildResult',
    'BuildMetadata',
    'create_fit_df',

    # Categorization Service
    'ConfigBasedCategorizer',
    'get_ship_role_categorizer',
    'ShipRoleConfig',
    'categorize_ship_by_role',
]
