# Architecture Refactoring Project (Phases 8-13)

Extends the Domain -> Repository -> Service -> Page pattern established in Phases 1-7 to market data, build costs, and shared infrastructure. Implements recommendations from `docs/architecture_review.md`.

## Quick Resume Guide

**Current Status:** Phase 8 COMPLETE. Ready to begin Phase 9.

**Branch:** `architecture-review`

**Run tests:** `uv run pytest -q` (41 tests, all passing)

**Key context for next session:**
- Phase 8 removed RWLock and local_access() from the entire codebase
- `repositories/base.py` now provides `BaseRepository.read_df()` with malformed-DB recovery
- `market_metrics.py` bugs fixed (module-level side effects, duplicate computation block)
- SDE caches changed from `@st.cache_data(ttl=3600)` to `@st.cache_resource`
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

## Upcoming Phases

### Phase 9: Market Repository & Cache Strategy
- Create `repositories/market_repo.py` (MarketRepository inheriting BaseRepository)
- Create targeted cache invalidation (replace global `st.cache_data.clear()`)
- Extract `sync()` Streamlit coupling from `config.py`
- Update `pages/downloads.py`, `pages/low_stock.py`, `pages/doctrine_status.py`, `pages/doctrine_report.py`, `ui/popovers.py` to use MarketRepository
- Add backward-compat shims in `db_handler.py` (marked DEPRECATED)

### Phase 10: Market Service & Page Migration
- Create `services/market_service.py` (pure calculation logic)
- Create `pages/components/market_components.py` (UI rendering)
- Refactor `pages/market_stats.py` as orchestrator
- Delete `market_metrics.py`

### Phase 11: Build Cost Repository & Service
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
  |-- Phase 9 -> Phase 10
  |-- Phase 11 (independent of 9-10, requires 8)
       |-- Phase 12 (requires 9-11) -> Phase 13
```
