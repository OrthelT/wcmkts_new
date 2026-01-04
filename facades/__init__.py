"""
Facade Layer

Provides simplified, high-level interfaces for Streamlit pages,
hiding the complexity of orchestrating multiple services.

Patterns Applied:
1. Facade Pattern - Single entry point to complex subsystems
2. Dependency Injection - Services injected or lazily created
3. Session State Integration - Leverages Streamlit caching
4. Factory Functions - Simplified instantiation

Main Components:
- DoctrineFacade: Unified interface for doctrine operations
- get_doctrine_facade(): Factory function with session state integration
"""

from facades.doctrine_facade import DoctrineFacade, get_doctrine_facade

__all__ = [
    'DoctrineFacade',
    'get_doctrine_facade',
]
