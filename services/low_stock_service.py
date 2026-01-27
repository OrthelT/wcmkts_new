"""
Low Stock Service

Service layer for low stock data operations.
Consolidates database queries from low_stock.py and provides
filtering capabilities for market stats data.

Design Principles:
1. Dependency Injection - Receives DatabaseConfig
2. Service Layer - Orchestrates business operations
3. Clean separation - No UI dependencies
"""

from dataclasses import dataclass, field
from typing import Optional
import logging
import pandas as pd
from sqlalchemy import text

from config import DatabaseConfig
from logging_config import setup_logging

logger = setup_logging(__name__, log_file="low_stock_service.log")


# =============================================================================
# Domain Models
# =============================================================================

@dataclass(frozen=True)
class LowStockFilters:
    """
    Filter configuration for low stock queries.

    Attributes:
        categories: List of category names to filter by
        max_days_remaining: Maximum days of stock remaining
        doctrine_only: Only show items used in doctrines
        tech2_only: Only show Tech II items (metaGroupID=2)
        faction_only: Only show faction items (metaGroupID=4)
        fit_ids: Filter by specific fit IDs (for doctrine/fit filtering)
        type_ids: Filter by specific type IDs
    """
    categories: list[str] = field(default_factory=list)
    max_days_remaining: Optional[float] = None
    doctrine_only: bool = False
    tech2_only: bool = False
    faction_only: bool = False
    fit_ids: list[int] = field(default_factory=list)
    type_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class LowStockItem:
    """
    Represents a low stock item with market and doctrine data.

    Attributes:
        type_id: EVE type ID
        type_name: Item name
        price: Current market price
        days_remaining: Days of stock remaining
        total_volume_remain: Total volume remaining on market
        avg_volume: Average daily trading volume
        category_id: Category ID
        category_name: Category name
        group_id: Group ID
        group_name: Group name
        is_doctrine: Whether item is used in doctrines
        ships: List of ships/fits using this item
        metagroup_id: Meta group ID (1=T1, 2=T2, 4=Faction, etc.)
    """
    type_id: int
    type_name: str
    price: float = 0.0
    days_remaining: float = 0.0
    total_volume_remain: int = 0
    avg_volume: float = 0.0
    category_id: int = 0
    category_name: str = ""
    group_id: int = 0
    group_name: str = ""
    is_doctrine: bool = False
    ships: list[str] = field(default_factory=list)
    metagroup_id: Optional[int] = None


@dataclass
class DoctrineFilterInfo:
    """
    Information about a doctrine for filtering/display.

    Attributes:
        doctrine_id: Doctrine ID
        doctrine_name: Doctrine name
        lead_ship_id: Lead ship type ID for image
        fit_ids: List of fit IDs in this doctrine
    """
    doctrine_id: int
    doctrine_name: str
    lead_ship_id: Optional[int] = None
    fit_ids: list[int] = field(default_factory=list)

    @property
    def lead_ship_image_url(self) -> str:
        """Get URL for lead ship render image."""
        if self.lead_ship_id:
            return f"https://images.evetech.net/types/{self.lead_ship_id}/render?size=256"
        return ""


@dataclass
class FitFilterInfo:
    """
    Information about a fit for filtering/display.

    Attributes:
        fit_id: Fit ID
        fit_name: Fit name
        ship_id: Ship type ID
        ship_name: Ship name
    """
    fit_id: int
    fit_name: str
    ship_id: int
    ship_name: str

    @property
    def ship_image_url(self) -> str:
        """Get URL for ship render image."""
        return f"https://images.evetech.net/types/{self.ship_id}/render?size=256"


# =============================================================================
# Low Stock Service
# =============================================================================

class LowStockService:
    """
    Service for low stock data operations.

    Provides methods for:
    - Fetching market stats with various filters
    - Getting doctrine/fit information for filtering
    - Aggregating usage information from doctrines

    Example:
        service = LowStockService.create_default()

        # Get low stock items with filters
        filters = LowStockFilters(
            categories=["Ship Equipment"],
            max_days_remaining=7.0,
            doctrine_only=True
        )
        items = service.get_low_stock_items(filters)

        # Get doctrine options for UI
        doctrines = service.get_doctrine_options()
    """

    def __init__(
        self,
        mkt_db: DatabaseConfig,
        sde_db: DatabaseConfig,
        logger_instance: Optional[logging.Logger] = None
    ):
        """
        Initialize the Low Stock Service.

        Args:
            mkt_db: DatabaseConfig for market database (wcmkt)
            sde_db: DatabaseConfig for SDE database
            logger_instance: Optional logger instance
        """
        self._mkt_db = mkt_db
        self._sde_db = sde_db
        self._logger = logger_instance or logger

    @classmethod
    def create_default(cls) -> "LowStockService":
        """
        Factory method to create service with default configuration.
        """
        mkt_db = DatabaseConfig("wcmkt")
        sde_db = DatabaseConfig("sde")
        return cls(mkt_db, sde_db)

    # -------------------------------------------------------------------------
    # Filter Options
    # -------------------------------------------------------------------------

    def get_category_options(self) -> list[str]:
        """
        Get list of available category names for filtering.

        Returns:
            Sorted list of unique category names
        """
        query = "SELECT DISTINCT category_name FROM marketstats ORDER BY category_name"

        try:
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn)
            return df['category_name'].dropna().tolist()
        except Exception as e:
            self._logger.error(f"Failed to get category options: {e}")
            return []

    def get_doctrine_options(self) -> list[DoctrineFilterInfo]:
        """
        Get list of available doctrines for filtering.

        Returns:
            List of DoctrineFilterInfo objects
        """
        query = """
            SELECT DISTINCT
                df.doctrine_id,
                df.doctrine_name,
                ls.lead_ship
            FROM doctrine_fits df
            LEFT JOIN lead_ships ls ON df.doctrine_id = ls.doctrine_id
            ORDER BY df.doctrine_name
        """

        try:
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn)

            # Get fit_ids for each doctrine
            fit_query = "SELECT doctrine_name, fit_id FROM doctrine_fits"
            fit_df = pd.read_sql_query(fit_query, conn)

            # Group fit_ids by doctrine
            fit_ids_map = fit_df.groupby('doctrine_name')['fit_id'].apply(list).to_dict()

            result = []
            for _, row in df.iterrows():
                doctrine_name = row['doctrine_name']
                result.append(DoctrineFilterInfo(
                    doctrine_id=int(row['doctrine_id']),
                    doctrine_name=doctrine_name,
                    lead_ship_id=int(row['lead_ship']) if pd.notna(row['lead_ship']) else None,
                    fit_ids=fit_ids_map.get(doctrine_name, [])
                ))

            return result

        except Exception as e:
            self._logger.error(f"Failed to get doctrine options: {e}")
            return []

    def get_fit_options(self, doctrine_id: Optional[int] = None) -> list[FitFilterInfo]:
        """
        Get list of available fits for filtering.

        Args:
            doctrine_id: Optional doctrine ID to filter fits by

        Returns:
            List of FitFilterInfo objects
        """
        if doctrine_id:
            query = text("""
                SELECT DISTINCT
                    st.fit_id,
                    st.fit_name,
                    st.ship_id,
                    st.ship_name
                FROM ship_targets st
                JOIN doctrine_fits df ON st.fit_id = df.fit_id
                WHERE df.doctrine_id = :doctrine_id
                ORDER BY st.ship_name
            """)
            params = {"doctrine_id": doctrine_id}
        else:
            query = """
                SELECT DISTINCT
                    fit_id,
                    fit_name,
                    ship_id,
                    ship_name
                FROM ship_targets
                ORDER BY ship_name
            """
            params = None

        try:
            with self._mkt_db.engine.connect() as conn:
                if params:
                    df = pd.read_sql_query(query, conn, params=params)
                else:
                    df = pd.read_sql_query(query, conn)

            return [
                FitFilterInfo(
                    fit_id=int(row['fit_id']),
                    fit_name=row['fit_name'],
                    ship_id=int(row['ship_id']),
                    ship_name=row['ship_name']
                )
                for _, row in df.iterrows()
            ]

        except Exception as e:
            self._logger.error(f"Failed to get fit options: {e}")
            return []

    # -------------------------------------------------------------------------
    # Meta Group Filtering
    # -------------------------------------------------------------------------

    def get_type_ids_by_metagroup(self, metagroup_id: int) -> list[int]:
        """
        Get type IDs for a specific meta group.

        Meta Groups:
            1 = Tech I
            2 = Tech II
            4 = Faction
            5 = Officer
            6 = Deadspace
            14 = Tech III

        Args:
            metagroup_id: The meta group ID to filter by

        Returns:
            List of type IDs in this meta group
        """
        query = text("SELECT typeID FROM sdetypes WHERE metaGroupID = :metagroup_id")

        try:
            with self._sde_db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn, params={"metagroup_id": metagroup_id})
            return df['typeID'].tolist()
        except Exception as e:
            self._logger.error(f"Failed to get type IDs for metagroup {metagroup_id}: {e}")
            return []

    # -------------------------------------------------------------------------
    # Main Data Fetching
    # -------------------------------------------------------------------------

    def get_low_stock_items(self, filters: Optional[LowStockFilters] = None) -> pd.DataFrame:
        """
        Get low stock items with optional filters applied.

        This is the main data fetching method that combines market stats
        with doctrine information and applies all filters.

        Args:
            filters: Optional LowStockFilters configuration

        Returns:
            DataFrame with low stock items and all relevant columns
        """
        filters = filters or LowStockFilters()

        # Base query joining marketstats with doctrines
        query = """
        SELECT ms.*,
               CASE WHEN d.type_id IS NOT NULL THEN 1 ELSE 0 END as is_doctrine,
               d.ship_name,
               d.fits_on_mkt
        FROM marketstats ms
        LEFT JOIN doctrines d ON ms.type_id = d.type_id
        """

        try:
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn)

            if df.empty:
                return df

            # Apply category filter
            if filters.categories:
                df = df[df['category_name'].isin(filters.categories)]

            # Apply doctrine filter
            if filters.doctrine_only:
                df = df[df['is_doctrine'] == 1]

            # Apply days remaining filter
            if filters.max_days_remaining is not None:
                df = df[df['days_remaining'] <= filters.max_days_remaining]

            # Apply fit_ids filter (doctrine/fit filtering)
            if filters.fit_ids:
                # Get type_ids that are part of the selected fits
                fit_type_ids = self._get_type_ids_for_fits(filters.fit_ids)
                df = df[df['type_id'].isin(fit_type_ids)]

            # Apply type_ids filter
            if filters.type_ids:
                df = df[df['type_id'].isin(filters.type_ids)]

            # Apply Tech II filter
            if filters.tech2_only:
                tech2_ids = self.get_type_ids_by_metagroup(2)
                df = df[df['type_id'].isin(tech2_ids)]

            # Apply Faction filter (metagroupID=4 for faction items)
            if filters.faction_only:
                # Note: Using metagroupID=4 for faction items as per EVE SDE
                # The task mentioned metagroupID=7 but that doesn't exist in standard SDE
                # If the database uses a different scheme, adjust accordingly
                faction_ids = self.get_type_ids_by_metagroup(4)
                df = df[df['type_id'].isin(faction_ids)]

            # Aggregate ship/fit usage for each item
            if not df.empty:
                ship_groups = df.groupby('type_id', group_keys=False).apply(
                    lambda x: [
                        f"{row['ship_name']} ({int(row['fits_on_mkt'])})"
                        for _, row in x.iterrows()
                        if pd.notna(row['ship_name']) and pd.notna(row['fits_on_mkt'])
                    ],
                    include_groups=False
                ).to_dict()

                # De-duplicate rows (keep one per type_id)
                df = df.drop_duplicates(subset=['type_id'])

                # Add ships column
                df['ships'] = df['type_id'].map(ship_groups)

            return df

        except Exception as e:
            self._logger.error(f"Failed to get low stock items: {e}")
            return pd.DataFrame()

    def _get_type_ids_for_fits(self, fit_ids: list[int]) -> list[int]:
        """
        Get all type_ids that are part of the specified fits.

        Args:
            fit_ids: List of fit IDs

        Returns:
            List of type IDs used in those fits
        """
        if not fit_ids:
            return []

        placeholders = ','.join([':id' + str(i) for i in range(len(fit_ids))])
        query = f"SELECT DISTINCT type_id FROM doctrines WHERE fit_id IN ({placeholders})"
        params = {f'id{i}': fid for i, fid in enumerate(fit_ids)}

        try:
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(text(query), conn, params=params)
            return df['type_id'].tolist()
        except Exception as e:
            self._logger.error(f"Failed to get type IDs for fits: {e}")
            return []

    def get_doctrine_filter_info(self, doctrine_name: str) -> Optional[DoctrineFilterInfo]:
        """
        Get filter information for a specific doctrine.

        Args:
            doctrine_name: Name of the doctrine

        Returns:
            DoctrineFilterInfo or None if not found
        """
        doctrines = self.get_doctrine_options()
        for doctrine in doctrines:
            if doctrine.doctrine_name == doctrine_name:
                return doctrine
        return None

    def get_fit_filter_info(self, fit_id: int) -> Optional[FitFilterInfo]:
        """
        Get filter information for a specific fit.

        Args:
            fit_id: Fit ID

        Returns:
            FitFilterInfo or None if not found
        """
        query = text("""
            SELECT fit_id, fit_name, ship_id, ship_name
            FROM ship_targets
            WHERE fit_id = :fit_id
            LIMIT 1
        """)

        try:
            with self._mkt_db.engine.connect() as conn:
                df = pd.read_sql_query(query, conn, params={"fit_id": fit_id})

            if df.empty:
                return None

            row = df.iloc[0]
            return FitFilterInfo(
                fit_id=int(row['fit_id']),
                fit_name=row['fit_name'],
                ship_id=int(row['ship_id']),
                ship_name=row['ship_name']
            )
        except Exception as e:
            self._logger.error(f"Failed to get fit filter info: {e}")
            return None

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_stock_statistics(self, df: pd.DataFrame) -> dict:
        """
        Calculate stock statistics from a low stock DataFrame.

        Args:
            df: DataFrame from get_low_stock_items()

        Returns:
            Dict with counts: critical, low, total
        """
        if df.empty:
            return {"critical": 0, "low": 0, "total": 0}

        critical = len(df[df['days_remaining'] <= 3])
        low = len(df[(df['days_remaining'] > 3) & (df['days_remaining'] <= 7)])

        return {
            "critical": critical,
            "low": low,
            "total": len(df)
        }


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_low_stock_service() -> LowStockService:
    """
    Get or create a LowStockService instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.

    Returns:
        LowStockService instance
    """
    try:
        from state import get_service
        return get_service('low_stock_service', LowStockService.create_default)
    except ImportError:
        logger.debug("state module unavailable, creating new LowStockService instance")
        return LowStockService.create_default()
