# Code Simplification Review

**Date:** 2026-02-20
**Scope:** Full codebase review against established architecture standards
**Codebase size:** 75 Python files, ~19,400 lines (excluding tests, depreciated-code, .venv)

---

## Executive Summary

The layered architecture established during the Phase 1-13 refactoring is **largely holding**. The domain layer is clean, repositories follow consistent patterns, and the service layer provides good abstraction. However, organic growth has introduced several categories of drift:

1. **Layer violations** — repositories importing from services, services importing from UI, state importing downward from repositories/services
2. **Duplicate implementations** — price fetching logic duplicated across two services, malformed-DB recovery pattern copy-pasted across repositories
3. **Dead code accumulation** — backwards-compatibility wrappers and debug utilities that are no longer called
4. **Over-sized functions** — several 300-400+ line `main()` functions in pages, and a 1,375-line doctrine service
5. **Infrastructure complexity** — 6 connection types per database alias in `DatabaseConfig` when 2-3 would suffice

None of these are critical bugs. They represent accumulated technical debt that increases maintenance burden and makes the codebase harder to navigate than it needs to be.

---

## Table of Contents

1. [Architecture Violations](#1-architecture-violations)
2. [Duplicate Implementations](#2-duplicate-implementations)
3. [Dead Code](#3-dead-code)
4. [Over-Sized Functions](#4-over-sized-functions)
5. [Infrastructure Simplification](#5-infrastructure-simplification)
6. [Misplaced Responsibilities](#6-misplaced-responsibilities)
7. [Minor Issues](#7-minor-issues)
8. [What's Working Well](#8-whats-working-well)
9. [Prioritized Action Items](#9-prioritized-action-items)

---

## 1. Architecture Violations

The layered architecture from CLAUDE.md defines strict dependency rules. Several modules violate these.

### 1.1 Repositories importing from Services (CRITICAL)

`repositories/doctrine_repo.py` imports from `services/module_equivalents_service.py`:

```
doctrine_repo.py → services.module_equivalents_service.get_module_equivalents_service
```

**Location:** `repositories/doctrine_repo.py:212, 250`
**Impact:** Breaks the repository → service direction rule. Repositories should provide raw data; equivalence aggregation belongs in the service layer.
**Fix:** Move `get_module_stock_with_equivalents()` from `DoctrineRepository` to `DoctrineService`. The repository should only return raw module stock data.

### 1.2 Services importing from UI layer (CRITICAL)

`services/pricer_service.py` imports `get_image_url` from `ui/formatters.py`:

```
services/pricer_service.py:38 → from ui.formatters import get_image_url
```

**Location:** `services/pricer_service.py:38`
**Impact:** Violates "services must NOT import from ui/" rule.
**Fix:** `get_image_url()` is pure string construction (no Streamlit dependency). Move it to `domain/converters.py` where any layer can import it. Other pure formatting functions in `ui/formatters.py` like `format_price()` and `format_delta_percentage()` should also be evaluated for relocation.

### 1.3 State layer importing downward from Repositories and Services (HIGH)

`state/market_state.py` imports directly from repositories and services for cache invalidation:

```
state/market_state.py:96  → from repositories.market_repo import invalidate_market_caches
state/market_state.py:103 → from repositories.doctrine_repo import (6 cached functions)
state/market_state.py:122 → from services.module_equivalents_service import (2 cached functions)
```

**Location:** `state/market_state.py:93-129`
**Impact:** Creates upward dependency from state → services/repositories. Since services and repositories import from `state/` in their factory functions, this is a circular dependency risk.
**Fix:** Have each repository/service register its own cache-clearing callback. The state layer would call a generic `clear_registered_caches()` function instead of importing specific cached functions by name. This also eliminates the hardcoded `_MARKET_SERVICE_NAMES` tuple (line 71-82) that must be manually updated when adding new services.

### 1.4 Streamlit in Services (HIGH)

Four services import `streamlit`:

| Service | Location | Usage |
|---------|----------|-------|
| `price_service.py` | Line 25 | `st.secrets` for Janice API key |
| `pricer_service.py` | Line 37 | `st.secrets` for Janice API key |
| `module_equivalents_service.py` | Line 18 | `@st.cache_data` decorators |
| `selection_service.py` | Line 393 | Full Streamlit UI rendering |

**Fix for secrets access:** Pass the API key as a constructor parameter. The page or factory function reads from `st.secrets` and passes it down.
**Fix for caching:** Use `functools.lru_cache` or move caching to repository level.
**Fix for selection_service rendering:** Move `render_sidebar_selections()` (lines 386-421) to `ui/` or `pages/`.

### 1.5 Repositories importing from State (MEDIUM)

`doctrine_repo.py` and `market_repo.py` import from `state/` in factory functions:

```
doctrine_repo.py:138 → from state.market_state import get_active_market_key
market_repo.py:303   → from state import ss_get
```

The try/except guards make this technically safe, but the pattern creates fragile coupling. Consider passing market keys as parameters to factory functions instead.

---

## 2. Duplicate Implementations

### 2.1 Price Fetching (HIGH — ~200 duplicate lines)

Two completely separate implementations of Fuzzwork and Janice API calls:

| Implementation | File | Lines | Returns |
|---------------|------|-------|---------|
| `FuzzworkProvider` + `JaniceProvider` | `services/price_service.py` | 169-341 | `PriceResult`/`BatchPriceResult` |
| `JitaPriceProvider` | `services/pricer_service.py` | 73-219 | `dict[int, JitaPriceData]` |

Both make identical HTTP requests to the same endpoints with the same parameters. The only functional difference: `pricer_service` extracts both buy and sell prices while `price_service` extracts only sell prices.

**Fix:** Extend `price_service.py` providers to return both buy and sell prices. Delete `JitaPriceProvider` from `pricer_service.py` and have `PricerService` consume `PriceService` providers.

### 2.2 Malformed-DB Recovery (MEDIUM — ~100 duplicate lines)

The pattern "try local → if malformed, sync and retry → fall back to remote" is copy-pasted in:

- `repositories/market_repo.py`: `_get_all_stats_impl()`, `_get_all_orders_impl()`, `_get_all_history_impl()` (lines 33-116)
- `repositories/sde_repo.py`: `_get_types_for_group_impl()` (lines 98-140)

This logic already exists in `BaseRepository.read_df()` but isn't being used by these functions.

**Fix:** Either use `BaseRepository.read_df()` consistently, or extract a `_run_with_recovery(local_fn, remote_fn)` helper on `BaseRepository` that the `_impl` functions can call.

### 2.3 Factory Pattern (LOW — repeated boilerplate)

Every repository and service factory follows an identical pattern:

```python
def get_X_repository() -> XRepository:
    def _create():
        db = DatabaseConfig(...)
        return XRepository(db)
    try:
        from state import get_service
        return get_service(f'X_repository_{key}', _create)
    except ImportError:
        return _create()
```

Copy-pasted 10+ times across `repositories/__init__.py` and `services/__init__.py`.

**Fix:** Create a shared `_create_service(name, factory_fn)` utility that handles the try/except pattern once.

---

## 3. Dead Code

### 3.1 Confirmed Dead Code (safe to remove)

| Item | Location | Evidence |
|------|----------|----------|
| `DoctrineRepository.get_methods()` | `repositories/doctrine_repo.py:522-535` | No callers found in codebase |
| `DoctrineRepository.print_methods()` | `repositories/doctrine_repo.py:537-555` | No callers found in codebase |
| `SDELookupService.resolve_items()` (public) | `services/pricer_service.py:307+` | Only private `_resolve_items()` is called |
| `calculate_jita_fit_cost_and_delta()` | `services/price_service.py:815+` | Exported in `__init__` but never called |
| `get_multi_item_jita_price()` | `services/price_service.py:809-812` | Exported in `__init__` but never called |
| `render_sidebar_selections()` | `services/selection_service.py:386-421` | Exported in `__init__` but never called |

### 3.2 Likely Dead Code (verify before removing)

| Item | Location | Notes |
|------|----------|-------|
| `config.py` instance attributes (lines 103-108) | `self._engine`, `self._remote_engine`, etc. | All access uses class-level dicts instead; instance attrs set but never read |
| `run_tests.py` | Root level | Legacy test script; superseded by `pytest` |

---

## 4. Over-Sized Functions

Functions above 150 lines that should be broken up:

| Function | File | Lines | Size |
|----------|------|-------|------|
| `main()` | `pages/doctrine_status.py` | 125-609 | ~484 lines |
| `main()` | `pages/build_costs.py` | 361-756 | ~395 lines |
| `main()` | `pages/market_stats.py` | 344-671 | ~327 lines |
| `display_low_stock_modules()` | `pages/doctrine_report.py` | 121-299 | ~178 lines |
| `build()` | `services/doctrine_service.py` | 826-926 | ~101 lines |
| `get_low_stock_items()` | `services/low_stock_service.py` | 371-478 | ~108 lines |
| `price_input()` | `services/pricer_service.py` | 470-572 | ~103 lines |

### Recommended approach for page `main()` functions

Each page's `main()` follows a similar monolithic pattern: sidebar setup → data fetching → filtering → rendering. Extract each concern into a private function:

```python
def main():
    _render_header()
    data = _fetch_and_filter_data()
    _render_content(data)
    _render_sidebar_status()
```

This doesn't require new modules — just functions within the same file.

---

## 5. Infrastructure Simplification

### 5.1 DatabaseConfig Connection Proliferation

`config.py` maintains **6 connection types per database alias**:

| Type | Property | Purpose |
|------|----------|---------|
| `_engines` | `engine` | SQLAlchemy local reads |
| `_remote_engines` | `remote_engine` | SQLAlchemy remote reads |
| `_libsql_connects` | `libsql_local_connect` | Direct libsql local reads |
| `_libsql_sync_connects` | `libsql_sync_connect` | libsql sync operations |
| `_sqlite_local_connects` | `sqlite_local_connect` | Raw sqlite3 reads |
| `_ro_engines` | `ro_engine` | SQLAlchemy read-only |

**Analysis:** The codebase primarily uses `engine` (for all repository reads) and `libsql_sync_connect` (for sync). The `remote_engine` is used for fallback reads. The `sqlite_local_connect`, `ro_engine`, and `libsql_local_connect` appear to have limited active use.

**Recommendation:** Audit which connection types are actually called, and remove or lazily-create the ones that aren't used in the hot path. The `_dispose_local_connections()` method (lines 177-210) has 5 nearly identical cleanup blocks that would shrink proportionally.

### 5.2 Timestamp Extraction Duplication in config.py

Four separate locations extract and format database timestamps:

- `_sync_once()` (lines 254-265)
- `_local_matches_remote()` (lines 380-391)
- `validate_sync()` (lines 417-429)
- `get_most_recent_update()` (lines 524-553)

**Fix:** Extract a `_get_timestamp(engine_or_conn, local=True) -> datetime` utility used by all four.

### 5.3 init_db.py String-Based Status

`init_db.py` uses emoji-embedded strings as status values:

```python
status[key] = "success initialized🟢"
status[key] = "failed🔴"
```

Then checks for emoji in strings:

```python
if "🟢" in status[key]:
```

**Fix:** Use a simple enum (`Status.SUCCESS`, `Status.FAILED`) with display formatting separate from logic.

---

## 6. Misplaced Responsibilities

### 6.1 `new_display_sync_status()` lives in `pages/market_stats.py`

This shared utility function is defined in `pages/market_stats.py:264-325` but imported by 3 other pages:

```
pages/low_stock.py:21       → from pages.market_stats import new_display_sync_status
pages/doctrine_status.py:19 → from pages.market_stats import new_display_sync_status
pages/doctrine_report.py    → from pages.market_stats import new_display_sync_status
```

**Fix:** Move to `ui/` as a shared component (e.g., `ui/sync_display.py`).

### 6.2 Business logic in pages

Several pages contain logic that belongs in the service layer:

| Page | Logic | Lines | Should be in |
|------|-------|-------|-------------|
| `market_stats.py` | `get_filter_options()` — queries SDE via `service._repo` | 55-90 | `MarketService` |
| `market_stats.py` | `check_db()` — sync decision logic | 193-246 | Sync service or `config.py` |
| `doctrine_status.py` | `render_export_data()` — bulk market stock queries | 31-68 | `DoctrineService` |
| `doctrine_report.py` | `get_module_stock_list()` — iterates modules, calls service | 31-55 | `DoctrineService` |
| `build_costs.py` | Cost calculation and DataFrame manipulation | 622-641 | `BuildCostService` |
| `low_stock.py` | `create_days_remaining_chart()` — chart creation | 28-58 | `MarketService` |

### 6.3 Settings loading in doctrine_repo.py

`_load_preferred_fits()` in `repositories/doctrine_repo.py:561-588` reads `settings.toml` directly instead of using `settings_service.py`. This couples the repository to file system layout.

**Fix:** Use `SettingsService` or accept preferred fits as a parameter.

### 6.4 sync_state.py at root level

`sync_state.py` manages session state but lives at the root level instead of in `state/`. It imports from `state.session_state` and `state.market_state`, suggesting it belongs in that package.

**Fix:** Move to `state/sync_state.py`.

---

## 7. Minor Issues

### 7.1 Inconsistent ORM base classes

- `models.py` and `sdemodels.py` use modern `DeclarativeBase` (recommended)
- `build_cost_models.py` uses old-style `declarative_base()`

**Fix:** Migrate `build_cost_models.py` to `DeclarativeBase`.

### 7.2 Boilerplate `__repr__` on ORM models

Every ORM model manually implements `__repr__` with f-strings listing all fields. SQLAlchemy's `MappedAsDataclass` or a mixin could eliminate this boilerplate.

### 7.3 Database readiness check repeated 7 times

The pattern below is copy-pasted in every page:

```python
if not ensure_market_db_ready(market.database_alias):
    st.error(...)
    st.stop()
```

**Fix:** Wrap into a single `require_market_db(market)` function in a shared location.

### 7.4 Module-level service initialization in pages

Several pages initialize services at module level (outside `main()`):

- `doctrine_status.py:26-29`
- `doctrine_report.py:26`
- `low_stock.py:25`

Module-level initialization runs on every import, not just when the page is displayed. Move inside `main()` or use lazy initialization.

### 7.5 `depreciated-code/` directory name

The directory is named "depreciated" (meaning "reduced in value") rather than "deprecated" (meaning "no longer recommended"). Minor but potentially confusing.

---

## 8. What's Working Well

The review isn't only about problems. Several architectural decisions are paying dividends:

- **Domain layer is clean.** Zero external dependencies, frozen dataclasses, safe factory methods. This is the strongest layer in the codebase.
- **Repository abstraction works.** `BaseRepository.read_df()` with malformed-DB recovery is a good pattern (it just needs to be used more consistently).
- **Factory functions with state fallback.** The try/except `ImportError` pattern for `get_service()` keeps services testable outside Streamlit. The pattern is repetitive but functional.
- **Targeted cache invalidation over global clears.** The move away from `st.cache_data.clear()` to specific function `.clear()` calls is correct.
- **`settings_service.py` is stdlib-only.** This prevents circular imports from the infrastructure layer.
- **`MarketConfig` domain model.** Multi-market support via configuration rather than code changes is well-designed.
- **Service protocol/ABC usage.** `PriceProvider`, `ShipRoleCategorizer` abstractions enable clean dependency injection and testing.
- **No TODO/FIXME/HACK comments.** The codebase is clean of deferred work markers.

---

## 9. Prioritized Action Items

### Tier 1 — Architecture Violations (fix first)

| # | Action | Files | Impact |
|---|--------|-------|--------|
| 1 | Move `get_module_stock_with_equivalents()` from `DoctrineRepository` to `DoctrineService` | `doctrine_repo.py`, `doctrine_service.py` | Removes repo → service import |
| 2 | Move `get_image_url()` (and other pure functions) from `ui/formatters.py` to `domain/converters.py` | `ui/formatters.py`, `domain/converters.py`, `services/pricer_service.py` | Removes service → UI import |
| 3 | Refactor `state/market_state.py` cache invalidation to use registered callbacks | `state/market_state.py`, repositories, services | Removes state → repo/service imports |
| 4 | Pass API keys as constructor params instead of reading `st.secrets` in services | `price_service.py`, `pricer_service.py` | Removes Streamlit from services |
| 5 | Move `render_sidebar_selections()` from `services/selection_service.py` to `ui/` | `services/selection_service.py` | Removes Streamlit UI from services |

### Tier 2 — Duplicate Code Elimination

| # | Action | Files | Lines Saved |
|---|--------|-------|-------------|
| 6 | Consolidate price providers: delete `JitaPriceProvider`, extend `PriceService` providers | `pricer_service.py`, `price_service.py` | ~150 lines |
| 7 | Extract malformed-DB recovery to `BaseRepository` helper | `market_repo.py`, `sde_repo.py`, `base.py` | ~80 lines |
| 8 | Create shared factory builder for repositories/services | `repositories/__init__.py`, `services/__init__.py` | ~60 lines |

### Tier 3 — Dead Code Removal

| # | Action | Files | Lines Saved |
|---|--------|-------|-------------|
| 9 | Delete `get_methods()` and `print_methods()` | `doctrine_repo.py` | ~35 lines |
| 10 | Delete unused backwards-compat wrappers: `calculate_jita_fit_cost_and_delta`, `get_multi_item_jita_price` | `price_service.py`, `services/__init__.py` | ~25 lines |
| 11 | Delete unused `render_sidebar_selections()` (after moving if needed) | `services/selection_service.py` | ~35 lines |
| 12 | Delete unused public `SDELookupService.resolve_items()` | `services/pricer_service.py` | ~15 lines |
| 13 | Remove unused instance attributes from `DatabaseConfig.__init__` | `config.py:103-108` | 6 lines |

### Tier 4 — Code Organization

| # | Action | Files |
|---|--------|-------|
| 14 | Move `new_display_sync_status()` to `ui/sync_display.py` | `pages/market_stats.py` → `ui/` |
| 15 | Move `sync_state.py` to `state/sync_state.py` | Root → `state/` |
| 16 | Move settings loading from `doctrine_repo.py` to `settings_service.py` | `doctrine_repo.py`, `settings_service.py` |
| 17 | Move module-level service initialization inside `main()` in pages | `doctrine_status.py`, `doctrine_report.py`, `low_stock.py` |

### Tier 5 — Simplification (lower priority)

| # | Action | Files |
|---|--------|-------|
| 18 | Break up page `main()` functions into sub-functions | All pages |
| 19 | Audit and reduce `DatabaseConfig` connection types | `config.py` |
| 20 | Consolidate timestamp extraction in `config.py` | `config.py` |
| 21 | Migrate `build_cost_models.py` to `DeclarativeBase` | `build_cost_models.py` |
| 22 | Replace string-based status in `init_db.py` with enum | `init_db.py` |
| 23 | Extract shared `require_market_db()` helper for pages | Pages directory |

---

## Metrics Summary

| Category | Count |
|----------|-------|
| Architecture violations (layers) | 5 distinct violations |
| Duplicate implementations | 3 patterns (~330 duplicate lines) |
| Dead code items | 6 confirmed, 2 likely |
| Over-sized functions (>150 lines) | 7 functions |
| Misplaced responsibilities | 6 items |
| Minor issues | 5 items |

**Estimated lines removable from dead code + deduplication:** ~400-500 lines
**Estimated lines improvable via restructuring:** ~1,500 lines across pages and services
