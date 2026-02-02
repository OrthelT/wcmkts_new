"""
Repository Layer Package

This package contains repository classes that encapsulate all database access.
Repositories provide a clean abstraction over the database, making the code
more testable and maintainable.

Key Components:
- BaseRepository: Foundation class with read_df() and malformed-DB recovery
- DoctrineRepository: All doctrine-related database operations
- MarketOrdersRepository: Market order aggregation for Pricer feature
"""

from repositories.base import BaseRepository
from repositories.doctrine_repo import DoctrineRepository, get_doctrine_repository
from repositories.market_orders_repo import MarketOrdersRepository, get_market_orders_repository

__all__ = [
    "BaseRepository",
    "DoctrineRepository",
    "get_doctrine_repository",
    "MarketOrdersRepository",
    "get_market_orders_repository",
]
