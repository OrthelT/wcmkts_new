"""
Doctrine Service Module

Streamlit-compatible service for doctrine/fit data operations.

Follows the same caching pattern as price_service.py:
1. Module-level cached functions (stateless, hashable args)
2. Service class coordinates cached functions
3. Service adds rich types, validation, business logic

Consolidates logic from:
- doctrines.py (create_fit_df, get_all_fit_data, get_targets)
- doctrine_status.py (get_fit_summary, get_fit_name, get_ship_target)
- doctrine_report.py (get_fit_name_from_db, categorize_ship_by_role)
"""

from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum, auto
from functools import lru_cache
import logging
import time
import pandas as pd

# Type aliases
FitID = int
TypeID = int
ShipID = int


# =============================================================================
# Domain Models
# =============================================================================

class FitStatus(Enum):
    """Stock status for a fit."""
    CRITICAL = auto()      # <= 40% of target
    NEEDS_ATTENTION = auto()  # 40-90% of target
    GOOD = auto()          # > 90% of target

    @classmethod
    def from_percentage(cls, pct: float) -> "FitStatus":
        if pct <= 40:
            return cls.CRITICAL
        elif pct <= 90:
            return cls.NEEDS_ATTENTION
        return cls.GOOD


class ShipRole(Enum):
    """Functional role of a ship in a doctrine."""
    DPS = "DPS"
    LOGI = "Logi"
    LINKS = "Links"
    SUPPORT = "Support"


@dataclass(frozen=True)
class FitItem:
    """
    A single item in a doctrine fit.

    frozen=True makes it hashable for caching.
    """
    type_id: TypeID
    type_name: str
    fit_qty: int
    price: float = 0.0
    total_stock: int = 0
    fits_on_mkt: int = 0
    group_name: str = "Unknown"
    category_id: int = 0
    avg_vol: float = 0.0

    @property
    def item_cost(self) -> float:
        """Cost of this item in the fit."""
        return self.fit_qty * self.price

    @property
    def days_remaining(self) -> float:
        """Estimated days of stock remaining based on avg volume."""
        if self.avg_vol <= 0:
            return float('inf')
        return self.total_stock / self.avg_vol

    @classmethod
    def from_series(cls, row: pd.Series) -> "FitItem":
        """Create from DataFrame row."""
        return cls(
            type_id=int(row.get('type_id', 0)),
            type_name=str(row.get('type_name', 'Unknown')),
            fit_qty=int(row.get('fit_qty', 1)),
            price=float(row.get('price', 0) or 0),
            total_stock=int(row.get('total_stock', 0) or 0),
            fits_on_mkt=int(row.get('fits_on_mkt', 0) or 0),
            group_name=str(row.get('group_name', 'Unknown')),
            category_id=int(row.get('category_id', 0) or 0),
            avg_vol=float(row.get('avg_vol', 0) or 0),
        )


@dataclass
class FitSummary:
    """
    Summary of a complete doctrine fit.

    Mutable (not frozen) because we may update items list.
    """
    fit_id: FitID
    fit_name: str
    ship_name: str
    ship_id: ShipID
    ship_group: str
    hulls: int = 0
    fits: int = 0  # Minimum fits available (bottleneck)
    price: float = 0.0  # Hull price
    total_cost: float = 0.0  # Full fit cost
    ship_target: int = 20
    target_percentage: int = 0
    daily_avg: float = 0.0
    items: list[FitItem] = field(default_factory=list)

    @property
    def status(self) -> FitStatus:
        """Current stock status."""
        return FitStatus.from_percentage(self.target_percentage)

    @property
    def is_critical(self) -> bool:
        return self.status == FitStatus.CRITICAL

    @property
    def needs_attention(self) -> bool:
        return self.status == FitStatus.NEEDS_ATTENTION

    @property
    def is_good(self) -> bool:
        return self.status == FitStatus.GOOD

    @property
    def fits_delta(self) -> int:
        """Difference from target (positive = over target)."""
        return self.fits - self.ship_target

    @property
    def hulls_delta(self) -> int:
        """Hull difference from target."""
        return self.hulls - self.ship_target

    @property
    def lowest_stock_items(self) -> list[FitItem]:
        """Return 3 lowest stock modules (excluding hull)."""
        modules = [i for i in self.items if i.type_id != self.ship_id]
        return sorted(modules, key=lambda x: x.fits_on_mkt)[:3]

    @property
    def bottleneck_item(self) -> Optional[FitItem]:
        """The item limiting fit production."""
        if not self.items:
            return None
        return min(self.items, key=lambda x: x.fits_on_mkt)

    def to_dict(self) -> dict:
        """Convert to dictionary for DataFrame/display."""
        return {
            'fit_id': self.fit_id,
            'fit_name': self.fit_name,
            'ship_name': self.ship_name,
            'ship_id': self.ship_id,
            'ship_group': self.ship_group,
            'hulls': self.hulls,
            'fits': self.fits,
            'price': self.price,
            'total_cost': self.total_cost,
            'ship_target': self.ship_target,
            'target_percentage': self.target_percentage,
            'daily_avg': self.daily_avg,
            'status': self.status.name,
        }

    @classmethod
    def from_summary_row(
        cls,
        row: pd.Series,
        items: Optional[list[FitItem]] = None,
        fit_name: str = "Unknown Fit"
    ) -> "FitSummary":
        """Create from summary DataFrame row."""
        return cls(
            fit_id=int(row.get('fit_id', 0)),
            fit_name=fit_name,
            ship_name=str(row.get('ship_name', 'Unknown')),
            ship_id=int(row.get('ship_id', 0)),
            ship_group=str(row.get('ship_group', 'Ungrouped')),
            hulls=int(row.get('hulls', 0) or 0),
            fits=int(row.get('fits', 0) or 0),
            price=float(row.get('price', 0) or 0),
            total_cost=float(row.get('total_cost', 0) or 0),
            ship_target=int(row.get('ship_target', 20) or 20),
            target_percentage=int(row.get('target_percentage', 0) or 0),
            daily_avg=float(row.get('daily_avg', 0) or 0),
            items=items or [],
        )


@dataclass
class DoctrineData:
    """
    Complete doctrine data package.

    Returned by the service to provide both raw DataFrames
    (for compatibility) and rich domain objects.
    """
    raw_df: pd.DataFrame
    summary_df: pd.DataFrame
    summaries: dict[FitID, FitSummary] = field(default_factory=dict)

    @property
    def fit_ids(self) -> list[FitID]:
        """All fit IDs in the data."""
        return list(self.summaries.keys())

    def get_fit(self, fit_id: FitID) -> Optional[FitSummary]:
        """Get a specific fit summary."""
        return self.summaries.get(fit_id)

    def get_fits_by_status(self, status: FitStatus) -> list[FitSummary]:
        """Filter fits by status."""
        return [f for f in self.summaries.values() if f.status == status]

    def get_fits_by_ship_group(self, group: str) -> list[FitSummary]:
        """Filter fits by ship group."""
        return [f for f in self.summaries.values() if f.ship_group == group]

    @property
    def all_summaries(self) -> list[FitSummary]:
        """All fit summaries as a list."""
        return list(self.summaries.values())


# =============================================================================
# Ship Role Categorization
# =============================================================================

class ShipRoleCategorizer:
    """
    Categorizes ships by their role in a doctrine.

    Uses configuration file with lru_cache for efficiency.
    """

    def __init__(self, config_path: str = "settings.toml"):
        self._config_path = config_path
        self._config = self._load_config()

    @lru_cache(maxsize=1)
    def _load_config(self) -> dict:
        """Load and cache configuration."""
        try:
            import tomllib
            with open(self._config_path, "rb") as f:
                settings = tomllib.load(f)
            return settings.get('ship_roles', {})
        except Exception:
            return {}

    def categorize(self, ship_name: str, fit_id: FitID) -> ShipRole:
        """Determine the role of a ship in a doctrine."""
        fit_id_str = str(fit_id)
        config = self._config

        # Check special cases first
        special = config.get('special_cases', {})
        if ship_name in special and fit_id_str in special[ship_name]:
            role_str = special[ship_name][fit_id_str]
            return ShipRole(role_str)

        # Check role lists
        if ship_name in config.get('dps', []):
            return ShipRole.DPS
        if ship_name in config.get('logi', []):
            return ShipRole.LOGI
        if ship_name in config.get('links', []):
            return ShipRole.LINKS
        if ship_name in config.get('support', []):
            return ShipRole.SUPPORT

        # Fallback: pattern matching
        return self._fallback_categorize(ship_name)

    def _fallback_categorize(self, ship_name: str) -> ShipRole:
        """Fallback categorization based on ship name patterns."""
        name_lower = ship_name.lower()

        patterns = {
            ShipRole.DPS: ['hurricane', 'ferox', 'zealot', 'bellicose', 'navy'],
            ShipRole.LOGI: ['osprey', 'guardian', 'basilisk', 'scimitar'],
            ShipRole.LINKS: ['claymore', 'vulture', 'command'],
        }

        for role, keywords in patterns.items():
            if any(kw in name_lower for kw in keywords):
                return role

        return ShipRole.SUPPORT

    def group_by_role(
        self,
        fits: list[FitSummary]
    ) -> dict[ShipRole, list[FitSummary]]:
        """Group fits by their ship role."""
        result = {role: [] for role in ShipRole}
        for fit in fits:
            role = self.categorize(fit.ship_name, fit.fit_id)
            result[role].append(fit)
        return result


# =============================================================================
# Streamlit-Compatible Cached Functions
# =============================================================================

def _get_streamlit_cache():
    """Get Streamlit cache decorator or no-op fallback."""
    try:
        import streamlit as st
        return st.cache_data
    except Exception:
        return lambda **kwargs: lambda fn: fn


def _create_cached_functions():
    """Create cached doctrine data functions."""
    cache_data = _get_streamlit_cache()
    logger = logging.getLogger(__name__)

    @cache_data(ttl=600, show_spinner="Loading doctrine data...")
    def fetch_all_doctrines_cached(db_alias: str = "wcmkt") -> pd.DataFrame:
        """
        Fetch all doctrine data from database.

        Args:
            db_alias: Database alias (hashable string, not object)

        Returns:
            Raw DataFrame from doctrines table
        """
        from config import DatabaseConfig

        db = DatabaseConfig(db_alias)
        query = "SELECT * FROM doctrines"

        try:
            with db.local_access():
                with db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn)
            return df.reset_index(drop=True)
        except Exception as e:
            logger.error(f"Failed to fetch doctrines: {e}")
            # Try sync and retry
            try:
                db.sync()
                with db.local_access():
                    with db.engine.connect() as conn:
                        df = pd.read_sql_query(query, conn)
                return df.reset_index(drop=True)
            except Exception as e2:
                logger.error(f"Failed after sync: {e2}")
                raise

    @cache_data(ttl=600, show_spinner="Loading targets...")
    def fetch_ship_targets_cached(db_alias: str = "wcmkt") -> pd.DataFrame:
        """Fetch ship targets from database."""
        from config import DatabaseConfig
        from sqlalchemy import text

        db = DatabaseConfig(db_alias)
        query = "SELECT fit_id, ship_target, fit_name, ship_name, ship_id FROM ship_targets"

        try:
            with db.local_access():
                with db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn)
            return df.reset_index(drop=True)
        except Exception as e:
            logger.error(f"Failed to fetch targets: {e}")
            return pd.DataFrame(columns=['fit_id', 'ship_target', 'fit_name'])

    @cache_data(ttl=600, show_spinner="Loading doctrine fits...")
    def fetch_doctrine_fits_cached(db_alias: str = "wcmkt") -> pd.DataFrame:
        """Fetch doctrine-to-fit mappings."""
        from config import DatabaseConfig

        db = DatabaseConfig(db_alias)
        query = "SELECT doctrine_id, doctrine_name, fit_id FROM doctrine_fits"

        try:
            with db.local_access():
                with db.engine.connect() as conn:
                    df = pd.read_sql_query(query, conn)
            return df.reset_index(drop=True)
        except Exception as e:
            logger.error(f"Failed to fetch doctrine fits: {e}")
            return pd.DataFrame()

    @cache_data(ttl=600)
    def build_fit_summary_cached(db_alias: str = "wcmkt") -> tuple:
        """
        Build complete fit summary data.

        Returns tuple of (raw_df, summary_df) for caching.
        Tuples are hashable, custom objects are not.
        """
        t0 = time.perf_counter()

        # Fetch raw data
        df = fetch_all_doctrines_cached(db_alias)
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()

        # Aggregate summary per fit
        summary = df.groupby('fit_id').agg({
            'ship_name': 'first',
            'ship_id': 'first',
            'hulls': 'first',
            'fits_on_mkt': 'min',
        }).reset_index()

        # Get ship-specific data (where type_id == ship_id)
        ship_mask = df['type_id'] == df['ship_id']
        ship_data = df[ship_mask].groupby('fit_id').agg({
            'group_name': 'first',
            'price': 'first',
            'avg_vol': 'first',
        }).reset_index()

        summary = summary.merge(ship_data, on='fit_id', how='left')
        summary['ship_group'] = summary['group_name'].fillna('Ungrouped')
        summary['price'] = summary['price'].fillna(0)

        # Rename for clarity
        summary = summary.rename(columns={'fits_on_mkt': 'fits'})

        # Handle null prices in raw data
        if df['price'].isna().any():
            df = _fill_null_prices_internal(df)

        # Calculate total cost per fit
        df['item_cost'] = df['fit_qty'] * df['price']
        fit_costs = df.groupby('fit_id')['item_cost'].sum().reset_index()
        fit_costs = fit_costs.rename(columns={'item_cost': 'total_cost'})
        summary = summary.merge(fit_costs, on='fit_id', how='left')
        summary['total_cost'] = summary['total_cost'].fillna(0)

        # Add targets
        targets = fetch_ship_targets_cached(db_alias)
        targets_dedup = targets.drop_duplicates(subset=['fit_id'])[['fit_id', 'ship_target']]
        summary = summary.merge(targets_dedup, on='fit_id', how='left')
        summary['ship_target'] = summary['ship_target'].fillna(20).astype(int)

        # Calculate target percentage
        summary['target_percentage'] = (
            (summary['fits'] / summary['ship_target'] * 100)
            .clip(upper=100)
            .fillna(0)
            .astype(int)
        )
        summary.loc[summary['ship_target'] == 0, 'target_percentage'] = 0

        # Set daily_avg
        summary['daily_avg'] = summary.get('avg_vol', pd.Series(0)).fillna(0)

        # Select final columns
        final_cols = [
            'fit_id', 'ship_name', 'ship_id', 'hulls', 'fits',
            'ship_group', 'price', 'total_cost', 'ship_target',
            'target_percentage', 'daily_avg'
        ]
        summary = summary[[c for c in final_cols if c in summary.columns]]

        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(f"build_fit_summary_cached completed in {elapsed}ms")

        return df, summary

    return (
        fetch_all_doctrines_cached,
        fetch_ship_targets_cached,
        fetch_doctrine_fits_cached,
        build_fit_summary_cached,
    )


def _fill_null_prices_internal(df: pd.DataFrame) -> pd.DataFrame:
    """Fill null prices with fallback values."""
    from services.price_service import get_price_service

    df = df.copy()
    null_mask = df['price'].isna()

    if not null_mask.any():
        return df

    try:
        service = get_price_service()
        null_ids = [int(tid) for tid in df.loc[null_mask, 'type_id'].unique()]
        prices = service.get_jita_prices_dict(null_ids)

        for type_id, price in prices.items():
            mask = (df['type_id'] == type_id) & df['price'].isna()
            df.loc[mask, 'price'] = price
    except Exception:
        pass

    df['price'] = df['price'].fillna(0)
    return df


# Create cached functions at module load
(
    fetch_all_doctrines_cached,
    fetch_ship_targets_cached,
    fetch_doctrine_fits_cached,
    build_fit_summary_cached,
) = _create_cached_functions()


# =============================================================================
# Doctrine Service
# =============================================================================

class DoctrineService:
    """
    Streamlit-compatible service for doctrine operations.

    Coordinates cached functions and provides rich domain objects.

    Example:
        service = get_doctrine_service()

        # Get all fit summaries
        data = service.get_doctrine_data()

        # Filter by status
        critical = data.get_fits_by_status(FitStatus.CRITICAL)

        # Get specific fit
        fit = data.get_fit(473)
        print(f"{fit.ship_name}: {fit.fits}/{fit.ship_target}")
    """

    def __init__(
        self,
        db_alias: str = "wcmkt",
        logger: Optional[logging.Logger] = None
    ):
        self._db_alias = db_alias
        self._logger = logger or logging.getLogger(__name__)
        self._categorizer = ShipRoleCategorizer()

    def get_doctrine_data(self, include_items: bool = False) -> DoctrineData:
        """
        Get complete doctrine data with optional item details.

        Args:
            include_items: If True, populate items list in each FitSummary

        Returns:
            DoctrineData with raw DataFrames and rich domain objects
        """
        raw_df, summary_df = build_fit_summary_cached(self._db_alias)

        if summary_df.empty:
            return DoctrineData(raw_df=raw_df, summary_df=summary_df)

        # Build FitSummary objects
        targets_df = fetch_ship_targets_cached(self._db_alias)
        fit_names = dict(zip(targets_df['fit_id'], targets_df['fit_name']))

        summaries = {}
        for _, row in summary_df.iterrows():
            fit_id = int(row['fit_id'])
            fit_name = fit_names.get(fit_id, "Unknown Fit")

            items = []
            if include_items:
                fit_rows = raw_df[raw_df['fit_id'] == fit_id]
                items = [FitItem.from_series(r) for _, r in fit_rows.iterrows()]

            summaries[fit_id] = FitSummary.from_summary_row(row, items, fit_name)

        return DoctrineData(
            raw_df=raw_df,
            summary_df=summary_df,
            summaries=summaries
        )

    def get_fit_summary(self, fit_id: FitID) -> Optional[FitSummary]:
        """Get summary for a specific fit."""
        data = self.get_doctrine_data(include_items=True)
        return data.get_fit(fit_id)

    def get_fit_items(self, fit_id: FitID) -> list[FitItem]:
        """Get all items for a specific fit."""
        raw_df, _ = build_fit_summary_cached(self._db_alias)
        fit_rows = raw_df[raw_df['fit_id'] == fit_id]
        return [FitItem.from_series(r) for _, r in fit_rows.iterrows()]

    def get_fit_name(self, fit_id: FitID) -> str:
        """Get the display name for a fit."""
        targets = fetch_ship_targets_cached(self._db_alias)
        match = targets[targets['fit_id'] == fit_id]
        if not match.empty and pd.notna(match.iloc[0].get('fit_name')):
            return str(match.iloc[0]['fit_name'])
        return "Unknown Fit"

    def get_ship_target(self, fit_id: FitID) -> int:
        """Get target quantity for a fit."""
        targets = fetch_ship_targets_cached(self._db_alias)
        match = targets[targets['fit_id'] == fit_id]
        if not match.empty and pd.notna(match.iloc[0].get('ship_target')):
            return int(match.iloc[0]['ship_target'])
        return 20  # Default

    def get_fits_by_doctrine(self, doctrine_name: str) -> list[FitSummary]:
        """Get all fits belonging to a doctrine."""
        doctrine_fits = fetch_doctrine_fits_cached(self._db_alias)
        fit_ids = doctrine_fits[
            doctrine_fits['doctrine_name'] == doctrine_name
        ]['fit_id'].unique()

        data = self.get_doctrine_data()
        return [data.get_fit(fid) for fid in fit_ids if data.get_fit(fid)]

    def get_doctrine_names(self) -> list[str]:
        """Get list of all doctrine names."""
        doctrine_fits = fetch_doctrine_fits_cached(self._db_alias)
        return doctrine_fits['doctrine_name'].unique().tolist()

    def categorize_ship(self, ship_name: str, fit_id: FitID) -> ShipRole:
        """Get the role of a ship in a doctrine."""
        return self._categorizer.categorize(ship_name, fit_id)

    def group_fits_by_role(
        self,
        fits: list[FitSummary]
    ) -> dict[ShipRole, list[FitSummary]]:
        """Group fits by ship role."""
        return self._categorizer.group_by_role(fits)

    def get_low_stock_modules(
        self,
        fit_id: FitID,
        count: int = 3
    ) -> list[FitItem]:
        """Get the N lowest stock modules for a fit."""
        items = self.get_fit_items(fit_id)
        # Get ship_id to exclude hull
        raw_df, _ = build_fit_summary_cached(self._db_alias)
        fit_rows = raw_df[raw_df['fit_id'] == fit_id]
        if fit_rows.empty:
            return []
        ship_id = int(fit_rows.iloc[0]['ship_id'])

        modules = [i for i in items if i.type_id != ship_id]
        return sorted(modules, key=lambda x: x.fits_on_mkt)[:count]

    def apply_target_multiplier(
        self,
        summaries: list[FitSummary],
        multiplier: float
    ) -> list[FitSummary]:
        """
        Apply a target multiplier to summaries.

        Returns new list with adjusted targets (doesn't mutate originals).
        """
        result = []
        for s in summaries:
            new_target = int(s.ship_target * multiplier)
            new_pct = int((s.fits / new_target * 100) if new_target > 0 else 0)
            new_pct = min(100, new_pct)

            # Create new summary with adjusted values
            result.append(FitSummary(
                fit_id=s.fit_id,
                fit_name=s.fit_name,
                ship_name=s.ship_name,
                ship_id=s.ship_id,
                ship_group=s.ship_group,
                hulls=s.hulls,
                fits=s.fits,
                price=s.price,
                total_cost=s.total_cost,
                ship_target=new_target,
                target_percentage=new_pct,
                daily_avg=s.daily_avg,
                items=s.items,
            ))
        return result

    def clear_cache(self):
        """Clear all doctrine caches."""
        try:
            import streamlit as st
            st.cache_data.clear()
            self._logger.info("Doctrine caches cleared")
        except Exception:
            pass


# =============================================================================
# Service Factory
# =============================================================================

def get_doctrine_service() -> DoctrineService:
    """
    Get or create a DoctrineService instance.

    Uses @st.cache_resource for the service object itself.
    """
    try:
        import streamlit as st

        @st.cache_resource
        def _create_service():
            return DoctrineService()

        return _create_service()

    except Exception:
        return DoctrineService()


# =============================================================================
# Backwards Compatibility
# =============================================================================

def create_fit_df() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Backwards-compatible wrapper for create_fit_df.

    Returns (raw_df, summary_df) tuple.
    """
    return build_fit_summary_cached("wcmkt")


def get_all_fit_data() -> pd.DataFrame:
    """Backwards-compatible wrapper for raw doctrine data."""
    return fetch_all_doctrines_cached("wcmkt")


def get_target_from_fit_id(fit_id: int) -> int:
    """Backwards-compatible target lookup."""
    service = get_doctrine_service()
    return service.get_ship_target(fit_id)
