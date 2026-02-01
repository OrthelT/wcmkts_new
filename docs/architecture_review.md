# Architecture Review: Three Refactoring Proposals

## Executive Summary

The doctrine module refactoring (Phases 1-7) established a clean Domain -> Repository -> Service pattern that is working well. However, the rest of the codebase has not adopted this architecture. Three modules -- `market_metrics.py`, `db_handler.py`, and `pages/build_costs.py` -- contain the most severe architectural violations and account for the bulk of the remaining technical debt.

This document proposes three refactoring projects, ordered by impact and dependency:

1. **Flatten the Architecture** -- Simplify the layered pattern itself before extending it
2. **Market Data Refactoring** -- Extract `market_metrics.py` and market functions from `db_handler.py`
3. **Build Cost Refactoring** -- Extract `pages/build_costs.py` into proper layers

---

## Current State: What Works and What Doesn't

### Pages That Follow the Architecture

| Page | Pattern | How It Accesses Data |
|------|---------|---------------------|
| `doctrine_status.py` | Service + Repository | `get_doctrine_service()` -> service methods |
| `doctrine_report.py` | Service + Repository | `get_doctrine_service()` -> service methods |
| `pricer.py` | Service only | `get_pricer_service()` -> `service.price_input()` |

### Pages That Bypass the Architecture

| Page | Lines | How It Accesses Data |
|------|-------|---------------------|
| `market_stats.py` | 999 | Raw SQL via `read_df()`, direct `DatabaseConfig`, limited service use |
| `build_costs.py` | 1136 | Creates `sa.create_engine()` 6+ times, direct ORM queries throughout |
| `low_stock.py` | 306 | Raw SQL with `LEFT JOIN` via `read_df()`, zero service usage |
| `downloads.py` | 417 | Mixed: services for doctrine data, raw `read_df()` for market/low-stock |

### Modules That Mix Concerns

| Module | Lines | Concerns Mixed |
|--------|-------|----------------|
| `market_metrics.py` | 908 | DB queries + pandas calculations + Plotly charts + Streamlit UI (`st.fragment`, `st.metric`, `st.columns`) |
| `db_handler.py` | 457 | DB reads + malformed-DB recovery + ESI API calls + Streamlit caching + session state |
| `utils.py` | ~225 | External API calls (Fuzzwork, Janice) + DB writes + session state + deprecated re-exports |
| `type_info.py` | ~150 | DB queries + Fuzzwork API fallback + TypeInfo class |
| `set_targets.py` | ~120 | Raw SQL target CRUD operations |

---

## Is the Domain -> Repo -> Service Hierarchy Too Complex?

**Short answer: The pattern itself is fine. The overhead around it is the problem.**

The three-tier pattern (Domain models -> Repository for data access -> Service for business logic) is appropriate for this application. `pricer.py` demonstrates this well: it calls `get_pricer_service()`, passes text input, and gets back a typed `PricerResult`. Clean and simple.

However, the doctrine refactoring introduced several layers of overhead that should not be replicated:

### What to Keep
- **Domain models** (`domain/models.py`, `domain/enums.py`) -- Typed dataclasses with factory methods work well. They make code self-documenting and catch bugs.
- **Repositories** (`repositories/doctrine_repo.py`) -- Centralizing SQL queries behind methods is clearly beneficial. It eliminated duplicate queries across pages.
- **Services** (`services/doctrine_service.py`) -- The `FitDataBuilder` pipeline is a good fit for the complex multi-step aggregation it performs.

### What to Simplify

1. **Drop the Facade layer entirely.** It was documented as complete in REFACTOR_PLAN.md (27 methods) but no page actually imports from `facades/`. The pages use services directly, and this is the right call. A Facade adds indirection without value when pages can just call service methods. Don't resurrect it for future refactoring.

2. **Simplify factory functions.** Every service has a `get_*_service()` factory that goes through `state/service_registry.py` -> `st.session_state`. For most services in a Streamlit app, a module-level `@st.cache_resource` singleton is simpler and achieves the same thing. The `state/` package adds a layer of abstraction over what is essentially `st.session_state.setdefault()`.

3. **Don't over-invest in backwards-compatibility wrappers.** The doctrine refactoring preserved old function signatures (e.g., `create_fit_df()` as a wrapper). For internal code with a single codebase and no external consumers, just update the call sites and delete the old functions.

4. **Keep Builder pattern only where warranted.** The `FitDataBuilder` with its 7-step pipeline and `BuildMetadata` tracking is appropriate for the complex fit aggregation. But most new repositories and services should be simple classes with straightforward methods -- don't cargo-cult the Builder pattern into every new service.

### Recommended Pattern Going Forward

```
Page (Streamlit UI)
  └── Service (business logic, orchestration)
        └── Repository (SQL queries, data access)
              └── Domain models (dataclasses, enums -- where useful)
```

Four layers maximum. No facades, no separate state package, no backwards-compat wrappers. Domain models are optional -- use them where they add clarity (like `FitSummary` with its computed `status` property), but don't create domain models for simple data that works fine as a DataFrame.

---

## Project 1: Market Data Refactoring

### Problem

`market_metrics.py` (908 lines) is the worst architectural violation in the codebase. It contains:

- **Database queries** (`get_category_type_ids()`, `get_market_history_by_type_ids()`, `get_available_date_range()`)
- **Business logic** (`calculate_30day_metrics()`, `calculate_ISK_volume_by_period()`, `detect_outliers()`, `handle_outliers()`)
- **Chart creation** (`create_ISK_volume_chart()`, `create_ISK_volume_table()`)
- **Full Streamlit UI components** (`render_ISK_volume_chart_ui()`, `render_30day_metrics_ui()`, `render_current_market_status_ui()`, `render_top_n_items_ui()`, `configure_top_n_items_ui()`)

These are five different concerns in one file. The `render_*` functions contain complete Streamlit layouts with `st.fragment`, `st.columns`, `st.metric`, `st.expander`, `st.radio`, `st.slider`, and `st.plotly_chart`. This means any change to a database query forces you to reason about the UI code surrounding it, and vice versa.

Meanwhile, `db_handler.py` (457 lines) is a catch-all utility containing:
- Market data reads (`get_all_mkt_stats()`, `get_all_mkt_orders()`, `get_all_market_history()`)
- Generic query functions (`read_df()`, `new_read_df()`)
- ESI API calls (`request_type_names()`)
- Data transformation (`clean_mkt_data()`, `new_get_market_data()`)
- SDE queries (`get_groups_for_category()`, `get_types_for_group()`, `extract_sde_info()`)

All decorated with `@st.cache_data`, coupling the database layer to Streamlit.

### Scope

Files to refactor:
- `market_metrics.py` (908 lines) -- split into 3 files
- `db_handler.py` (457 lines) -- extract market queries to repository
- `pages/market_stats.py` (999 lines) -- update imports
- `pages/low_stock.py` (306 lines) -- update imports (uses same raw SQL patterns)
- `pages/downloads.py` (417 lines) -- update market data imports

### Target Architecture

```
repositories/
  market_repo.py          # NEW: All market data queries
    MarketRepository
      get_all_stats() -> DataFrame
      get_all_orders() -> DataFrame
      get_all_history() -> DataFrame
      get_history_by_type_id(type_id) -> DataFrame
      get_history_by_type_ids(type_ids) -> DataFrame
      get_category_type_ids(category_name) -> list[int]
      get_watchlist_type_ids() -> list[int]
      get_market_type_ids() -> list[int]
      get_low_stock_items(max_days, doctrine_only, tech2_only) -> DataFrame
      get_market_data_for_item(type_id) -> tuple[DataFrame, DataFrame, DataFrame]

services/
  market_service.py       # NEW: Market calculations and data transformation
    MarketService
      calculate_30day_metrics(category, item_id) -> MetricsResult
      calculate_isk_volume_by_period(period, start, end, category) -> Series
      calculate_daily_isk_volume() -> Series
      get_top_n_items(df_7days, df_30days, sort_by, count) -> DataFrame
      clean_order_data(df) -> DataFrame
      detect_outliers(series, method, threshold) -> Series
      handle_outliers(series, method, threshold, cap_pct) -> Series
      create_isk_volume_chart(...) -> Figure
      get_available_date_range(category) -> tuple[datetime, datetime]
```

The `render_*` functions from `market_metrics.py` move into `pages/market_stats.py` where they belong -- they are page-specific UI components, not reusable services.

### What Happens to `db_handler.py`

After extracting market queries to `MarketRepository`, `db_handler.py` retains only:
- `read_df()` / `new_read_df()` -- generic query utilities used across repos (could become a base repository method)
- `request_type_names()` -- ESI API call (belongs in a client module, not DB handler)
- `safe_format()` -- pure utility
- `get_update_time()` -- sync status helper

Eventually `db_handler.py` should be eliminated entirely, with `read_df()` becoming a method on a base repository class. But that's a follow-up, not part of this project.

### Key Decisions

1. **Caching stays in the repository**, but moves from `@st.cache_data` (Streamlit-coupled) to instance-level caching or `@st.cache_data` only in the factory function. This keeps repos testable outside Streamlit.

2. **Chart creation stays in the service** (not the repository). `create_ISK_volume_chart()` takes computed data and returns a Plotly Figure -- this is presentation logic but doesn't depend on Streamlit. Putting it in the service keeps it testable.

3. **The `render_*` UI functions move to the page** or to a `pages/components/` directory if they're shared across pages. They are Streamlit-specific and should live with the presentation layer.

4. **`low_stock.py` and `downloads.py` get updated** to use `MarketRepository` methods instead of raw SQL. The duplicated `LEFT JOIN` query in both `low_stock.py:60-70` and `downloads.py:133-140` becomes `repo.get_low_stock_items()`.

### Migration Strategy

1. Create `repositories/market_repo.py` with methods extracted from `db_handler.py` and `market_metrics.py`
2. Create `services/market_service.py` with calculation logic extracted from `market_metrics.py`
3. Move `render_*` functions into `pages/market_stats.py` (inline them where they're used)
4. Update `pages/low_stock.py` to use `MarketRepository`
5. Update `pages/downloads.py` to use `MarketRepository`
6. Remove extracted functions from `db_handler.py` and `market_metrics.py`
7. Delete `market_metrics.py` once empty

### Estimated Impact

- Eliminates ~900 lines of mixed-concern code in `market_metrics.py`
- Eliminates ~200 lines of market-related code from `db_handler.py`
- Removes duplicated `LEFT JOIN` query from `low_stock.py` and `downloads.py`
- Makes market data access testable without Streamlit
- Establishes `MarketRepository` as the single source of truth for market queries

---

## Project 2: Build Cost Refactoring

### Problem

`pages/build_costs.py` (1136 lines) is the largest single file in the codebase and has zero architectural layering. It:

- Creates `sa.create_engine(build_cost_url)` at least 6 times in different functions (lines 109, 129, 138, 151, 178, 204, 391)
- Directly executes SQLAlchemy ORM queries (`session.query(Rig).filter(...)`)
- Makes external API calls to `api.everef.net` (the EveRef industry cost API)
- Contains async HTTP client logic (`httpx.AsyncClient`, `asyncio.Semaphore`)
- Has full Streamlit UI rendering (`st.progress`, `st.dataframe`, `st.image`, `st.metric`)
- Manages complex session state (`st.session_state.super`, `st.session_state.cost_results`)
- Reads from CSV files for category/group data

This is effectively an entire application crammed into one file. It is also the only module that writes to a database (`update_industry_index()` in `utils.py` updates the `industry_index` table).

### Scope

Files to refactor:
- `pages/build_costs.py` (1136 lines) -- split into 3 files
- `build_cost_models.py` (ORM models) -- keep as-is
- `utils.py` -- extract `update_industry_index()` and `fetch_industry_system_cost_indices()`

### Target Architecture

```
repositories/
  build_cost_repo.py      # NEW: Build cost database operations
    BuildCostRepository
      get_all_structures(super_mode) -> list[Structure]
      get_structure_by_name(name) -> Structure
      get_structure_rigs() -> dict[str, list[str]]
      get_valid_rigs() -> dict[str, int]
      get_rig_id(rig_name) -> int | None
      get_manufacturing_cost_index(system_id) -> float
      get_system_id(system_name) -> int
      update_industry_indices(data) -> None

services/
  build_cost_service.py   # NEW: Build cost calculations and API orchestration
    BuildCostService
      calculate_costs(job) -> tuple[dict, dict]    # sync or async
      get_jita_price(type_id) -> float | None
      get_local_price(type_id) -> float | None
      check_industry_index_expiry() -> None
      construct_api_url(job, structure) -> str

    JobQuery                # MOVED from build_costs.py (dataclass)
```

### Key Decisions

1. **Keep async logic in the service.** The async HTTP calls to `api.everef.net` are business logic (fetching cost data from an external API). They belong in the service, not the repository.

2. **The `JobQuery` dataclass moves to the service** (or to `domain/` if other modules need it). It currently lives in the page file but contains business logic in `__post_init__` (super mode detection, cache clearing).

3. **Remove session state from `JobQuery.__post_init__`.** Currently `JobQuery.__post_init__` reads/writes `st.session_state.super` and clears `get_all_structures` cache. This Streamlit coupling should move to the page.

4. **Single engine instance.** The repository gets one engine from `DatabaseConfig("build_cost")` and reuses it, replacing the 6+ `sa.create_engine()` calls scattered across functions.

5. **`get_groups_for_category()` and `get_types_for_group()`** in `db_handler.py` are SDE queries used only by `build_costs.py`. They move to the build cost repository (or a shared SDE repository if other pages need them later).

### Migration Strategy

1. Create `repositories/build_cost_repo.py` -- extract all DB query functions
2. Create `services/build_cost_service.py` -- extract API calls and cost calculation
3. Move `JobQuery` to service module, remove `st.session_state` from `__post_init__`
4. Slim down `pages/build_costs.py` to pure UI (sidebar widgets, display logic, session state management)
5. Move `update_industry_index()` from `utils.py` to `BuildCostRepository`
6. Remove extracted functions from `db_handler.py`

### Estimated Impact

- Reduces `pages/build_costs.py` from ~1136 lines to ~400-500 lines (UI only)
- Eliminates 6+ duplicate engine creation calls
- Makes cost calculation testable without Streamlit or network
- Separates async HTTP orchestration from UI
- Removes the last DB-write function from `utils.py`

---

## Project 3: Consolidate Infrastructure and Eliminate db_handler.py

### Problem

After Projects 1 and 2, `db_handler.py` will have lost most of its functions. What remains is infrastructure that should be reorganized:

- `read_df()` / `new_read_df()` -- generic query execution with malformed-DB recovery
- `request_type_names()` -- ESI API call
- `safe_format()` -- pure utility
- `get_update_time()` -- sync status display helper
- `extract_sde_info()` -- SDE table reader with string injection (SQL injection risk)

Meanwhile, several other standalone modules also need consolidation:

- `type_info.py` -- mixes SDE DB queries with Fuzzwork API fallback
- `set_targets.py` -- raw SQL CRUD operations that should be in a repository
- `sync_state.py` -- reads DB state and writes to `st.session_state`
- `config.py` -- DatabaseConfig has too many responsibilities (connection management + sync logic + integrity checks + Streamlit cache clearing)

### Scope

This is a cleanup/consolidation project rather than a feature-area refactoring.

### Target Changes

#### 3a. Create a Base Repository with `read_df()` Logic

```python
# repositories/base.py
class BaseRepository:
    def __init__(self, db: DatabaseConfig):
        self._db = db

    def read_df(self, query, params=None, fallback_remote=True) -> pd.DataFrame:
        """Execute query with malformed-DB recovery."""
        # Move read_df() logic here
        ...
```

All repositories inherit from `BaseRepository` and get malformed-DB recovery for free. This eliminates the need for `db_handler.read_df()` as a standalone function.

#### 3b. Create `repositories/sde_repo.py`

```python
class SDERepository(BaseRepository):
    def get_type_name(self, type_id: int) -> str | None: ...
    def get_type_id(self, type_name: str) -> int | None: ...
    def get_types_for_group(self, group_id: int) -> DataFrame: ...
    def get_groups_for_category(self, category_id: int) -> DataFrame: ...
    def get_sde_table(self, table_name: str) -> DataFrame: ...
```

This absorbs functions from `type_info.py`, `db_handler.py`, and replaces `extract_sde_info()` (which has a SQL injection risk via f-string table name interpolation).

#### 3c. Create `services/type_resolution_service.py`

```python
class TypeResolutionService:
    def __init__(self, sde_repo: SDERepository):
        self._repo = sde_repo

    def resolve_type_id(self, type_name: str) -> int | None:
        """SDE lookup with Fuzzworks API fallback."""
        type_id = self._repo.get_type_id(type_name)
        if type_id is None:
            type_id = self._fetch_from_fuzzworks(type_name)
        return type_id
```

This replaces `type_info.py`'s `get_type_id_with_fallback()` and the `TypeInfo` class.

#### 3d. Move `set_targets.py` into `repositories/doctrine_repo.py`

The ship target functions (`get_target_from_db`, `update_target`, `get_all_ship_targets`, etc.) operate on the `ship_targets` table, which `DoctrineRepository` already queries. They should be methods on `DoctrineRepository` rather than a standalone module.

#### 3e. Remove Streamlit Coupling from `config.py`

`DatabaseConfig.sync()` currently calls `st.cache_data.clear()`, `st.cache_resource.clear()`, `st.toast()`, and writes to `st.session_state`. These Streamlit operations should be in the caller (the page or a sync service), not in the database configuration class. This makes `DatabaseConfig` testable and reusable outside Streamlit.

### What Gets Deleted

After all three projects:

| Module | Status |
|--------|--------|
| `market_metrics.py` | **Deleted** -- split into `repositories/market_repo.py` + `services/market_service.py` + page components |
| `db_handler.py` | **Deleted** -- functions distributed to repositories, services, and utilities |
| `type_info.py` | **Deleted** -- replaced by `SDERepository` + `TypeResolutionService` |
| `set_targets.py` | **Deleted** -- merged into `DoctrineRepository` |
| `doctrines.py` | **Deleted** -- already replaced by doctrine service (deprecated since Phase 6) |
| `utils.py` | **Deleted** -- industry index to `BuildCostRepository`, price functions already in `PriceService`, deprecated re-exports removed |
| `sync_state.py` | **Simplified** -- returns data instead of writing to session state |

### Final Architecture

```
repositories/
  base.py                    # BaseRepository with read_df() + recovery
  doctrine_repo.py           # Existing (+ ship targets from set_targets.py)
  market_repo.py             # NEW from Project 1
  market_orders_repo.py      # Existing (pricer feature)
  build_cost_repo.py         # NEW from Project 2
  sde_repo.py                # NEW from Project 3

services/
  doctrine_service.py        # Existing
  price_service.py           # Existing
  pricer_service.py          # Existing
  categorization.py          # Existing
  market_service.py          # NEW from Project 1
  build_cost_service.py      # NEW from Project 2
  type_resolution_service.py # NEW from Project 3

domain/
  models.py                  # Existing (doctrine models)
  enums.py                   # Existing (StockStatus, ShipRole)
  pricer.py                  # Existing (pricer models)
  converters.py              # Existing (safe_int, etc.)

pages/
  market_stats.py            # Slim UI (imports from market_service)
  doctrine_status.py         # Already refactored
  doctrine_report.py         # Already refactored
  low_stock.py               # Slim UI (imports from market_repo)
  build_costs.py             # Slim UI (imports from build_cost_service)
  downloads.py               # Uses repositories directly for CSV export
  pricer.py                  # Already refactored

config.py                    # DatabaseConfig (no Streamlit imports)
```

---

## Dependency and Ordering

These three projects have a natural ordering:

```
Project 1 (Market Data)  ─┐
                           ├──> Project 3 (Consolidation)
Project 2 (Build Costs)  ─┘
```

Projects 1 and 2 are **independent** and can be done in parallel. Project 3 depends on both being complete, since it cleans up the shared infrastructure (`db_handler.py`, `utils.py`, `type_info.py`) that Projects 1 and 2 reduce.

### Effort Estimates (Relative)

| Project | New Files | Files Modified | Files Deleted | Relative Effort |
|---------|-----------|---------------|---------------|----------------|
| 1. Market Data | 2 | 5 | 1 | Large |
| 2. Build Costs | 2 | 3 | 0 | Medium |
| 3. Consolidation | 3 | 8 | 6 | Large |

### Risk Assessment

| Project | Risk | Mitigation |
|---------|------|------------|
| 1. Market Data | `market_stats.py` is the main landing page -- bugs here are visible | Test each render function independently as it's migrated |
| 2. Build Costs | Async API calls are complex and hard to test | Keep async logic isolated in service; test sync path first |
| 3. Consolidation | Touches many files; risk of breaking imports | Incremental migration with backwards-compat imports during transition |

---

## Metrics for Success

After all three projects, the codebase should satisfy:

1. **No page directly imports `DatabaseConfig`** (except for display/sync operations)
2. **No page contains raw SQL** (all queries go through repository methods)
3. **No `sa.create_engine()` calls outside of `config.py`**
4. **`db_handler.py` is deleted** (all functions migrated)
5. **`market_metrics.py` is deleted** (split into proper layers)
6. **Every `render_*` function lives in `pages/`** (UI code stays in the UI layer)
7. **All repositories are testable** with an in-memory SQLite database
8. **All services are testable** without Streamlit imports
