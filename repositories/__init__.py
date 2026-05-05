"""
Repository Layer Package

This package contains repository classes that encapsulate all database access.
Repositories provide a clean abstraction over the database, making the code
more testable and maintainable.

Key Components:
- BaseRepository: Foundation class with read_df() and malformed-DB recovery
- DoctrineRepository: All doctrine-related database operations
- MarketRepository: Market stats, orders, and history with targeted cache invalidation
- MarketOrdersRepository: Market order aggregation for Pricer feature
- BuildCostRepository: Structures, rigs, and industry indices
- SDERepository: Static Data Export lookups (types, groups, categories)
"""

from repositories.base import BaseRepository
from repositories.doctrine_repo import DoctrineRepository, get_doctrine_repository
from repositories.market_repo import (
    MarketRepository,
    get_market_repository,
    invalidate_market_caches,
    get_update_time,
)
from repositories.market_orders_repo import MarketOrdersRepository, get_market_orders_repository
from repositories.build_cost_repo import (
    BuildCostRepository,
    get_build_cost_repository,
    invalidate_build_cost_caches,
    invalidate_structure_caches,
)
from repositories.sde_repo import SDERepository, get_sde_repository

__all__ = [
    "BaseRepository",
    "DoctrineRepository",
    "get_doctrine_repository",
    "MarketRepository",
    "get_market_repository",
    "invalidate_market_caches",
    "get_update_time",
    "MarketOrdersRepository",
    "get_market_orders_repository",
    "BuildCostRepository",
    "get_build_cost_repository",
    "invalidate_build_cost_caches",
    "invalidate_structure_caches",
    "SDERepository",
    "get_sde_repository",
]
