"""
Repository Layer Package

This package contains repository classes that encapsulate all database access
for the doctrine module. Repositories provide a clean abstraction over the
database, making the code more testable and maintainable.

Key Components:
- DoctrineRepository: All doctrine-related database operations
"""

from repositories.doctrine_repo import DoctrineRepository, get_doctrine_repository

__all__ = [
    "DoctrineRepository",
    "get_doctrine_repository",
]
