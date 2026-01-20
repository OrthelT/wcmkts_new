"""
Doctrine Service Module

This module provides business logic for doctrine data processing,
replacing the monolithic create_fit_df() function with a clean,
testable architecture.

Patterns Applied:
1. Builder Pattern - FitDataBuilder for complex DataFrame construction
2. Dependency Injection - Repository and PriceService injected
3. Service Layer - Orchestrates business operations
4. Domain Models - Returns typed FitSummary objects

Replaces business logic from:
- doctrines.py (create_fit_df, calculate_jita_fit_cost_and_delta)
- Null price handling scattered across multiple functions
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime
import time
import logging
import pandas as pd

from domain import FitItem, FitSummary, StockStatus
from repositories import DoctrineRepository
from services.price_service import PriceService, FitCostAnalysis
import streamlit as st


# =============================================================================
# Build Metadata - Tracking Build Information
# =============================================================================

@dataclass
class BuildMetadata:
    """
    Metadata about a FitDataBuilder build operation.

    Tracks timing, counts, and steps executed during the build process.
    Useful for debugging, performance monitoring, and logging.

    Attributes:
        build_started_at: Timestamp when build started
        build_completed_at: Timestamp when build completed
        total_duration_ms: Total build time in milliseconds
        steps_executed: List of step names that were executed
        step_durations_ms: Dict mapping step name to duration in ms
        raw_row_count: Number of rows in raw DataFrame
        summary_row_count: Number of rows in summary DataFrame
        unique_fit_count: Number of unique fits
        unique_type_count: Number of unique item types
        null_prices_found: Number of null prices found
        null_prices_filled: Number of null prices successfully filled
        prices_filled_from_avg: Count filled from avg_price
        prices_filled_from_jita: Count filled from Jita API
        prices_defaulted_to_zero: Count defaulted to 0
        has_price_service: Whether PriceService was available
    """
    build_started_at: Optional[datetime] = None
    build_completed_at: Optional[datetime] = None
    total_duration_ms: float = 0.0
    steps_executed: list[str] = field(default_factory=list)
    step_durations_ms: dict[str, float] = field(default_factory=dict)
    raw_row_count: int = 0
    summary_row_count: int = 0
    unique_fit_count: int = 0
    unique_type_count: int = 0
    null_prices_found: int = 0
    null_prices_filled: int = 0
    prices_filled_from_avg: int = 0
    prices_filled_from_jita: int = 0
    prices_defaulted_to_zero: int = 0
    has_price_service: bool = False

    def to_dict(self) -> dict:
        """Convert metadata to a dictionary for logging or display."""
        return {
            'build_started_at': self.build_started_at.isoformat() if self.build_started_at else None,
            'build_completed_at': self.build_completed_at.isoformat() if self.build_completed_at else None,
            'total_duration_ms': round(self.total_duration_ms, 2),
            'steps_executed': self.steps_executed,
            'step_durations_ms': {k: round(v, 2) for k, v in self.step_durations_ms.items()},
            'raw_row_count': self.raw_row_count,
            'summary_row_count': self.summary_row_count,
            'unique_fit_count': self.unique_fit_count,
            'unique_type_count': self.unique_type_count,
            'null_prices_found': self.null_prices_found,
            'null_prices_filled': self.null_prices_filled,
            'prices_filled_from_avg': self.prices_filled_from_avg,
            'prices_filled_from_jita': self.prices_filled_from_jita,
            'prices_defaulted_to_zero': self.prices_defaulted_to_zero,
            'has_price_service': self.has_price_service,
        }

    def summary_string(self) -> str:
        """Return a human-readable summary of the build."""
        lines = [
            f"Build completed in {self.total_duration_ms:.1f}ms",
            f"  Raw data: {self.raw_row_count} rows, {self.unique_type_count} unique types",
            f"  Summaries: {self.summary_row_count} fits",
            f"  Steps: {' -> '.join(self.steps_executed)}",
        ]
        if self.null_prices_found > 0:
            lines.append(
                f"  Prices: {self.null_prices_found} null, "
                f"{self.prices_filled_from_avg} from avg, "
                f"{self.prices_filled_from_jita} from Jita, "
                f"{self.prices_defaulted_to_zero} defaulted"
            )
        return "\n".join(lines)


# =============================================================================
# Build Result - Output of the Builder
# =============================================================================

@dataclass
class FitBuildResult:
    """
    Result of building fit data.

    Contains both the raw DataFrame (for backwards compatibility)
    and the typed domain model list (for new code), along with
    metadata about the build process.

    Attributes:
        raw_df: DataFrame with all doctrine items (one row per item per fit)
        summary_df: DataFrame with aggregated fit summaries (one row per fit)
        summaries: List of FitSummary domain model objects
        metadata: BuildMetadata with timing and statistics

    Properties:
        is_empty: True if no data was loaded
        fit_count: Number of fits in the result

    Example:
        result = builder.build()
        print(f"Built {result.fit_count} fits in {result.metadata.total_duration_ms}ms")
        print(result.metadata.summary_string())
        
    """
    raw_df: pd.DataFrame
    summary_df: pd.DataFrame
    summaries: list[FitSummary] = field(default_factory=list)
    metadata: BuildMetadata = field(default_factory=BuildMetadata)

    @property
    def is_empty(self) -> bool:
        """Return True if no data was loaded."""
        return self.raw_df.empty

    @property
    def fit_count(self) -> int:
        """Return the number of fits in the result."""
        return len(self.summaries)

    def get_metadata(self) -> BuildMetadata:
        """
        Get the build metadata.

        Returns:
            BuildMetadata object with timing, counts, and step information.
        """
        return self.metadata

    def get_metadata_dict(self) -> dict:
        """
        Get metadata as a dictionary.

        Useful for JSON serialization or logging.

        Returns:
            Dict representation of build metadata.
        """
        return self.metadata.to_dict()

    def print_metadata(self) -> None:
        """Print a human-readable summary of the build metadata."""
        print(self.metadata.summary_string())

    def get_columns(self, result_type: str = "summary") -> list[str]:
        """
        Get the columns of the result DataFrame.
        """
        if result_type == "summary":
            return self.summary_df.columns.tolist()
        elif result_type == "raw":
            return self.raw_df.columns.tolist()
        else:
            raise ValueError(f"Invalid result type: {result_type}")

# =============================================================================
# FitDataBuilder - Builder Pattern for Complex Aggregation
# =============================================================================

class FitDataBuilder:
    """
    Builder for constructing fit data with proper aggregation.

    Replaces the monolithic create_fit_df() with a step-by-step
    builder that can be customized and tested at each stage.

    The builder tracks metadata throughout the build process, including
    timing for each step, row counts, and price filling statistics.

    ## Attributes:
    - `repository`: DoctrineRepository for database access
    - `price_service`: Optional PriceService for Jita price lookups
    - `logger`: Logger instance for debug/info messages

    ## Example usage:
    ```python
        result = (FitDataBuilder(repo, price_service, logger)
            .load_raw_data()
            .fill_null_prices()
            .aggregate_summaries()
            .calculate_costs()
            .merge_targets()
            .finalize_columns()
            .build())
    ```

    ## Access metadata:
    ```python
        print(result.metadata.summary_string())
        print(f"Build took {result.metadata.total_duration_ms}ms")
    ```

    ## Pipeline Steps:
    ```python
        1. load_raw_data() - Fetch all doctrine items from database 
        2. fill_null_prices() - Apply price fallback chain
        3. aggregate_summaries() - Group by fit_id, calculate fits
        4. calculate_costs() - Sum item costs per fit
        5. merge_targets() - Join target stock levels
        6. finalize_columns() - Select and order output columns
        7. build() - Generate FitBuildResult with domain models
    ```
        """

    def __init__(
        self,
        repository: DoctrineRepository,
        price_service: Optional[PriceService] = None,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the FitDataBuilder.

        Args:
            repository: DoctrineRepository instance for database access.
                       Required for loading fit data and targets.
            price_service: Optional PriceService for Jita price lookups.
                          If not provided, null prices will only be filled
                          from avg_price or defaulted to 0.
            logger: Optional logger instance. If not provided, creates a
                   default logger for the module.
        """
        self._repo = repository
        self._price_service = price_service
        self._logger = logger or logging.getLogger(__name__)

        # Internal state
        self._raw_df: Optional[pd.DataFrame] = None
        self._summary_df: Optional[pd.DataFrame] = None
        self._targets_df: Optional[pd.DataFrame] = None

        # Metadata tracking
        self._metadata = BuildMetadata(has_price_service=price_service is not None)
        self._build_start_time: Optional[float] = None
        self._step_start_time: Optional[float] = None

    def _start_step(self, step_name: str) -> None:
        """Record the start of a build step for timing."""
        self._step_start_time = time.perf_counter()
        if not self._build_start_time:
            self._build_start_time = self._step_start_time
            self._metadata.build_started_at = datetime.now()

    def _end_step(self, step_name: str) -> None:
        """Record the end of a build step and update metadata."""
        if self._step_start_time:
            duration_ms = (time.perf_counter() - self._step_start_time) * 1000
            self._metadata.steps_executed.append(step_name)
            self._metadata.step_durations_ms[step_name] = duration_ms

    # -------------------------------------------------------------------------
    # Builder Steps
    # -------------------------------------------------------------------------

    def load_raw_data(self) -> "FitDataBuilder":
        """
        Load raw fit data from the repository.

        This is Step 1 of the build pipeline. Fetches all rows from the
        doctrines table via DoctrineRepository.get_all_fits().

        The raw DataFrame contains one row per item per fit, with columns:
        - fit_id: Unique identifier for the fit
        - ship_id, ship_name: The ship type this fit is for
        - type_id, type_name: The item in the fit
        - fit_qty: Quantity of this item in the fit
        - price: Current market price (may be null)
        - fits_on_mkt: Number of complete fits supportable by stock
        - hulls: Number of ship hulls in stock
        - group_name, category_id: Item categorization
        - avg_vol: Average daily trading volume

        Returns:
            self for method chaining

        Side Effects:
            - Sets self._raw_df with loaded DataFrame
            - Updates metadata.raw_row_count, unique_fit_count, unique_type_count
            - Logs warning if no data found
        """
        self._start_step('load_raw_data')
        self._logger.info("Loading raw fit data from repository")

        self._raw_df = self._repo.get_all_fits()

        if self._raw_df.empty:
            self._logger.warning("No fit data found in repository")
        else:
            self._metadata.raw_row_count = len(self._raw_df)
            self._metadata.unique_fit_count = self._raw_df['fit_id'].nunique()
            self._metadata.unique_type_count = self._raw_df['type_id'].nunique()

        self._end_step('load_raw_data')
        return self

    def fill_null_prices(self) -> "FitDataBuilder":
        """
        Fill null prices using a fallback chain.

        This is Step 2 of the build pipeline. Applies a three-tier
        fallback strategy for items with missing prices:

        Fallback Chain:
            1. avg_price from marketstats table (via repository)
            2. Jita sell price (via PriceService, if available)
            3. Default to 0 (final fallback)

        The method tracks statistics about how many prices were filled
        from each source, available in metadata after build.

        Returns:
            self for method chaining

        Side Effects:
            - Modifies self._raw_df['price'] to fill null values
            - Updates metadata price-filling statistics:
              - null_prices_found
              - prices_filled_from_avg
              - prices_filled_from_jita
              - prices_defaulted_to_zero
            - Logs warnings for items with null prices
        """
        self._start_step('fill_null_prices')

        if self._raw_df is None or self._raw_df.empty:
            self._end_step('fill_null_prices')
            return self

        null_mask = self._raw_df['price'].isna()
        if not null_mask.any():
            self._logger.info("No null prices to fill")
            self._end_step('fill_null_prices')
            return self

        initial_null_count = null_mask.sum()
        self._metadata.null_prices_found = int(initial_null_count)
        self._logger.info(f"Filling {initial_null_count} null prices")

        # Get unique type_ids with null prices
        null_type_ids = self._raw_df[null_mask]['type_id'].unique().tolist()

        # Log warnings for null prices
        null_items = self._raw_df[null_mask][['type_id', 'type_name', 'fit_id']].drop_duplicates()
        for _, row in null_items.iterrows():
            self._logger.warning(
                f"Null price: {row.get('type_name', 'unknown')} "
                f"(type_id: {row['type_id']}) in fit_id {row['fit_id']}"
            )

        # Step 2a: Try avg_price from repository
        avg_prices = self._repo.get_avg_prices(null_type_ids)
        avg_filled = 0
        for type_id, avg_price in avg_prices.items():
            if pd.notna(avg_price) and avg_price > 0:
                mask = (self._raw_df['type_id'] == type_id) & self._raw_df['price'].isna()
                count_before = self._raw_df['price'].isna().sum()
                self._raw_df.loc[mask, 'price'] = avg_price
                count_after = self._raw_df['price'].isna().sum()
                avg_filled += (count_before - count_after)
                self._logger.debug(f"Filled type_id {type_id} with avg_price: {avg_price}")
        self._metadata.prices_filled_from_avg = avg_filled

        # Step 2b: Try Jita prices for remaining nulls
        jita_filled = 0
        if self._price_service:
            remaining_nulls = self._raw_df['price'].isna()
            if remaining_nulls.any():
                remaining_ids = self._raw_df[remaining_nulls]['type_id'].unique().tolist()
                self._logger.info(f"Fetching Jita prices for {len(remaining_ids)} items")

                jita_result = self._price_service.get_jita_prices(remaining_ids)
                for type_id, price_result in jita_result.prices.items():
                    if price_result.success and price_result.price > 0:
                        mask = (self._raw_df['type_id'] == type_id) & self._raw_df['price'].isna()
                        count_before = self._raw_df['price'].isna().sum()
                        self._raw_df.loc[mask, 'price'] = price_result.price
                        count_after = self._raw_df['price'].isna().sum()
                        jita_filled += (count_before - count_after)
                        self._logger.debug(f"Filled type_id {type_id} with Jita: {price_result.price}")
        self._metadata.prices_filled_from_jita = jita_filled

        # Step 2c: Final fallback to 0
        final_nulls = self._raw_df['price'].isna()
        if final_nulls.any():
            null_count = int(final_nulls.sum())
            self._metadata.prices_defaulted_to_zero = null_count
            self._logger.warning(f"Filling {null_count} remaining prices with 0")
            self._raw_df['price'] = self._raw_df['price'].fillna(0)

        self._metadata.null_prices_filled = (
            self._metadata.prices_filled_from_avg +
            self._metadata.prices_filled_from_jita
        )

        self._end_step('fill_null_prices')
        return self

    def aggregate_summaries(self) -> "FitDataBuilder":
        """
        Aggregate raw data into fit summaries.

        This is Step 3 of the build pipeline. Groups the raw item data
        by fit_id to create one summary row per fit.

        Aggregation Logic:
            - ship_name, ship_id, hulls: First value (same for all items in fit)
            - fits_on_mkt: MINIMUM value (bottleneck item determines fit count)
            - group_name, price, avg_vol: From hull row (where type_id == ship_id)

        The "fits" column represents the number of complete fits that can
        be assembled from current stock, limited by the lowest-stock item.

        Returns:
            self for method chaining

        Side Effects:
            - Creates self._summary_df with one row per fit
            - Updates metadata.summary_row_count
        """
        self._start_step('aggregate_summaries')

        if self._raw_df is None or self._raw_df.empty:
            self._summary_df = pd.DataFrame()
            self._end_step('aggregate_summaries')
            return self

        self._logger.info("Aggregating fit summaries")

        # Basic aggregation: one row per fit_id
        summary = self._raw_df.groupby('fit_id').agg({
            'ship_name': 'first',
            'ship_id': 'first',
            'hulls': 'first',
            'fits_on_mkt': 'min',  # Bottleneck: minimum across all items
        }).reset_index()

        # Get ship-specific data (from hull rows where type_id == ship_id)
        hull_rows = self._raw_df[self._raw_df['type_id'] == self._raw_df['ship_id']]
        ship_data = hull_rows.groupby('fit_id').agg({
            'group_name': 'first',
            'price': 'first',
            'avg_vol': 'first',
        }).reset_index()

        # Merge ship data
        summary = summary.merge(ship_data, on='fit_id', how='left')
        summary['price'] = summary['price'].fillna(0)
        summary['ship_group'] = summary['group_name']

        # Rename for expected output
        summary = summary.rename(columns={'fits_on_mkt': 'fits'})

        self._summary_df = summary
        self._metadata.summary_row_count = len(summary)

        self._end_step('aggregate_summaries')
        return self

    def calculate_costs(self) -> "FitDataBuilder":
        """
        Calculate total cost per fit.

        This is Step 4 of the build pipeline. Computes the total ISK
        cost for each fit by summing (fit_qty * price) for all items.

        Cost Calculation:
            item_cost = fit_qty * price
            total_cost = SUM(item_cost) for all items in fit

        Returns:
            self for method chaining

        Side Effects:
            - Adds 'item_cost' column to self._raw_df
            - Adds 'total_cost' column to self._summary_df
        """
        self._start_step('calculate_costs')

        if self._raw_df is None or self._raw_df.empty:
            self._end_step('calculate_costs')
            return self
        if self._summary_df is None or self._summary_df.empty:
            self._end_step('calculate_costs')
            return self

        self._logger.info("Calculating fit costs")

        # Calculate item costs in raw DataFrame
        self._raw_df['item_cost'] = self._raw_df['fit_qty'] * self._raw_df['price']

        # Aggregate to fit level
        fit_costs = self._raw_df.groupby('fit_id')['item_cost'].sum().reset_index()
        fit_costs = fit_costs.rename(columns={'item_cost': 'total_cost'})

        # Merge into summary
        self._summary_df = self._summary_df.merge(fit_costs, on='fit_id', how='left')
        self._summary_df['total_cost'] = self._summary_df['total_cost'].fillna(0)

        self._end_step('calculate_costs')
        return self

    def merge_targets(self) -> "FitDataBuilder":
        """
        Merge target stock levels from ship_targets table.

        This is Step 5 of the build pipeline. Joins the fit summaries
        with target stock levels and calculates target_percentage.

        Target Percentage Calculation:
            target_percentage = (fits / ship_target) * 100
            - Capped at 100% maximum
            - 0% if ship_target is 0 or missing

        Returns:
            self for method chaining

        Side Effects:
            - Adds 'ship_target' column to self._summary_df
            - Adds 'target_percentage' column to self._summary_df
            - Logs warning if no targets found
        """
        self._start_step('merge_targets')

        if self._summary_df is None or self._summary_df.empty:
            self._end_step('merge_targets')
            return self

        self._logger.info("Merging target data")

        # Get targets from repository
        targets_df = self._repo.get_all_targets()
        if targets_df.empty:
            self._logger.warning("No targets found")
            self._summary_df['ship_target'] = 0
        else:
            targets_df = targets_df.drop_duplicates(subset=['fit_id'], keep='first')
            targets_df = targets_df[['fit_id', 'ship_target']]
            self._summary_df = self._summary_df.merge(targets_df, on='fit_id', how='left')
            self._summary_df['ship_target'] = self._summary_df['ship_target'].fillna(0)

        # Calculate target percentage (vectorized)
        self._summary_df['target_percentage'] = (
            (self._summary_df['fits'] / self._summary_df['ship_target'] * 100)
            .clip(upper=100)
            .fillna(0)
            .astype(int)
        )

        # Handle division by zero
        self._summary_df.loc[self._summary_df['ship_target'] == 0, 'target_percentage'] = 0

        self._end_step('merge_targets')
        return self

    def finalize_columns(self) -> "FitDataBuilder":
        """
        Finalize summary DataFrame with expected columns.

        This is Step 6 of the build pipeline. Selects and orders
        the final output columns for backwards compatibility.

        Output Columns (in order):
            - fit_id: Unique fit identifier
            - ship_name: Name of the ship
            - ship_id: Type ID of the ship
            - hulls: Number of hulls in stock
            - fits: Number of complete fits available (bottleneck)
            - ship_group: Ship group name (e.g., "Battlecruiser")
            - price: Hull price
            - total_cost: Total fit cost
            - ship_target: Target number of fits
            - target_percentage: Percentage of target achieved (0-100)
            - daily_avg: Average daily sales volume

        Returns:
            self for method chaining

        Side Effects:
            - Adds 'daily_avg' column from 'avg_vol'
            - Reorders columns to expected output format
        """
        self._start_step('finalize_columns')

        if self._summary_df is None or self._summary_df.empty:
            self._end_step('finalize_columns')
            return self

        # Set daily_avg column
        if 'avg_vol' in self._summary_df.columns:
            self._summary_df['daily_avg'] = self._summary_df['avg_vol'].fillna(0)
        else:
            self._summary_df['daily_avg'] = 0

        # Select final columns in expected order
        expected_columns = [
            'fit_id', 'ship_name', 'ship_id', 'hulls', 'fits',
            'ship_group', 'price', 'total_cost', 'ship_target',
            'target_percentage', 'daily_avg'
        ]

        # Only include columns that exist
        available_columns = [c for c in expected_columns if c in self._summary_df.columns]
        self._summary_df = self._summary_df[available_columns]

        self._end_step('finalize_columns')
        return self

    def build(self) -> FitBuildResult:
        """
        Finalize the build and return results.

        This is the terminal step of the builder. It creates FitSummary
        domain model objects from the summary DataFrame, calculates the
        lowest-stock modules for each fit, and packages everything into
        a FitBuildResult.

        For each fit, the 3 lowest-stock modules (excluding the hull)
        are identified and stored in FitSummary.lowest_modules.

        Returns:
            FitBuildResult containing:
                - raw_df: Complete item-level DataFrame
                - summary_df: Aggregated fit-level DataFrame
                - summaries: List of FitSummary domain objects
                - metadata: BuildMetadata with timing and statistics

        Example:
            result = builder.load_raw_data().aggregate_summaries().build()
            for fit in result.summaries:
                print(f"{fit.ship_name}: {fit.status.display_name}")
            print(result.metadata.summary_string())
        """
        self._start_step('build')

        if self._raw_df is None:
            self._end_step('build')
            self._finalize_metadata()
            return FitBuildResult(
                raw_df=pd.DataFrame(),
                summary_df=pd.DataFrame(),
                summaries=[],
                metadata=self._metadata
            )

        # Build domain models from summary
        summaries = []
        if self._summary_df is not None and not self._summary_df.empty:
            for _, row in self._summary_df.iterrows():
                fit_id = int(row['fit_id'])

                # Get lowest stock modules for this fit
                fit_items = self._raw_df[self._raw_df['fit_id'] == fit_id]
                ship_id = int(row['ship_id'])

                # Exclude hull, sort by fits_on_mkt, get top 3
                modules = fit_items[fit_items['type_id'] != ship_id]
                lowest = modules.nsmallest(3, 'fits_on_mkt')
                lowest_modules = [
                    f"{r['type_name']} ({int(r['fits_on_mkt'])})"
                    for _, r in lowest.iterrows()
                    if pd.notna(r['type_name']) and pd.notna(r['fits_on_mkt'])
                ]

                summary = FitSummary.from_dataframe_row(row, lowest_modules=lowest_modules)
                summaries.append(summary)

        self._end_step('build')
        self._finalize_metadata()

        return FitBuildResult(
            raw_df=self._raw_df.copy(),
            summary_df=self._summary_df.copy() if self._summary_df is not None else pd.DataFrame(),
            summaries=summaries,
            metadata=self._metadata
        )

    def _finalize_metadata(self) -> None:
        """Finalize metadata with completion time and total duration."""
        self._metadata.build_completed_at = datetime.now()
        if self._build_start_time:
            self._metadata.total_duration_ms = (time.perf_counter() - self._build_start_time) * 1000

    def get_metadata(self) -> BuildMetadata:
        """
        Get current build metadata.

        Can be called at any point during the build to inspect
        current state and timing information.

        Returns:
            BuildMetadata with current statistics
        """
        return self._metadata

    def build_dataframes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Execute build and return just the DataFrames.

        Backwards-compatible method matching create_fit_df() signature.
        """
        result = self.build()
        return result.raw_df, result.summary_df


# =============================================================================
# DoctrineService - Main Service Class
# =============================================================================

class DoctrineService:
    """
    Service for doctrine-related business operations.

    Orchestrates the repository and price service to provide
    high-level operations for Streamlit pages.

    Example usage:
        service = DoctrineService.create_default()

        # Get all fit summaries
        summaries = service.get_all_fit_summaries()

        # Get summaries filtered by status
        critical = service.get_fits_by_status(StockStatus.CRITICAL)

        # Get fit cost analysis
        analysis = service.analyze_fit_cost(fit_id=473)
    """

    def __init__(
        self,
        repository: DoctrineRepository,
        price_service: Optional[PriceService] = None,
        logger: Optional[logging.Logger] = None
    ):
        self._repo = repository
        self._price_service = price_service
        self._logger = logger or logging.getLogger(__name__)

        # Cached build result
        self._cached_result: Optional[FitBuildResult] = None

    @property
    def repository(self) -> DoctrineRepository:
        """Expose repository for direct access when needed."""
        return self._repo

    @classmethod
    def create_default(cls) -> "DoctrineService":
        """
        Factory method to create service with default configuration.

        This is the recommended way to instantiate the service.
        """
        from config import DatabaseConfig

        db = DatabaseConfig("wcmkt")
        repository = DoctrineRepository(db)

        # Price service is optional but recommended
        try:
            from services.price_service import PriceService
            price_service = PriceService.create_default(db_config=db)
        except Exception:
            price_service = None

        return cls(repository=repository, price_service=price_service)

    # -------------------------------------------------------------------------
    # Core Operations
    # -------------------------------------------------------------------------

    def build_fit_data(self, use_cache: bool = True) -> FitBuildResult:
        """
        Build complete fit data using the builder pipeline.

        Args:
            use_cache: If True, return cached result if available

        Returns:
            FitBuildResult with raw data, summaries, and domain models
        """
        if use_cache and self._cached_result is not None:
            return self._cached_result

        self._logger.info("Building fit data")

        result = (
            FitDataBuilder(self._repo, self._price_service, self._logger)
            .load_raw_data()
            .fill_null_prices()
            .aggregate_summaries()
            .calculate_costs()
            .merge_targets()
            .finalize_columns()
            .build()
        )

        self._cached_result = result
        return result

    def get_all_fit_summaries(self) -> list[FitSummary]:
        """
        Get all fit summaries as domain models.
        Returns:
            List of FitSummary objects
        """
        result = self.build_fit_data()
        return result.summaries

    def get_fit_summary(self, fit_id: int) -> Optional[FitSummary]:
        """
        Get a specific fit summary by ID.
        Args:
            fit_id: The fit ID to retrieve
        Returns:
            FitSummary or None if not found
        """
        summaries = self.get_all_fit_summaries()
        for summary in summaries:
            if summary.fit_id == fit_id:
                return summary
        return None

    def get_fits_by_status(self, status: StockStatus) -> list[FitSummary]:
        """
        Get fits filtered by stock status.
        Args:
            status: StockStatus to filter by
        Returns:
            List of FitSummary objects matching the status
        """
        return [s for s in self.get_all_fit_summaries() if s.status == status]

    def get_fits_by_group(self, ship_group: str) -> list[FitSummary]:
        """
        Get fits filtered by ship group.
        Args:
            ship_group: Ship group name (e.g., "Battlecruiser")
        Returns:
            List of FitSummary objects in the group
        """
        return [s for s in self.get_all_fit_summaries() if s.ship_group == ship_group]

    def get_critical_fits(self) -> list[FitSummary]:
        """Get all fits at critical stock levels."""
        return self.get_fits_by_status(StockStatus.CRITICAL)

    def get_low_stock_fits(self) -> list[FitSummary]:
        """
        Get all fits that are below target (Critical + Needs Attention).

        Returns fits where target_percentage <= 90%.
        """
        return [
            s for s in self.get_all_fit_summaries()
            if s.status in (StockStatus.CRITICAL, StockStatus.NEEDS_ATTENTION)
        ]

    def get_good_stock_fits(self) -> list[FitSummary]:
        """Get all fits at good stock levels (> 90% of target)."""
        return self.get_fits_by_status(StockStatus.GOOD)

    def filter_fits_by_status_name(
        self,
        status_name: str,
        summaries: Optional[list[FitSummary]] = None
    ) -> list[FitSummary]:
        """
        Filter fits by status name string (for UI dropdown compatibility).

        Args:
            status_name: One of "All", "Critical", "Needs Attention", "All Low Stock", "Good"
            summaries: Optional list to filter; uses all fits if not provided

        Returns:
            Filtered list of FitSummary objects
        """
        if summaries is None:
            summaries = self.get_all_fit_summaries()

        if status_name == "All":
            return summaries
        elif status_name == "Good":
            return [s for s in summaries if s.status == StockStatus.GOOD]
        elif status_name == "All Low Stock":
            return [s for s in summaries if s.status != StockStatus.GOOD]
        elif status_name == "Needs Attention":
            return [s for s in summaries if s.status == StockStatus.NEEDS_ATTENTION]
        elif status_name == "Critical":
            return [s for s in summaries if s.status == StockStatus.CRITICAL]
        else:
            self._logger.warning(f"Unknown status filter: {status_name}")
            return summaries

    def filter_fits_by_group(
        self,
        ship_group: str,
        summaries: Optional[list[FitSummary]] = None
    ) -> list[FitSummary]:
        """
        Filter fits by ship group.

        Args:
            ship_group: Ship group name or "All"
            summaries: Optional list to filter; uses all fits if not provided

        Returns:
            Filtered list of FitSummary objects
        """
        if summaries is None:
            summaries = self.get_all_fit_summaries()

        if ship_group == "All":
            return summaries

        return [s for s in summaries if s.ship_group == ship_group]

    def apply_target_multiplier(
        self,
        multiplier: float,
        summaries: Optional[list[FitSummary]] = None
    ) -> list[FitSummary]:
        """
        Apply a target multiplier to all fits.

        Args:
            multiplier: Multiplier to apply (e.g., 1.5 = 150% of target)
            summaries: Optional list to modify; uses all fits if not provided

        Returns:
            List of FitSummary objects with adjusted targets
        """
        if summaries is None:
            summaries = self.get_all_fit_summaries()

        if multiplier == 1.0:
            return summaries

        return [s.with_target_multiplier(multiplier) for s in summaries]

    def get_unique_ship_groups(self) -> list[str]:
        """Get sorted list of unique ship groups."""
        summaries = self.get_all_fit_summaries()
        groups = sorted(set(s.ship_group for s in summaries if s.ship_group))
        return groups

    # -------------------------------------------------------------------------
    # Module Status Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def get_module_status(module_fits: int, target: int) -> StockStatus:
        """
        Determine module stock status.

        Args:
            module_fits: Number of fits this module can support
            target: Target number of fits

        Returns:
            StockStatus enum value
        """
        return StockStatus.from_stock_and_target(module_fits, target)

    def get_fit_items(self, fit_id: int) -> list[FitItem]:
        """
        Get all items for a specific fit.
        Args:
            fit_id: The fit ID
        Returns:
            List of FitItem objects
        """
        return self._repo.get_fit_items(fit_id)

    def get_fit_name(self, fit_id: int) -> str:
        """
        Get the name of a specific fit.
        Args:
            fit_id: The fit ID
        Returns:
            The name of the fit
        """
        return self._repo.get_fit_name(fit_id)
    # -------------------------------------------------------------------------
    # Cost Analysis
    # -------------------------------------------------------------------------

    def analyze_fit_cost(
        self,
        fit_id: int,
        jita_price_map: Optional[dict[int, float]] = None
    ) -> Optional["FitCostAnalysis"]:
        """
        Analyze fit cost compared to Jita prices.

        Args:
            fit_id: The fit ID to analyze
            jita_price_map: Optional pre-fetched Jita prices

        Returns:
            FitCostAnalysis from price_service, or None if unavailable
        """
        if not self._price_service:
            self._logger.warning("Price service not available for cost analysis")
            return None

        # Get fit data
        fit_df = self._repo.get_fit_by_id(fit_id)
        if fit_df.empty:
            return None

        # Get current cost from summary
        summary = self.get_fit_summary(fit_id)
        local_cost = summary.total_cost if summary else 0

        return self._price_service.analyze_fit_cost(fit_df, local_cost, jita_price_map)

    def calculate_all_jita_deltas(
        self,
        jita_price_map: Optional[dict[int, float]] = None
    ) -> dict[int, Optional[float]]:
        """
        Calculate Jita price deltas for all fits.

        Args:
            jita_price_map: Optional pre-fetched Jita prices (recommended for performance)

        Returns:
            Dict mapping fit_id to percentage delta (or None if unavailable)
        """
        if not self._price_service:
            self._logger.warning("Price service not available")
            return {}

        result = self.build_fit_data()
        deltas = {}

        # Fetch all Jita prices in one batch if not provided
        if jita_price_map is None:
            all_type_ids = result.raw_df['type_id'].dropna().unique().tolist()
            all_type_ids = [int(t) for t in all_type_ids]
            jita_price_map = self._price_service.get_jita_prices_as_dict(all_type_ids)

        for summary in result.summaries:
            fit_df = result.raw_df[result.raw_df['fit_id'] == summary.fit_id]
            analysis = self._price_service.analyze_fit_cost(
                fit_df, summary.total_cost, jita_price_map
            )
            deltas[summary.fit_id] = analysis.delta_percentage if analysis else None

        return deltas

    # -------------------------------------------------------------------------
    # Cache Management
    # -------------------------------------------------------------------------

    def clear_cache(self):
        """Clear the cached build result."""
        self._cached_result = None
        self._logger.info("Doctrine service cache cleared")

    def refresh(self) -> FitBuildResult:
        """Force refresh of cached data."""
        self.clear_cache()
        return self.build_fit_data(use_cache=False)

# =============================================================================
# Streamlit Integration
# =============================================================================

def get_doctrine_service() -> DoctrineService:
    """
    Get or create a DoctrineService instance.

    Uses Streamlit session state for persistence across reruns.

    Example:
        from services.doctrine_service import get_doctrine_service

        service = get_doctrine_service()
        summaries = service.get_all_fit_summaries()
    """

    if 'doctrine_service' not in st.session_state:
        st.session_state.doctrine_service = DoctrineService.create_default()

    return st.session_state.doctrine_service


# =============================================================================
# Backwards Compatibility
# =============================================================================

def create_fit_df() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Backwards-compatible wrapper for create_fit_df().

    Delegates to DoctrineService but returns the same tuple format
    as the original function.
    """
    service = get_doctrine_service()
    result = service.build_fit_data()
    return result.raw_df, result.summary_df
