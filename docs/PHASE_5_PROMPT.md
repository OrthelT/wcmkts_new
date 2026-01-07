# Phase 5: Facade Layer - Implementation Prompt

## Context
We're refactoring a Streamlit application's doctrine management system using clean architecture patterns. Phases 1-4 are complete (domain models, repository, services, categorization). You're implementing Phase 5: the Facade Layer.

## What's Been Done (Phases 1-4)

✅ **Phase 1: Domain Layer** - Immutable dataclasses (FitItem, FitSummary, ModuleStock, Doctrine)
✅ **Phase 2: Repository Layer** - DoctrineRepository with 17 database access methods
✅ **Phase 3: Service Layer** - DoctrineService with Builder pattern, PriceService
✅ **Phase 4: Categorization** - ConfigBasedCategorizer with cached TOML loading

All verified and documented in `REFACTOR_PLAN.md`.

## Your Task: Phase 5 - Facade Layer

Create `facades/doctrine_facade.py` that provides a **simplified, high-level API** for Streamlit pages, hiding the complexity of orchestrating multiple services.

### Why We Need a Facade

Current problems in `pages/doctrine_status.py` and `pages/doctrine_report.py`:
- Pages directly instantiate multiple services (repository, price service, doctrine service)
- Session state management is scattered throughout page code
- Repeated patterns like "get service from session or create new"
- No single entry point for common operations

### What the Facade Should Provide

A single class that:
1. **Manages service lifecycle** - Creates and caches service instances
2. **Simplifies common operations** - One method call instead of multiple service calls
3. **Integrates with Streamlit session state** - Handles caching transparently
4. **Provides typed domain models** - Returns FitSummary, ModuleStock, not raw DataFrames

### Implementation Guidance

**Key methods to include** (reference the existing pages to see what they need):

```python
class DoctrineFacade:
    # Fit operations
    def get_all_fit_summaries() -> list[FitSummary]
    def get_fit_summary(fit_id: int) -> FitSummary
    def get_fits_by_status(status: StockStatus) -> list[FitSummary]
    def get_critical_fits() -> list[FitSummary]

    # Module operations
    def get_module_stock(name: str) -> ModuleStock
    def get_modules_stock(names: list[str]) -> list[ModuleStock]

    # Doctrine operations
    def get_doctrine(name: str) -> Doctrine
    def get_all_doctrines() -> list[Doctrine]

    # Categorization
    def categorize_ship(ship_name: str, fit_id: int) -> ShipRole

    # Price operations
    def get_jita_price(type_id: int) -> float
    def calculate_fit_jita_delta(fit_id: int) -> float

    # Bulk operations
    def refresh_all_data() -> None
    def clear_caches() -> None
```

**Factory function for Streamlit integration:**

```python
def get_doctrine_facade() -> DoctrineFacade:
    """Get facade from Streamlit session state or create new instance."""
    # Use st.session_state to cache the facade
    # Initialize with DatabaseConfig, auto-create services
```

## Files to Read First

1. **`REFACTOR_PLAN.md`** - Full context, especially Quick Resume Guide and Completed Work sections
2. **`services/doctrine_service.py`** - See how services orchestrate repositories
3. **`pages/doctrine_status.py`** - Identify what operations pages need (lines ~100-400)
4. **`pages/doctrine_report.py`** - More page operation patterns (lines ~100-300)
5. **`repositories/doctrine_repo.py`** - Available repository methods
6. **`services/categorization.py`** - Categorization service interface

## Success Criteria

✅ Facade simplifies page code - pages should call facade, not individual services
✅ Session state integration - facade cached in st.session_state
✅ Returns domain models - no raw DataFrames in facade API
✅ Backwards compatible - existing page code still works
✅ Comprehensive docstrings - explain each method's purpose
✅ Factory pattern - `get_doctrine_facade()` for easy instantiation

## Patterns to Follow

Based on previous phases, use:
- **Facade Pattern** - Single interface to complex subsystems
- **Dependency Injection** - Services passed to constructor
- **Lazy Initialization** - Create services only when needed
- **Caching** - Leverage Streamlit session state
- **Factory Function** - Provide `get_doctrine_facade()` for convenience

## Testing Strategy

Create a test script (update `dev.py`) that:
1. Instantiates the facade
2. Calls key methods (get_all_fit_summaries, get_critical_fits, etc.)
3. Verifies return types are domain models (not DataFrames)
4. Checks that repeated calls use cached data

## Documentation

Update `REFACTOR_PLAN.md` when complete:
1. Update Quick Resume Guide (Phase 5 complete, Phase 6 next)
2. Add detailed Phase 5 completion section (follow Phase 4 format)
3. Mark Phase 5 checklist items as complete
4. Add usage examples

## Questions to Consider

- Should the facade cache results internally, or rely on service-level caching?
- How should errors propagate from services through the facade?
- What logging should the facade provide?
- Should bulk operations (refresh_all) be synchronous or provide progress callbacks?

## Ready to Start?

Begin by reading `REFACTOR_PLAN.md` Quick Resume Guide, then scan the page files to understand what operations they perform. The facade should make those operations trivial.

Good luck! 🚀
