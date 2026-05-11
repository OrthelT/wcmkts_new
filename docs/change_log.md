# Change Log

Historical record of releases, the architectural refactoring project (Phases 1-13), and feature refinements. Useful for understanding why the codebase looks the way it does, and as reference for future work.

---

## Unreleased (v0.6.2 in pyproject)

Pricer overhaul release. Replaces the per-item price grid with a Janice-style fit availability hero, fixes a production crash on the Janice batch endpoint, and collapses three near-identical batch methods on the Jita price service into one.

### New Features
- **Fit Availability hero** (`pages/pricer.py`, `domain/pricer.py`): Pasting an EFT fit now shows a focal `fits-available` count, three supporting metrics, a progress bar, and a red/orange bottleneck callout for the lowest-stock module — answering "how many of this fit can I buy right now?" without forcing the user to read the per-item table. Backed by pure `compute_fit_availability` helper and `FitAvailabilitySummary` / `ItemAvailability` domain models with 10 dedicated unit tests.
- **Faction-equivalent aggregation** on the pricer fit hero, toggleable (default on). Substitutes faction-equivalent modules into stock counts only where an equivalence group exists, reusing `ModuleEquivalentsService`.
- **Janice-style page layout**: Single bordered card, results on top, input below with right-aligned submit, mirroring janice.e-351.com.
- **Partial-data signals**: PricerResult now exposes `failed_jita_count` / `jita_provider_failed`; FitAvailabilitySummary exposes `unpriced_item_count`, `stock_unknown_count`, and `total_isk_complete`; ItemAvailability distinguishes "no local market data" from "zero stock". Headline totals no longer silently understate cost when partial data is missing -- honoring the *never lie to the user* rule.

### Improvements
- **Space-separated multibuy parsing**: Lines without tabs now resolve correctly. Walks tokens left-to-right, treating the first pure-integer token as quantity. Previously inputs like `Torpedo Launcher II 63` were treated as a single item name with qty=1 and failed to resolve against SDE.
- **Summary card totals**: Replaced Buy / Split / Sell row with explicit `{market} Sell Total`, `Jita Sell Total`, and `Jita Buy Total` grand totals.
- **Janice batch endpoint compatibility** (`services/price_service.py::JaniceProvider._parse_response`): Now accepts both the v2 `/pricer` top-level JSON list (`itemType.eid` + top-level `top5AveragePrices`) and the legacy `{"appraisalItems": [...]}` envelope. Fixes the production `'list' object has no attribute 'get'` crash. Defensive `isinstance` checks at every layer; missing fields no longer raise.
- **Derived fields as properties**: `FitAvailabilitySummary.bottleneck_items`, `counted_item_count`, `used_equivalents`, and `stock_unknown_count` are now `@property` derivations from `items` rather than fields that `compute_fit_availability` could contradict. `ItemAvailability.__post_init__` rejects negative `quantity_per_fit` / `raw_stock` / `stock_used` / `fits_possible` instead of silently accepting inconsistent rows.

### Refactoring
- **Collapsed three batch Jita-price methods into one**: `PriceService` previously had `get_jita_prices`, `get_jita_prices_as_dict`, and `get_jita_price_data_map` — three near-identical batch entry points where callers picked arbitrarily. Now only `get_jita_prices(type_ids) -> BatchPriceResult` exists; callers use `.prices` (dict[TypeID, PriceResult]) or `.to_dict()` (dict[TypeID, Price]) as needed. 7 caller sites audited as read-only before switching from defensive copy to shared reference.
- **Renamed `PriceService` → `JitaPriceService`**: The class identifier now reflects what it actually does — a Jita-specific price fetcher with provider chain (DB cache → Fuzzwork → Janice), distinct from the local-market aggregator in `MarketService`. The module file (`services/price_service.py`), factory function (`get_price_service()`), and session-state cache key are unchanged to minimize churn. Eliminates the long-standing one-letter confusion with `PricerService`.
- **Removed duplicate `get_jita_price` wrappers**: The module-level `get_jita_price` shim in `services/price_service.py` and the local helper in `ui/popovers.py` (both wrapping the same `PriceService.get_jita_price()` method) are gone. Callers go through `get_price_service().get_jita_price(type_id).sell_price` directly.
- **Single-source-of-truth tightening** on `domain/pricer.py`: dropped unused imports, collapsed multi-paragraph docstrings to one-liners, removed redundant fallback paths.

### Documentation
- Removed outdated docs: `code_simplification_review.md`, `docs.md`, `quick_reference.md`, `selectable-mkts.md` (~1,053 lines).

### Bug Fixes
- Parser tests now cover EFT charge stripping and space-separated multibuy edge cases.
- Removed accidental imports, stray `print()` calls, and a duplicate header from pricer code.
- Reverted a short-lived "clear Jita cache on each Price Items click" patch that broke the cross-session cache contract.

---

## v0.6.1 (2026-05-07)

Doctrine modules table on the Market Dashboard now mirrors the Doctrine Ships pattern, replacing the click-via-iloc routing that misrouted clicks when the low-stock filter hid rows.

### Improvements
- **Modules table mirrors ships pattern**: Replaced row-selection routing with `_mkt` / `_doc` checkbox columns matching the Doctrine Ships table. Fixes the iloc/positional mismatch where filtering hid rows but click events still used positional indexes, routing users to the wrong item's Market Stats page.
- **`fit_count` aggregation** added in `_compute_module_targets()`; modules now show how many doctrine fits use them.
- **Module deep-link** (`module_id` query param) on `pages/doctrine_status.py` filters fits to those using a specific module and renders a banner naming the module — completing the round trip from dashboard click to filtered doctrine view.
- **Column order**: `type_id`, image, item, % target, stock, fits, qty needed, prices, then `_mkt`/`_doc` checkbox columns.
- **New i18n keys** (`column_fits`, `hint_click_doctrine_status_module`, `module_filter_banner`) across en/zh/de/fr/ru/es.

### Bug Fixes
- Addressed PR #63 review findings.
- Minor dashboard table formatting tweaks.
- Removed the 5-minute-to-update balloon animation introduced in v0.5.0 (was disruptive at scale).

---

## v0.6.0 (2026-05-05)

Builder Helper release. Adds an importer-style profitability page for manufacturers, swaps the build-cost data source to the synced `buildcost.db` catalog, and replaces stacked toggle buttons with `st.menu_button` chord.

### New Features
- **Builder Helper page** (`pages/builder_helper.py`, `services/builder_helper_service.py`): EverRef-free profitability tool for manufacturers. Shows ROI, ISK/hour, 30-day profit, and turnover for items in the watchlist, sourced from the synced builder-cost catalog. Replaces the prototype that called EverRef live.
- **Price-basis toggle** (`st.segmented_control`) on the Builder Helper: switch profitability calculations between 30-day average and current price. Defaults to 30-day average — manufacturing horizons span hours-to-days, so current-price spikes can mislead.
- **Dashboard low-stock filter**: Market Dashboard now constrains to low-stock doctrine items by default with a filter override toggle, focusing FCs on the items that actually need attention.

### Improvements
- **Build-cost catalog from `buildcost.db`**: Switched both Build Costs and Builder Helper from the dead `wcmktprod.db.builder_costs` table to the synced `buildcost.db` catalog (the backend's source of truth). Item-name, group, and category metadata enriched in the service layer via watchlist + marketstats join. Old build-cost repository and industry-index fetch logic retired.
- **Corrected ROI formula**: Builder Helper's `cap_utils` was previously `(sell-cost)/sell` (gross margin, capped at 100%); now `(sell-cost)/cost` (ROI, can exceed 100%). Help strings updated in all 6 translated languages.
- **ISK/Hour column** added to Builder Helper (the description already promised it but the column was missing). Derived from `buildcost.db.builder_costs.time_per_unit`.
- **Doctrine Status ship display revisions**: Tightened the ship display layout; swapped stacked toggle buttons for a single `st.menu_button` chord that respects column `vertical_alignment` (see `reference_streamlit_menu_button.md` in memory).
- **Centralized shared page chrome** (`pages/components/page_chrome.py`): Logo, language selector, and page titles render through shared helpers. Removes duplicated Streamlit header code; main pages now visually consistent.
- **TZ-bug fix in PriceService**: `time_until_next_db_update` now correctly handles tz-aware non-UTC inputs.
- **Table formatting hygiene**: Replaced deprecated `use_container_width` calls with Streamlit native formats; cap_utils column no longer double-scaled (format="percent" already scales raw fractions).

### Bug Fixes
- Doctrine Ships row resolution now uses pandas `index` (not `iloc`) — fixes the same positional/index mismatch the v0.6.1 modules-table refactor addressed.
- `pd.read_sql_query` syntax updated for list parameters.
- Table styles render only when needed; eliminates flicker in narrow viewports.

### Refactoring
- **Repository cleanup**: `get_builder_cost_catalog` moved from `MarketRepository` to `BuildCostRepository` (correct domain).
- **Removed unused functions and short-if expressions** flagged by review.

---

## v0.5.1 (2026-05-04)

Dashboard refinement release. Builds on the v0.5.0 dashboard with target % progress bars, full-width layout, and harder error handling.

### Improvements
- **Doctrine Ships table**: New `% target` column (fits_on_mkt / ship_target) rendered as an inline progress bar; columns reordered to: icon, fit_id, item, progress bar, stock, fit_available, target, % target, sell_price, jita_sell.
- **Popular Modules table**: New `target %` and `qty needed` columns derived from doctrine requirements; alphabetized; includes all non-ship doctrine items. Column order: icon, item, stock, target %, qty needed, sell_price, jita_sell, jita_buy, % vs jita.
- **Full-width layout**: Doctrine Ships and Popular Modules tables now span the page width instead of sharing a two-column split.
- **Surface missing ship_targets**: Dashboard now reports doctrine fits that have no `ship_targets` row instead of silently dropping them.
- **Color refinement**: Mid-luminance tones used for low-stock highlights so they stay readable in dark mode; third neutral color for small positive deltas.

### Bug Fixes
- Hardened error handling around uninitialized DB access on the dashboard.
- Replaced deprecated `pandas.Styler.applymap` with `Styler.map`.

---

## v0.5.0 (2026-04-XX)

Market Dashboard release. Introduces a new default landing page with at-a-glance doctrine ship coverage and popular module stock, expanded multi-market support, and significant sync/cache plumbing improvements.

### New Features
- **Market Dashboard** (`pages/market_dashboard.py`): New default landing page with Doctrine Ships, Popular Modules, Minerals, and Isotopes tables. Rows are clickable -- ships jump to Doctrine Status filtered by ship; minerals/isotopes/modules jump to Market Stats with the item pre-selected via query parameter.
- **Module equivalents on dashboard**: Dashboard fits-on-market calculations apply the module-equivalents aggregation and use bottleneck (lowest-availability module) instead of hull count, matching Doctrine Status semantics.
- **x47 market hub**: Added as a third selectable hub alongside 4-HWWF and B-9C24; deployment switched to 4-HWWF Sotiyo with the new keepstar.
- **Low-stock doctrine market export**: New CSV export on the Downloads page that joins low-stock items with their doctrine usage.
- **Time-to-update progress bar**: Sidebar replaces text countdown with a progress bar; balloons fire when less than 5 minutes remain before the next scheduled update.
- **DB refresh extraction**: Shared `pages/components/db_refresh.py` drives database initialization and staleness check from the dashboard; Market Stats delegates to the same code.

### Improvements
- **Doctrine IDs as state**: Doctrine selectboxes now key on integer doctrine IDs (not display strings) for robust localization; `fit_name` added to all doctrine exports.
- **Active-market correctness**: Downloads page, doctrine downloads, and download section descriptions now respect the active market hub. Architecture rule added: never silently display data from the wrong market context -- fail with empty results instead.
- **Sync simplification**: Removed parallel sync validation paths; `local_matches_remote()` is the single source of truth for sync freshness. `time_until_next_db_update` correctly handles tz-aware non-UTC inputs. Cache orchestrator renamed for clarity.
- **Cache hygiene on sync**: Downloads page CSV caches and sidebar update times refresh after DB sync; manual sync button renamed; "Loading updated data" toast added after sync.
- **Performance**: Smaller `wclogo` for faster page load; deferred remote sync check until `check_update` runs; eliminated duplicate localization calls on Market Stats.
- **Pricer/Market Stats**: Auxiliary pricing table added to the Market Stats view with adjusted column sizing; Import Helper now filters zero-volume rows.
- **Removed mineral/isotope tables from Market Stats**: They now live on the dashboard.

### Bug Fixes
- Resolved `DatabasePriceProvider` deferred-issue regressions.
- Doctrine exports guarded against empty targets and missing columns.
- Removed unused sort column and redundant `reset_index` in low-stock export.

---

## v0.4.1 (2026-03-14)

Version bump. No functional changes.

---

## v0.4.0 (2026-03-12)

Multi-language support release. All pages now support 8 languages with localized item names and UI strings, plus robustness improvements from the type_id refactor.

### New Features
- **8-Language UI Translation**: Lightweight translation system (`ui/i18n.py`) supporting EN, ZH, DE, FR, RU, ES, JP, and KR across all pages — ~132 translation keys covering navigation, labels, tooltips, column headers, and help text.
- **Language Selector**: Top-right selectbox with flag emoji labels. Selection persists via URL query parameter (`?lang=xx`) for bookmarkable links.
- **Type Name Localization**: New `services/type_name_localization.py` leverages the SDE `localizations` table (~210k rows) to display localized item and ship names with automatic English fallback for untranslated items.
- **Language State Management**: New `state/language_state.py` synchronizes active language between session state and URL query params, surviving page reloads.

### Improvements
- **Category ID Filtering**: Market Stats, Low Stock, and Doctrine Status now filter by `category_id` (int) instead of `category_name` (string), making filtering robust across all languages.
- **Type ID Refactor in Doctrine Report**: Module selection state (`selected_modules`) now uses `set[int]` of type_ids instead of string names, preventing breakage when switching languages. Merged from main's type_id refactor (PR #35).
- **Configurable Shipping Cost**: Import Helper now exposes a user-facing number input for shipping cost per m³ (default 450 ISK/m³) with localized help text.
- **Localized Data Tables**: All Streamlit dataframes display localized column headers via `get_doctrine_report_column_config(language_code)` and friends.

### Technical Details
- New modules: `ui/i18n.py`, `state/language_state.py`, `services/type_name_localization.py`
- `sde_repo.py` extended with `get_localized_name()`, `get_localized_names()`, `get_all_translations()` methods
- English-language optimization: SDE queries skipped when `language_code="en"`
- All 6 data pages updated: Market Stats, Doctrine Status, Doctrine Report, Low Stock, Import Helper, Pricer
- Test suite grown from ~147 to 181 tests with new coverage for i18n, language state, and type name localization

---

## v0.3.1 (2026-03-08)

Patch release incorporating the Import Helper feature (PR #32), CLI database sync, and accumulated bug fixes since v0.3.0.

### New Features
- **Import Helper Page** (PR #32, contributed by MrDiao): Compare local market prices against Jita sell/buy to spot import opportunities. Displays shipping cost, profit margin, recommended retail price, and capital utilisation.
- **CLI Database Sync**: Run `uv run python config.py <alias>` to sync any database from the command line.
- **Module Equivalents Overhaul**: Renamed schema, added faction filter, explicit UI indicators (`~` badge), lowest-cost equivalent used in fit cost calculations, equivalent module popovers.
- **Doctrine Display Names from DB**: Display names loaded from `doctrine_display_names` table instead of a hardcoded dictionary.

### Improvements
- Alphabetized ship selections in doctrine pages.
- Per-market cache keying (`market_alias` in cache hash) to prevent incorrect module counts when switching hubs.
- Standardized update time displays across all pages.
- 7-phase code simplification refactor (PR #31).
- Documented layer dependency exceptions for `sync_display` and `sync_state`.
- Shipping cost moved to `settings.toml` (`[import_helper].default_shipping_cost`).

### Bug Fixes
- Fixed infinite loop from `st.rerun()` in `build_costs.py` (replaced with `st.stop()`).
- Synced `VALID_SDE_TABLES` allowlist with actual `sdelite.db` tables.
- Fixed edge case where proper module count is zero but exactly one equivalent exists.
- Ranked low-stock modules by own stock, not combined equivalent stock.
- Moved doctrine name DB query out of domain layer (layer violation fix).
- Fixed incorrect report of successful sync on failed validation.
- Used epsilon comparison in import helper test to prevent floating-point rounding failures.

---

## v0.3.0 (2026-02-20)

Major release introducing multi-market hub support.

### New Features
- **Selectable Multi-Market Support**: Toggle between 4-HWWF (primary) and B-9C24 (deployment) market hubs via a pills toggle in the UI.
- **Market Configuration in settings.toml**: `[markets.primary]` and `[markets.deployment]` sections define market hub metadata, database aliases, and Turso secret keys.
- **Dynamic Alias Resolution**: `_resolve_active_alias()` reads session state to resolve `wcmkt`/`wcmkt2`/`wcmkt3` to the currently active market.
- **Cold-Start Database Guards**: All pages guard against unsynced market databases on cold start.
- **Stale Replica Detection**: `sync()` detects stale embedded-replica metadata and retries with a fresh database file.

### Improvements
- `init_db()` must succeed for all databases before setting `db_initialized`.
- `verify_db_content()` prevents empty db files from bypassing cold-start sync.
- `[db_turso_keys]` override in `settings.toml` maps aliases to non-standard Turso secret names.
- Doctrine name display tidied up.
- Market selector changed from dropdown to pills toggle.

### Bug Fixes
- Fixed Turso credential mismatch for `sde` and `build_cost` aliases.
- Prevented empty db files from bypassing cold-start sync.
- Fixed `_db` attribute usage in `DoctrineRepository` cached wrappers.
- Fixed `DataFrame` truth value error in `_rebuild_selections`.
- Prevented improper `marketstats` table check in sde and build_cost databases.

---

## v0.2.0 — Architectural Refactoring (Phases 1-13)

### Executive Summary

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
