# Refactoring Log

Historical record of the architectural refactoring project (Phases 1-13) and feature refinements (Tasks 1-7). Useful for understanding why the codebase looks the way it does, and as reference for future refactoring efforts.

---

## Executive Summary

Over January-February 2026, the codebase was transformed from a monolithic Streamlit application into a clean layered architecture (Domain -> Repository -> Service -> Page). The project completed 13 phases of structural refactoring plus 7 feature refinement tasks.

**Key outcomes:**
- Established layered architecture across the entire codebase
- Deleted 6 legacy modules (~2,000+ lines of mixed-concern code)
- Created 5 repositories, 10+ services, and a domain model layer
- Grew test suite from ~12 tests to ~128 tests
- Implemented targeted cache invalidation (replacing global cache clears)
- Removed unnecessary concurrency infrastructure (RWLock)

---

## Before State

The original codebase had these problems:

- **Mixed concerns**: `market_metrics.py` (908 lines) contained DB queries, pandas calculations, Plotly charts, and full Streamlit UI components in one file
- **Scattered database access**: `db_handler.py` (457 lines) was a catch-all utility mixing DB reads, ESI API calls, data transforms, and Streamlit caching
- **No domain models**: Raw DataFrames passed everywhere with implicit column requirements
- **Duplicate code**: `get_module_stock_list()` existed in both doctrine pages; `get_fit_name()` had two versions
- **Tight coupling**: Functions created `DatabaseConfig` internally; `config.py` called `st.cache_data.clear()` and `st.toast()` during sync
- **Performance issues**: `categorize_ship_by_role()` loaded TOML file on every call; global cache invalidation cleared all 37 cached functions on every sync
- **Unnecessary complexity**: `RWLock` class (~65 lines) for concurrency that SQLite handles natively

---

## Phase Summary

### Phases 1-7: Doctrine Module Refactoring

Established the layered architecture pattern using doctrine data as the pilot.

| Phase | Scope | Key Changes |
|-------|-------|-------------|
| 1 | Domain Models | Created `domain/models.py` and `domain/enums.py` -- FitItem, FitSummary, ModuleStock, StockStatus, ShipRole |
| 2 | Repository Layer | Created `repositories/doctrine_repo.py` (17 methods) -- consolidated duplicate queries from both doctrine pages |
| 3 | Service Layer | Created `services/doctrine_service.py` with FitDataBuilder (7-step pipeline replacing 175-line `create_fit_df()`) |
| 4 | Categorization | Created `services/categorization.py` with Strategy pattern -- cached TOML loading replaced per-call file I/O |
| 5 | Service Registry | Created `state/` package with `service_registry.py` and `session_state.py`. Facade layer was built then removed as unnecessary |
| 6 | Page Refactoring | Refactored `doctrine_status.py` and `doctrine_report.py` to use services. Eliminated ~233 lines of duplicate code |
| 7 | Performance | Diagnosed and fixed sluggish `doctrine_status.py` performance |

### Phases 8-13: Architecture Extension

Extended the layered pattern to market data, build costs, and shared infrastructure.

| Phase | Date | Scope | Key Changes |
|-------|------|-------|-------------|
| 8 | 2026-02-02 | Foundation | Created `BaseRepository` with `read_df()` + malformed-DB recovery. Removed `RWLock` (~65 lines). Fixed module-level eager initialization in `market_metrics.py`. |
| 9 | 2026-02-02 | Market Repository | Created `MarketRepository` with targeted cache invalidation. Converted `db_handler` market functions to deprecated shims. Decoupled `config.py sync()` from Streamlit. |
| 10 | 2026-02-02 | Market Service | Created `MarketService` and `pages/components/market_components.py`. Deleted `market_metrics.py` (907 lines). Reduced `market_stats.py` from 1001 to ~629 lines. |
| 11 | 2026-02-04 | Build Costs | Created `BuildCostRepository` and `BuildCostService`. Reduced `build_costs.py` from 1137 to 699 lines. Removed async mode toggle (async-only). |
| 11a | 2026-02-04 | Settings + Performance | Created `settings_service.py`. Refactored `doctrine_status.py` selectbox logic. |
| 12 | 2026-02-07 | Infrastructure | Created `SDERepository` and `TypeResolutionService`. Deleted `type_info.py` (107), `set_targets.py` (196), `utils.py` (158). |
| 12a | 2026-02-07 | Selection Bug Fix | Fixed checkbox selection bug (last-writer-wins). Implemented rebuild-from-checkboxes pattern. Added multibuy-compatible export format. |
| 13 | 2026-02-07 | Final Cleanup | Deleted `db_handler.py` (353 lines) and 3 legacy test files. Standardized `ss_set()` in infrastructure files. Documented cache TTL tiers. |

### Feature Refinements (Tasks 1-7)

Completed alongside or between the architectural phases.

| Task | Scope | Key Changes |
|------|-------|-------------|
| 1 | Low Stock Page | Created `LowStockService`. Added doctrine/fit filters, faction items checkbox. |
| 2 | Pricer Enhancement | Added market stats, doctrine info, and stock metrics to `PricedItem`. |
| 3 | Market Popovers | Created `ui/popovers.py` with reusable market data popover components. |
| 4 | Doctrine Pages | Created `SelectionService`. Improved sidebar selections with `st.code()` display. |
| 5 | Bug Fixes | Fixed `get_jita_price()` returning PriceResult instead of float. Fixed connection scope bug in `low_stock_service.py`. |
| 6 | Module Equivalents | Created `ModuleEquivalentsService`, `init_equivalents.py`, `ModuleEquivalents` ORM model. Added equivalence indicators to doctrine pages. |
| 7 | Performance Fixes | Fixed `init_equivalents.py` to use raw sqlite3 (libsql DDL limitation). Added batch prefetching for popovers. Changed Jita fetching default to disabled. |

---

## Files Deleted

Legacy modules removed during the project, with what replaced them:

| File | Lines | Phase | Replacement |
|------|-------|-------|-------------|
| `market_metrics.py` | 907 | 10 | `services/market_service.py` + `pages/components/market_components.py` |
| `db_handler.py` | 353 | 13 | Functions distributed across `BaseRepository`, `MarketRepository`, `SDERepository`, `TypeResolutionService` |
| `utils.py` | 158 | 12 | Price functions already in `PriceService`; industry index in `BuildCostService` |
| `set_targets.py` | 196 | 12 | Target methods already in `DoctrineRepository` |
| `type_info.py` | 107 | 12 | `SDERepository` + `TypeResolutionService` |
| `facades/` (2 files) | ~150 | 5 | Removed as unnecessary abstraction; pages use services directly |
| 3 legacy test files | ~150 | 13 | Tested deprecated `db_handler` shims only |
| `example_test_run.py` | ~30 | 13 | Example file importing deprecated function |

**Total deleted:** ~2,050 lines of production code + ~180 lines of test code

---

## Metrics

**Overall:** 101 files changed across 87 commits -- 17,001 lines inserted, 20,073 lines deleted, **net reduction of 3,072 lines**.

| Metric | Before | After |
|--------|--------|-------|
| Architectural layers | 1 (monolithic pages) | 6 (pages/state/ui/services/repos/domain) |
| Legacy mixed-concern modules | 6 | 0 |
| Repository classes | 0 | 6 |
| Service classes | 1 (PriceService) | 10+ |
| Domain model files | 0 | 5 |
| Test count | ~12 | ~128 |
| Largest page file | ~1,137 lines (build_costs) | ~745 lines (build_costs) |
| Cache invalidation | Global (all 37 functions) | Targeted (market-only) |
| `sa.create_engine()` in pages | 6+ (build_costs alone) | 0 |
| Direct SQL in pages | Common | Eliminated |

---

## Lessons Learned

1. **Facades add indirection without value** when services already have clean APIs. The facade layer was implemented and then removed -- pages calling services directly is simpler and more maintainable.

2. **Streamlit's execution model dominates architecture decisions.** Every widget interaction re-runs the entire page script. Caching strategy, service singleton management, and avoiding module-level initialization all stem from this reality.

3. **Targeted cache invalidation is critical.** The old global `st.cache_data.clear()` nuked 37 cached functions (including immutable SDE data and external API results) when only market data changed. Targeted invalidation was one of the highest-impact changes.

4. **`@st.cache_resource` for immutable data.** SDE data never changes at runtime. Switching from `@st.cache_data(ttl=3600)` to `@st.cache_resource` eliminated unnecessary re-queries, serialization overhead, and TTL expirations.

5. **Batch prefetching prevents N+1 problems in Streamlit.** Popover content runs on every rerun even when closed. API calls inside popovers caused 10+ second load times. Batch-fetching data before render loops was essential.

6. **Builder pattern earns its complexity selectively.** `FitDataBuilder`'s 7-step pipeline with metadata tracking is justified for the complex fit aggregation. But most services work fine as simple classes with straightforward methods.

7. **The `_impl()` / `_cached()` / class method pattern** cleanly separates testable logic from Streamlit caching. The `_url` cache key trick handles the unhashable `self` limitation.

8. **Local-only tables don't survive syncs.** Turso embedded replicas use pull-only sync from the remote, so any local-only tables are overwritten on the next sync regardless of how they were created. The workaround is to recreate them on every app startup (via `init_db.py` -> `init_module_equivalents()`), or add the table to the remote schema. This limitation may be resolved by migrating to Turso's newer database engine, which supports bidirectional sync.

9. **Backwards-compatibility wrappers should be temporary.** The deprecated shim functions in `db_handler.py` (delegating to repositories) served their purpose during migration but became dead code. Delete them promptly rather than maintaining indefinitely.

10. **Incremental migration with a clear target architecture** worked well. Each phase was scoped to fit a context window, had clear deliverables, and left the codebase in a working state. The architecture review document (`architecture_review.md`) that planned Phases 8-13 was valuable for maintaining direction across sessions.
