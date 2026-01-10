"""
Domain Models Package

This package contains the core domain models for the doctrine module.
These dataclasses provide typed, immutable structures that replace
raw DataFrame passing throughout the codebase.

Key Components:
- Enums: StockStatus, ShipRole for categorical data
- Models: FitItem, FitSummary, ModuleStock, Doctrine
- Pricer: ParsedItem, PricedItem, PricerResult for pricing feature
"""

from domain.enums import StockStatus, ShipRole
from domain.models import (
    FitItem,
    FitSummary,
    ModuleStock,
    ModuleUsage,
    Doctrine,
    ShipStock,
)
from domain.pricer import (
    InputFormat,
    SlotType,
    ParsedItem,
    PricedItem,
    PricerResult,
    LocalPriceData,
)

__all__ = [
    # Enums
    "StockStatus",
    "ShipRole",
    # Models
    "FitItem",
    "FitSummary",
    "ModuleStock",
    "ModuleUsage",
    "Doctrine",
    "ShipStock",
    # Pricer
    "InputFormat",
    "SlotType",
    "ParsedItem",
    "PricedItem",
    "PricerResult",
    "LocalPriceData",
]
