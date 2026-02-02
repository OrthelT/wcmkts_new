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
]
