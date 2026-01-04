# Doctrine Module Refactoring Plan

## Quick Resume Guide

**Current Status:** Phases 1-4 complete, ready for Phase 5 (Facade)

**Completed Packages:**
```
domain/           # Dataclasses: FitItem, FitSummary, ModuleStock, Doctrine
  ├── enums.py    # StockStatus, ShipRole enums + from_string(), display_name
  └── models.py   # Domain model dataclasses

repositories/     # Database access layer
  └── doctrine_repo.py  # DoctrineRepository (17 methods)

services/         # Business logic layer
  ├── price_service.py        # PriceService (already existed)
  ├── doctrine_service.py     # DoctrineService + FitDataBuilder + BuildMetadata
  └── categorization.py       # ShipRoleCategorizer + ConfigBasedCategorizer
```

**To continue, read these files:**
1. `services/categorization.py` - Latest work (cached categorization, Protocol pattern)
2. `services/doctrine_service.py` - Business logic with Builder pattern
3. `repositories/doctrine_repo.py` - All 17 repository methods
4. `pages/doctrine_status.py` - Page to refactor with facade
5. `pages/doctrine_report.py` - Page to refactor with facade

**Next task:** Create `facades/doctrine_facade.py` with simplified API for Streamlit

---

## Project Overview

This document summarizes the architectural analysis and refactoring work for the doctrine-related modules in the `wcmkts_new` Streamlit application. The goal is to transform scattered, tightly-coupled code into a clean, maintainable architecture using advanced Python patterns.

---

## Current Architecture (Before Refactoring)

### Key Files Analyzed

| File | Purpose | Lines |
|------|---------|-------|
| `doctrines.py` | Core data functions (`create_fit_df`, `get_all_fit_data`) | ~265 |
| `pages/doctrine_status.py` | Streamlit page for ship/module status | ~990 |
| `pages/doctrine_report.py` | Streamlit page for doctrine-based reporting | ~505 |
| `db_handler.py` | Database access functions | ~510 |
| `utils.py` | Utility functions including price fetching | ~225 |
| `config.py` | `DatabaseConfig` class with connection management | ~450 |

### Problems Identified

1. **Code Duplication**
   - `get_module_stock_list()` exists in both `doctrine_status.py` (lines 141-221) and `doctrine_report.py` (lines 21-51)
   - `get_fit_name()` / `get_fit_name_from_db()` are similar functions in different files
   - Price fetching logic scattered across `utils.py`, `doctrines.py`, and `doctrine_status.py`

2. **No Domain Models**
   - Raw DataFrames passed everywhere without typed structure
   - Implicit column requirements (e.g., expecting `'type_id'`, `'fit_qty'` columns)
   - Business logic embedded in presentation layer

3. **Tight Coupling**
   - Database access, business logic, and presentation mixed together
   - Functions create `DatabaseConfig` instances internally rather than receiving them
   - Session state management scattered across functions

4. **Long Functions**
   - `create_fit_df()` in `doctrines.py` is ~175 lines doing multiple responsibilities
   - `main()` functions in pages are 400+ lines

5. **Inline Configuration**
   - `categorize_ship_by_role()` loads TOML file on every call (no caching)

---

## Recommended Architecture (Target State)

```
wcmkts_new/
├── domain/
│   ├── __init__.py
│   ├── models.py          # Dataclasses: FitSummary, FitItem, Doctrine, ModuleStock
│   └── enums.py           # Status enums, role types, price sources
├── repositories/
│   ├── __init__.py
│   ├── base.py            # Abstract repository protocol
│   └── doctrine_repo.py   # DoctrineRepository
├── services/
│   ├── __init__.py
│   ├── price_service.py   # ✅ COMPLETED - Price fetching with fallback chain
│   ├── doctrine_service.py    # Business logic orchestration
│   └── categorization.py      # Ship role categorization strategies
├── facades/
│   ├── __init__.py
│   └── doctrine_facade.py     # Simplified interface for Streamlit pages
├── pages/
│   ├── doctrine_status.py     # Uses facade (simplified)
│   └── doctrine_report.py     # Uses facade (simplified)
├── config.py                  # DatabaseConfig (unchanged)
├── db_handler.py              # Keep for non-doctrine queries
└── doctrines.py               # Eventually deprecated, replaced by services
```

---

## Patterns to Apply

### 1. Dataclasses for Domain Models
```python
@dataclass(frozen=True)
class FitSummary:
    fit_id: int
    ship_name: str
    ship_id: int
    fits: int
    hulls: int
    ship_target: int
    target_percentage: int
    total_cost: float
    items: list[FitItem]

    @property
    def is_critical(self) -> bool:
        return self.target_percentage <= 40
```

### 2. Repository Pattern
```python
class DoctrineRepository:
    def __init__(self, db: DatabaseConfig):
        self._db = db

    def get_all_fits(self) -> pd.DataFrame: ...
    def get_fit_by_id(self, fit_id: int) -> pd.DataFrame: ...
    def get_targets(self) -> pd.DataFrame: ...
```

### 3. Dependency Injection
```python
class DoctrineService:
    def __init__(self, repository: DoctrineRepository, price_service: PriceService):
        self._repo = repository
        self._prices = price_service
```

### 4. Strategy Pattern (for categorization)
```python
class ShipRoleCategorizer(Protocol):
    def categorize(self, ship_name: str, fit_id: int) -> str: ...

class ConfigBasedCategorizer:
    @lru_cache(maxsize=1)
    def _load_config(self): ...
```

### 5. Builder Pattern (for complex DataFrame construction)
```python
class FitDataBuilder:
    def load_raw_data(self) -> "FitDataBuilder": ...
    def aggregate_summaries(self) -> "FitDataBuilder": ...
    def calculate_costs(self) -> "FitDataBuilder": ...
    def build(self) -> tuple[pd.DataFrame, pd.DataFrame]: ...
```

### 6. Facade Pattern (simplified interface)
```python
class DoctrineFacade:
    def get_all_fit_summaries(self) -> list[FitSummary]: ...
    def get_fits_by_status(self, status: str) -> list[FitSummary]: ...
    def get_module_stock_info(self, names: list[str]) -> dict: ...
```

---

## Completed Work

### `services/price_service.py` (✅ Complete)

**Commit:** `f0671d2 feat: add price_service.py demonstrating advanced Python patterns`

This module demonstrates all the patterns above and consolidates price logic from:
- `utils.py` (`get_jita_price`, `get_multi_item_jita_price`, `get_janice_price`)
- `doctrines.py` (`calculate_jita_fit_cost_and_delta`, null price handling in `create_fit_df`)
- `doctrine_status.py` (`fetch_jita_prices_for_types`)

**Key Components:**

| Component | Type | Purpose |
|-----------|------|---------|
| `PriceResult` | Dataclass | Immutable result of a price lookup |
| `BatchPriceResult` | Dataclass | Result of batch price lookup with stats |
| `FitCostAnalysis` | Dataclass | Cost comparison analysis for a fit |
| `PriceSource` | Enum | Identifies price data source |
| `PriceProvider` | Protocol | Interface for price providers |
| `FuzzworkProvider` | Class | Primary Jita price provider |
| `JaniceProvider` | Class | Fallback Jita price provider |
| `LocalMarketProvider` | Class | Local database price provider |
| `FallbackPriceProvider` | Class | Chain of responsibility for fallback |
| `PriceService` | Class | Main facade for all price operations |
| `get_price_service()` | Function | Streamlit session state integration |

**Backwards Compatibility:** Wrapper functions maintain API compatibility:
```python
def get_jita_price(type_id: int) -> float:
    """Backwards-compatible wrapper."""
    return get_price_service().get_jita_price(type_id).price
```

### `domain/` Package (✅ Complete)

Domain models providing typed, immutable structures to replace raw DataFrame rows.

**Files Created:**
- `domain/__init__.py` - Package exports
- `domain/enums.py` - Status and role enumerations
- `domain/models.py` - Core domain dataclasses

**Key Components:**

| Component | Type | Purpose |
|-----------|------|---------|
| `StockStatus` | Enum | Stock levels (CRITICAL, NEEDS_ATTENTION, GOOD) with display helpers |
| `ShipRole` | Enum | Ship roles (DPS, LOGI, LINKS, SUPPORT) with styling metadata |
| `FitItem` | Dataclass | Individual item in a fit (module, hull, ammo) |
| `FitSummary` | Dataclass | Aggregated fit summary with computed properties |
| `ModuleStock` | Dataclass | Module with stock levels and usage info |
| `ModuleUsage` | Dataclass | Where a module is used (ship_name, qty) |
| `Doctrine` | Dataclass | Fleet doctrine grouping multiple fits |

**Design Principles Applied:**
- `frozen=True` for immutability and hashability (safe for caching)
- Factory methods (`from_dataframe_row`) for clean construction from pandas
- Computed properties encapsulate business logic (e.g., `target_percentage`, `status`)
- Type aliases (`TypeID`, `FitID`, `Price`) for code clarity

**Example Usage:**
```python
from domain import FitSummary, StockStatus

# Create from DataFrame row
summary = FitSummary.from_dataframe_row(row, lowest_modules=['Module A', 'Module B'])

# Access computed properties
print(f"Status: {summary.status.display_name}")  # "Needs Attention"
print(f"Color: {summary.status.display_color}")  # "orange"

# Apply target multiplier (returns new immutable instance)
adjusted = summary.with_target_multiplier(1.5)
```

### `repositories/` Package (✅ Complete)

Repository layer encapsulating all doctrine-related database access.

**Files Created:**
- `repositories/__init__.py` - Package exports
- `repositories/doctrine_repo.py` - DoctrineRepository class

**Consolidated Queries From:**
- `doctrines.py` - `get_all_fit_data()`, `get_target_from_fit_id()`, `new_get_targets()`
- `doctrine_status.py` - `get_fit_name()`, `get_ship_target()`, `get_module_stock_list()`
- `doctrine_report.py` - `get_fit_name_from_db()`, `get_doctrine_lead_ship()`, `get_module_stock_list()`

**Key Methods (17 total):**

| Method | Purpose | Replaces |
|--------|---------|----------|
| `get_all_fits()` | All doctrine fit data | `doctrines.get_all_fit_data()` |
| `get_fit_by_id(fit_id)` | Items for specific fit | Direct queries |
| `get_all_targets()` | All ship targets | `doctrines.new_get_targets()` |
| `get_target_by_fit_id(fit_id)` | Target for a fit | Duplicate queries in both pages |
| `get_fit_name(fit_id)` | Display name for fit | `get_fit_name()` in both pages |
| `get_all_doctrine_compositions()` | Fleet doctrines | `doctrine_report.py` query |
| `get_doctrine_lead_ship(id)` | Lead ship for doctrine | `get_doctrine_lead_ship()` |
| `get_module_stock(name)` | Module stock as domain model | `get_module_stock_list()` in both pages |
| `get_fit_items(fit_id)` | Items as `list[FitItem]` | N/A (new) |
| `get_doctrine(name)` | Complete `Doctrine` model | N/A (new) |

**Example Usage:**
```python
from repositories import get_doctrine_repository

repo = get_doctrine_repository()

# Raw DataFrame access
fits_df = repo.get_all_fits()  # 2026 rows, 107 unique fits

# Simple lookups
target = repo.get_target_by_fit_id(473)  # Returns 50
name = repo.get_fit_name(473)  # Returns "WC-EN Shield DPS FNI v1.0"

# Domain model access
items = repo.get_fit_items(473)  # Returns list[FitItem]
doctrine = repo.get_doctrine("SUBS - WC Hurricane")  # Returns Doctrine
module = repo.get_module_stock("Damage Control II")  # Returns ModuleStock
```

### `services/doctrine_service.py` (✅ Complete)

Business logic layer using Builder pattern for complex data aggregation.

**Key Components:**

| Component | Type | Purpose |
|-----------|------|---------|
| `BuildMetadata` | Dataclass | Tracks timing, counts, and price-fill statistics |
| `FitBuildResult` | Dataclass | Build output with raw_df, summary_df, domain models, and metadata |
| `FitDataBuilder` | Class | Builder pattern for step-by-step DataFrame construction |
| `DoctrineService` | Class | Main service orchestrating repository + price service |
| `get_doctrine_service()` | Function | Streamlit session state integration |
| `create_fit_df()` | Function | Backwards-compatible wrapper |

**Builder Pipeline (replaces 175-line `create_fit_df()`):**
```python
result = (FitDataBuilder(repo, price_service, logger)
    .load_raw_data()        # Step 1: Fetch from repository
    .fill_null_prices()     # Step 2: avg_price -> Jita -> 0 fallback
    .aggregate_summaries()  # Step 3: Group by fit_id
    .calculate_costs()      # Step 4: Sum item costs
    .merge_targets()        # Step 5: Join ship_targets
    .finalize_columns()     # Step 6: Select output columns
    .build())               # Returns FitBuildResult with metadata
```

**BuildMetadata Fields:**
```python
@dataclass
class BuildMetadata:
    build_started_at: datetime      # When build started
    build_completed_at: datetime    # When build completed
    total_duration_ms: float        # Total time in milliseconds
    steps_executed: list[str]       # ['load_raw_data', 'fill_null_prices', ...]
    step_durations_ms: dict         # {'load_raw_data': 20.9, 'build': 153.1, ...}
    raw_row_count: int              # 2026
    summary_row_count: int          # 107
    unique_fit_count: int           # 107
    unique_type_count: int          # 577
    null_prices_found: int          # Count of null prices detected
    prices_filled_from_avg: int     # Filled from marketstats.avg_price
    prices_filled_from_jita: int    # Filled from Jita API
    prices_defaulted_to_zero: int   # Defaulted to 0
    has_price_service: bool         # Whether PriceService was available
```

**FitBuildResult Methods:**
| Method | Returns | Purpose |
|--------|---------|---------|
| `get_metadata()` | BuildMetadata | Access the metadata object |
| `get_metadata_dict()` | dict | JSON-serializable metadata |
| `print_metadata()` | None | Print human-readable summary |
| `get_columns(type)` | list[str] | Get column names ("summary" or "raw") |

**DoctrineService Methods:**

| Method | Returns | Purpose |
|--------|---------|---------|
| `build_fit_data()` | FitBuildResult | Full pipeline with caching |
| `get_all_fit_summaries()` | list[FitSummary] | All fits as domain models |
| `get_fit_summary(id)` | FitSummary | Single fit by ID |
| `get_fits_by_status(status)` | list[FitSummary] | Filter by StockStatus |
| `get_critical_fits()` | list[FitSummary] | Shortcut for critical status |
| `calculate_all_jita_deltas()` | dict[int, float] | Batch Jita comparison |
| `clear_cache()` | None | Clear cached build result |
| `refresh()` | FitBuildResult | Force rebuild, bypassing cache |

**Verification:** Output matches original `create_fit_df()` exactly:
- Same row counts (2026 raw, 107 summaries)
- Same columns in same order
- Same values (0% cost difference)

**Example Usage:**
```python
from services import get_doctrine_service, StockStatus

service = get_doctrine_service()

# Get all summaries as domain models
summaries = service.get_all_fit_summaries()

# Filter by status
critical = service.get_fits_by_status(StockStatus.CRITICAL)

# Get specific fit with computed properties
fit = service.get_fit_summary(473)
print(f"{fit.ship_name}: {fit.target_percentage}% ({fit.status.display_name})")

# Access build metadata
result = service.build_fit_data()
result.print_metadata()
# Output:
# Build completed in 184.6ms
#   Raw data: 2026 rows, 577 unique types
#   Summaries: 107 fits
#   Steps: load_raw_data -> fill_null_prices -> aggregate_summaries -> ...
```

### `services/categorization.py` (✅ Complete)

Ship role categorization service using cached configuration and Strategy pattern.

**Key Components:**

| Component | Type | Purpose |
|-----------|------|---------|
| `ShipRoleConfig` | Dataclass | Immutable TOML configuration (frozen=True) |
| `ShipRoleCategorizer` | Protocol | Interface for categorization strategies |
| `ConfigBasedCategorizer` | Class | Config-based categorization with @cache |
| `get_ship_role_categorizer()` | Function | Factory for categorizer instances |
| `categorize_ship_by_role()` | Function | Backwards-compatible wrapper |

**Categorization Priority:**
1. **Special cases** - Ship + fit_id combinations (e.g., Vulture 369 → DPS, Vulture 475 → Links)
2. **Configured lists** - Ship name in dps/logi/links/support lists from settings.toml
3. **Keyword fallback** - Pattern matching on ship name (e.g., "hurricane" → DPS)

**Performance Improvements:**
- **Original**: Loaded settings.toml on every `categorize_ship_by_role()` call
- **New**: Load once with `@cache` decorator, cache forever (process lifetime)
- **Impact**: Eliminates repeated file I/O when categorizing hundreds of ships

**ShipRole Enum Enhancements:**
Added to `domain/enums.py`:
- `from_string(role_name)` - Convert string to enum ("DPS" → ShipRole.DPS)
- `display_name` property - Convert enum to string (ShipRole.DPS → "DPS")

**Verification Results:**
- ✅ 18/18 test scenarios passed
- ✅ 4 configured ship tests (Hurricane, Osprey, Claymore, Sabre)
- ✅ 7 special case tests (Vulture, Deimos, Drake with different fit IDs)
- ✅ 4 keyword fallback tests (unconfigured ships)
- ✅ 3 additional configured ship tests (Ferox, Guardian, Stiletto)

**Example Usage:**
```python
from services import get_ship_role_categorizer
from services.categorization import categorize_ship_by_role

# Using the service
categorizer = get_ship_role_categorizer()
role = categorizer.categorize("Hurricane", 473)
print(f"{role.display_emoji} {role.display_name}")  # "💥 DPS"
print(role.description)  # "Primary DPS Ships"

# Using backwards-compatible wrapper
role_str = categorize_ship_by_role("Hurricane", 473)
print(role_str)  # "DPS"
```

**Design Patterns:**
- **Strategy Pattern**: Protocol-based abstraction allows multiple categorization strategies
- **Dependency Injection**: Factory function enables easy testing with mock configurations
- **Configuration as Code**: Frozen dataclass makes config immutable and cacheable

---

## Next Steps (Priority Order)

### Phase 1: Domain Models ✅ COMPLETE
Create `domain/models.py` with:
- [x] `FitItem` dataclass
- [x] `FitSummary` dataclass
- [x] `ModuleStock` dataclass
- [x] `Doctrine` dataclass
- [x] Factory methods (`from_dataframe_row`)

### Phase 2: Repository Layer ✅ COMPLETE
Create `repositories/doctrine_repo.py` with:
- [x] `DoctrineRepository` class
- [x] Methods: `get_all_fits()`, `get_fit_by_id()`, `get_targets()`, `get_fit_name()`, `get_module_stock()`
- [x] Consolidate duplicate queries from `doctrine_status.py` and `doctrine_report.py`

### Phase 3: Service Layer ✅ COMPLETE
Create `services/doctrine_service.py` with:
- [x] `DoctrineService` class
- [x] Business logic from `create_fit_df()` refactored into Builder pattern
- [x] Integration with `PriceService` for cost calculations

### Phase 4: Categorization ✅ COMPLETE
Create `services/categorization.py` with:
- [x] `ShipRoleCategorizer` protocol
- [x] `ConfigBasedCategorizer` with cached TOML loading
- [x] Move logic from `doctrine_report.py:categorize_ship_by_role()`
- [x] Add `ShipRole.from_string()` and `display_name` to enums
- [x] Backwards-compatible wrapper `categorize_ship_by_role()`
- [x] Verification: 18/18 test scenarios passed

### Phase 5: Facade
Create `facades/doctrine_facade.py` with:
- [ ] `DoctrineFacade` class
- [ ] Simplified API for Streamlit pages
- [ ] Session state management

### Phase 6: Page Refactoring
Update Streamlit pages to use facade:
- [ ] `doctrine_status.py` - replace direct DB calls with facade
- [ ] `doctrine_report.py` - replace direct DB calls with facade
- [ ] Remove duplicated functions

---

## Migration Strategy

1. **Additive changes first** - Create new modules alongside existing code
2. **Backwards compatibility wrappers** - Old function signatures delegate to new services
3. **Gradual migration** - Update call sites one at a time
4. **Remove old code last** - Only after all call sites migrated

---

## Key Files to Reference

When continuing this work, read these files for context:

```
domain/models.py              # Domain models (FitItem, FitSummary, etc.)
domain/enums.py               # Status and role enums
repositories/doctrine_repo.py # Repository for doctrine DB access
services/price_service.py     # Price fetching with fallback chain
services/doctrine_service.py  # Business logic with Builder pattern
doctrines.py                  # Original code (being replaced)
pages/doctrine_status.py      # Consumer of doctrine data
pages/doctrine_report.py      # Consumer of doctrine data
config.py                     # DatabaseConfig class (dependency)
```

---

## Testing Considerations

- Each service should be injectable with mock dependencies
- Repository methods should be testable with in-memory SQLite
- Domain models with `frozen=True` are hashable and cacheable
- Backwards compatibility wrappers ensure no breaking changes during migration
