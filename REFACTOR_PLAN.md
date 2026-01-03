# Doctrine Module Refactoring Plan

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

---

## Next Steps (Priority Order)

### Phase 1: Domain Models
Create `domain/models.py` with:
- [ ] `FitItem` dataclass
- [ ] `FitSummary` dataclass
- [ ] `ModuleStock` dataclass
- [ ] `Doctrine` dataclass
- [ ] Factory methods (`from_dataframe_row`)

### Phase 2: Repository Layer
Create `repositories/doctrine_repo.py` with:
- [ ] `DoctrineRepository` class
- [ ] Methods: `get_all_fits()`, `get_fit_by_id()`, `get_targets()`, `get_fit_name()`, `get_module_stock()`
- [ ] Consolidate duplicate queries from `doctrine_status.py` and `doctrine_report.py`

### Phase 3: Service Layer
Create `services/doctrine_service.py` with:
- [ ] `DoctrineService` class
- [ ] Business logic from `create_fit_df()` refactored into Builder pattern
- [ ] Integration with `PriceService` for cost calculations

### Phase 4: Categorization
Create `services/categorization.py` with:
- [ ] `ShipRoleCategorizer` protocol
- [ ] `ConfigBasedCategorizer` with cached TOML loading
- [ ] Move logic from `doctrine_report.py:categorize_ship_by_role()`

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
services/price_service.py    # Completed example of all patterns
doctrines.py                 # Main target for refactoring
pages/doctrine_status.py     # Consumer of doctrine data
pages/doctrine_report.py     # Consumer of doctrine data
config.py                    # DatabaseConfig class (dependency)
db_handler.py                # Existing DB access patterns
```

---

## Testing Considerations

- Each service should be injectable with mock dependencies
- Repository methods should be testable with in-memory SQLite
- Domain models with `frozen=True` are hashable and cacheable
- Backwards compatibility wrappers ensure no breaking changes during migration
