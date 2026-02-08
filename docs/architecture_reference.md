# Architecture Reference

Technical reference for the Winter Coalition Market Stats Viewer architecture. For project setup, commands, and contribution guidelines, see [CLAUDE.md](../CLAUDE.md).

---

## Architecture Overview

The codebase follows a strict layered architecture where dependencies flow downward only:

```
Presentation    pages/, app.py
State           state/ (session_state, service_registry)
UI              ui/ (formatters, column_definitions, popovers)
Services        services/ (business logic, orchestration)
Repositories    repositories/ (database access)
Domain          domain/ (models, enums, converters)
Infrastructure  config.py, models.py, settings_service.py, logging_config.py
```

**Key principles:**
- Upper layers import from lower layers, never the reverse
- Services and repositories have zero Streamlit imports (except `@st.cache_data`/`@st.cache_resource` in cached wrappers)
- Domain layer depends only on Python stdlib
- Pages are thin UI layers that delegate to services

See CLAUDE.md for the full dependency rules table.

---

## Module Inventory

### `domain/` -- Core Business Models

| File | Key Contents |
|------|-------------|
| `models.py` | `FitItem`, `FitSummary`, `ModuleStock`, `Doctrine` dataclasses with factory methods (`from_dataframe_row`) |
| `enums.py` | `StockStatus` (CRITICAL/NEEDS_ATTENTION/GOOD), `ShipRole` (DPS/LOGI/LINKS/SUPPORT) with display helpers |
| `converters.py` | `safe_int()`, `safe_float()`, `safe_str()` -- centralized type conversion |
| `pricer.py` | `PricedItem`, `PricingResult`, `InputFormat` for the Pricer page |
| `doctrine_names.py` | User-friendly doctrine display name mappings |

All domain dataclasses use `frozen=True` for immutability and safe caching.

### `repositories/` -- Database Access

| File | Key Contents |
|------|-------------|
| `base.py` | `BaseRepository` with `read_df()` + malformed-DB recovery logic |
| `doctrine_repo.py` | `DoctrineRepository` (17+ methods) -- fits, targets, doctrine compositions, module stock, equivalents |
| `market_repo.py` | `MarketRepository` -- stats, orders, history, local prices, SDE info, targeted cache invalidation |
| `build_cost_repo.py` | `BuildCostRepository` -- structures, rigs, industry indices |
| `sde_repo.py` | `SDERepository` -- type/group/category lookups, SDE table exports, SQL injection protection via table name allowlist |
| `market_orders_repo.py` | Market orders for Pricer page |

### `services/` -- Business Logic

| File | Key Contents |
|------|-------------|
| `doctrine_service.py` | `DoctrineService` + `FitDataBuilder` (7-step Builder pipeline), `BuildMetadata` |
| `market_service.py` | `MarketService` -- 30-day metrics, ISK volume, outlier handling, Plotly chart creation |
| `build_cost_service.py` | `BuildCostService` -- async cost fetching (httpx), URL construction, `BuildCostJob` dataclass |
| `price_service.py` | `PriceService` -- provider chain (Fuzzwork -> Janice) with `FallbackPriceProvider` |
| `pricer_service.py` | `PricerService` -- EFT/multibuy parsing, dual-market price lookups |
| `low_stock_service.py` | `LowStockService` -- low stock analysis with category/doctrine/tech2/faction filtering |
| `categorization.py` | `ConfigBasedCategorizer` -- ship role categorization via Strategy pattern |
| `module_equivalents_service.py` | `ModuleEquivalentsService` -- interchangeable faction module lookups |
| `selection_service.py` | `SelectionService` -- item selection state management for doctrine pages |
| `type_resolution_service.py` | `TypeResolutionService` -- type name/ID resolution with SDE + API fallbacks |
| `parser_utils.py` | Parsing utilities for EFT fittings and item lists |

### `state/` -- Session State Management

| File | Key Contents |
|------|-------------|
| `session_state.py` | `ss_get()`, `ss_has()`, `ss_set()`, `ss_init()` -- None-safe state access wrappers |
| `service_registry.py` | `get_service()` -- singleton service management via `st.session_state` |

### `ui/` -- UI Utilities

| File | Key Contents |
|------|-------------|
| `formatters.py` | Pure formatting functions for prices, percentages, image URLs, ship roles |
| `column_definitions.py` | `st.column_config` definitions for data tables |
| `popovers.py` | Market data popover components (Jita fetching disabled by default for performance) |

### `pages/` -- Streamlit Pages

| File | Page |
|------|------|
| `market_stats.py` | Primary market data visualization with Plotly charts |
| `doctrine_status.py` | Doctrine fit status tracking with stock levels |
| `doctrine_report.py` | Detailed doctrine analysis and reporting |
| `low_stock.py` | Low inventory alerting with category/doctrine filtering |
| `build_costs.py` | Manufacturing cost analysis with async API calls |
| `downloads.py` | Centralized CSV export (uses callable pattern for lazy data loading) |
| `pricer.py` | Item/fitting price calculator (EFT + multibuy input) |
| `components/market_components.py` | Extracted Streamlit rendering functions for market_stats |

### Infrastructure (Root Level)

| File | Purpose |
|------|---------|
| `app.py` | Streamlit entry point with page routing |
| `config.py` | `DatabaseConfig` -- SQLite/LibSQL connections, Turso sync, `_SYNC_LOCK` |
| `models.py` | SQLAlchemy ORM models (MarketStats, Doctrines, DoctrineFits, etc.) |
| `sdemodels.py` | SDE ORM models (InvTypes, InvGroups, InvCategories) |
| `build_cost_models.py` | Manufacturing ORM models (Structures, IndustryIndex, Rigs) |
| `settings_service.py` | Module-level settings cache (stdlib only, no Streamlit dependency) |
| `logging_config.py` | Centralized logging with rotating file handlers to `./logs/` |
| `sync_state.py` | Database update time tracking (uses `ss_set()`) |
| `init_db.py` | Database initialization with path verification and auto-sync |
| `init_equivalents.py` | Module equivalents table creation (uses raw sqlite3, not libsql) |

---

## Design Patterns

### Repository Pattern

Three-layer structure separating concerns:

```python
# 1. _impl() -- pure logic, takes engine param, testable with MagicMock
def _get_all_fits_impl(engine):
    with Session(engine) as session:
        return pd.read_sql_query(query, session.connection())

# 2. _cached() -- Streamlit caching wrapper, uses _url as cache key
@st.cache_data(ttl=600)
def _get_all_fits_cached(_url: str):
    return _get_all_fits_impl(DatabaseConfig().mkt_engine)

# 3. Class method -- delegates to cached wrapper
class DoctrineRepository:
    def get_all_fits(self) -> pd.DataFrame:
        return _get_all_fits_cached(self._url)
```

The `_url` cache key is needed because Streamlit cannot hash `self`. Factory functions use `state.get_service()` for singleton management.

**Note:** `market_repo` varies from this pattern -- its `_impl()` functions create `DatabaseConfig` internally (needed for malformed-DB recovery). Both patterns work correctly.

### Service Pattern

- Services receive repositories via dependency injection
- Use `Protocol` classes for callbacks (e.g., `ProgressCallback` in build_cost_service)
- Dataclasses with `@property` replace stateful classes (e.g., `BuildCostJob.is_super`)
- Factory functions: `try: from state import get_service` / `except ImportError: return _create()`

### Builder Pattern (FitDataBuilder)

Used in `doctrine_service.py` for the complex 7-step fit data aggregation pipeline:

```
load_raw_data -> apply_module_equivalents -> fill_null_prices ->
aggregate_summaries -> calculate_costs -> merge_targets -> finalize_columns -> build
```

Returns `FitBuildResult` with `BuildMetadata` tracking timing, row counts, and price-fill statistics.

### Strategy Pattern (Ship Role Categorization)

`ShipRoleCategorizer` Protocol with `ConfigBasedCategorizer` implementation. Categorization priority: special cases (ship + fit_id) -> configured lists -> keyword fallback.

### Service Registry

`state/service_registry.py` provides `get_service()` for singleton service management via `st.session_state.setdefault()`. Services are created once per session and cached.

---

## Caching Strategy

### TTL Tiers

| TTL | Data Type | Rationale |
|-----|-----------|-----------|
| 600s (10 min) | Market stats, doctrine fits, local prices, equivalence groups | Volatile data, sync-triggered invalidation |
| 1800s (30 min) | Market orders, download CSVs, DB update checks, history by type_ids | Moderate volatility |
| 3600s (1 hr) | Market history, SDE tables, build cost structures/rigs, equivalence mappings | Stable data |
| No TTL (`cache_resource`) | SDE type/group/category lookups, watchlist type_ids | Immutable at runtime |

### Cache Decorator Choice

- `@st.cache_data` -- for data that changes (market stats, orders). Serializes return values.
- `@st.cache_resource` -- for immutable data (SDE lookups) and singleton objects. No serialization overhead, no TTL expiration.

### Targeted Invalidation

After database sync, only market-data caches are cleared via `invalidate_market_caches()` in `market_repo.py`. SDE, build cost, and settings caches are preserved. This replaced the old global `st.cache_data.clear()` approach.

### Popover Performance

Streamlit runs popover content on every rerun even when closed. Avoid API calls inside popovers. Use batch prefetching before render loops -- see `prefetch_popover_data()` in `doctrine_status.py` for the pattern. Jita price fetching in popovers is disabled by default (`show_jita=False`).

---

## Key Design Decisions

### Facade Layer Removal
The `facades/` layer was implemented during Phases 1-7 but later removed. It acted as a pass-through to service methods, adding indirection without value. Pages now access services directly via factory functions. The service registry pattern provides the same lifecycle management with less abstraction.

### SDE Data Uses `cache_resource`
SDE (Static Data Export) data is immutable at runtime -- it only changes on EVE game patches. Using `@st.cache_resource` (no TTL) eliminates unnecessary re-queries and serialization overhead compared to `@st.cache_data(ttl=3600)`.

### Malformed-DB Recovery
`BaseRepository.read_df()` implements automatic fallback to remote database queries when the local SQLite file is malformed. Repository `_impl()` functions in `market_repo` also include this recovery logic (they create `DatabaseConfig` internally to access both local and remote engines).

### `init_equivalents.py` Recreates Table on Startup
Turso embedded replicas currently use pull-only sync, so local-only tables are overwritten on each sync. The module equivalents table is recreated on every app startup via `init_db.py` -> `init_module_equivalents()` using raw `sqlite3`. This workaround may become unnecessary after migrating to Turso's newer database engine with bidirectional sync support.

### `settings_service.py` at Root Level
Lives at root level (not in `services/`) because it is infrastructure. Uses only stdlib imports to avoid circular dependencies through `services/__init__.py`'s eager imports.

### Session State Standardization
Infrastructure files use `ss_set()` wrapper. Complex pages (market_stats, doctrine_status, build_costs) retain direct `st.session_state` access where dynamic keys and widget bindings make wrapper adoption impractical.

### `config.py` Sync Returns Bool
`DatabaseConfig.sync()` returns a boolean success indicator. The calling page handles UI feedback (toasts, session state updates) and cache invalidation. This keeps `DatabaseConfig` testable outside Streamlit.
