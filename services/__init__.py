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

from services.pricer_service import (
    # Main service
    PricerService,
    get_pricer_service,
    # Supporting classes
    JitaPriceProvider,
    JitaPriceData,
    SDELookupService,
)

from services.low_stock_service import (
    # Main service
    LowStockService,
    get_low_stock_service,
    # Domain models
    LowStockFilters,
    LowStockItem,
    DoctrineFilterInfo,
    FitFilterInfo,
)

from services.selection_service import (
    # Main service
    SelectionService,
    get_selection_service,
    # Domain models
    SelectedItem,
    SelectionState,
    # Helpers
    get_status_filter_options,
    apply_status_filter,
    render_sidebar_selections,
)

from services.module_equivalents_service import (
    # Main service
    ModuleEquivalentsService,
    get_module_equivalents_service,
    # Domain models
    EquivalentModule,
    EquivalenceGroup,
)

from services.market_service import (
    # Main service
    MarketService,
    get_market_service,
)

from services.build_cost_service import (
    # Main service
    BuildCostService,
    get_build_cost_service,
    # Domain model
    BuildCostJob,
    # Constants
    PRICE_SOURCE_MAP,
)

from services.type_resolution_service import (
    # Main service
    TypeResolutionService,
    get_type_resolution_service,
)

__all__ = [
    # Price Service
    "PriceService",
    "get_price_service",
    "PriceResult",
    "BatchPriceResult",
    "FitCostAnalysis",
    "PriceSource",
    "FuzzworkProvider",
    "JaniceProvider",
    "LocalMarketProvider",
    "FallbackPriceProvider",
    "get_jita_price",
    "get_multi_item_jita_price",
    "calculate_jita_fit_cost_and_delta",
    # Doctrine Service
    "DoctrineService",
    "get_doctrine_service",
    "FitDataBuilder",
    "FitBuildResult",
    "BuildMetadata",
    "create_fit_df",
    # Categorization Service
    "ConfigBasedCategorizer",
    "get_ship_role_categorizer",
    "ShipRoleConfig",
    "categorize_ship_by_role",
    # Pricer Service
    "PricerService",
    "get_pricer_service",
    "JitaPriceProvider",
    "JitaPriceData",
    "SDELookupService",
    # Low Stock Service
    "LowStockService",
    "get_low_stock_service",
    "LowStockFilters",
    "LowStockItem",
    "DoctrineFilterInfo",
    "FitFilterInfo",
    # Selection Service
    "SelectionService",
    "get_selection_service",
    "SelectedItem",
    "SelectionState",
    "get_status_filter_options",
    "apply_status_filter",
    "render_sidebar_selections",
    # Module Equivalents Service
    "ModuleEquivalentsService",
    "get_module_equivalents_service",
    "EquivalentModule",
    "EquivalenceGroup",
    # Market Service
    "MarketService",
    "get_market_service",
    # Build Cost Service
    "BuildCostService",
    "get_build_cost_service",
    "BuildCostJob",
    "PRICE_SOURCE_MAP",
    # Type Resolution Service
    "TypeResolutionService",
    "get_type_resolution_service",
]
