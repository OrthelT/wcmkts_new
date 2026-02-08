# Architecture Refactoring Project (Phases 8-13)

Extends the Domain -> Repository -> Service -> Page pattern established in Phases 1-7 to market data, build costs, and shared infrastructure. Implements recommendations from `docs/architecture_review.md`.

## Quick Resume Guide

**Current Status:** Phase 13 COMPLETE. All phases done.

**Branch:** `architecture-review`

**Run tests:** `uv run pytest -q` (~128 tests, all passing)

**Architecture is fully layered:**
- All legacy modules deleted: `db_handler.py`, `utils.py`, `type_info.py`, `set_targets.py`, `market_metrics.py`
- All production code uses: `repositories/`, `services/`, `domain/`, `ui/`, `state/`
- Infrastructure files (`sync_state.py`) now use `ss_set()` instead of direct `st.session_state` writes
- Cache TTLs reviewed and documented (600s/1800s/3600s/no-TTL tiers)

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

### Phase 11: Build Cost Repository & Service - COMPLETE

**Date:** 2026-02-04

**Files Created:**
| File | Purpose |
|------|---------|
| `repositories/build_cost_repo.py` | BuildCostRepository with cached access to structures, rigs, industry indices. `_impl()`/`_cached()` pattern with `_url` cache key. |
| `services/build_cost_service.py` | BuildCostService with async cost fetching (httpx), URL construction, industry index management, `BuildCostJob` dataclass. |
| `tests/test_build_cost_repo.py` | 7 tests: rigs, valid rigs filtering, manufacturing cost index, structures (super/non-super) |
| `tests/test_build_cost_service.py` | 14 tests: BuildCostJob properties, URL construction, rig filtering, super group detection, industry index check/parse |

**Files Modified:**
| File | Changes |
|------|---------|
| `pages/build_costs.py` | Refactored from 1137 to 699 lines. Extracted all DB access to repo, all business logic to service. Removed async mode toggle (async-only now). Page is UI-only. |
| `logging_config.py` | Fixed log routing: all logs now go to `./logs/` relative to source file. `os.path.basename()` strips directory components. Absolute paths (test tmpdir) respected. |
| `build_cost_models.py` | Minor cleanup, removed unused DatabaseConfig instantiation |
| `config.py` | Added `bc_engine` property for build cost database access |
| `repositories/__init__.py` | Added `BuildCostRepository`, `get_build_cost_repository` exports |
| `services/__init__.py` | Added `BuildCostService`, `get_build_cost_service` exports |
| `utils.py` | Removed `fetch_industry_indices()` (moved to BuildCostService) |

**Verification:**
- 111 tests pass (`uv run pytest -q`)
- Ruff check passes on all modified files
- No circular imports
- No remaining inline DB queries in build_costs.py (except SDE lookups via db_handler, deferred to Phase 12)

**Design Decisions:**
- **Async-only cost fetching**: The sync path was the original implementation; async was added later and has been stable for months. The sync toggle and legacy code were removed during post-phase cleanup to reduce complexity.
- **`_impl()` takes engine param**: Unlike market_repo (which creates DatabaseConfig internally for malformed-DB recovery), build_cost_repo `_impl()` functions take an engine param for direct testability with `MagicMock()`. Build cost data doesn't need the same recovery logic as market data.
- **`_url` cache key in cached wrappers**: Follows the doctrine_repo pattern. Streamlit can't hash `self`, so module-level cached functions use the database URL string as a cache discriminator.
- **BuildCostJob dataclass**: Replaces the old dict-based job parameters. The `is_super` property replaces standalone super-group checks, keeping the logic co-located with the data.
- **ProgressCallback Protocol**: Enables progress reporting without Streamlit dependency. The page layer passes a lambda wrapping `st.progress()`.
- **Dead code removed during cleanup**: `get_type_id()`, `get_structure_by_name()`, `get_rig_id()`, `get_system_id()` were extracted from the original page but never actually called. Removed along with their tests to keep the repo surface minimal.

**New features/functionality for documentation updates:**
- None (internal refactoring only)

---
### 11A: SettingsService and Performance Enhancements to doctrine_status.py - COMPLETE
- Refactored select_box logic to key on type_ids rather than module names.
- Introduced centralized SettingsService class in settings_service.py

---
### Phase 12: Infrastructure Consolidation - COMPLETE

**Date:** 2026-02-07

**Files Created:**
| File | Purpose |
|------|---------|
| `repositories/sde_repo.py` | SDERepository: type lookups, group/category queries, table exports. Absorbs functions from `type_info.py` and `db_handler.py`. SQL injection protection via table name allowlist. |
| `services/type_resolution_service.py` | TypeResolutionService: type name/ID resolution with SDE + Fuzzworks/ESI API fallbacks. |
| `tests/test_sde_repo.py` | 15 tests: type name/ID lookups, groups, types, SDE tables, tech2 IDs, edge cases |
| `tests/test_type_resolution_service.py` | 9 tests: SDE resolution, Fuzzworks fallback, ESI batch, chunking, error handling |

**Files Modified:**
| File | Changes |
|------|---------|
| `repositories/market_repo.py` | Added `get_local_price()` method + `_get_local_price_impl`/`_get_local_price_cached`. Added to cache invalidation. |
| `repositories/__init__.py` | Added `SDERepository`, `get_sde_repository` exports |
| `services/__init__.py` | Added `TypeResolutionService`, `get_type_resolution_service` exports |
| `models.py` | Changed `from type_info import get_type_name` -> `from repositories.sde_repo import get_type_name` |
| `pages/market_stats.py` | Replaced `get_type_id_with_fallback` -> `TypeResolutionService.resolve_type_id()`, `get_jita_price` -> `services.get_jita_price` |
| `pages/build_costs.py` | Replaced all `db_handler` imports with `SDERepository`/`MarketRepository`/`TypeResolutionService`. Replaced `utils.get_jita_price` with `services.get_jita_price`. |
| `pages/downloads.py` | Replaced `extract_sde_info` -> `SDERepository.get_sde_table()`, `read_df` -> `BaseRepository.read_df()`, tech2 query -> `SDERepository.get_tech2_type_ids()` |
| `tests/test_market_repo.py` | Added 2 tests for `get_local_price` (found, not found) |

**Files Deleted:**
| File | Reason |
|------|--------|
| `set_targets.py` (196 lines) | Zero active imports. DoctrineRepository already has equivalent methods. |
| `type_info.py` (107 lines) | All functions migrated to `sde_repo` + `type_resolution_service` |
| `utils.py` (158 lines) | Price functions duplicated in `PriceService`, session state re-exports deprecated |
| `tests/test_safe_format.py` | Tested `db_handler.safe_format` which is now dead code |
| `tests/test_clean_mkt_data.py` | Tested deprecated `db_handler.clean_mkt_data` shim |

**Test Results:** 136 tests passing (111 - 3 deleted + 28 new)

**Key Decisions:**
- SDE data cached with `@st.cache_resource` (no TTL) since it's immutable at runtime
- Module-level `get_type_name()` in sde_repo as layering accommodation for `models.py` ORM events
- `request_type_names` (ESI batch) moved to TypeResolutionService rather than creating separate ESI service
- `get_sde_table` validates table names against allowlist (12 tables) to prevent SQL injection
- Downloads composite market+doctrine query uses `BaseRepository.read_df()` directly (one-off query)

### Phase 12a: Fix doctrine_status.py Selection & Clipboard - COMPLETE

**Date:** 2026-02-07

**Bug:** When a module `type_id` appeared in the lowest-stock list of multiple fits, checking its checkbox in one fit correctly called `_add_selection()`, but unchecked instances of the same `type_id` in other fits called `_remove_selection()` on the same rerun — the last-processed checkbox won, so shared modules could never stay selected.

**Root Cause:** Streamlit's execution model re-runs the entire script on every interaction. With N fits showing the same module, there are N checkboxes but only 1 selection set entry. The incremental add/remove approach is inherently order-dependent (last writer wins).

**Files Modified:**
| File | Changes |
|------|---------|
| `pages/doctrine_status.py` | (1) Added `_rebuild_selections()` — scans all `mod_*`/`ship_*` session state keys after rendering to rebuild `selected_type_ids` from checkbox ground truth. (2) Removed `else: _remove_selection()` branches from ship and module checkbox blocks. (3) Changed selected items display from `"  {name}"` to `"{name} {qty}"` (EVE multibuy-compatible format). (4) Removed "Copy to Clipboard" button and column split; replaced with single `st.sidebar.download_button()`. Removed `text_lines`/`export_text` variables. |

**Verification:**
- 136 tests pass (`uv run pytest -q`)
- Ruff check passes on `pages/doctrine_status.py`

**Design Decisions:**
- **Rebuild-from-checkboxes pattern**: Instead of incremental add/remove during rendering, `_rebuild_selections()` runs once after all checkboxes have rendered. It scans session state keys to determine which type_ids are checked. This is idempotent — checkbox processing order doesn't matter.
- **`_add_selection()` still runs during rendering**: Populates `type_id_info` with module names and `max(qty_needed)` across fits. The rebuild step only overwrites `selected_type_ids` (the set), not the info dict.
- **Multibuy format**: `st.code()` has a built-in copy button, making the separate "Copy to Clipboard" button redundant. The `Name Qty` format is directly pasteable into EVE Online's multibuy window.

**New features/functionality for documentation updates:**
- Selected items sidebar now shows EVE multibuy-compatible format (`ModuleName QtyNeeded`)
- "Copy to Clipboard" button removed; users copy via `st.code()` built-in copy button

### Phase 13: Final Cleanup & Optimization - COMPLETE

**Date:** 2026-02-07

**Files Deleted:**
| File | Reason |
|------|--------|
| `db_handler.py` (353 lines) | All functions were deprecated shims delegating to repositories, or dead code. Zero production imports. |
| `tests/test_get_all_mkt_orders.py` | Tested deprecated `db_handler` shim only |
| `tests/test_get_all_market_history.py` | Tested deprecated `db_handler` shim only |
| `tests/test_get_market_history.py` | Tested deprecated `db_handler` shim only |
| `example_test_run.py` | Example file importing deprecated function |

**Files Modified:**
| File | Changes |
|------|---------|
| `sync_state.py` | Replaced `st.session_state.X = value` with `ss_set()`. Removed `import streamlit as st`. |
| `pages/low_stock.py` | Converted 5 `st.session_state.X = value` writes to `ss_set()` |
| `pages/pricer.py` | Converted 4 `st.session_state.X = value` writes to `ss_set()`, 2 reads to `ss_has()`/`ss_get()`. Added `ss_set` to imports. |
| `repositories/base.py` | Updated docstring: historical reference to db_handler.py now uses past tense |
| `repositories/market_repo.py` | Updated docstring: historical reference to db_handler.py now uses past tense |
| `CLAUDE.md` | Removed all `db_handler.py` references from project structure, architecture diagram, and examples |

**Not Changed (intentionally):**
| File | Reason |
|------|--------|
| `pages/market_stats.py` | Complex interdependent state patterns (db init, sync checks, cascading filters). Converting partial writes would create inconsistency. |
| `pages/doctrine_status.py` | Dynamic checkbox keys, bulk iteration over session state |
| `pages/doctrine_report.py` | List mutations (`.append()`, `.remove()`) on session state |
| `pages/build_costs.py` | Heavy state machine with interdependent writes |

**Cache TTL Review:**
| TTL | Data Type | Rationale |
|-----|-----------|-----------|
| 600s (10 min) | Market stats, doctrine fits, local prices, equivalence groups | Volatile data |
| 1800s (30 min) | Market orders, download CSVs, DB update checks, history by type_ids | Moderate volatility |
| 3600s (1 hr) | Market history, SDE tables, build cost structures/rigs, preferred fits, equivalence mappings | Stable data |
| No TTL (`cache_resource`) | SDE type/group/category lookups, watchlist type_ids | Immutable at runtime |

No TTL changes needed - tiers are well-organized and appropriate.

**Test Results:** ~128 tests passing (136 - 8 deleted shim tests)

**Key Decisions:**
- Session state standardization was **targeted, not exhaustive**: infrastructure files and simple page patterns converted, but complex pages with dynamic keys and widget bindings left as-is to avoid regression risk
- `market_stats.py` left with mixed patterns because its state management is deeply intertwined with Streamlit's execution model (widget keys, cascading filters, db init flow)

**Execution order (all complete):**
```
Phase 8 (DONE)
  |-- Phase 9 (DONE) -> Phase 10 (DONE)
  |-- Phase 11 (DONE) -> Phase 11a (DONE)
       |-- Phase 12 (DONE) -> Phase 12a (DONE) -> Phase 13 (DONE)
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
