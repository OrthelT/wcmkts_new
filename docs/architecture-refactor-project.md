# Architecture Refactoring Project (Phases 8-13)

Extends the Domain -> Repository -> Service -> Page pattern established in Phases 1-7 to market data, build costs, and shared infrastructure. Implements recommendations from `docs/architecture_review.md`.

## Quick Resume Guide

**Current Status:** Phase 10 COMPLETE. Ready to begin Phase 11.

**Branch:** `architecture-review`

**Run tests:** `uv run pytest -q` (87 tests, all passing)

**Key context for next session:**
- Phase 10 created `MarketService` (pure logic), `pages/components/market_components.py` (Streamlit rendering)
- `market_metrics.py` (907 lines) deleted - all functions migrated to service/components
- `pages/market_stats.py` refactored from 1001 to ~629 lines, no more `db_handler` imports
- `MarketRepository` expanded with 5 new query methods (SDE, watchlist, market type IDs, history by type_ids)
- `db_handler.py` functions `new_get_market_data`, `clean_mkt_data`, `get_stats`, `get_price_from_mkt_orders` marked DEPRECATED
- Dead code `get_chart_table_data()` deleted from db_handler.py
- `services/__init__.py` exports `MarketService`, `get_market_service`
- Architecture: Page -> Service -> Repository pattern fully implemented for market data
- The full phase plan is at the bottom of this file (copied from the planning session)

---

## Phase Log

### Phase 8: Foundation & Quick Wins - COMPLETE

**Date:** 2026-02-02

**Files Created:**
| File | Purpose |
|------|---------|
| `repositories/base.py` | BaseRepository with `read_df()` + malformed-DB recovery (extracted from `db_handler.py:18-65`) |
| `tests/test_base_repository.py` | 9 tests: local reads, recovery, remote fallback, params forwarding |

**Files Modified:**
| File | Changes |
|------|---------|
| `config.py` | Removed `RWLock` class (~65 lines), `_local_locks`, `_get_local_lock()`, `local_access()`, `contextmanager` import. Simplified `sync()` to use only `_SYNC_LOCK`. |
| `market_metrics.py` | (1) Module-level `service = get_doctrine_service()` -> lazy `_get_service()`. (2) Module-level `tomllib.load()` -> `_get_default_outliers_method()` via cached `get_settings()`. (3) Removed duplicate computation block in `wrap_top_n_items` (lines 101-119 were copy-pasted at 111-119). |
| `db_handler.py` | Removed `local_access()` wrappers from 5 functions. Changed `get_groups_for_category()` and `get_types_for_group()` from `@st.cache_data(ttl=3600)` -> `@st.cache_resource`. |
| `pages/market_stats.py` | Changed `all_sde_info()` and `get_watchlist_type_ids()` to `@st.cache_resource`. |
| `repositories/doctrine_repo.py` | Removed 6 `local_access()` wrappers. |
| `repositories/__init__.py` | Added `BaseRepository` export. |
| `services/price_service.py` | Removed 1 `local_access()` wrapper. |
| `tests/test_rwlock.py` | Replaced 12 RWLock tests with 2 removal-verification tests. |
| `tests/test_database_config_concurrency.py` | Replaced 6 concurrency tests with 5 simplified-model tests. |
| `tests/test_get_market_history.py` | Removed `local_access` mock setup (7 lines). |
| `tests/test_get_all_market_history.py` | Removed `local_access` mock setup (2 lines). |
| `tests/test_get_all_mkt_orders.py` | Removed `local_access` mock setup (1 line). |

**Verification:**
- 41 tests pass (`uv run pytest -q`)
- Import checks confirm: no `RWLock`, no `local_access`, `_SYNC_LOCK` preserved
- `market_metrics.py` no longer triggers DB access on import

**Design Decisions:**
- `_SYNC_LOCK` (simple `threading.Lock`) retained to serialize sync operations. SQLite handles its own reader concurrency, so no read locking needed.
- `@st.cache_resource` used for SDE data because it's immutable at runtime (only changes on EVE game patches). Avoids unnecessary TTL expiration and serialization overhead vs `@st.cache_data`.
- `BaseRepository.read_df()` signature matches the old `db_handler.read_df()` exactly for easy migration in Phase 9.

**New features/functionality for documentation updates:**
- None (internal refactoring only)

---

### Phase 9: Market Repository & Cache Strategy - COMPLETE

**Date:** 2026-02-02

**Files Created:**
| File | Purpose |
|------|---------|
| `repositories/market_repo.py` | MarketRepository with cached stats/orders/history, targeted invalidation, factory function |
| `tests/test_market_repo.py` | 16 tests: cached functions, malformed recovery, class delegation, update time, invalidation, factory |

**Files Modified:**
| File | Changes |
|------|---------|
| `config.py` | Removed `st.cache_data.clear()`, `st.cache_resource.clear()`, `st.toast()`, `st.session_state` mutations from `sync()`. Returns `bool` now. Removed dead `self.alias == "wcmkt2"` branch. |
| `db_handler.py` | Converted `get_all_mkt_stats`, `get_all_mkt_orders`, `get_all_market_history`, `get_market_history`, `get_update_time` to DEPRECATED shims delegating to `market_repo`. Removed ~120 lines of duplicated query/recovery logic. |
| `repositories/__init__.py` | Added `MarketRepository`, `get_market_repository`, `invalidate_market_caches`, `get_update_time` exports. |
| `pages/downloads.py` | Replaced `get_all_mkt_orders/stats/history` imports with `get_market_repository()`. |
| `pages/low_stock.py` | Replaced `from db_handler import get_update_time` with `from repositories import get_update_time`. |
| `pages/doctrine_status.py` | Same as low_stock.py. |
| `pages/doctrine_report.py` | Same as low_stock.py. |
| `ui/popovers.py` | Replaced lazy `from db_handler import get_all_mkt_stats` with `from repositories import get_market_repository`. |
| `pages/market_stats.py` | Added `from repositories import invalidate_market_caches`. Replaced global `st.cache_data.clear()` with `invalidate_market_caches()`. Added toast feedback after sync (moved from config.py). |
| `tests/test_database_config_concurrency.py` | Added 4 tests verifying sync() no longer calls Streamlit APIs. |

**Verification:**
- 61 tests pass (`uv run pytest -q`)
- Import checks confirm: no circular imports, shims delegate correctly to market_repo
- Single cache per function (db_handler shims -> market_repo cached functions)

**Design Decisions:**
- **Two-layer caching**: `_impl()` functions contain query + recovery logic (testable), `_cached()` wrappers add `@st.cache_data` (Streamlit integration). This separates concerns and simplifies testing.
- **Shim pattern**: db_handler functions become thin wrappers delegating to market_repo's cached functions. This ensures a single cache entry per query while maintaining backward compatibility for Phase 10 targets (market_stats.py, market_metrics.py).
- **sync() returns bool**: Callers handle UI feedback (toasts, session state). This makes sync() testable outside Streamlit and eliminates the double-clear bug where caches were cleared twice per sync.
- **Dead code removed**: `self.alias == "wcmkt2"` branch in sync() was unreachable because the constructor remaps "wcmkt2" → "wcmktprod"/"wcmkttest". Removed along with its st.toast/st.session_state calls.

**New features/functionality for documentation updates:**
- None (internal refactoring only)

---

### Phase 10: Market Service & Page Migration - COMPLETE

**Date:** 2026-02-02

**Files Created:**
| File | Purpose |
|------|---------|
| `services/market_service.py` | MarketService with pure calculation logic, chart creation (Plotly), ISK volume aggregation, outlier handling, factory function |
| `pages/components/__init__.py` | Package init for page components |
| `pages/components/market_components.py` | Streamlit rendering functions extracted from market_metrics.py: ISK volume chart/table UI, 30-day metrics, current market status, top N items, history display, column configs |
| `tests/test_market_service.py` | 26 tests: 30-day metrics, ISK volume by period, outlier detection/handling, chart creation, top N items, clean order data, get_market_data |

**Files Modified:**
| File | Changes |
|------|---------|
| `repositories/market_repo.py` | Added 5 query methods (`get_history_by_type_ids`, `get_category_type_ids`, `get_watchlist_type_ids`, `get_market_type_ids`, `get_sde_info`) with `_impl()`/`_cached()` pattern. Added `bindparam` import. Updated `invalidate_market_caches()` to clear new caches. |
| `pages/market_stats.py` | Refactored from 1001 to ~629 lines. Removed all `db_handler` imports. Uses `MarketService` for data access/calculations and `market_components` for rendering. Removed inline `create_price_volume_chart`, `create_history_chart`, `display_history_data`, `display_history_metrics`, `get_fitting_col_config`, `get_display_formats`, `all_sde_info`, `get_watchlist_type_ids`, `get_market_type_ids`. |
| `services/__init__.py` | Added `MarketService`, `get_market_service` exports |
| `db_handler.py` | Marked `new_get_market_data()`, `clean_mkt_data()`, `get_stats()`, `get_price_from_mkt_orders()` as DEPRECATED. Deleted dead code `get_chart_table_data()`. |

**Files Deleted:**
| File | Reason |
|------|--------|
| `market_metrics.py` (907 lines) | All functions migrated to `services/market_service.py` (pure logic) and `pages/components/market_components.py` (Streamlit rendering) |

**Verification:**
- 87 tests pass (`uv run pytest -q`)
- Ruff check passes on all modified/created files
- No circular imports (verified via direct Python import test)
- No remaining `from db_handler import` in market_stats.py
- No remaining `from market_metrics` imports anywhere
- `market_metrics.py` deleted

**Design Decisions:**
- **Service takes repository via DI**: `MarketService.__init__(market_repo)` enables full mocking in tests. All 26 service tests use synthetic DataFrames, no DB needed.
- **Chart creation in service layer**: Returns `go.Figure` (Plotly is a pure data structure). The page layer only calls `st.plotly_chart(fig)`. This keeps chart logic testable without Streamlit.
- **Static methods for pure transforms**: `detect_outliers()`, `handle_outliers()`, `clean_order_data()`, `get_top_n_items()` are static because they don't need repo access. Callable without service instantiation.
- **Components receive service, not data**: `render_30day_metrics_ui(service)` calls service methods internally, keeping the page orchestrator thin. Exception: `render_current_market_status_ui` receives pre-computed data since it renders multiple unrelated metrics.
- **SDE queries use `cache_resource`**: `get_sde_info()` and `get_watchlist_type_ids()` use `@st.cache_resource` (no TTL) because SDE data is immutable at runtime. Market data queries use `@st.cache_data` with TTLs.
- **`get_filter_options()` stays in page**: It manages session state (`selected_category_info`), which is presentation-layer responsibility. It accesses the repo through the service's `_repo` attribute.

**New features/functionality for documentation updates:**
- None (internal refactoring only)

---

## Upcoming Phases

### Phase 11: Build Cost Repository & Service
- Save log files in ./logs instead of in the root directory
- Create `repositories/build_cost_repo.py`
- Create `services/build_cost_service.py`
- Slim `pages/build_costs.py` to UI-only

### Phase 12: Infrastructure Consolidation
- Create `repositories/sde_repo.py`
- Create `services/type_resolution_service.py`
- Merge `set_targets.py` into doctrine_repo
- Delete `type_info.py`, `set_targets.py`, `doctrines.py`, `utils.py`

### Phase 13: Final Cleanup & Optimization
- Delete `db_handler.py` (remove all shims)
- Standardize session state on `ss_get`/`ss_has`/`ss_set`
- Optimize cache TTLs
- Update all documentation

**Execution order:**
```
Phase 8 (DONE)
  |-- Phase 9 (DONE) -> Phase 10 (DONE)
  |-- Phase 11 (independent of 9-10, requires 8)
       |-- Phase 12 (requires 9-11) -> Phase 13
```

# USER INSTRUCTIONS
Prioritize reducing complexity and increasing performance. Avoid long files. Split functionality into separate files when it is logically cohesive and generally in keeping with architecture. Consider Streamlit's execution model which re-runs on every interaction. Caching and use of session_state in-memory cache is critical to performance. Each phase should be able to fit within your context window. You are the senior developer on this project and most maintain a clear picture of the overall objections and work involved. Use sub-agents as needed to preserve your context window. 

### Project Plan Document
Use this file (docs/architecture-refactor-project.md) to document your work and to continually track progress. It should include a record of the work completed with each phase and the information a new Claude instance will need to continue with the next phase as well as any handoff instructions. Record any new features or functionality introduced that will need to be updated in the apps documentation so they can be easily identified for documentation updates at the end of the project. 

### Workflow for Each Phase
*At the beginning of each phase:*
- Write tests that verify correctness of upcoming work.
- Add additional tests as work progresses to reflect any adjustments. 

*The conclusion of each phase should include:*
- A review of the implementation for simplicity and consistency with the architecture
- Testing of the refactored code
- A refactoring phase to address any issues identified. 
- Updates to docs/architecture-refactor-project.md as described above.
- If the full work planned for a phase cannot be completed before your context window is exhausted, add a sub-phase to the project plan with instructions for a new Claude instance to complete the work. 

### Additional information
- docs/architecture_review.md (note USER COMMENTS)
