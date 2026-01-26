"""
Market Orders Repository

Repository for aggregating market order data from the marketorders table.
Provides 4-HWWF market prices by aggregating raw buy/sell orders.

This is a specialized repository for the Pricer feature that needs
comprehensive local market data beyond what's in the pre-aggregated
marketstats table (which only covers ~860 items).

Design:
- Aggregates on-the-fly from marketorders table
- Returns both min sell price and max buy price
- Includes total volumes for buy/sell sides
"""

from typing import Optional
import logging
import pandas as pd
from sqlalchemy import text

from config import DatabaseConfig
from domain.pricer import LocalPriceData
from logging_config import setup_logging

logger = setup_logging(__name__, log_file="market_orders_repo.log")


class MarketOrdersRepository:
    """
    Repository for aggregating market order data.

    Queries the marketorders table to compute:
    - Minimum sell price
    - Maximum buy price
    - Total sell volume
    - Total buy volume

    This provides comprehensive 4-HWWF pricing data for any item
    with active market orders.
    """

    def __init__(self, db: DatabaseConfig, logger_instance: Optional[logging.Logger] = None):
        """
        Initialize repository with database configuration.

        Args:
            db: DatabaseConfig instance for the market database (wcmkt)
            logger_instance: Optional logger instance
        """
        self._db = db
        self._logger = logger_instance or logger

    def get_local_prices(self, type_ids: list[int]) -> dict[int, LocalPriceData]:
        """
        Get aggregated local market prices for multiple type IDs.

        Aggregates from marketorders table to get:
        - Minimum sell price (lowest sell order)
        - Maximum buy price (highest buy order)
        - Total sell volume
        - Total buy volume

        Args:
            type_ids: List of EVE type IDs to query

        Returns:
            Dictionary mapping type_id to LocalPriceData
        """
        if not type_ids:
            return {}

        try:
            # Build placeholders for IN clause
            placeholders = ','.join([':id' + str(i) for i in range(len(type_ids))])

            # Combined query for both buy and sell aggregation
            query = f"""
                SELECT
                    type_id,
                    MIN(CASE WHEN is_buy_order = 0 THEN price END) as min_sell_price,
                    MAX(CASE WHEN is_buy_order = 1 THEN price END) as max_buy_price,
                    COALESCE(SUM(CASE WHEN is_buy_order = 0 THEN volume_remain ELSE 0 END), 0) as total_sell_volume,
                    COALESCE(SUM(CASE WHEN is_buy_order = 1 THEN volume_remain ELSE 0 END), 0) as total_buy_volume
                FROM marketorders
                WHERE type_id IN ({placeholders})
                GROUP BY type_id
            """

            # Build params dict
            params = {f'id{i}': tid for i, tid in enumerate(type_ids)}

            with self._db.engine.connect() as conn:
                df = pd.read_sql_query(text(query), conn, params=params)

            # Convert to LocalPriceData objects
            result = {}
            for _, row in df.iterrows():
                type_id = int(row['type_id'])
                result[type_id] = LocalPriceData(
                    type_id=type_id,
                    min_sell_price=float(row['min_sell_price']) if pd.notna(row['min_sell_price']) else 0.0,
                    max_buy_price=float(row['max_buy_price']) if pd.notna(row['max_buy_price']) else 0.0,
                    total_sell_volume=int(row['total_sell_volume']),
                    total_buy_volume=int(row['total_buy_volume']),
                )

            # Add empty entries for type_ids not found
            for tid in type_ids:
                if tid not in result:
                    result[tid] = LocalPriceData(type_id=tid)

            self._logger.debug(f"Retrieved local prices for {len(result)} items")
            return result

        except Exception as e:
            self._logger.error(f"Error fetching local prices: {e}")
            # Return empty LocalPriceData for all requested IDs
            return {tid: LocalPriceData(type_id=tid) for tid in type_ids}

    def get_local_price(self, type_id: int) -> LocalPriceData:
        """
        Get aggregated local market price for a single type ID.

        Args:
            type_id: EVE type ID to query

        Returns:
            LocalPriceData with price information
        """
        result = self.get_local_prices([type_id])
        return result.get(type_id, LocalPriceData(type_id=type_id))

    def get_sell_orders(self, type_ids: list[int]) -> pd.DataFrame:
        """
        Get all sell orders for given type IDs.

        Args:
            type_ids: List of type IDs

        Returns:
            DataFrame with sell order details
        """
        if not type_ids:
            return pd.DataFrame()

        placeholders = ','.join([':id' + str(i) for i in range(len(type_ids))])
        query = f"""
            SELECT
                order_id,
                type_id,
                type_name,
                price,
                volume_remain,
                duration,
                issued
            FROM marketorders
            WHERE is_buy_order = 0
              AND type_id IN ({placeholders})
            ORDER BY type_id, price ASC
        """
        params = {f'id{i}': tid for i, tid in enumerate(type_ids)}

        try:
            with self._db.engine.connect() as conn:
                return pd.read_sql_query(text(query), conn, params=params)
        except Exception as e:
            self._logger.error(f"Error fetching sell orders: {e}")
            return pd.DataFrame()

    def get_buy_orders(self, type_ids: list[int]) -> pd.DataFrame:
        """
        Get all buy orders for given type IDs.

        Args:
            type_ids: List of type IDs

        Returns:
            DataFrame with buy order details
        """
        if not type_ids:
            return pd.DataFrame()

        placeholders = ','.join([':id' + str(i) for i in range(len(type_ids))])
        query = f"""
            SELECT
                order_id,
                type_id,
                type_name,
                price,
                volume_remain,
                duration,
                issued
            FROM marketorders
            WHERE is_buy_order = 1
              AND type_id IN ({placeholders})
            ORDER BY type_id, price DESC
        """
        params = {f'id{i}': tid for i, tid in enumerate(type_ids)}

        try:
            with self._db.engine.connect() as conn:
                return pd.read_sql_query(text(query), conn, params=params)
        except Exception as e:
            self._logger.error(f"Error fetching buy orders: {e}")
            return pd.DataFrame()

    def has_orders(self, type_id: int) -> bool:
        """
        Check if there are any orders for a type ID.

        Args:
            type_id: EVE type ID

        Returns:
            True if orders exist
        """
        query = "SELECT 1 FROM marketorders WHERE type_id = :type_id LIMIT 1"
        try:
            with self._db.engine.connect() as conn:
                result = conn.execute(text(query), {"type_id": type_id}).fetchone()
                return result is not None
        except Exception as e:
            self._logger.error(f"Error checking orders for {type_id}: {e}")
            return False


# =============================================================================
# Streamlit Integration
# =============================================================================

def get_market_orders_repository() -> MarketOrdersRepository:
    """
    Get or create a MarketOrdersRepository instance.

    Uses state.get_service for session state persistence across reruns.
    Falls back to direct instantiation if state module unavailable.

    Returns:
        MarketOrdersRepository instance
    """
    def _create_market_orders_repository() -> MarketOrdersRepository:
        db = DatabaseConfig("wcmkt")
        return MarketOrdersRepository(db)

    try:
        from state import get_service
        return get_service('market_orders_repository', _create_market_orders_repository)
    except ImportError:
        # Fallback for non-Streamlit contexts or missing state module
        return _create_market_orders_repository()
