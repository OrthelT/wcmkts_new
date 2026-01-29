"""
Doctrine Repository

Encapsulates all database access for doctrine-related data.
Consolidates queries scattered across:
- doctrines.py (get_all_fit_data, get_target_from_fit_id, new_get_targets)
- doctrine_status.py (get_fit_name, get_ship_target, get_module_stock_list)
- doctrine_report.py (get_fit_name_from_db, get_doctrine_lead_ship, get_module_stock_list)

Design Principles:
1. Single Responsibility - Only database access, no business logic
2. Dependency Injection - Receives DatabaseConfig, doesn't create it
3. Consistent return types - Returns DataFrames or Optional values
4. Error handling - Logs errors and provides sensible defaults
"""

from typing import Optional
import logging
import pandas as pd
from sqlalchemy import text

from config import DatabaseConfig, DEFAULT_SHIP_TARGET
from domain import FitItem, FitSummary, ModuleStock, ModuleUsage, Doctrine, ShipStock
import streamlit as st
from logging_config import setup_logging
logger = setup_logging(__name__, log_file="doctrine_repo.log")

class DoctrineRepository:
    """
    Repository for all doctrine-related database operations.

    Centralizes database queries that were previously scattered across
    multiple files, eliminating duplication and providing a single
    source of truth for data access patterns.

    ## Attributes:
    - `db`: DatabaseConfig instance for the market database
    - `logger`: Optional logger instance

    ## Helper Methods:
    - `get_methods(print_methods: bool = False)`: Get all methods of the DoctrineRepository class

    ## All Methods:
    - `get_all_fits()`: Get all fit data from the doctrines table
    - `get_fit_by_id(fit_id)`: Get all items for a specific fit
    - `get_fits_by_type_id(type_id)`: Get all fits containing a specific type
    - `get_all_targets()`: Get all ship targets
    - `get_target_by_fit_id(fit_id)`: Get target stock level for a specific fit
    - `get_target_by_ship_id(ship_id)`: Get target stock level for a specific ship type
    - `get_fit_name(fit_id)`: Get the display name for a fit
    - `get_all_doctrine_compositions()`: Get all doctrine compositions
    - `get_doctrine_fit_ids(doctrine_name)`: Get all fit IDs belonging to a specific doctrine
    - `get_doctrine_lead_ship(doctrine_id)`: Get the lead ship type ID for a doctrine
    - `get_module_stock_info(module_name)`: Get stock information for a specific module
    - `get_module_usage(module_name)`: Get usage information for a module
    - `get_module_stock(module_name)`: Get complete module stock information as a domain model
    - `get_multiple_module_stocks(module_names)`: Get stock information for multiple modules
    - `get_ship_stock(ship_name)`: Get stock information for a specific ship hull
    - `get_multiple_ship_stocks(ship_names)`: Get stock information for multiple ships
    - `get_avg_prices(type_ids)`: Get average prices for multiple type IDs from marketstats
    - `get_fit_items(fit_id)`: Get all items for a fit as domain models
    - `get_doctrine(doctrine_name)`: Get a complete Doctrine domain model

    ## Example usage:
    ```python
        db = DatabaseConfig("wcmkt")
        repo = DoctrineRepository(db)

        # Get all fit data
        fits_df = repo.get_all_fits()

        # Get target for a specific fit
        target = repo.get_target_by_fit_id(123)

        # Get module stock info
        module = repo.get_module_stock("Damage Control II")
    """

    def __init__(self, db: DatabaseConfig, logger: Optional[logging.Logger] = None):
        """
        Initialize repository with database configuration.

        Args:
            db: DatabaseConfig instance for the market database
            logger: Optional logger instance
        """
        self._db = db
        self._logger = logger or logging.getLogger(__name__)

    # =========================================================================
    # Core Fit Data
    # =========================================================================
    # Moved to outer scope to facilitate caching

    def get_all_fits(self) -> pd.DataFrame:
        return get_all_fits_with_cache()

    def get_fit_by_id(self, fit_id: int) -> pd.DataFrame:
        return get_fit_by_id_with_cache(fit_id)

    def get_all_targets(self) -> pd.DataFrame:
        return get_all_targets_with_cache()

    def get_target_by_fit_id(self, fit_id: int, default: int = DEFAULT_SHIP_TARGET) -> int:
        return get_target_by_fit_id_with_cache(fit_id, default)

    def get_target_by_ship_id(self, ship_id: int, default: int = DEFAULT_SHIP_TARGET) -> int:
        return get_target_by_ship_id_with_cache(ship_id, default)
    # =========================================================================
    # Fit Names
    # =========================================================================

    def get_fit_name(self, fit_id: int, default: str = "Unknown Fit") -> str:
        return get_fit_name_with_cache(fit_id, default)

    # =========================================================================
    # Doctrine Compositions
    # =========================================================================

    def get_all_doctrine_compositions(self) -> pd.DataFrame:
        """
        Get all doctrine compositions (fleet compositions).

        Replaces: doctrine_report.py SELECT * FROM doctrine_fits

        Returns:
            DataFrame with columns: doctrine_id, doctrine_name, fit_id
        """
        query = "SELECT * FROM doctrine_fits"

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            self._logger.error(f"Failed to get doctrine compositions: {e}")
            return pd.DataFrame()

    def get_doctrine_fit_ids(self, doctrine_name: str) -> list[int]:
        """
        Get all fit IDs belonging to a specific doctrine.

        Args:
            doctrine_name: Name of the doctrine

        Returns:
            List of fit IDs in this doctrine
        """
        df = self.get_all_doctrine_compositions()
        if df.empty:
            return []

        filtered = df[df['doctrine_name'] == doctrine_name]
        return filtered['fit_id'].unique().tolist()

    def get_doctrine_lead_ship(self, doctrine_id: int) -> Optional[int]:
        """
        Get the lead ship type ID for a doctrine.

        Replaces: doctrine_report.py:get_doctrine_lead_ship()

        Args:
            doctrine_id: The doctrine ID

        Returns:
            Lead ship type ID, or None if not found
        """
        query = text("SELECT lead_ship FROM lead_ships WHERE doctrine_id = :doctrine_id")

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn, params={"doctrine_id": doctrine_id})

            if not df.empty and pd.notna(df.loc[0, 'lead_ship']):
                return int(df.loc[0, 'lead_ship'])
            return None

        except Exception as e:
            self._logger.error(f"Failed to get lead ship for doctrine {doctrine_id}: {e}")
            return None

    # =========================================================================
    # Module Stock
    # =========================================================================

    def get_module_stock_with_equivalents(self, module_name: str) -> pd.DataFrame:
        """
        Get stock information for a module, including equivalent modules.

        For modules with equivalents (e.g., faction hardeners), returns
        the combined stock across all equivalent modules.

        Args:
            module_name: Name of the module

        Returns:
            DataFrame with type_name, type_id, total_stock (aggregated),
            fits_on_mkt (recalculated based on combined stock)
        """
        from services.module_equivalents_service import get_module_equivalents_service

        # Get basic stock info
        stock_df = self.get_module_stock_info(module_name)
        if stock_df.empty:
            return stock_df

        type_id = int(stock_df.iloc[0]['type_id'])

        # Check for equivalents
        equiv_service = get_module_equivalents_service()
        if not equiv_service.has_equivalents(type_id):
            return stock_df

        # Get equivalence group with all stock info
        group = equiv_service.get_equivalence_group(type_id)
        if not group:
            return stock_df

        # Update the stock with combined value
        result = stock_df.copy()
        result['total_stock'] = group.total_stock
        result['has_equivalents'] = True
        result['equivalent_count'] = len(group.modules)

        return result

    def get_equivalent_modules_stock(self, type_id: int) -> list[dict]:
        """
        Get stock information for all equivalent modules.

        Args:
            type_id: EVE type ID of any module in the equivalence group

        Returns:
            List of dicts with type_id, type_name, stock, price for each
            equivalent module, or empty list if no equivalents
        """
        from services.module_equivalents_service import get_module_equivalents_service

        equiv_service = get_module_equivalents_service()
        group = equiv_service.get_equivalence_group(type_id)

        if not group:
            return []

        return [
            {
                'type_id': m.type_id,
                'type_name': m.type_name,
                'stock': m.stock,
                'price': m.price,
            }
            for m in group.modules
        ]

    def get_module_stock_info(self, module_name: str) -> pd.DataFrame:
        """
        Get stock information for a specific module.

        Replaces queries in:
        - doctrine_status.py:get_module_stock_list()
        - doctrine_report.py:get_module_stock_list()

        Args:
            module_name: Name of the module

        Returns:
            DataFrame with type_name, type_id, total_stock, fits_on_mkt
        """
        query = text("""
            SELECT type_name, type_id, total_stock, fits_on_mkt
            FROM doctrines
            WHERE type_name = :module_name
            LIMIT 1
        """)

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    return pd.read_sql_query(query, conn, params={"module_name": module_name})
        except Exception as e:
            self._logger.error(f"Failed to get module stock for {module_name}: {e}")
            return pd.DataFrame()

    def get_module_usage(self, module_name: str) -> pd.DataFrame:
        """
        Get usage information for a module (which fits use it).

        Replaces: doctrine_status.py usage query in get_module_stock_list()

        Args:
            module_name: Name of the module

        Returns:
            DataFrame with ship_name, ship_target, fit_qty
        """
        query = text("""
            SELECT st.ship_name, st.ship_target, d.fit_qty
            FROM doctrines d
            JOIN ship_targets st ON d.fit_id = st.fit_id
            WHERE d.type_name = :module_name
        """)

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    return pd.read_sql_query(query, conn, params={"module_name": module_name})
        except Exception as e:
            self._logger.error(f"Failed to get module usage for {module_name}: {e}")
            return pd.DataFrame()

    def get_module_stock(self, module_name: str) -> Optional[ModuleStock]:
        """
        Get complete module stock information as a domain model.

        Combines stock and usage queries into a single ModuleStock object.

        Args:
            module_name: Name of the module

        Returns:
            ModuleStock instance, or None if not found
        """
        stock_df = self.get_module_stock_info(module_name)
        if stock_df.empty:
            return None

        usage_df = self.get_module_usage(module_name)

        return ModuleStock.from_query_results(stock_df.iloc[0], usage_df)

    def get_multiple_module_stocks(self, module_names: list[str]) -> dict[str, ModuleStock]:
        """
        Get stock information for multiple modules.

        More efficient than calling get_module_stock() in a loop when
        you need data for many modules.

        Args:
            module_names: List of module names

        Returns:
            Dict mapping module name to ModuleStock
        """
        result = {}
        for name in module_names:
            stock = self.get_module_stock(name)
            if stock:
                result[name] = stock
        return result

    # =========================================================================
    # Ship Stock
    # =========================================================================

    def get_ship_stock(self, ship_name: str) -> Optional[ShipStock]:
        """
        Get stock information for a specific ship hull.

        Handles ships with multiple fits by using preferred_fits configuration
        from settings.toml. Falls back to first available fit if not configured.

        Args:
            ship_name: Name of the ship (e.g., "Hurricane Fleet Issue")

        Returns:
            ShipStock domain model, or None if not found
        """
        preferred_fits = _load_preferred_fits()
        preferred_fit_id = preferred_fits.get(ship_name)

        # Build query with optional fit_id filter
        if preferred_fit_id:
            query = text("""
                SELECT type_name, type_id, total_stock, fits_on_mkt, fit_id
                FROM doctrines
                WHERE type_name = :ship_name AND fit_id = :fit_id
                LIMIT 1
            """)
            params = {"ship_name": ship_name, "fit_id": preferred_fit_id}
        else:
            query = text("""
                SELECT type_name, type_id, total_stock, fits_on_mkt, fit_id
                FROM doctrines
                WHERE type_name = :ship_name
                LIMIT 1
            """)
            params = {"ship_name": ship_name}

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn, params=params)

            if df.empty:
                self._logger.warning(f"No stock data found for ship: {ship_name}")
                return None

            row = df.iloc[0]

            # Validate required fields
            if pd.isna(row.get('total_stock')) or pd.isna(row.get('type_id')):
                self._logger.warning(f"Invalid stock data for ship: {ship_name}")
                return None

            # Get target from ship_id
            ship_id = int(row['type_id'])
            ship_target = self.get_target_by_ship_id(ship_id)

            return ShipStock.from_query_result(row, ship_target=ship_target)

        except Exception as e:
            self._logger.error(f"Failed to get ship stock for {ship_name}: {e}")
            return None

    def get_multiple_ship_stocks(self, ship_names: list[str]) -> dict[str, ShipStock]:
        """
        Get stock information for multiple ships.

        Args:
            ship_names: List of ship names

        Returns:
            Dict mapping ship name to ShipStock
        """
        result = {}
        for name in ship_names:
            stock = self.get_ship_stock(name)
            if stock:
                result[name] = stock
        return result

    # =========================================================================
    # Market Stats (for price fallback)
    # =========================================================================

    def get_avg_prices(self, type_ids: list[int]) -> dict[int, float]:
        """
        Get average prices for multiple type IDs from marketstats.

        Replaces: doctrines.py avg_price query in create_fit_df()

        Args:
            type_ids: List of type IDs

        Returns:
            Dict mapping type_id to avg_price
        """
        if not type_ids:
            return {}

        placeholders = ','.join(['?' for _ in type_ids])
        query = f"SELECT type_id, avg_price FROM marketstats WHERE type_id IN ({placeholders})"

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn, params=tuple(type_ids))

            return dict(zip(df['type_id'], df['avg_price']))

        except Exception as e:
            self._logger.error(f"Failed to get avg prices: {e}")
            return {}

    # =========================================================================
    # Domain Model Builders
    # =========================================================================

    def get_fit_items(self, fit_id: int) -> list[FitItem]:
        """
        Get all items for a fit as domain models.

        Args:
            fit_id: The fit ID

        Returns:
            List of FitItem instances
        """
        df = self.get_fit_by_id(fit_id)
        if df.empty:
            return []

        return [FitItem.from_dataframe_row(row) for _, row in df.iterrows()]

    def get_doctrine(self, doctrine_name: str) -> Optional[Doctrine]:
        """
        Get a complete Doctrine domain model.

        Args:
            doctrine_name: Name of the doctrine

        Returns:
            Doctrine instance, or None if not found
        """
        compositions_df = self.get_all_doctrine_compositions()
        if compositions_df.empty:
            return None

        doctrine_rows = compositions_df[compositions_df['doctrine_name'] == doctrine_name]
        if doctrine_rows.empty:
            return None

        first_row = doctrine_rows.iloc[0]
        doctrine_id = int(first_row['doctrine_id'])
        fit_ids = doctrine_rows['fit_id'].unique().tolist()
        lead_ship_id = self.get_doctrine_lead_ship(doctrine_id)

        return Doctrine.from_dataframe(
            first_row,
            fit_ids=fit_ids,
            lead_ship_id=lead_ship_id
        )
    def get_methods(self) -> list[str]:
        """
        Get list of all public method names in the DoctrineRepository.

        Returns:
            List of method names (excluding private methods starting with '_')

        Example:
            >>> repo = DoctrineRepository(db)
            >>> methods = repo.get_methods()
            >>> print(methods)
            ['get_all_fits', 'get_fit_by_id', 'get_all_targets', ...]
        """
        return [attr for attr in dir(DoctrineRepository) if not attr.startswith("_")]

    def print_methods(self) -> None:
        """
        Print all public methods with their documentation.

        Useful for exploring the repository API.

        Example:
            >>> repo = DoctrineRepository(db)
            >>> repo.print_methods()
            get_all_fits: Get all fit data from the doctrines table...
            ----------------------------------------
            get_fit_by_id: Get all items for a specific fit...
            ----------------------------------------
        """
        for method_name in self.get_methods():
            method = getattr(DoctrineRepository, method_name)
            doc = method.__doc__ if method.__doc__ else 'No documentation'
            print(f"{method_name}: {doc}")
            print("----------------------------------------")

# =============================================================================
# Configuration Loaders
# =============================================================================

@st.cache_data(ttl=3600)
def _load_preferred_fits() -> dict[str, int]:
    """
    Load preferred fit mappings from settings.toml.

    Maps ship names to their preferred fit_id for ships with multiple fits.
    Cached for 1 hour.

    Returns:
        Dict mapping ship_name -> fit_id
    """
    import tomllib
    from pathlib import Path

    try:
        settings_path = Path("settings.toml")
        if not settings_path.exists():
            logger.warning("settings.toml not found, no preferred fits configured")
            return {}

        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        return settings.get("preferred_fits", {})

    except Exception as e:
        logger.error(f"Failed to load preferred fits from settings.toml: {e}")
        return {}


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_doctrine_repository() -> DoctrineRepository:
    """
    Get or create a DoctrineRepository instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.

    Example:
        from repositories import get_doctrine_repository

        repo = get_doctrine_repository()
        fits = repo.get_all_fits()
    """
    logger.debug("Getting DoctrineRepository")

    def _create_doctrine_repository() -> DoctrineRepository:
        logger.debug("Creating DoctrineRepository instance")
        db = DatabaseConfig("wcmkt")
        return DoctrineRepository(db)

    try:
        from state import get_service
        return get_service('doctrine_repository', _create_doctrine_repository)
    except ImportError:
        logger.debug("state module unavailable, creating new DoctrineRepository instance")
        return _create_doctrine_repository()


# =============================================================================
# Caching Functions
# =============================================================================
@st.cache_data(ttl=600, show_spinner="Getting all fits...")
def get_all_fits_with_cache() -> pd.DataFrame:
    logger.info("Getting all fits...with cache")
    """
    Get all fit data from the doctrines table.

    Replaces: doctrines.py:get_all_fit_data()

    Returns:
        DataFrame with columns: fit_id, ship_id, ship_name, type_id,
        type_name, fit_qty, total_stock, fits_on_mkt, price, avg_vol,
        group_name, category_id, hulls, etc.
    """
    query = "SELECT * FROM doctrines"
    db = DatabaseConfig("wcmkt")
    engine = db.engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn,index_col='id')
            return df
    except Exception as e:
        logger.error(f"Failed to get all fits: {e}")

@st.cache_data(ttl=600, show_spinner="Getting fit {fit_id}...")
def get_fit_by_id_with_cache(fit_id: int) -> pd.DataFrame:
    logger.debug(f"Getting fit {fit_id}...with cache")
    """
    Get all items for a specific fit.

    Args:
        fit_id: The fit ID to retrieve

    Returns:
        DataFrame with all items belonging to the fit
    """
    query = text("SELECT * FROM doctrines WHERE fit_id = :fit_id")
    engine = DatabaseConfig("wcmkt").engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})
            return df
    except Exception as e:
        logger.error(f"Failed to get fit {fit_id}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner="Getting all ship targets...")
def get_all_targets_with_cache() -> pd.DataFrame:
    logger.debug("Getting all ship targets...")
    """
    Get all ship targets.

    Returns:
        DataFrame with columns: fit_id, ship_id, ship_name, ship_target
    """
    query = text("SELECT * FROM ship_targets")
    engine = DatabaseConfig("wcmkt").engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        logger.error(f"Failed to get all targets: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner="Getting target for fit {fit_id}...")
def get_target_by_fit_id_with_cache(fit_id: int, default: int = DEFAULT_SHIP_TARGET) -> int:
    logger.debug(f"Getting target for fit {fit_id}...")
    """
    Get target stock level for a specific fit.

    Returns:
        Target stock level, or default if not found
    """
    query = text("SELECT ship_target FROM ship_targets WHERE fit_id = :fit_id")
    engine = DatabaseConfig("wcmkt").engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})
            if not df.empty:
                return int(df.iloc[0]['ship_target'])
            return default
    except Exception as e:
        logger.error(f"Failed to get target for fit {fit_id}: {e}")
        return default

@st.cache_data(ttl=600, show_spinner="Getting target for ship {ship_id}...")
def get_target_by_ship_id_with_cache(ship_id: int, default: int = DEFAULT_SHIP_TARGET) -> int:
    logger.debug(f"Getting target for ship {ship_id}...")
    """
    Get target stock level for a specific ship type.

    Returns:
        Target stock level, or default if not found
    """
    query = text("SELECT ship_target FROM ship_targets WHERE ship_id = :ship_id")
    engine = DatabaseConfig("wcmkt").engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"ship_id": ship_id})
            if not df.empty:
                return int(df.iloc[0]['ship_target'])
            return default
    except Exception as e:
        logger.error(f"Failed to get target for ship {ship_id}: {e}")
        return default

@st.cache_data(ttl=600, show_spinner="Getting fit name for {fit_id}...")
def get_fit_name_with_cache(fit_id: int, default: str = "Unknown Fit") -> str:
    """
    Get the display name for a fit.

    Checks ship_targets first, then falls back to doctrine_fits.

    Returns:
        Fit name string
    """
    logger.debug(f"Getting fit name for {fit_id}...")
    engine = DatabaseConfig("wcmkt").engine
    try:
        with engine.connect() as conn:
            # Try ship_targets first
            query = text("SELECT fit_name FROM ship_targets WHERE fit_id = :fit_id")
            df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})
            if not df.empty:
                name = df.iloc[0]['fit_name']
                if pd.notna(name) and str(name).strip():
                    return str(name).strip()

            # Fall back to doctrine_fits
            query = text("SELECT fit_name FROM doctrine_fits WHERE fit_id = :fit_id LIMIT 1")
            df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})
            if not df.empty:
                name = df.iloc[0]['fit_name']
                if pd.notna(name) and str(name).strip():
                    return str(name).strip()

            return default
    except Exception as e:
        logger.error(f"Failed to get fit name for {fit_id}: {e}")
        return default
