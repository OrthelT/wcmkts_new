# Architecture Review: Three Refactoring Proposals

## USER INSTRUCTIONS
Review this document and develop a plan for implementing its recommendations. Your plan should prioritize reducing complexity and increasing performance. Avoid long files. Split functionality into separate files when it is logically cohesive and generally in keeping with architecture. It should also consider Streamlit's execution model which re-runs on every interaction. Therefore caching and use of session_state in-memory cache is critical to performance. Divide the plan into reasonable phases. Each phase should be able to fit within your context window. You are the senior developer on this project and most maintain a clear picture of the overall objections and work involved. Use sub-agents as needed to preserve your context window. 

### Additional considerations
- The read-write lock functionality at the top of config.py was intended to handle a bug in the database engine that has subsequently been addressed. Locking should be handled properly by the database engine, making this code unnecessary. 
- At some point in the future, I'd like to make the market context selectable by the user. I'd also like to make the app easily configurable for new markets so it can be implemented by others. This does not need to be implemented as part of this project, but thought it was worth noting so that you can consider it in your architecture design.


### Project Plan Document
Create a docs/architecture-refactor-project.md file to document your and to continually track progress. It should include a record of the work completed with each phase and the information a new Claude instance will need to continue with the next phase as well as any handoff instructions. Record any new features or functionality introduced that will need to be updated in the apps documentation so they can be easily identified for documentation updates at the end of the project. 

### Workflow for Each Phase
At the beginning of each phase:
- Write tests that verify correctness.
- Add additional tests as work progresses to adjust to any adjustments. 

The conclusion of each phase should include:
- A review of the implementation for simplicity and consistency with the architecture
- Testing of the refactored code
- A refactoring phase to address any issues identified. 
- Updates to docs/architecture-refactor-project.md as described above.
- If the full work planned for a phase cannot be completed before your context window is exhausted, add a sub-phase to the project plan with instructions for a new Claude instance to complete the work. 


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

**USER COMMENTS:**
The Facade layer has already been removed. Please update the documentation to make this clear if it isn't alresdy. 

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

---

## Project 4: Session State and Caching Strategy

Streamlit re-runs the entire script on every user interaction. This makes session state management and caching strategy critical to performance -- every unnecessary recomputation, redundant state read, or poorly-scoped cache invalidation directly impacts response time.

### Current State Inventory

#### All Session State Keys (41 keys across 12 files)

**Market Stats page (14 keys):**

| Key | Type | Read By | Written By |
|-----|------|---------|------------|
| `selected_item` | str | market_stats, market_metrics | market_stats |
| `selected_item_id` | int | market_stats, market_metrics | market_stats, db_handler |
| `selected_category` | str | market_stats, market_metrics | market_stats |
| `selected_category_info` | dict | market_stats, db_handler | market_stats |
| `jita_price` | float | market_stats, market_metrics | market_stats |
| `current_price` | float | market_metrics | market_stats |
| `db_initialized` | bool | market_stats | market_stats |
| `db_init_time` | datetime | market_stats | market_stats |
| `last_check` | float | market_stats | market_stats |
| `chart_start_date` | datetime | market_metrics | market_metrics (widget) |
| `chart_end_date` | datetime | market_metrics | market_metrics (widget) |
| `chart_date_period_radio` | str | market_metrics | market_metrics (widget) |
| `week_month_pill` | int | market_metrics | market_metrics (widget) |
| `daily_total_pill` | int | market_metrics | market_metrics (widget) |

**Sync/DB state (5 keys):**

| Key | Type | Read By | Written By |
|-----|------|---------|------------|
| `local_update_status` | dict | sync_state, market_stats, db_handler, market_metrics | sync_state |
| `remote_update_status` | dict | sync_state, market_stats | sync_state |
| `sync_status` | str | config | config |
| `sync_check` | bool | config | config |
| `isk_volume_pill` | int | market_metrics | market_metrics (widget) |

**Build Costs page (8 keys):**

| Key | Type | Read By | Written By |
|-----|------|---------|------------|
| `super` | bool | build_costs | build_costs |
| `initialised` | bool | build_costs | build_costs |
| `price_source` | str | build_costs | build_costs |
| `price_source_name` | str | build_costs | build_costs |
| `async_mode` | bool | build_costs | build_costs |
| `calculate_clicked` | bool | build_costs | build_costs |
| `current_job_params` | dict | build_costs | build_costs |
| `cost_results` | dict | build_costs | build_costs |

**Doctrine pages (9 keys):**

| Key | Type | Read By | Written By |
|-----|------|---------|------------|
| `module_list_state` | dict | doctrine_report, doctrine_status | doctrine_report, doctrine_status |
| `csv_module_list_state` | dict | doctrine_report, doctrine_status | doctrine_report, doctrine_status |
| `target_multiplier` | float | doctrine_report | doctrine_report |
| `selected_modules` | list | doctrine_report, doctrine_status | doctrine_report, doctrine_status |
| `ship_list_state` | dict | doctrine_status | doctrine_status |
| `csv_ship_list_state` | dict | doctrine_status | doctrine_status |
| `ds_target_multiplier` | float | doctrine_status | doctrine_status |
| `selected_ships` | list | doctrine_status | doctrine_status |
| `jita_deltas` | dict | doctrine_status | doctrine_status |

**External API state (3 keys):**

| Key | Type | Read By | Written By |
|-----|------|---------|------------|
| `etag` | str | utils | utils |
| `sci_last_modified` | datetime | utils, build_costs | utils |
| `sci_expires` | datetime | utils, build_costs | utils |

**Dynamic keys (created per-item):**

| Pattern | Type | Used By |
|---------|------|---------|
| `ship_<id>` | bool | doctrine_status (checkbox per ship) |
| `<id>_<module>` | bool | doctrine_status (checkbox per module) |
| `top_items_count` | int | market_metrics |

#### All Cached Functions (37 functions)

| Function | File | TTL | Notes |
|----------|------|-----|-------|
| `get_settings()` | config.py | 3600s | Settings file |
| `get_all_mkt_stats()` | db_handler.py | 600s | `SELECT * FROM marketstats` |
| `get_all_mkt_orders()` | db_handler.py | 1800s | `SELECT * FROM marketorders` |
| `request_type_names()` | db_handler.py | 3600s | ESI API call |
| `clean_mkt_data()` | db_handler.py | 1800s | DataFrame transform |
| `get_stats()` | db_handler.py | 600s | Market stats query |
| `get_market_history()` | db_handler.py | 3600s | Single-item history |
| `get_all_market_history()` | db_handler.py | 3600s | Full history table |
| `get_groups_for_category()` | db_handler.py | 3600s | SDE groups |
| `get_types_for_group()` | db_handler.py | 3600s | SDE types |
| `get_category_type_ids()` | market_metrics.py | 3600s | SDE type IDs by category |
| `get_market_history_by_type_ids()` | market_metrics.py | 1800s | Multi-item history |
| `get_available_date_range()` | market_metrics.py | 3600s | Min/max history dates |
| `get_watchlist_type_ids()` | market_stats.py | 3600s | Watchlist IDs |
| `get_market_type_ids()` | market_stats.py | 1800s | All market type IDs |
| `all_sde_info()` | market_stats.py | 1800s | SDE info for market items |
| `check_for_db_updates()` | market_stats.py | 1800s | DB sync validation |
| `get_valid_rigs()` | build_costs.py | 3600s | Rig data |
| `fetch_rigs()` | build_costs.py | 3600s | Rig names/IDs |
| `get_structure_rigs()` | build_costs.py | 3600s | Structure rig mapping |
| `get_4H_manufacturing_cost_index()` | build_costs.py | 3600s | Build cost index |
| `get_all_structures()` | build_costs.py | 3600s | Structure list |
| `get_filter_options()` | low_stock.py | 600s | Category/item lists |
| `get_market_stats()` | low_stock.py | 600s | Low stock data |
| `get_jita_price()` | utils.py | 600s | Fuzzwork API |
| `get_janice_price()` | utils.py | 3600s | Janice API |
| `get_fit_metadata()` | doctrine_repo.py | 3600s | Fit metadata |
| `get_all_fits()` | doctrine_repo.py | 600s | All doctrine fits |
| `get_fit_by_id()` | doctrine_repo.py | 600s | Single fit |
| `get_all_ship_targets()` | doctrine_repo.py | 600s | Ship targets |
| `get_target_for_fit()` | doctrine_repo.py | 600s | Fit target |
| `get_target_for_ship()` | doctrine_repo.py | 600s | Ship target |
| `get_fit_name()` | doctrine_repo.py | 600s | Fit name |
| 8 download functions | downloads.py | 600s | Export data |
| 3 download functions | downloads.py | 1800s | Export data |

### Problem 1: Aggressive Global Cache Invalidation

**Location:** `config.py:327-328` and `pages/market_stats.py:362-363`

```python
# config.py sync() method:
st.cache_data.clear()       # Nukes ALL 37 cached functions
st.cache_resource.clear()   # Nukes ALL cached resources
```

When a database sync happens (triggered by `check_db()` every 10 minutes or manually), **every cached function in the entire application is invalidated**. This means:

- `get_jita_price()` results are thrown away (requires re-fetching from Fuzzwork API)
- `request_type_names()` results are thrown away (requires re-fetching from ESI API)
- `get_settings()` is thrown away (requires re-reading settings.toml)
- `get_all_structures()`, `get_valid_rigs()`, etc. are thrown away (build cost data is unaffected by market sync)
- All SDE queries are thrown away (SDE data never changes during runtime)

The sync only updates market data tables (`marketstats`, `marketorders`, `market_history`). Clearing caches for SDE data, external API results, build cost structures, and settings is pure waste.

**Fix: Targeted cache invalidation.** After sync, only clear market-data caches:

```python
# In the caller (page or sync service), NOT in DatabaseConfig.sync():
def invalidate_market_caches():
    """Clear only caches that depend on market data."""
    get_all_mkt_stats.clear()
    get_all_mkt_orders.clear()
    get_all_market_history.clear()
    get_stats.clear()
    get_market_history.clear()           # per-item history
    get_market_history_by_type_ids.clear()
    clean_mkt_data.clear()
    check_for_db_updates.clear()
```

This preserves SDE caches, external API caches, build cost caches, and settings -- all of which are expensive to reconstruct and unrelated to market data sync.

### Problem 2: `st.cache_data` in Non-UI Code


**USER COMMENTS:**
Streamlit's st.cache_data() and st.cache_resource() decorators can only be used on functions with hashable arguments. So, it cannot normally be applied to class methods that take self as an argument. Streamlit's documentation offers two solutions that may be relevant:
- Streamlit caching functions will ignore any argument prepended with an underscore. For instants, a class method get_fit_price(_self, fit_id) can be used with st.cache_data. Self will be ignored and the return value will be cached. However, if pertinent values are passed from the cache, they will be ignored and the cached result will still be returned as long as fit_id is the same.
- Streamlit's st.cache decorators can also accept a hash_funcs() argument to specify the caching strategy. 
Review Streamlit's cache documentation here and consider it in your refactor plan. https://docs.streamlit.io/develop/concepts/architecture/caching


Every `@st.cache_data` decorator couples the decorated function to Streamlit's runtime. This means:

- Functions cannot be tested without a Streamlit context
- Cache behavior is invisible (no way to inspect what's cached or measure hit rates)
- Cache keys are based on argument hashing, which can produce collisions with mutable arguments (DataFrames)
- `clean_mkt_data()` is cached with a DataFrame as input -- Streamlit hashes the entire DataFrame to generate the cache key, which is expensive for large frames

**Current locations of `@st.cache_data` in non-UI code:**

| File | Functions | Should Be Cached Here? |
|------|-----------|----------------------|
| `db_handler.py` | 9 functions | No -- move to repository layer |
| `market_metrics.py` | 3 functions | No -- move to repository/service |
| `config.py` | `get_settings()` | Acceptable (infrastructure) |
| `utils.py` | `get_jita_price()`, `get_janice_price()` | No -- move to price service |
| `repositories/doctrine_repo.py` | 7 functions | Acceptable pattern, but see below |

**Recommended caching strategy after refactoring:**

```
Page Layer:       No @st.cache_data (pages re-run, call services)
Service Layer:    No @st.cache_data (pure logic, stateless)
Repository Layer: @st.cache_data on query methods (TTL-based)
Config Layer:     @st.cache_data on settings load only
```

The repository is the right place for `@st.cache_data` because:
1. Repository methods have stable, hashable arguments (type_id, category_name, etc.)
2. Repository return values are DataFrames or simple types that cache well
3. Cache invalidation can be targeted per-repository after sync

The doctrine repository already follows this pattern. The new `MarketRepository` and `BuildCostRepository` should do the same.

### USER COMMENT: 
Streamlit's st.cache_data() and st.cache_resource() decorators can only be used on functions with hashable arguments. So, it cannot normally be applied to class methods that take self as an argument. Streamlit's documentation offers two solutions that may be relevant:
- Streamlit caching functions will ignore any argument prepended with an underscore. For instants, a class method get_fit_price(_self, fit_id) can be used with st.cache_data. Self will be ignored and the return value will be cached. However, if pertinent values are passed from the cache, they will be ignored and the cached result will still be returned as long as fit_id is the same.
- Streamlit's st.cache decorators can also accept a hash_funcs() argument to specify the caching strategy. 
Review Streamlit's cache documentation here and consider it in your refactor plan. https://docs.streamlit.io/develop/concepts/architecture/caching


### Problem 3: Redundant Work on Every Rerun

Streamlit re-runs the entire page script on every interaction. Several patterns in the codebase cause unnecessary work on each rerun:

#### 3a. Module-level DatabaseConfig instantiation

```python
# db_handler.py (lines 12-14) -- runs on import, every rerun
mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")
build_cost_db = DatabaseConfig("build_cost")

# pages/market_stats.py (lines 25-27) -- DUPLICATE, runs on import
mkt_db = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")
build_cost_db = DatabaseConfig("build_cost")
```

`DatabaseConfig.__init__` resolves aliases, checks file paths, and sets up lazy engine properties. The engines themselves are cached at the class level, so the per-instance cost is low but not zero. Having two files each create their own instances of the same three configs is redundant.

**Fix:** After the repository refactoring, each repository receives its `DatabaseConfig` via constructor injection. The factories (`get_market_repo()`, etc.) handle instantiation once and cache the repository in session state via the service registry.

#### 3b. Service initialization at module level

```python
# market_metrics.py (line 17) -- runs on import
service = get_doctrine_service()

# pages/doctrine_report.py (line 22) -- runs on import
service = get_doctrine_service()

# pages/doctrine_status.py (line 21) -- runs on import
service = get_doctrine_service()
```

Three files eagerly call `get_doctrine_service()` at module scope. The service registry (`state/service_registry.py`) caches the instance in session state, so subsequent calls are cheap. But the first call in a session constructs the entire service + repository chain, and if this happens before `init_db()` has run, it can fail or produce stale results.

**Fix:** Always use lazy initialization:

```python
# Correct pattern (already used in market_stats.py:39-41):
def _get_service():
    return get_doctrine_service()

# Call _get_service() only when needed, never at module level
```

#### 3c. Module-level settings file reads

```python
# market_metrics.py (lines 19-22) -- runs on import, BYPASSES cache
import tomllib
with open("settings.toml", "rb") as f:
    settings = tomllib.load(f)
default_outliers_method = settings['outliers']['default_method']
```

This reads and parses `settings.toml` on every import of `market_metrics.py`, completely bypassing the `get_settings()` cache in `config.py`. Since `market_metrics.py` is imported by `market_stats.py`, this file I/O happens on every page load.

**Fix:** Use the cached `get_settings()` from config:

```python
from config import get_settings
# Access at call time, not import time:
def _get_default_outlier_method():
    return get_settings()['outliers']['default_method']
```

#### 3d. Redundant session state reads in market_stats.py main()

`st.session_state.selected_item` is read 10+ times across the 400-line `main()` function (lines 693, 705, 776, 777, 841, 864, 903, 908, 912, 929). Each read is individually cheap, but the pattern reflects a lack of local variable caching:

```python
# Current (repeated reads):
if ss_has('selected_item'):
    selected_item = st.session_state.selected_item       # read 1
    sell_data = sell_data[sell_data['type_name'] == selected_item]
# ... 50 lines later ...
if ss_has('selected_item'):
    selected_item = st.session_state.selected_item       # read 2 (same value)
    st.subheader("Sell Orders for " + selected_item)
# ... 70 lines later ...
if st.session_state.get('selected_item') is not None:    # read 3 (different API)
    st.subheader("Market History - " + st.session_state.get('selected_item'))
```

**Fix:** Read once at the top of `main()`, use local variables throughout:

```python
def main():
    selected_item = ss_get('selected_item')
    selected_item_id = ss_get('selected_item_id')
    selected_category = ss_get('selected_category')
    # Use local variables everywhere below
```

#### 3e. Duplicate computation in `wrap_top_n_items()`

`market_metrics.py:92-126` contains a copy-paste duplication where the same filtering logic runs twice:

```python
# Lines 98-106: first computation
if st.session_state.week_month_pill == 0:
    top_n_items = df_7days.copy()
else:
    top_n_items = df_30days.copy()
if st.session_state.daily_total_pill == 0:
    top_n_items = top_n_items.groupby('type_name').agg(...)
else:
    top_n_items = top_n_items.groupby('type_name').agg(...)

# Lines 108-116: IDENTICAL computation (overwrites result from above)
if st.session_state.week_month_pill == 0:
    top_n_items = df_7days.copy()
else:
    top_n_items = df_30days.copy()
if st.session_state.daily_total_pill == 0:
    top_n_items = top_n_items.groupby('type_name').agg(...)
else:
    top_n_items = top_n_items.groupby('type_name').agg(...)
```

The second block completely overwrites the first. This is a copy-paste bug that doubles the computation.

### Problem 4: Cache TTL Inconsistencies

The current TTLs don't align with data volatility:

| Data Type | Current TTL | Data Changes | Recommended TTL |
|-----------|-------------|-------------|-----------------|
| Market orders | 1800s | Every ESI pull (~5 min) | 600s (sync-triggered invalidation) |
| Market stats | 600s | Every ESI pull | 600s (sync-triggered invalidation) |
| Market history | 3600s | Daily | 3600s (correct) |
| SDE data | 3600s | Never during runtime | 86400s or `@st.cache_resource` |
| Settings file | 3600s | Never during runtime | `@st.cache_resource` (no TTL) |
| Fit metadata | 3600s | Rarely | 3600s (correct) |
| External API prices | 600s | External | 1800s (reduce API calls) |
| Doctrine fits | 600s | Only on manual update | 1800s (event-triggered invalidation) |

Key observations:

1. **SDE data has a 1-hour TTL but never changes.** `get_category_type_ids()`, `get_groups_for_category()`, `get_types_for_group()`, `all_sde_info()` query static data (EVE Online's Static Data Export). These should use `@st.cache_resource` (permanent cache) rather than `@st.cache_data(ttl=3600)`. This eliminates unnecessary re-queries of data that is loaded once per deployment.

2. **External API prices have a 10-minute TTL.** `get_jita_price()` calls the Fuzzwork API on every expiry. Increasing to 30 minutes reduces external API load by 3x with minimal staleness impact (Jita prices don't move that fast for market stocking decisions).

3. **Market data has time-based TTLs but should use event-based invalidation.** The current approach expires market caches on a timer (600s for stats, 1800s for orders). But the data only changes when a sync occurs. With targeted invalidation (Problem 1 fix), these functions can use longer TTLs and get explicitly cleared when sync happens:

```python
@st.cache_data(ttl=3600)  # Long TTL as safety net
def get_all_mkt_stats():
    ...

# After sync, explicitly clear:
get_all_mkt_stats.clear()
```

This gives both responsiveness (fresh data immediately after sync) and efficiency (no re-queries between syncs).

### Problem 5: Session State Written from Infrastructure Code

Several non-UI modules write directly to `st.session_state`, creating hidden dependencies and making those modules untestable:

| Module | Keys Written | Why It's a Problem |
|--------|-------------|-------------------|
| `config.py` (sync()) | `sync_status`, `sync_check` | DB config class coupled to Streamlit |
| `sync_state.py` | `local_update_status`, `remote_update_status` | Infrastructure writes to UI state |
| `db_handler.py` (new_get_market_data) | Reads from session state | Data layer reads UI state for filtering |

**Fix:** These functions should return values and let the caller write to session state:

```python
# sync_state.py -- BEFORE:
def update_wcmkt_state():
    local_status = {...}
    st.session_state.local_update_status = local_status  # side effect

# sync_state.py -- AFTER:
def get_wcmkt_state() -> tuple[dict, dict]:
    local_status = {...}
    remote_status = {...}
    return local_status, remote_status

# Caller (page):
local, remote = get_wcmkt_state()
ss_set('local_update_status', local)
ss_set('remote_update_status', remote)
```

Similarly, `config.py`'s `sync()` should not call `st.cache_data.clear()`, `st.toast()`, or write to `st.session_state`. It should return a status, and the calling page handles UI feedback and cache invalidation.

### Problem 6: Inconsistent State Access Patterns

The codebase uses three different patterns to read session state:

```python
# Pattern 1: Wrapper functions (state/ module)
from state import ss_get, ss_has
value = ss_get('key', default)          # 14 call sites
exists = ss_has('key')                  # 8 call sites

# Pattern 2: Direct attribute access
value = st.session_state.selected_item  # 100+ call sites
value = st.session_state['key']         # 20+ call sites

# Pattern 3: .get() method
value = st.session_state.get('key')     # 15+ call sites
value = st.session_state.get('key', default)  # 10+ call sites
```

The wrapper functions (`ss_get`, `ss_has`) provide None-safety (they treat None values as absent), but 80% of the codebase uses direct access, which throws `AttributeError` on missing keys or returns None without distinguishing "key absent" from "key is None".

**Fix:** Standardize on the wrapper functions. The wrappers are well-designed -- they just need consistent adoption:

```python
# Replace all direct access:
st.session_state.selected_item           -> ss_get('selected_item')
st.session_state.get('key')              -> ss_get('key')
st.session_state.get('key', default)     -> ss_get('key', default)
'key' in st.session_state               -> ss_has('key')
st.session_state['key'] = value          -> ss_set('key', value)
```

This makes state access grep-able, adds consistent None-handling, and keeps the door open for future enhancements (logging, validation, type checking) in one place.

### Recommended Implementation Order

These fixes have different dependencies and can be phased:

**Phase A (standalone, do first):**
1. Fix `wrap_top_n_items()` duplicate computation (1 line delete)
2. Fix module-level service init in `market_metrics.py`, `doctrine_report.py`, `doctrine_status.py` (3 files, small change each)
3. Fix module-level settings read in `market_metrics.py` (use `get_settings()`)
4. Change SDE query caches from `@st.cache_data(ttl=3600)` to `@st.cache_resource`

**Phase B (with Project 1 - Market Data Refactoring):**
5. Move `@st.cache_data` from `db_handler.py` functions to `MarketRepository` methods
6. Implement targeted cache invalidation (replace global `st.cache_data.clear()`)
7. Extract session state writes from `config.py` sync() into page-level code
8. Consolidate `local_update_status` / `remote_update_status` reads into `sync_state.py` returning values

**Phase C (with Project 3 - Consolidation):**
9. Standardize all session state access on `ss_get`/`ss_has`/`ss_set`
10. Increase external API TTLs to 1800s
11. Switch SDE repository to `@st.cache_resource` (permanent cache)
12. Eliminate module-level `DatabaseConfig` instantiation in favor of repository injection
