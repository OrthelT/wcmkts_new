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

from config import DatabaseConfig
from domain import FitItem, FitSummary, ModuleStock, ModuleUsage, Doctrine


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

    def get_all_fits(self) -> pd.DataFrame:
        """
        Get all fit data from the doctrines table.

        Replaces: doctrines.py:get_all_fit_data()

        Returns:
            DataFrame with columns: fit_id, ship_id, ship_name, type_id,
            type_name, fit_qty, total_stock, fits_on_mkt, price, avg_vol,
            group_name, category_id, hulls, etc.
        """
        query = "SELECT * FROM doctrines"

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    return pd.read_sql_query(query, conn,index_col='id')
        except Exception as e:
            self._logger.error(f"Failed to get all fits: {e}")
            # Try sync and retry
            try:
                self._db.sync()
                with self._db.local_access():
                    with self._db.engine.connect() as conn:
                        return pd.read_sql_query(query, conn,index_col='id')
            except Exception as e2:
                self._logger.error(f"Failed after sync: {e2}")
                return pd.DataFrame()

    def get_fit_by_id(self, fit_id: int) -> pd.DataFrame:
        """
        Get all items for a specific fit.

        Args:
            fit_id: The fit ID to retrieve

        Returns:
            DataFrame with all items belonging to the fit
        """
        query = text("SELECT * FROM doctrines WHERE fit_id = :fit_id")

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    return pd.read_sql_query(query, conn, params={"fit_id": fit_id})
        except Exception as e:
            self._logger.error(f"Failed to get fit {fit_id}: {e}")
            return pd.DataFrame()

    def get_fits_by_type_id(self, type_id: int) -> pd.DataFrame:
        """
        Get all fits containing a specific type.

        Replaces: db_handler.py query for doctrines by type_id

        Args:
            type_id: The type ID to search for

        Returns:
            DataFrame of fits containing this type
        """
        query = text("SELECT * FROM doctrines WHERE type_id = :type_id")

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    return pd.read_sql_query(query, conn, params={"type_id": type_id})
        except Exception as e:
            self._logger.error(f"Failed to get fits for type {type_id}: {e}")
            return pd.DataFrame()

    # =========================================================================
    # Targets
    # =========================================================================

    def get_all_targets(self) -> pd.DataFrame:
        """
        Get all ship targets.

        Replaces: doctrines.py:new_get_targets()

        Returns:
            DataFrame with columns: fit_id, ship_id, ship_name, ship_target, fit_name
        """
        query = text("SELECT * FROM ship_targets")

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    return pd.read_sql_query(query, conn)
        except Exception as e:
            self._logger.error(f"Failed to get targets: {e}")
            return pd.DataFrame()

    def get_target_by_fit_id(self, fit_id: int, default: int = 20) -> int:
        """
        Get target stock level for a specific fit.

        Replaces:
        - doctrines.py:get_target_from_fit_id()
        - doctrine_status.py:get_ship_target(0, fit_id)

        Args:
            fit_id: The fit ID to look up
            default: Default value if not found (default: 20)

        Returns:
            Target stock level, or default if not found
        """
        query = text("SELECT ship_target FROM ship_targets WHERE fit_id = :fit_id")

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})

            if not df.empty and pd.notna(df.loc[0, 'ship_target']):
                return int(df.loc[0, 'ship_target'])
            return default

        except Exception as e:
            self._logger.error(f"Failed to get target for fit {fit_id}: {e}")
            return default

    def get_target_by_ship_id(self, ship_id: int, default: int = 20) -> int:
        """
        Get target stock level for a specific ship type.

        Replaces: doctrine_status.py:get_ship_target(ship_id, 0)

        Args:
            ship_id: The ship type ID to look up
            default: Default value if not found (default: 20)

        Returns:
            Target stock level, or default if not found
        """
        query = text("SELECT ship_target FROM ship_targets WHERE ship_id = :ship_id")

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn, params={"ship_id": ship_id})

            if not df.empty and pd.notna(df.loc[0, 'ship_target']):
                return int(df.loc[0, 'ship_target'])
            return default

        except Exception as e:
            self._logger.error(f"Failed to get target for ship {ship_id}: {e}")
            return default

    # =========================================================================
    # Fit Names
    # =========================================================================

    def get_fit_name(self, fit_id: int, default: str = "Unknown Fit") -> str:
        """
        Get the display name for a fit.

        Replaces:
        - doctrine_status.py:get_fit_name()
        - doctrine_report.py:get_fit_name_from_db()

        Args:
            fit_id: The fit ID to look up
            default: Default name if not found

        Returns:
            Fit name string
        """
        query = text("SELECT fit_name FROM ship_targets WHERE fit_id = :fit_id")

        try:
            with self._db.local_access():
                with self._db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})

            if not df.empty and pd.notna(df.loc[0, 'fit_name']):
                return str(df.loc[0, 'fit_name'])
            return default

        except Exception as e:
            self._logger.error(f"Failed to get fit name for {fit_id}: {e}")
            return default

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
    def get_methods(print_methods: bool = False) -> list[str]:
        """
        Get all methods of the DoctrineRepository class.
        """
        methods: list[dict[str, str]] = []

        _dir = dir(DoctrineRepository)
        for method in _dir:
            if method.startswith("_"):
                continue
            methods.append(method)

        if print_methods:
            for method in methods:
                print(f"{method}: {getattr(DoctrineRepository, method).__doc__ if getattr(DoctrineRepository, method).__doc__ else 'No documentation'}")
                print("----------------------------------------")
        else:
            return methods

# =============================================================================
# Streamlit Integration
# =============================================================================

def get_doctrine_repository() -> DoctrineRepository:
    """
    Get or create a DoctrineRepository instance.

    Uses Streamlit session state for persistence across reruns.
    This is the recommended way to get the repository in Streamlit pages.

    Example:
        from repositories import get_doctrine_repository

        repo = get_doctrine_repository()
        fits = repo.get_all_fits()
    """
    import streamlit as st

    if 'doctrine_repository' not in st.session_state:
        db = DatabaseConfig("wcmkt")
        st.session_state.doctrine_repository = DoctrineRepository(db)

    return st.session_state.doctrine_repository


