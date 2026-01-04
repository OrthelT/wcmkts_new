"""
Doctrine Facade

Provides a simplified, unified API for Streamlit pages to interact with
the doctrine management system without needing to know about the underlying
service architecture.

This facade orchestrates:
- DoctrineRepository (database access)
- DoctrineService (business logic)
- PriceService (price lookups)
- ConfigBasedCategorizer (ship role categorization)

Design Goals:
1. Hide complexity - Pages don't need to know about multiple services
2. Simplify common operations - One method call instead of multiple service calls
3. Session state integration - Transparent caching via Streamlit
4. Type safety - Returns domain models (FitSummary, ModuleStock, etc.)

Example Usage:
```python
from facades import get_doctrine_facade

# Get facade (cached in session state)
facade = get_doctrine_facade()

# Get all fit summaries
summaries = facade.get_all_fit_summaries()

# Get critical fits
critical = facade.get_critical_fits()

# Get module stock
module = facade.get_module_stock("Damage Control II")

# Categorize a ship
role = facade.categorize_ship("Hurricane", 473)
```
"""

from typing import Optional
import logging
import streamlit as st
import pandas as pd

from config import DatabaseConfig
from domain import FitSummary, ModuleStock, Doctrine, ShipRole, StockStatus
from repositories import DoctrineRepository, get_doctrine_repository
from services import (
    DoctrineService,
    get_doctrine_service,
    PriceService,
    get_price_service,
)
from services.categorization import (
    ConfigBasedCategorizer,
    get_ship_role_categorizer,
)
from services.doctrine_service import FitBuildResult


class DoctrineFacade:
    """
    Facade providing simplified access to doctrine management operations.

    This class orchestrates multiple services to provide a clean,
    high-level API for Streamlit pages. It handles service lifecycle,
    caching, and provides methods that return typed domain models.

    ## Core Dependencies:
    - repository: DoctrineRepository for database access
    - doctrine_service: DoctrineService for business logic
    - price_service: PriceService for price operations
    - categorizer: ConfigBasedCategorizer for ship role categorization

    ## Method Categories:

    ### Fit Operations
    - get_all_fit_summaries() - Get all fits as domain models
    - get_fit_summary(fit_id) - Get specific fit by ID
    - get_fits_by_status(status) - Filter fits by stock status
    - get_critical_fits() - Shortcut for critical status fits
    - get_fit_name(fit_id) - Get display name for a fit
    - build_fit_data() - Build raw and summary DataFrames

    ### Module Operations
    - get_module_stock(name) - Get stock info for one module
    - get_modules_stock(names) - Get stock info for multiple modules

    ### Doctrine Operations
    - get_doctrine(name) - Get complete doctrine with all fits
    - get_all_doctrines() - Get all doctrine compositions
    - get_doctrine_lead_ship(doctrine_id) - Get lead ship type ID

    ### Ship Categorization
    - categorize_ship(ship_name, fit_id) - Categorize ship by role

    ### Price Operations
    - get_jita_price(type_id) - Get Jita price for an item
    - calculate_fit_jita_delta(fit_id) - Compare fit cost to Jita

    ### Bulk Operations
    - refresh_all_data() - Force rebuild of all cached data
    - clear_caches() - Clear all service caches

    ## Example Usage:
    ```python
    # Get facade from factory
    facade = get_doctrine_facade()

    # Get all fit summaries
    summaries = facade.get_all_fit_summaries()
    for fit in summaries:
        print(f"{fit.ship_name}: {fit.target_percentage}% ({fit.status.display_name})")

    # Get critical fits
    critical = facade.get_critical_fits()
    print(f"Found {len(critical)} critical fits")

    # Get module stock
    module = facade.get_module_stock("Damage Control II")
    print(f"{module.name}: {module.total_stock} in stock, {module.fits_available} fits")

    # Categorize ship
    role = facade.categorize_ship("Hurricane", 473)
    print(f"Role: {role.display_name} ({role.display_emoji})")
    ```
    """

    def __init__(
        self,
        repository: Optional[DoctrineRepository] = None,
        doctrine_service: Optional[DoctrineService] = None,
        price_service: Optional[PriceService] = None,
        categorizer: Optional[ConfigBasedCategorizer] = None,
        db_config: Optional[DatabaseConfig] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the facade with optional service dependencies.

        Services can be injected for testing or will be lazily created
        using their factory functions.

        Args:
            repository: Optional DoctrineRepository (lazy-created if None)
            doctrine_service: Optional DoctrineService (lazy-created if None)
            price_service: Optional PriceService (lazy-created if None)
            categorizer: Optional ConfigBasedCategorizer (lazy-created if None)
            db_config: Optional DatabaseConfig (created if None and needed)
            logger: Optional logger instance
        """
        self._repository = repository
        self._doctrine_service = doctrine_service
        self._price_service = price_service
        self._categorizer = categorizer
        self._db_config = db_config or DatabaseConfig("wcmkt")
        self._logger = logger or logging.getLogger(__name__)

    # =========================================================================
    # Property Accessors - Lazy Service Creation
    # =========================================================================

    @property
    def repository(self) -> DoctrineRepository:
        """Get repository, creating it if needed."""
        if self._repository is None:
            self._repository = get_doctrine_repository()
        return self._repository

    @property
    def doctrine_service(self) -> DoctrineService:
        """Get doctrine service, creating it if needed."""
        if self._doctrine_service is None:
            self._doctrine_service = get_doctrine_service()
        return self._doctrine_service

    @property
    def price_service(self) -> PriceService:
        """Get price service, creating it if needed."""
        if self._price_service is None:
            self._price_service = get_price_service()
        return self._price_service

    @property
    def categorizer(self) -> ConfigBasedCategorizer:
        """Get categorizer, creating it if needed."""
        if self._categorizer is None:
            self._categorizer = get_ship_role_categorizer()
        return self._categorizer

    # =========================================================================
    # Fit Operations
    # =========================================================================

    def get_all_fit_summaries(self) -> list[FitSummary]:
        """
        Get all doctrine fit summaries as domain models.

        Returns:
            List of FitSummary domain models with computed properties
            (status, target_percentage, etc.)

        Example:
            ```python
            summaries = facade.get_all_fit_summaries()
            for fit in summaries:
                print(f"{fit.ship_name}: {fit.fits} fits available")
            ```
        """
        return self.doctrine_service.get_all_fit_summaries()

    def get_fit_summary(self, fit_id: int) -> Optional[FitSummary]:
        """
        Get a specific fit summary by ID.

        Args:
            fit_id: The fit ID to retrieve

        Returns:
            FitSummary domain model or None if not found

        Example:
            ```python
            fit = facade.get_fit_summary(473)
            if fit:
                print(f"Status: {fit.status.display_name}")
            ```
        """
        return self.doctrine_service.get_fit_summary(fit_id)

    def get_fits_by_status(self, status: StockStatus) -> list[FitSummary]:
        """
        Get all fits matching a specific stock status.

        Args:
            status: StockStatus enum value (CRITICAL, NEEDS_ATTENTION, GOOD)

        Returns:
            List of FitSummary domain models matching the status

        Example:
            ```python
            from domain import StockStatus
            critical = facade.get_fits_by_status(StockStatus.CRITICAL)
            print(f"Found {len(critical)} critical fits")
            ```
        """
        return self.doctrine_service.get_fits_by_status(status)

    def get_critical_fits(self) -> list[FitSummary]:
        """
        Get all fits with critical stock status (≤40% of target).

        Convenience method equivalent to get_fits_by_status(StockStatus.CRITICAL).

        Returns:
            List of critical FitSummary domain models

        Example:
            ```python
            critical = facade.get_critical_fits()
            for fit in critical:
                print(f"⚠️ {fit.ship_name}: {fit.target_percentage}%")
            ```
        """
        return self.doctrine_service.get_critical_fits()

    def get_fit_name(self, fit_id: int) -> str:
        """
        Get the display name for a fit.

        Args:
            fit_id: The fit ID to look up

        Returns:
            Fit display name or "Unknown Fit" if not found

        Example:
            ```python
            name = facade.get_fit_name(473)
            print(name)  # "WC-EN Shield DPS FNI v1.0"
            ```
        """
        return self.repository.get_fit_name(fit_id)

    def get_target_by_fit_id(self, fit_id: int) -> int:
        """
        Get the ship target for a specific fit ID.

        Args:
            fit_id: The fit ID to look up

        Returns:
            Target quantity or DEFAULT_SHIP_TARGET (20) if not found

        Example:
            ```python
            target = facade.get_target_by_fit_id(473)
            print(f"Target: {target}")  # "Target: 50"
            ```
        """
        return self.repository.get_target_by_fit_id(fit_id)

    def get_target_by_ship_id(self, ship_id: int) -> int:
        """
        Get the ship target for a specific ship ID.

        Args:
            ship_id: The ship type ID to look up

        Returns:
            Target quantity or DEFAULT_SHIP_TARGET (20) if not found

        Example:
            ```python
            target = facade.get_target_by_ship_id(638)  # Ferox
            print(f"Target: {target}")
            ```
        """
        return self.repository.get_target_by_ship_id(ship_id)

    def build_fit_data(self, use_cache: bool = True) -> FitBuildResult:
        """
        Build raw and summary DataFrames for all fits.

        This method runs the full FitDataBuilder pipeline to create
        both raw (item-level) and summary (fit-level) DataFrames.

        Args:
            use_cache: If True, return cached result if available

        Returns:
            FitBuildResult with raw_df, summary_df, summaries, and metadata

        Example:
            ```python
            result = facade.build_fit_data()
            print(f"Built {result.metadata.summary_row_count} fits")
            result.print_metadata()
            ```
        """
        if use_cache:
            return self.doctrine_service.build_fit_data()
        else:
            return self.doctrine_service.refresh()

    # =========================================================================
    # Module Operations
    # =========================================================================

    def get_module_stock(self, module_name: str) -> Optional[ModuleStock]:
        """
        Get stock information for a specific module.

        Args:
            module_name: Name of the module to look up

        Returns:
            ModuleStock domain model or None if not found

        Example:
            ```python
            module = facade.get_module_stock("Damage Control II")
            if module:
                print(f"{module.name}: {module.total_stock} in stock")
                print(f"Status: {module.status.display_name}")
            ```
        """
        return self.repository.get_module_stock(module_name)

    def get_modules_stock(self, module_names: list[str]) -> dict[str, ModuleStock]:
        """
        Get stock information for multiple modules.

        Args:
            module_names: List of module names to look up

        Returns:
            Dict mapping module name to ModuleStock domain model
            (excludes not-found modules)

        Example:
            ```python
            modules = facade.get_modules_stock([
                "Damage Control II",
                "Medium Shield Extender II",
                "Ballistic Control System II"
            ])
            for name, module in modules.items():
                print(f"{name}: {module.fits_on_mkt} fits")
            ```
        """
        return self.repository.get_multiple_module_stocks(module_names)

    # =========================================================================
    # Doctrine Operations
    # =========================================================================

    def get_doctrine(self, doctrine_name: str) -> Optional[Doctrine]:
        """
        Get a complete doctrine with all its fits.

        Args:
            doctrine_name: Name of the doctrine (e.g., "SUBS - WC Hurricane")

        Returns:
            Doctrine domain model or None if not found

        Example:
            ```python
            doctrine = facade.get_doctrine("SUBS - WC Hurricane")
            if doctrine:
                print(f"{doctrine.name}: {len(doctrine.fits)} fits")
                for fit in doctrine.fits:
                    print(f"  - {fit.ship_name}")
            ```
        """
        return self.repository.get_doctrine(doctrine_name)

    def get_all_doctrines(self) -> pd.DataFrame:
        """
        Get all doctrine compositions from the database.

        Returns:
            DataFrame with columns: doctrine_id, doctrine_name, fit_id, ship_name, etc.

        Example:
            ```python
            doctrines_df = facade.get_all_doctrines()
            unique_doctrines = doctrines_df['doctrine_name'].unique()
            ```
        """
        return self.repository.get_all_doctrine_compositions()

    def get_doctrine_lead_ship(self, doctrine_id: int) -> Optional[int]:
        """
        Get the lead ship type ID for a doctrine.

        Args:
            doctrine_id: The doctrine ID to look up

        Returns:
            Type ID of the lead ship or None if not found

        Example:
            ```python
            lead_ship_id = facade.get_doctrine_lead_ship(5)
            if lead_ship_id:
                print(f"Lead ship type ID: {lead_ship_id}")
            ```
        """
        return self.repository.get_doctrine_lead_ship(doctrine_id)

    # =========================================================================
    # Ship Categorization
    # =========================================================================

    def categorize_ship(self, ship_name: str, fit_id: int) -> ShipRole:
        """
        Categorize a ship by its functional role.

        Uses the ConfigBasedCategorizer to determine if a ship is
        DPS, Logi, Links, or Support based on configuration and keywords.

        Args:
            ship_name: Name of the ship
            fit_id: Fit ID (for special case handling)

        Returns:
            ShipRole enum value (DPS, LOGI, LINKS, SUPPORT)

        Example:
            ```python
            role = facade.categorize_ship("Hurricane", 473)
            print(f"{role.display_emoji} {role.display_name}")  # "💥 DPS"
            print(f"Description: {role.description}")
            print(f"Color: {role.display_color}")
            ```
        """
        return self.categorizer.categorize(ship_name, fit_id)

    # =========================================================================
    # Price Operations
    # =========================================================================

    def get_jita_price(self, type_id: int) -> float:
        """
        Get the Jita sell price for an item.

        Args:
            type_id: EVE Online type ID

        Returns:
            Jita sell price or 0.0 if unavailable

        Example:
            ```python
            price = facade.get_jita_price(2048)  # Damage Control II
            print(f"Price: {price:,.2f} ISK")
            ```
        """
        result = self.price_service.get_jita_price(type_id)
        return result.price

    def calculate_fit_jita_delta(self, fit_id: int) -> float:
        """
        Calculate the difference between fit build cost and Jita cost.

        Compares the total cost of building a fit from current stock prices
        against the cost of buying all items at Jita prices.

        Args:
            fit_id: The fit ID to analyze

        Returns:
            Delta in ISK (positive means Jita is more expensive)

        Example:
            ```python
            delta = facade.calculate_fit_jita_delta(473)
            if delta > 0:
                print(f"Savings: {delta:,.2f} ISK vs Jita")
            else:
                print(f"Premium: {abs(delta):,.2f} ISK vs Jita")
            ```
        """
        deltas = self.doctrine_service.calculate_all_jita_deltas()
        return deltas.get(fit_id, 0.0)

    def calculate_all_jita_deltas(self) -> dict[int, float]:
        """
        Calculate Jita deltas for all fits.

        Returns:
            Dictionary mapping fit_id to delta (ISK)

        Example:
            ```python
            deltas = facade.calculate_all_jita_deltas()
            for fit_id, delta in deltas.items():
                name = facade.get_fit_name(fit_id)
                print(f"{name}: {delta:,.2f} ISK delta")
            ```
        """
        return self.doctrine_service.calculate_all_jita_deltas()

    # =========================================================================
    # Bulk Operations
    # =========================================================================

    def refresh_all_data(self) -> FitBuildResult:
        """
        Force a complete rebuild of all cached fit data.

        Clears caches and rebuilds from the database. Use this when
        you know the underlying data has changed.

        Returns:
            FitBuildResult with fresh data and metadata

        Example:
            ```python
            result = facade.refresh_all_data()
            print(f"Refreshed {result.metadata.summary_row_count} fits")
            result.print_metadata()
            ```
        """
        return self.doctrine_service.refresh()

    def clear_caches(self) -> None:
        """
        Clear all service-level caches.

        Useful when you want to force fresh data on the next operation
        without immediately rebuilding.

        Example:
            ```python
            facade.clear_caches()
            # Next operation will fetch fresh data
            summaries = facade.get_all_fit_summaries()
            ```
        """
        self.doctrine_service.clear_cache()
        self._logger.info("Cleared all facade caches")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_fit_items(self, fit_id: int) -> list:
        """
        Get all items (modules, hulls, etc.) for a specific fit.

        Args:
            fit_id: The fit ID to retrieve items for

        Returns:
            List of FitItem domain models

        Example:
            ```python
            items = facade.get_fit_items(473)
            for item in items:
                print(f"{item.name} x{item.quantity}: {item.price:,.2f} ISK")
            ```
        """
        return self.repository.get_fit_items(fit_id)


# =============================================================================
# Factory Function - Streamlit Session State Integration
# =============================================================================


def get_doctrine_facade(
    db_config: Optional[DatabaseConfig] = None,
    logger: Optional[logging.Logger] = None,
    use_session_state: bool = True,
) -> DoctrineFacade:
    """
    Get or create a DoctrineFacade instance with optional session state caching.

    This factory function provides the recommended way to instantiate the facade
    in Streamlit applications. By default, it caches the facade in session state
    to avoid recreating services on every rerun.

    Args:
        db_config: Optional DatabaseConfig (defaults to "wcmkt" database)
        logger: Optional logger instance
        use_session_state: If True, cache facade in st.session_state

    Returns:
        DoctrineFacade instance (cached or new)

    Example:
        ```python
        # In a Streamlit page
        facade = get_doctrine_facade()
        summaries = facade.get_all_fit_summaries()
        ```

    Session State Key:
        The facade is stored in st.session_state['doctrine_facade']
    """
    if use_session_state and hasattr(st, "session_state"):
        # Use Streamlit session state if available
        if "doctrine_facade" not in st.session_state:
            st.session_state.doctrine_facade = DoctrineFacade(
                db_config=db_config,
                logger=logger,
            )
        return st.session_state.doctrine_facade
    else:
        # Create new instance (useful for testing or non-Streamlit contexts)
        return DoctrineFacade(
            db_config=db_config,
            logger=logger,
        )
