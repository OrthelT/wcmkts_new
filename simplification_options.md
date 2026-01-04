# Codebase Simplification Analysis
**Project:** RefactorDoctrines
**Analysis Date:** 2026-01-04
**Scope:** Phases 1-5 Doctrine Refactoring (Pre-Phase 6 Review)

---

## Executive Summary

The Phases 1-5 refactoring has successfully transformed a monolithic doctrine management system into a well-layered architecture. The codebase demonstrates strong adherence to clean architecture principles with clear separation of concerns. However, there are **9 opportunities for simplification** before proceeding to Phase 6 (page refactoring). Most are low-risk, high-benefit changes that will improve maintainability and reduce technical debt.

**Key Findings:**
- **Redundancy:** Helper functions duplicated across 3 domain models (43 occurrences)
- **Over-Engineering:** BuildMetadata tracking 14+ metrics that may not be needed yet
- **Facade Complexity:** 27 methods in DoctrineFacade could be better organized
- **Missing Validation:** Domain models lack input validation despite complex factory methods
- **Inconsistent Patterns:** Mixed use of defaults vs Optional returns

**Overall Health:** GOOD - Solid foundation with minor optimization opportunities

---

## Codebase Shape

### Key Modules
- **domain/** - Immutable dataclasses (FitItem, FitSummary, ModuleStock, Doctrine) + enums (450 LOC)
- **repositories/** - Database access layer (DoctrineRepository with 17 methods, 568 LOC)
- **services/** - Business logic (DoctrineService, PriceService, Categorization, 1019 LOC)
- **facades/** - Unified API (DoctrineFacade with 27 methods, 624 LOC)

### Entry Points
- **Streamlit Pages:** Use `get_doctrine_facade()` as primary interface
- **Direct Access:** Factory functions (get_doctrine_service, get_doctrine_repository, get_price_service)
- **Legacy Compatibility:** Backwards-compatible wrappers maintained

### Architecture Pattern
Clean Architecture with dependency injection:
```
Pages -> Facade -> Services -> Repository -> Database
                            -> Domain Models
```

### Notable Dependencies
- **External:** pandas, requests, streamlit, sqlalchemy, tomllib
- **Internal:** config.DatabaseConfig for DB access
- **Session State:** Lazy initialization via st.session_state for all major services

---

## Prioritized Recommendations

### Priority 1: Eliminate Duplicate Helper Functions in Domain Models

**What:** Consolidate `safe_int()`, `safe_str()`, `safe_float()` helper functions
**Why:** These functions appear **43 times** across 3 domain model factory methods (FitItem.from_dataframe_row, FitSummary.from_dataframe_row, ModuleStock.from_query_results). They're identical implementations doing the same null-safe type conversion.

**Current Code Pattern:**
```python
# In FitItem.from_dataframe_row (lines 82-96)
def safe_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default
    return int(value)

# In FitSummary.from_dataframe_row (lines 176-184) - DUPLICATE
def safe_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default
    return int(value)

# In ModuleStock.from_query_results (lines 333-341) - DUPLICATE
def safe_int(value, default: int = 0) -> int:
    if pd.isna(value):
        return default
    return int(value)
```

**Recommended Solution:**
Create a new file `domain/converters.py`:
```python
"""Type conversion utilities for domain model factories."""
import pandas as pd

def safe_int(value, default: int = 0) -> int:
    """Convert value to int, returning default if null/invalid."""
    if pd.isna(value):
        return default
    return int(value)

def safe_float(value, default: float = 0.0) -> float:
    """Convert value to float, returning default if null/invalid."""
    if pd.isna(value):
        return default
    return float(value)

def safe_str(value, default: str = "") -> str:
    """Convert value to str, returning default if null/invalid."""
    if pd.isna(value):
        return default
    return str(value)
```

Then import in models.py:
```python
from domain.converters import safe_int, safe_float, safe_str
```

**Impact:**
- **Scope:** Small (3 files, ~40 lines moved)
- **Risk:** Low (pure refactor, no logic change)
- **Benefit:** High (DRY principle, single source of truth, easier to enhance)
- **Difficulty:** Easy (30 minutes)

**Dependencies:** None
**Validation:** Run existing tests, verify all factory methods still work

---

### Priority 2: Reduce BuildMetadata Complexity

**What:** Simplify BuildMetadata to track only essential metrics
**Why:** BuildMetadata tracks **14 different metrics** (build times, step durations, row counts, null price stats, etc.) but it's unclear if all are actively used. This adds cognitive load and maintenance burden.

**Current State:**
```python
@dataclass
class BuildMetadata:
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
```

**Questions to Answer:**
1. Are the detailed price-filling stats (`prices_filled_from_avg`, `prices_filled_from_jita`, `prices_defaulted_to_zero`) used in any UI or debugging?
2. Are `step_durations_ms` per-step timings needed, or is `total_duration_ms` sufficient?
3. Is `has_price_service` ever checked programmatically?

**Recommended Approach (Phased):**

**Phase A: Add Usage Tracking (Do First)**
- Add logging to see which metadata fields are actually accessed
- Monitor for 1-2 weeks to understand real usage patterns

**Phase B: Simplify Based on Data**
- Keep: `total_duration_ms`, `summary_row_count`, `null_prices_found`
- Consider removing: Individual step timings, granular price source counts
- Move detailed metrics to a separate `DebugMetadata` class for opt-in verbose mode

**Impact:**
- **Scope:** Medium (affects FitDataBuilder and consumers)
- **Risk:** Low (metadata is informational, not functional)
- **Benefit:** Medium (reduced complexity, clearer intent)
- **Difficulty:** Moderate (requires usage analysis first)

**Dependencies:** Need to audit where metadata is consumed
**Validation:** Ensure no critical monitoring relies on removed fields

---

### Priority 3: Add Input Validation to Domain Model Factory Methods

**What:** Add validation to factory methods that create domain models from DataFrames
**Why:** Factory methods like `FitItem.from_dataframe_row()` accept any pandas Series without validating required fields exist. This can lead to silent failures or confusing errors downstream.

**Current Code (FitItem.from_dataframe_row):**
```python
return cls(
    fit_id=safe_int(row.get('fit_id')),  # What if 'fit_id' doesn't exist?
    type_id=safe_int(row.get('type_id')),
    type_name=safe_str(row.get('type_name')),
    # ...
)
```

**Problem Scenarios:**
- If database schema changes and column is renamed, `row.get('fit_id')` returns `None`
- `safe_int(None)` returns `0` (the default)
- A FitItem is created with `fit_id=0`, which is semantically invalid
- Error surfaces much later when logic breaks on invalid ID

**Recommended Solution:**
```python
@dataclass(frozen=True)
class FitItem:
    # ... existing fields ...

    @classmethod
    def from_dataframe_row(cls, row: pd.Series) -> "FitItem":
        """Create FitItem from DataFrame row with validation."""
        # Validate required fields exist
        required_fields = ['fit_id', 'type_id', 'type_name']
        missing = [f for f in required_fields if f not in row or pd.isna(row[f])]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        # Validate fit_id and type_id are positive
        fit_id = safe_int(row.get('fit_id'))
        type_id = safe_int(row.get('type_id'))

        if fit_id <= 0:
            raise ValueError(f"Invalid fit_id: {fit_id}")
        if type_id <= 0:
            raise ValueError(f"Invalid type_id: {type_id}")

        return cls(
            fit_id=fit_id,
            type_id=type_id,
            type_name=safe_str(row.get('type_name')),
            # ... rest of fields
        )
```

**Impact:**
- **Scope:** Small (3-4 factory methods)
- **Risk:** Medium (could surface errors in existing data that were silently handled)
- **Benefit:** High (fail-fast principle, clearer error messages, prevents data corruption)
- **Difficulty:** Easy (add validation, write tests)

**Dependencies:** None
**Validation:** Add tests with invalid data, ensure graceful error handling in callers

**Rollout Strategy:**
1. Start with logging warnings instead of raising exceptions
2. Monitor logs for actual invalid data
3. Fix any data quality issues found
4. Switch to raising exceptions

---

### Priority 4: Simplify Facade API Surface

**What:** Reorganize DoctrineFacade's 27 methods into logical groups or sub-facades
**Why:** The facade has grown large with diverse responsibilities. While this provides convenience, it violates the Interface Segregation Principle and makes the class harder to understand and test.

**Current Structure:**
- 6 fit operations (get_all_fit_summaries, get_fit_summary, get_fits_by_status, etc.)
- 2 module operations (get_module_stock, get_modules_stock)
- 4 doctrine operations (get_doctrine, get_all_doctrines, etc.)
- 1 categorization operation (categorize_ship)
- 4 price operations (get_jita_price, calculate_fit_jita_delta, etc.)
- 4 bulk operations (refresh_all_data, clear_caches, etc.)
- 1 utility method (get_fit_items)

**Analysis:** The facade is mixing:
1. **Query Operations** (read-only data access)
2. **Analysis Operations** (computations like Jita delta)
3. **Cache Management** (refresh, clear)
4. **Categorization** (ship role logic)

**Option A: Sub-Facades (Composition)**
```python
class DoctrineFacade:
    def __init__(self, ...):
        self.fits = FitQueries(...)
        self.modules = ModuleQueries(...)
        self.doctrines = DoctrineQueries(...)
        self.analysis = PriceAnalysis(...)
        self.cache = CacheManager(...)
```

Usage:
```python
facade = get_doctrine_facade()
summaries = facade.fits.get_all()
critical = facade.fits.get_by_status(StockStatus.CRITICAL)
delta = facade.analysis.calculate_jita_delta(fit_id)
```

**Option B: Keep Current, Add Method Grouping Comments**
```python
class DoctrineFacade:
    # =========================================================================
    # Fit Queries
    # =========================================================================
    def get_all_fit_summaries(self) -> list[FitSummary]: ...
    def get_fit_summary(self, fit_id: int) -> Optional[FitSummary]: ...
    # ... (already has this structure)
```

**Recommendation:** **Option B** for now, with **Option A** as future enhancement if facade continues to grow.

**Rationale:**
- Current grouping comments already provide organization
- 27 methods is manageable for a facade (not excessive yet)
- Pages already use this API; changing would require updating all page files
- Wait until Phase 6 (page refactoring) to see actual usage patterns before splitting

**Impact:**
- **Scope:** Large if choosing Option A (affects all page code)
- **Risk:** Low for Option B (no change), Medium for Option A (API break)
- **Benefit:** Medium (better organization, but current state is workable)
- **Difficulty:** Easy for Option B, Moderate for Option A

**Dependencies:** Phase 6 page refactoring
**Status:** DEFERRED until Phase 6 reveals usage patterns

---

### Priority 5: Inconsistent Default Handling - Target Values

**What:** Standardize default values for target lookups across repository and service layers
**Why:** `get_target_by_fit_id()` and `get_target_by_ship_id()` both default to `20`, but this magic number is hardcoded in two places with no clear rationale.

**Current Code:**
```python
# repositories/doctrine_repo.py
def get_target_by_fit_id(self, fit_id: int, default: int = 20) -> int:
    """Get target stock level for a specific fit."""
    # ...
    return default

def get_target_by_ship_id(self, ship_id: int, default: int = 20) -> int:
    """Get target stock level for a specific ship type."""
    # ...
    return default
```

**Questions:**
1. Why is 20 the default target? Is this a business rule?
2. Should "no target set" be represented differently (e.g., `None` or `Optional[int]`)?
3. Do different ship classes have different default targets?

**Recommended Solution:**
```python
# config.py or domain/constants.py
DEFAULT_SHIP_TARGET = 20  # Default stock target when not explicitly set

# repositories/doctrine_repo.py
from config import DEFAULT_SHIP_TARGET

def get_target_by_fit_id(
    self,
    fit_id: int,
    default: int = DEFAULT_SHIP_TARGET
) -> int:
    """
    Get target stock level for a specific fit.

    Args:
        fit_id: The fit ID to look up
        default: Default value if not found (default: DEFAULT_SHIP_TARGET)

    Returns:
        Target stock level, or default if not found
    """
    # ...
```

**Alternative (More Explicit):**
```python
def get_target_by_fit_id(self, fit_id: int) -> Optional[int]:
    """Get target stock level for a specific fit, or None if not set."""
    # ...
    if not df.empty and pd.notna(df.loc[0, 'ship_target']):
        return int(df.loc[0, 'ship_target'])
    return None  # Explicit: no target configured
```

Then callers decide the fallback:
```python
target = repo.get_target_by_fit_id(473) or DEFAULT_SHIP_TARGET
```

**Impact:**
- **Scope:** Small (2 methods + constant definition)
- **Risk:** Low (logic unchanged, just centralized)
- **Benefit:** Medium (clearer intent, easier to change default)
- **Difficulty:** Easy (15 minutes)

**Dependencies:** None
**Validation:** Verify all callers handle the default correctly

---

### Priority 6: Redundant DataFrame Operations in FitDataBuilder

**What:** The builder performs redundant DataFrame operations when handling ship-specific data
**Why:** In `aggregate_summaries()`, the code filters `hull_rows` then immediately groups by `fit_id`, when it could directly filter and get first value in the main aggregation.

**Current Code (lines 467-486):**
```python
def aggregate_summaries(self) -> "FitDataBuilder":
    # Basic aggregation: one row per fit_id
    summary = self._raw_df.groupby('fit_id').agg({
        'ship_name': 'first',
        'ship_id': 'first',
        'hulls': 'first',
        'fits_on_mkt': 'min',
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
```

**Problem:** This creates `hull_rows` DataFrame, then groups it, then merges back. Two DataFrame copies and a merge operation.

**Optimized Approach:**
```python
def aggregate_summaries(self) -> "FitDataBuilder":
    # Create a function to get hull value
    def get_hull_value(group, column):
        hull_row = group[group['type_id'] == group['ship_id'].iloc[0]]
        if not hull_row.empty:
            return hull_row.iloc[0][column]
        return None

    summary = self._raw_df.groupby('fit_id').agg({
        'ship_name': 'first',
        'ship_id': 'first',
        'hulls': 'first',
        'fits_on_mkt': 'min',
        'group_name': lambda x: get_hull_value(x.group, 'group_name'),
        'price': lambda x: get_hull_value(x.group, 'price'),
        'avg_vol': lambda x: get_hull_value(x.group, 'avg_vol'),
    }).reset_index()
```

**Wait, that's more complex!** Let me reconsider...

**Actually Better Approach:**
Keep current implementation but combine the two groupby operations:
```python
def aggregate_summaries(self) -> "FitDataBuilder":
    # Single-pass aggregation with conditional selection
    def first_hull_value(series, fit_data):
        # Get value from row where type_id == ship_id
        hull_mask = fit_data['type_id'] == fit_data['ship_id'].iloc[0]
        if hull_mask.any():
            return series[hull_mask].iloc[0]
        return None

    # Actually, current approach is fine - it's clear and performs well enough
```

**Verdict:** **REJECTED** - Current approach is clear and maintainable. Optimization would sacrifice readability for negligible performance gain (runs once per page load).

**Impact:**
- **Scope:** Small (one method)
- **Risk:** Low
- **Benefit:** Low (negligible performance improvement)
- **Difficulty:** Moderate (requires careful testing)

**Status:** REJECTED (clarity > micro-optimization)

---

### Priority 7: Missing Type Hints in Some Factory Functions

**What:** Some factory/helper functions lack complete type hints
**Why:** Inconsistent typing makes it harder for IDEs to provide autocomplete and catch type errors

**Examples:**
```python
# repositories/doctrine_repo.py, line 524
def get_methods(print_methods: bool = False) -> list[str]:  # Should return Optional[list[str]]
    """Get all methods of the DoctrineRepository class."""
    methods: list[dict[str, str]] = []  # Type says dict, but code appends strings
    # ...
    if print_methods:
        # ... prints to stdout, returns None implicitly
    else:
        return methods  # Returns list[str], not list[dict]
```

**Issues:**
1. Type annotation says `list[dict[str, str]]` but code appends strings
2. Return type says `list[str]` but can return `None` when `print_methods=True`
3. Function has side effect (printing) mixed with return value

**Recommended Fix:**
```python
def get_methods(print_methods: bool = False) -> Optional[list[str]]:
    """
    Get all public methods of the DoctrineRepository class.

    Args:
        print_methods: If True, print methods with docs instead of returning

    Returns:
        List of method names if print_methods=False, None otherwise
    """
    method_names: list[str] = []

    for attr in dir(DoctrineRepository):
        if attr.startswith("_"):
            continue
        method_names.append(attr)

    if print_methods:
        for name in method_names:
            method = getattr(DoctrineRepository, name)
            doc = method.__doc__ if method.__doc__ else 'No documentation'
            print(f"{name}: {doc}")
            print("----------------------------------------")
        return None
    else:
        return method_names
```

**Even Better: Separate Concerns**
```python
def get_methods() -> list[str]:
    """Get list of all public method names."""
    return [attr for attr in dir(DoctrineRepository) if not attr.startswith("_")]

def print_methods() -> None:
    """Print all methods with their documentation."""
    for name in get_methods():
        method = getattr(DoctrineRepository, name)
        doc = method.__doc__ or 'No documentation'
        print(f"{name}: {doc}")
        print("----------------------------------------")
```

**Impact:**
- **Scope:** Small (1-2 methods)
- **Risk:** Low
- **Benefit:** Medium (better IDE support, clearer API)
- **Difficulty:** Easy (20 minutes)

**Dependencies:** None
**Validation:** Run mypy or pyright to verify type correctness

---

### Priority 8: Consider Extracting Safe Conversion to Domain Layer

**What:** Move pandas-specific conversion logic out of domain models
**Why:** Domain models (FitItem, FitSummary, etc.) are coupled to pandas via `from_dataframe_row()` factory methods. This violates dependency inversion - domain shouldn't know about infrastructure (pandas).

**Current Architecture:**
```
domain/models.py
  └─ from_dataframe_row(row: pd.Series)  # Domain depends on pandas
```

**Cleaner Architecture:**
```
domain/models.py
  └─ __init__(fit_id: int, type_id: int, ...)  # Pure domain, no pandas

repositories/doctrine_repo.py or adapters/
  └─ dataframe_to_fit_item(row: pd.Series) -> FitItem
      └─ calls FitItem(...) constructor with converted values
```

**Benefits:**
1. Domain models become pure Python (no pandas dependency)
2. Easier to test domain logic without DataFrame fixtures
3. Adapters can be swapped (e.g., from JSON, from API response)
4. Clearer separation of concerns

**Trade-offs:**
1. Adds one more layer of indirection
2. Factory methods are convenient for repository layer
3. Pandas is already a core dependency, unlikely to change

**Recommendation:** **DEFERRED** - This is good architecture but not urgent. The current approach works well for a pandas-centric application. Consider if:
- You need to support non-DataFrame data sources
- You're building a domain model that will be used outside this codebase
- Testing becomes difficult due to DataFrame coupling

**Impact:**
- **Scope:** Large (all domain models + all factory callers)
- **Risk:** Medium (significant refactoring)
- **Benefit:** Medium (better architecture, but current design is acceptable)
- **Difficulty:** Moderate (requires new adapter layer)

**Dependencies:** Would benefit from Phase 6 page refactoring to see how models are used
**Status:** DEFERRED (not needed before Phase 6)

---

### Priority 9: Potential Over-Caching in Categorization Service

**What:** `ConfigBasedCategorizer._load_config()` uses `@cache` decorator, caching TOML file for entire process lifetime
**Why:** While this improves performance, it means settings.toml changes require app restart

**Current Code:**
```python
@staticmethod
@cache
def _load_config() -> ShipRoleConfig:
    """Load configuration from TOML (cached for process lifetime)."""
    return ShipRoleConfig.from_toml("settings.toml")
```

**Questions:**
1. How often do ship role configurations change?
2. Is there a UI to reload settings without restart?
3. Does Streamlit auto-reload handle this?

**Options:**

**Option A: Keep Current (Recommended)**
- Ship roles rarely change in production
- Performance benefit is significant (no repeated file I/O)
- Streamlit dev mode auto-restarts on file changes anyway
- **Status:** ACCEPTED - current design is appropriate

**Option B: TTL-based Cache**
```python
from functools import lru_cache
import time

class ConfigBasedCategorizer:
    _last_load_time = 0
    _cache_ttl = 300  # 5 minutes
    _cached_config = None

    @classmethod
    def _load_config(cls) -> ShipRoleConfig:
        now = time.time()
        if cls._cached_config is None or (now - cls._last_load_time) > cls._cache_ttl:
            cls._cached_config = ShipRoleConfig.from_toml("settings.toml")
            cls._last_load_time = now
        return cls._cached_config
```

**Option C: Add Manual Reload**
```python
class ConfigBasedCategorizer:
    @classmethod
    def reload_config(cls) -> None:
        """Force reload of configuration from disk."""
        cls._load_config.cache_clear()
```

**Recommendation:** **Keep Option A**, but document the caching behavior clearly. Add Option C (reload method) only if needed.

**Impact:**
- **Scope:** Small (one method)
- **Risk:** Low
- **Benefit:** Low (current behavior is fine for production)
- **Difficulty:** Easy

**Status:** ACCEPTED as-is, with note to add `reload_config()` if hot-reload becomes needed

---

## Additional Observations

### Strengths of Current Design

1. **Excellent Layering:** Clear separation of domain, repository, service, and facade layers
2. **Immutability:** Domain models use `frozen=True`, preventing accidental mutations
3. **Type Safety:** Extensive use of type hints and domain enums (ShipRole, StockStatus)
4. **Testability:** Dependency injection throughout, making unit testing straightforward
5. **Documentation:** Comprehensive docstrings with examples in facade and services
6. **Backwards Compatibility:** Legacy function wrappers ease migration from old code

### Naming Consistency

**Generally Good:**
- Consistent `get_*` prefix for queries
- Clear domain terminology (fit, doctrine, module, ship)
- Enum values match business language

**Minor Inconsistency:**
- `get_all_fit_summaries()` vs `get_all_targets()` - mixing "fit" and generic "all"
- `get_jita_price()` vs `calculate_fit_jita_delta()` - get vs calculate prefix mixing
- **Status:** Low priority, not worth changing existing API

### Documentation Clarity

**Excellent:**
- All major classes have comprehensive docstrings
- Examples provided for complex operations
- Factory functions documented with usage patterns

**Could Improve:**
- BuildMetadata fields lack clear description of "when to use this metric"
- Some helper methods (like `safe_int`) lack docstrings in current implementation
- **Recommendation:** Add docstrings when consolidating helpers (Priority 1)

### Testability Assessment

**Current State:**
- Services use dependency injection ✓
- Domain models are pure functions of their inputs ✓
- Repository separated from business logic ✓

**Potential Issues:**
- No validation in factory methods makes testing edge cases harder (Priority 3)
- BuildMetadata coupling makes testing builder steps verbose (Priority 2)
- Facade's 27 methods mean large test surface area (Priority 4, deferred)

**Overall:** Good testability, minor improvements needed

---

## Performance Considerations

### Identified Inefficiencies

**None Critical** - The refactoring has actually improved performance by:
- Eliminating duplicate database queries (consolidated in repository)
- Caching TOML config (categorization service)
- Batch price fetching (PriceService)

### Potential Future Optimizations

1. **DataFrame Operations:** Builder creates multiple intermediate DataFrames, but this is acceptable for current scale
2. **Lazy Loading:** Facade properties use lazy initialization, which is good
3. **Price Caching:** PriceService implements in-memory cache with TTL

**Status:** No action needed now, monitor as data scale increases

---

## Questions for Clarification

Before implementing recommendations, please clarify:

1. **BuildMetadata (Priority 2):** Are the detailed per-step timings and granular price stats actively monitored in production or debugging workflows?

2. **Default Target (Priority 5):** What's the business rule for the "20" default target? Is it universal or should it vary by ship class?

3. **Facade Splitting (Priority 4):** How are pages currently using the facade? All 27 methods or subset? This informs whether splitting is worthwhile.

4. **Validation Strictness (Priority 3):** Should invalid data (missing fit_id, type_id) fail loudly with exceptions, or log warnings and use defaults?

5. **Settings Hot-Reload (Priority 9):** Is there ever a need to reload settings.toml without restarting the Streamlit app?

---

## Implementation Roadmap

### Phase A: Quick Wins (Before Phase 6)
**Time: 2-3 hours**

1. **Priority 1:** Extract helper functions to `domain/converters.py` ✓ High benefit, low risk
2. **Priority 5:** Centralize DEFAULT_SHIP_TARGET constant ✓ Easy, improves clarity
3. **Priority 7:** Fix type hints in `get_methods()` ✓ IDE support improvement

### Phase B: Validation & Safety (Before or During Phase 6)
**Time: 4-6 hours**

4. **Priority 3:** Add input validation to factory methods
   - Start with logging warnings
   - Monitor for actual data issues
   - Switch to exceptions after data quality confirmed

### Phase C: Architecture Review (During/After Phase 6)
**Time: Variable, depends on findings**

5. **Priority 2:** Simplify BuildMetadata based on usage analysis
   - Instrument code to track which fields are accessed
   - Collect data during Phase 6 testing
   - Remove unused fields or split into DebugMetadata

6. **Priority 4:** Evaluate facade organization based on actual page usage
   - Complete Phase 6 page refactoring first
   - Analyze which facade methods are used together
   - Decide if sub-facades would improve page code

### Phase D: Advanced (Future, If Needed)
**Time: 8-12 hours**

7. **Priority 8:** Extract DataFrame adapters (only if needed)
   - Consider when adding non-DataFrame data sources
   - Or when testing becomes painful

---

## Success Metrics

After implementing Phases A & B recommendations:

- [ ] **DRY:** No duplicate helper functions (from 43 to 3 implementations)
- [ ] **Clarity:** Magic number "20" replaced with named constant
- [ ] **Safety:** Factory methods validate required fields
- [ ] **Type Safety:** All public functions have complete type hints
- [ ] **Documentation:** All helper functions have docstrings

**Target:** Complete Phase A & B before starting Phase 6 page refactoring

---

## Notes

**Status Key:**
- **RECOMMENDED:** High-value simplification, should implement
- **DEFERRED:** Good idea but wait for more context (Phase 6)
- **REJECTED:** Considered but not worth the trade-offs
- **ACCEPTED:** Current design is correct, no change needed

**Last Updated:** 2026-01-04
**Next Review:** After Phase 6 completion (page refactoring)
