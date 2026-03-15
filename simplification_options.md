# Simplification Options

Institutional memory for codebase simplification analysis.
Last analysis: 2026-03-14

---

## Previously Implemented Changes

### P1-A: Moved _drop_localized_backup_columns to ui/formatters.py
- Implemented: 2026-03-14
- Consolidated all 4 page-local copies into `drop_localized_backup_columns()` in `ui/formatters.py`
- Handles all known backup column names: type_name_en, ship_name_en, Item_en

### P1-B: Removed sys.path.append hacks from 6 pages
- Implemented: 2026-03-14
- Removed from: market_stats.py, doctrine_status.py, doctrine_report.py, build_costs.py, pricer.py, downloads.py
- Also cleaned up unused `import os, sys` in those files

### P1-C: Removed double-computed shipping_cost from fetch_base_data
- Implemented: 2026-03-14
- Removed shipping_cost, profit_jita_sell, profit_jita_sell_30d, and capital_utilis from fetch_base_data
- These are now only computed in get_import_items where the user's filter value is available
- Kept turnover_30d and volume_30d (independent of shipping cost)

### P1-D: Cleaned up wcmkt alias handling (partial — per user review)
- Implemented: 2026-03-14
- Removed wcmkt2/wcmkt3 deprecated aliases; kept wcmkt resolution to active market

### P2-A: Consolidated create_default alias resolution
- Implemented: 2026-03-14
- Added `resolve_db_alias()` to settings_service.py
- Updated 6 services: DoctrineService, LowStockService, ModuleEquivalentsService, PricerService, ImportHelperService, get_price_service()

### P2-B: Refactored market_repo _impl functions to use BaseRepository.read_df
- Implemented: 2026-03-14
- _get_all_stats_impl, _get_all_orders_impl, _get_all_history_impl now use BaseRepository.read_df()
- Eliminated ~60 lines of duplicated try/sync/retry/remote-fallback logic

### P2-C: Fixed SQL injection in _get_history_by_type_ids_impl
- Implemented: 2026-03-14
- Replaced string-formatted IN clause with bindparam(..., expanding=True)

### P2-D: Moved dead helpers.py to dev_files/
- Implemented: 2026-03-14
- File imported deleted modules (db_handler, type_info) and was not used by any active code path

### P2-E: Consolidated DEFAULT_LANGUAGE via settings.toml
- Implemented: 2026-03-14
- Added [i18n] section with default_language to settings.toml
- Added default_language property to SettingsService
- Updated ui/i18n.py and state/language_state.py to read from settings_service

---

## Active Recommendations

----------------------------------------------
# IMPORTANT: Proceed Only with P1 and P2, which have been reviewed. Phases 3+ Still Require reviews and should not be implemented yet. 
----------------------------------------------

### P1-A: Move _drop_localized_backup_columns to ui/formatters.py
- Status: IMPLEMENTED
- Added: 2026-03-14
- What: The four-line helper `_drop_localized_backup_columns` is defined identically in four page files: `pages/market_stats.py`, `pages/doctrine_status.py`, `pages/doctrine_report.py`, and `pages/pricer.py`. Move it once to `ui/formatters.py` and import it in each page.
- Why: Pure dead duplication, zero behavioral variation. The function is a one-liner (drop two columns with errors="ignore").
- Impact: Scope: Small | Risk: Low | Benefit: Medium | Difficulty: Easy
- Validation: Run existing test suite, verify pages still render.

### P1-B: Remove sys.path.append hacks from pages
- Status: IMPLEMENTED
- Added: 2026-03-14
- What: Six page files (`market_stats.py`, `doctrine_status.py`, `doctrine_report.py`, `build_costs.py`, `pricer.py`, `downloads.py`) contain `sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))`. The project has a proper `pyproject.toml` and is installed as a package; these are no-ops in normal execution.
- Why: Dead code noise, misleads readers into thinking path manipulation is necessary.
- Impact: Scope: Small | Risk: Low | Benefit: Low | Difficulty: Easy
- Validation: Run app and all tests. All imports work without these lines.

### P1-C: SHIPPING_COST_PER_M3 double-computed in fetch_base_data and get_import_items
- Status: IMPLEMENTED
- Added: 2026-03-14
- What: In `services/import_helper_service.py`, `fetch_base_data()` (line 327) computes `df["shipping_cost"] = df["volume_m3"] * SHIPPING_COST_PER_M3` using the module-level constant, then `get_import_items()` (line 366) immediately recomputes `df["shipping_cost"] = df["volume_m3"] * filters.shipping_cost_per_m3`. The first calculation is always thrown away by the second when called from the page. The first calculation (in fetch_base_data) should be removed; shipping should only be calculated in get_import_items where the filter value is available.
- Why: Wasteful computation; also misleadingly calculates profit/capital_utilis with the wrong (default) shipping rate in fetch_base_data, making those columns inaccurate unless the user uses the exact default value.
- Impact: Scope: Small | Risk: Low | Benefit: Medium | Difficulty: Easy
- Dependencies: Ensure tests use the two-call pattern (fetch_base_data -> get_import_items) not the old single-call path.
- Validation: Test that shipping cost overrides in the page UI correctly affect all computed columns.

### P1-D: Eliminate deprecated wcmkt alias handling in DatabaseConfig.__init__

**USER COMMENT**
REJECTED: "wcmkt" is no longer deprecated. It is resolved to the active db alias, which could be wcmktprod or wcmktnorth2 based on user input. wcmkt is still used throughout the code. You can remove wcmkt2 and wcmkt3, but I would rather just document that wcmkt is the equivelant of active database than change every caller to using the direct call meathod. just resolve wcmkt in config.py. it's only five characters after all, get_active_market().db_alias is 35, seven times longer. Verbose garbage no.  

- Status: ~~RECOMMENDED~~ REJECTED
- Added: 2026-03-14
- What: `config.py` line 87 has a special-case branch for aliases "wcmkt", "wcmkt2", "wcmkt3" that re-resolves them to the active market. Only "wcmkt" is used anywhere in the codebase (service create_default fallbacks), and "wcmkt2"/"wcmkt3" don't appear in any active code. Replace service fallback strings "wcmkt" with the direct call `get_active_market().database_alias` (already done in the happy path), then remove the alias branch.
- Why: The compat shim is the last remnant of a migration. It adds a confusing special case to a critical infrastructure class.
- Impact: Scope: Small | Risk: Low | Benefit: Low | Difficulty: Easy
- Note: Confirm no tests use "wcmkt" as a literal alias argument.
- Validation: Grep for "wcmkt" as a string literal, update fallbacks, run tests.

### P2-A: Consolidate duplicated create_default market-alias resolution across services
- Status: IMPLEMENTED
- Added: 2026-03-14
- What: The pattern "if db_alias is None: try: from state.market_state import get_active_market; db_alias = get_active_market().database_alias; except (ImportError, Exception): db_alias = 'wcmkt'" appears verbatim in six service create_default methods: `DoctrineService`, `LowStockService`, `ModuleEquivalentsService`, `PricerService`, `ImportHelperService`, and in `price_service.py`'s `get_price_service()`. Extract a small helper function `_resolve_db_alias(fallback: str = "wcmktprod") -> str` in a shared location (e.g. `settings_service.py` or a new `services/_utils.py`) and have each service call it.
- Why: Six copies of identical error-handling logic that must be updated together if the fallback alias or error handling changes.
- Impact: Scope: Medium | Risk: Low | Benefit: Medium | Difficulty: Easy
- Validation: All service create_default tests should continue to pass.

### P2-B: market_repo.py _impl functions duplicate BaseRepository.read_df pattern
- Status: IMPLEMENTED
- Added: 2026-03-14
- What: `_get_all_stats_impl`, `_get_all_orders_impl`, and `_get_all_history_impl` in `repositories/market_repo.py` each manually implement the try/sync/retry/remote-fallback pattern that is already centralized in `BaseRepository.read_df()`. Each is 20-30 lines of near-identical error handling. These should call `BaseRepository.read_df()` instead.
- Why: `BaseRepository.read_df()` was explicitly created to eliminate this duplication. Having three copies outside it defeats the purpose.
- Impact: Scope: Small | Risk: Low | Benefit: Medium | Difficulty: Easy
- Note: The cached wrappers pass `db_alias` as a string and create a new `DatabaseConfig` inside. They'd need to either keep doing that or accept an engine. The simplest fix is to instantiate the repo inside the _impl and call read_df.
- Validation: Run tests; confirm malformed-DB recovery path still works.

### P2-C: Market repo _get_history_by_type_ids_impl uses string-formatting for SQL IN clause
- Status: IMPLEMENTED
- Added: 2026-03-14
- What: In `repositories/market_repo.py` line 143, `_get_history_by_type_ids_impl` builds the SQL IN clause by string-joining quoted type_id values: `type_ids_joined = ','.join(f"'{tid}'" for tid in type_ids_str)`. This bypasses parameterization. It should use SQLAlchemy's `bindparam(..., expanding=True)` pattern, which is already used in other queries in the same codebase (see `_get_sde_info_impl`).
- Why: The string-formatting approach is a potential SQL injection vector, even though type_ids are nominally integers. The pattern is already solved correctly elsewhere.
- Impact: Scope: Small | Risk: Low | Benefit: Medium | Difficulty: Easy
- Validation: Test history queries, confirm results unchanged.

### P2-D: helpers.py imports deleted modules (db_handler, type_info)
- Status: IMPLEMENTED (moved to dev_files/)
- Added: 2026-03-14
- What: `helpers.py` at the project root imports `from db_handler import build_cost_url, request_type_names` and `from type_info import get_backup_type_id` (lines 6 and 9). These modules no longer exist in the codebase. The file also contains `pass`-body stubs (`add_item_to_watchlist`, `remove_item_from_watchlist`, `get_watchlist`, `clear_watchlist`) and print statements.
- Why: This file will crash on import. It's not imported by any active code path, but is a maintenance hazard.
- Recommendation: Move to `dev_files/` or delete. If any functions are genuinely needed, reimplement them using current infrastructure.
- Impact: Scope: Small | Risk: Low | Benefit: Low | Difficulty: Easy

### P2-E: Double DEFAULT_LANGUAGE constant — ui/i18n.py and state/language_state.py
**USER COMMENT**
I agree with consolidating these centrally. But, we already have settings.toml and a settings_service to call it. I think we should use the existing settings infrastructure rather than creating a new one. In fact, we should make this a rule and something we explicitly look for in code simplification reviews: For global configuration parameters always use the settings.toml --> settings_service path unless there is a strong reason to configure it separately. 

- Status: IMPLEMENTED (via settings.toml per user directive)
- Added: 2026-03-14
- What: `DEFAULT_LANGUAGE = "en"` is defined independently in both `ui/i18n.py` (line 9) and `state/language_state.py` (line 9). The `state` layer cannot import from `ui`, so `language_state.py` cannot reuse the `ui/i18n.py` constant. However, both could import from `domain/` or from a new thin `constants.py` file at root.
- Why: If the default language ever changes, two places must be updated in sync.
- Impact: Scope: Small | Risk: Low | Benefit: Low | Difficulty: Easy
- Note: The architectural constraint (state cannot import ui) is real — must put the constant at a lower layer.

----------------------------------------------
# STOP HERE: Phases 3+ Still Require reviews
----------------------------------------------

### P3-A: market_repo.py bypasses BaseRepository entirely (module-level functions create their own DatabaseConfig)
- Status: RECOMMENDED
- Added: 2026-03-14
- What: The cached `_impl` functions in `market_repo.py` each create `db = DatabaseConfig(db_alias)` inline rather than using the `MarketRepository` instance's `self.db`. The repository class exists but its `read_df()` and `self.db` are not used by the primary data paths — the class is just a thin wrapper that calls the module-level functions. This means the BaseRepository's recovery logic is not exercised on the main read paths.
- Why: The architecture intended BaseRepository.read_df() to centralize malformed-DB recovery. The market repo re-duplicates it instead of using it.
- Impact: Scope: Medium | Risk: Medium | Benefit: Medium | Difficulty: Moderate
- Note: This is a deeper refactor; the module-level functions exist to work around Streamlit's cache hashing. The right approach is for the _impl functions to accept an engine (not a db_alias string) and have the cached wrapper manage the alias. The _impl can then just do `read_df`.
- Validation: Full test suite + manual smoke test of all market-data pages.

### P3-B: Localization call sites in pages import from services.type_name_localization directly
- Status: DEFERRED (design decision required)
- Added: 2026-03-14
- What: Six page files import directly from `services.type_name_localization`. Per the architecture, pages should use services, not call service-layer helpers directly. The localization functions could be moved to `ui/formatters.py` or exposed through the service objects (e.g. `service.apply_localized_names(...)`). However, the current functions take `sde_repo` as a parameter and live at the service layer. This is a structural layering question.
- Why: Minor layer violation (pages reaching into services for utility functions rather than through a service method). Lower priority than other items.
- Impact: Scope: Medium | Risk: Low | Benefit: Low | Difficulty: Moderate
- Recommendation: Defer. The current approach works and is not harmful.

---

## Rejected Ideas
None yet.

---

## Notes and Context
- The codebase went through a major localization refactor (multi-lingual PR #34) and type_id refactor (PR #35) recently. Many of the duplication patterns were introduced during that work.
- The `helpers.py` file references `db_handler` and `type_info` which are legacy modules no longer present. This file is not imported anywhere active.
- The `market` section in settings.toml (lines 108-110) appears to be a leftover single-market config. With the multi-market system in `[markets.*]`, this section may be dead. Verify before removing.
- The `[env_db_aliases]` section in settings.toml and the corresponding `wcdbmap` in DatabaseConfig appear to be a pre-multi-market-hub remnant for selecting which DB to use in prod vs dev. It may be superseded by the `[markets.*]` config but serves a different purpose (env-based alias). Leave as-is.
