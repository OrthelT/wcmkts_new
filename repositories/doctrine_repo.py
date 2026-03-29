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
from domain import FitItem, ModuleStock, Doctrine, ShipStock
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
    - `get_module_stock_info(type_id)`: Get stock information for a specific module
    - `get_module_usage(type_id)`: Get usage information for a module
    - `get_module_stock(type_id)`: Get complete module stock information as a domain model
    - `get_multiple_module_stocks(type_ids)`: Get stock information for multiple modules
    - `get_ship_stock(type_id)`: Get stock information for a specific ship hull
    - `get_multiple_ship_stocks(type_ids)`: Get stock information for multiple ships
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
        module = repo.get_module_stock(2048)  # Damage Control II
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
        try:
            from state.market_state import get_active_market_key
            market_key = get_active_market_key()
        except ImportError:
            logger.debug("state.market_state unavailable, defaulting to 'primary'")
            market_key = "primary"
        except Exception:
            logger.error("Failed to resolve active market key — returning empty DataFrame", exc_info=True)
            return pd.DataFrame()
        return get_all_fits_with_cache(self._db.alias, market_key)

    def get_fit_by_id(self, fit_id: int) -> pd.DataFrame:
        return get_fit_by_id_with_cache(fit_id, self._db.alias)

    def get_all_targets(self) -> pd.DataFrame:
        return get_all_targets_with_cache(self._db.alias)

    def get_target_by_fit_id(self, fit_id: int, default: int = DEFAULT_SHIP_TARGET) -> int:
        return get_target_by_fit_id_with_cache(fit_id, default, self._db.alias)

    def get_target_by_ship_id(self, ship_id: int, default: int = DEFAULT_SHIP_TARGET) -> int:
        return get_target_by_ship_id_with_cache(ship_id, default, self._db.alias)
    # =========================================================================
    # Fit Names
    # =========================================================================

    def get_fit_name(self, fit_id: int, default: str = "Unknown Fit") -> str:
        return get_fit_name_with_cache(fit_id, default, self._db.alias)

    # =========================================================================
    # Doctrine Compositions
    # =========================================================================

    def get_all_doctrine_compositions(self) -> pd.DataFrame:
        """
        Get doctrine compositions filtered by the active market's key.

        Only returns fits whose market_flag matches the active market
        (e.g. 'primary') or 'both'.

        Returns:
            DataFrame with columns: doctrine_id, doctrine_name, fit_id, market_flag, ...
        """
        query = "SELECT * FROM doctrine_fits"

        try:
            with self._db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn)

            # Filter by active market key
            try:
                from state.market_state import get_active_market_key
                market_key = get_active_market_key()
            except ImportError:
                logger.debug("state.market_state unavailable, defaulting to 'primary'")
                market_key = "primary"
            except Exception:
                logger.error("Failed to resolve active market key — returning empty DataFrame", exc_info=True)
                return pd.DataFrame()

            if "market_flag" in df.columns:
                df = df[df["market_flag"].isin([market_key, "both"])]

            return df
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

    def get_module_stock_info(self, type_id: int) -> pd.DataFrame:
        """
        Get stock information for a specific module by type_id.

        Args:
            type_id: EVE type ID of the module

        Returns:
            DataFrame with type_name, type_id, total_stock, fits_on_mkt
        """
        query = text("""
            SELECT type_name, type_id, total_stock, fits_on_mkt
            FROM doctrines
            WHERE type_id = :type_id
            LIMIT 1
        """)

        try:
            with self._db.engine.connect() as conn:
                return pd.read_sql_query(query, conn, params={"type_id": type_id})
        except Exception as e:
            self._logger.error(f"Failed to get module stock for type_id={type_id}: {e}")
            return pd.DataFrame()

    def get_module_usage(self, type_id: int) -> pd.DataFrame:
        """
        Get usage information for a module (which fits use it).

        Args:
            type_id: EVE type ID of the module

        Returns:
            DataFrame with ship_name, ship_target, fit_qty
        """
        query = text("""
            SELECT st.ship_name, st.ship_target, d.fit_qty
            FROM doctrines d
            JOIN ship_targets st ON d.fit_id = st.fit_id
            WHERE d.type_id = :type_id
        """)

        try:
            with self._db.engine.connect() as conn:
                return pd.read_sql_query(query, conn, params={"type_id": type_id})
        except Exception as e:
            self._logger.error(f"Failed to get module usage for type_id={type_id}: {e}")
            return pd.DataFrame()

    def get_module_stock(self, type_id: int) -> Optional[ModuleStock]:
        """
        Get complete module stock information as a domain model.

        Combines stock and usage queries into a single ModuleStock object.

        Args:
            type_id: EVE type ID of the module

        Returns:
            ModuleStock instance, or None if not found
        """
        stock_df = self.get_module_stock_info(type_id)
        if stock_df.empty:
            return None

        usage_df = self.get_module_usage(type_id)

        return ModuleStock.from_query_results(stock_df.iloc[0], usage_df)

    def get_multiple_module_stocks(self, type_ids: list[int]) -> dict[int, ModuleStock]:
        """
        Get stock information for multiple modules.

        Args:
            type_ids: List of EVE type IDs

        Returns:
            Dict mapping type_id to ModuleStock
        """
        result = {}
        for tid in type_ids:
            stock = self.get_module_stock(tid)
            if stock:
                result[tid] = stock
        return result

    # =========================================================================
    # Ship Stock
    # =========================================================================

    def get_ship_stock(self, type_id: int) -> Optional[ShipStock]:
        """
        Get stock information for a specific ship hull by type_id.

        Handles ships with multiple fits by using preferred_fits configuration
        from settings.toml. Falls back to first available fit if not configured.

        Args:
            type_id: EVE type ID of the ship

        Returns:
            ShipStock domain model, or None if not found
        """
        preferred_fits = _load_preferred_fits()
        preferred_fit_id = preferred_fits.get(type_id)

        # Build query with optional fit_id filter
        if preferred_fit_id:
            query = text("""
                SELECT type_name, type_id, total_stock, fits_on_mkt, fit_id
                FROM doctrines
                WHERE type_id = :type_id AND fit_id = :fit_id
                LIMIT 1
            """)
            params = {"type_id": type_id, "fit_id": preferred_fit_id}
        else:
            query = text("""
                SELECT type_name, type_id, total_stock, fits_on_mkt, fit_id
                FROM doctrines
                WHERE type_id = :type_id
                LIMIT 1
            """)
            params = {"type_id": type_id}

        try:
            with self._db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn, params=params)

            if df.empty:
                self._logger.warning(f"No stock data found for type_id={type_id}")
                return None

            row = df.iloc[0]

            # Validate required fields
            if pd.isna(row.get('total_stock')) or pd.isna(row.get('type_id')):
                self._logger.warning(f"Invalid stock data for type_id={type_id}")
                return None

            # Get target from ship_id
            ship_target = self.get_target_by_ship_id(type_id)

            return ShipStock.from_query_result(row, ship_target=ship_target)

        except Exception as e:
            self._logger.error(f"Failed to get ship stock for type_id={type_id}: {e}")
            return None

    def get_multiple_ship_stocks(self, type_ids: list[int]) -> dict[int, ShipStock]:
        """
        Get stock information for multiple ships.

        Args:
            type_ids: List of EVE type IDs

        Returns:
            Dict mapping type_id to ShipStock
        """
        result = {}
        for tid in type_ids:
            stock = self.get_ship_stock(tid)
            if stock:
                result[tid] = stock
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

# =============================================================================
# Configuration Loaders
# =============================================================================

@st.cache_data(ttl=3600)
def _load_preferred_fits() -> dict[int, int]:
    """
    Load preferred fit mappings from settings.toml.

    Maps ship type_id to their preferred fit_id for ships with multiple fits.
    TOML keys are type_id strings (TOML requires string keys); parsed to ints here.
    Cached for 1 hour.

    Returns:
        Dict mapping type_id -> fit_id
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

        raw = settings.get("preferred_fits", {})
        return {int(k): int(v) for k, v in raw.items()}

    except Exception as e:
        logger.error(f"Failed to load preferred fits from settings.toml: {e}")
        return {}


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_doctrine_repository() -> DoctrineRepository:
    """
    Get or create a DoctrineRepository instance for the active market.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.
    """
    logger.debug("Getting DoctrineRepository")

    def _create_doctrine_repository() -> DoctrineRepository:
        logger.debug("Creating DoctrineRepository instance")
        from state.market_state import get_active_market
        db = DatabaseConfig(get_active_market().database_alias)
        return DoctrineRepository(db)

    try:
        from state import get_service
        from state.market_state import get_active_market_key
        return get_service(f'doctrine_repository_{get_active_market_key()}', _create_doctrine_repository)
    except ImportError:
        logger.debug("state module unavailable, creating new DoctrineRepository instance")
        return _create_doctrine_repository()


# =============================================================================
# Caching Functions
# =============================================================================
@st.cache_data(ttl=600, show_spinner="Getting all fits...")
def get_all_fits_with_cache(db_alias: str = "wcmkt", market_key: str = "primary") -> pd.DataFrame:
    """Get fit data from the doctrines table, filtered by market_flag.

    Only returns rows whose fit_id appears in doctrine_fits with a
    market_flag matching the active market key or 'both'.
    """
    logger.info("Getting all fits for market_key=%s ...with cache", market_key)
    db = DatabaseConfig(db_alias)
    engine = db.engine
    try:
        with engine.connect() as conn:
            # Get valid fit_ids for this market from doctrine_fits
            fits_df = pd.read_sql_query("SELECT fit_id, market_flag FROM doctrine_fits", conn)
            if "market_flag" in fits_df.columns:
                valid_fit_ids = fits_df[
                    fits_df["market_flag"].isin([market_key, "both"])
                ]["fit_id"].unique()
            else:
                valid_fit_ids = fits_df["fit_id"].unique()

            df = pd.read_sql_query("SELECT * FROM doctrines", conn, index_col='id')

            # Filter to only fits belonging to this market
            df = df[df["fit_id"].isin(valid_fit_ids)]
            if df.empty:
                logger.warning("No valid fit_ids found for market_key=%s", market_key)

            return df
    except Exception as e:
        logger.error(f"Failed to get all fits: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner="Getting fit {fit_id}...")
def get_fit_by_id_with_cache(fit_id: int, db_alias: str = "wcmkt") -> pd.DataFrame:
    """Get all items for a specific fit."""
    logger.debug(f"Getting fit {fit_id}...with cache")
    query = text("SELECT * FROM doctrines WHERE fit_id = :fit_id")
    engine = DatabaseConfig(db_alias).engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})
            return df
    except Exception as e:
        logger.error(f"Failed to get fit {fit_id}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner="Getting all ship targets...")
def get_all_targets_with_cache(db_alias: str = "wcmkt") -> pd.DataFrame:
    """Get all ship targets."""
    logger.debug("Getting all ship targets...")
    query = text("SELECT * FROM ship_targets")
    engine = DatabaseConfig(db_alias).engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
            return df
    except Exception as e:
        logger.error(f"Failed to get all targets: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner="Getting target for fit {fit_id}...")
def get_target_by_fit_id_with_cache(fit_id: int, default: int = DEFAULT_SHIP_TARGET, db_alias: str = "wcmkt") -> int:
    """Get target stock level for a specific fit."""
    logger.debug(f"Getting target for fit {fit_id}...")
    query = text("SELECT ship_target FROM ship_targets WHERE fit_id = :fit_id")
    engine = DatabaseConfig(db_alias).engine
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
def get_target_by_ship_id_with_cache(ship_id: int, default: int = DEFAULT_SHIP_TARGET, db_alias: str = "wcmkt") -> int:
    """Get target stock level for a specific ship type."""
    logger.debug(f"Getting target for ship {ship_id}...")
    query = text("SELECT ship_target FROM ship_targets WHERE ship_id = :ship_id")
    engine = DatabaseConfig(db_alias).engine
    try:
        with engine.connect() as conn:
            df = pd.read_sql_query(query, conn, params={"ship_id": ship_id})
            if not df.empty:
                return int(df.iloc[0]['ship_target'])
            return default
    except Exception as e:
        logger.error(f"Failed to get target for ship {ship_id}: {e}")
        return default

@st.cache_data(ttl=600)
def get_friendly_names_with_cache(db_alias: str = "wcmkt") -> dict[str, str]:
    """Load doctrine_name -> friendly_name mapping from the doctrine_fits table.

    Returns a dict of {doctrine_name: friendly_name} for all rows where
    friendly_name is not NULL. Cached for 10 minutes.
    """
    query = (
        "SELECT DISTINCT doctrine_name, friendly_name "
        "FROM doctrine_fits "
        "WHERE friendly_name IS NOT NULL"
    )
    db = DatabaseConfig(db_alias)
    try:
        with db.engine.connect() as conn:
            rows = conn.execute(text(query)).fetchall()
        return {row[0]: row[1] for row in rows}
    except Exception as e:
        logger.warning(f"Failed to load friendly names from DB: {e}")
        return {}


def get_doctrine_display_name(raw_name: str, db_alias: str = "wcmkt") -> str:
    """Return the user-friendly display name for a doctrine, or raw_name if unknown."""
    return get_friendly_names_with_cache(db_alias).get(raw_name, raw_name)


@st.cache_data(ttl=600, show_spinner="Getting fit name for {fit_id}...")
def get_fit_name_with_cache(fit_id: int, default: str = "Unknown Fit", db_alias: str = "wcmkt") -> str:
    """Get the display name for a fit.

    Checks ship_targets first, then falls back to doctrine_fits.
    """
    logger.debug(f"Getting fit name for {fit_id}...")
    engine = DatabaseConfig(db_alias).engine
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
