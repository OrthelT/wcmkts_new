
# WinterCo Markets Change Log 

## Version 0.7.5 
- pricer: use packaged volume for items that can be packaged)
- ui: render ships by clicking on image in market stats
- ui: add sde sync version and configuration setting to page footer 
- fix:restore filtering for supercarrier construction

## Version 0.7.4 
Various performance and ui enhancements, bump to Streamlit version 1.64
- Fewer loading pauses: when a table's cache expires and no new data has arrived, the app
  keeps showing the table and reloads it in the background.
- Faster controls: changing a fit checkbox on Doctrine Status, the ISK chart options on
  Market Stats, or the Pricer results reruns only that section, not the whole page.
- Dashboard shortcuts: each dashboard table row has buttons that open the item in
  Market Stats or Doctrine Status.
- Faster filters on Builder Helper and Low Stock.
- Doctrine Status export shows "—" for items with no stock data, not 0.
- After a data update, every open session sees the new data.

## Versions 0.7.1 and 0.7.2
Versions 0.7.1 and 0.7.2 include a number of performance optimizations that significantly reduce startup and page load times.
### Performance Improvements
Measured on the 4-HWWF Keepstar market database using the dashboard landing page:
| Scenario | Pre-PR80 | Main | Improvement |
|---|---:|---:|---:|
| Cold process, first render | 9.1 s | **2.29 s** | 4.0× faster |
| New session, warm process | 4.99 s | **0.18 s** | 27× faster |
| Rerun within a session | 0.77 s | **0.18 s** | 4.2× faster |
| Cold bootstrap, full database rebuild | 54.3 s | **27.7 s** | 2.0× faster |
| On-disk footprint after cold start | 759 MB | **246 MB** | 3.1× smaller |
### Optimizations
- Reduced unnecessary database staleness checks.
- Deprecated the local database backup subsystem.
- Added lazy loading of data when a market is selected.
- Limited the default market history load to 30 days. Users can still select longer time ranges when needed.

## version 0.7.0
Major refactor to migrate database library from libsql to pyturso. 
- database syncs are now executed with db.pull()
- local writes can use db.push() as well. 
- see [PR 79: pyturso migration: read-only sync-dialect replicas](https://github.com/OrthelT/wcmkts_new/pull/79) for details. 

## version 0.6.8
### New Features
- **30-day category pills on Market Stats**: New pills above the 30-day metrics -- All / Ships / Doctrine Ships / Modules / Materials. Ships exclude shuttles; Doctrine Ships are the distinct hulls from the active hub's doctrines; unknown or empty scopes fail closed with zeros and a warning rather than silently widening. Localized in all 8 languages.
- **30-day daily activity chart**: Daily ISK value (bars) plus units traded (line) below the 30-day metrics, re-scoping with whichever pill, item, or category filter is active. The historical stats section now defaults to expanded.

### Bug Fixes
- **Dashboard market value now matches Market Stats**: The dashboard's Total Market Value previously valued the watchlist-scoped order book at the best ask, missing ~550 non-watchlist types. Both pages now share one source of truth -- a SQL aggregation over actual sell orders (`get_order_book_summary`). Items Listed now counts actual listed sell-order types.
- **Popular Modules "Fits" column** now shows fits supported by current stock (zero stock displays 0) instead of counting fits that merely include the module.
- **30-day stats column headers** now match the daily average / total toggle selection.

### Other
- Renamed dashboard columns: Doctrine Ships stock is now **Ship Hulls**; **% Target** is now **% Fits Target** in both tables.
- Replaced deprecated Streamlit calls.

## version 0.6.7
### New Features and Fixes
- Add support for BKG market hub

## version 0.6.6
### New Features and Fixes
- Removed Group Filter from build costs and replaced with fuzzyfind type_name selection.

## version 0.6.5
### New Features and fixes
- Improves ui/ux when using market_dashboard navigation -> doctrine status or market stats
- Single row selection checkbox navigates to additional data destination based on toggle selection
- return button now navigates back to market_dashboard.
- fix: selected items now survive reruns so interaction with widget elements don't force rerun to default page view. This restores functionality for menu_button selection (fit details and low stock items) on doctrine stats page.

## version 0.6.4
### New Features
- **Builder Helper stock filters**: New sidebar filters let manufacturers narrow the table to what actually needs building -- `Min days of stock`, `Doctrine items only`, `Below doctrine target`, and `Low stock only`. `Min days` also sizes the suggested `need` column, so it is read before the data is built.
- **Multibuy / CSV export from Builder Helper**: Ticking rows in the table now produces an EVE-Multibuy / JEveAssets stockpile-compatible code block (`item_name<TAB>need`, paste-ready) plus a CSV download mirroring the Doctrine Status export.

### Other
- Added `repackagedVolume` to the SDE types ORM model.

## version 0.6.3
### Feature 
Adds support for three markets (primary, deployment, market3)

## version 0.6.2
### New Features
- **Fit Availability hero on Pricer**: Pasting an EFT fit now shows a focal `fits-available` count, three supporting metrics, a progress bar, and a red/orange bottleneck callout for the lowest-stock module -- a Janice-style layout that answers "how many of this fit can I buy right now?" without forcing the user to read the per-item table.
- **Faction-equivalent aggregation** on the pricer (toggle, default on): substitutes faction-equivalent modules into stock counts where an equivalence group exists.
- **Partial-data signals**: Pricer surfaces `failed_jita_count`, `unpriced_item_count`, and `stock_unknown_count` so headline ISK totals never silently understate cost when partial data is missing.

### Improvements
- **Space-separated multibuy parsing**: Lines without tabs now resolve correctly (e.g. `Torpedo Launcher II 63`).
- **Summary card totals**: Replaced Buy / Split / Sell row with explicit `{market} Sell Total`, `Jita Sell Total`, and `Jita Buy Total`.
- **Janice batch endpoint fix**: `JaniceProvider._parse_response` now accepts both the v2 `/pricer` top-level JSON list and the legacy appraisal envelope -- fixes a production `'list' object has no attribute 'get'` crash.

### Refactoring
- Collapsed three near-identical batch Jita-price methods on `PriceService` into one (`get_jita_prices -> BatchPriceResult`).
- Renamed `PriceService` -> `JitaPriceService` to eliminate the one-letter collision with `PricerService`.
- Removed duplicate `get_jita_price` wrappers from `services/price_service.py` and `ui/popovers.py`.
- Removed outdated docs (`code_simplification_review.md`, `docs.md`, `quick_reference.md`, `selectable-mkts.md`).

## version 0.6.1
- **Doctrine modules table** on the Market Dashboard now mirrors the Doctrine Ships pattern. Replaced row-selection routing with `_mkt` / `_doc` checkbox columns, fixing the iloc/positional mismatch that misrouted clicks when the low-stock filter hid rows.
- **`fit_count` aggregation** added; modules now show how many doctrine fits use them.
- **Module deep-link** (`module_id` query param) on Doctrine Status filters fits to those using a specific module, with a banner naming the module.
- New i18n keys (`column_fits`, `hint_click_doctrine_status_module`, `module_filter_banner`) across en/zh/de/fr/ru/es.
- Removed the 5-minute-to-update balloon animation (was disruptive at scale).

## version 0.6.0
### New Features
- **Builder Helper page** (`pages/builder_helper.py`, `services/builder_helper_service.py`): EverRef-free profitability tool for manufacturers. Shows ROI, ISK/hour, 30-day profit, and turnover for watchlist items, sourced from the synced builder-cost catalog.
- **Price-basis toggle** on Builder Helper (30-day average / current price) -- defaults to 30-day average since current-price spikes can mislead manufacturing decisions.
- **Dashboard low-stock filter**: Market Dashboard now constrains to low-stock doctrine items by default with a filter override toggle, focusing FCs on the items that actually need attention.

### Improvements
- **Build-cost catalog from `buildcost.db`**: Switched both Build Costs and Builder Helper from the dead `wcmktprod.db.builder_costs` table to the synced `buildcost.db` catalog.
- **Corrected ROI formula** on Builder Helper: `cap_utils` is now `(sell-cost)/cost` (ROI, can exceed 100%) instead of `(sell-cost)/sell` (gross margin, capped at 100%). Help strings updated in all 6 translated languages.
- **ISK/Hour column** added to Builder Helper (the description already promised it but the column was missing).
- **Doctrine Status ship display** revised; stacked toggle buttons replaced with a single `st.menu_button` chord that respects column `vertical_alignment`.
- **Centralized shared page chrome** (`pages/components/header.py`, `pages/components/layout.py`): logo, language selector, and page titles render through shared helpers.
- **TZ-bug fix in PriceService**: `time_until_next_db_update` now correctly handles tz-aware non-UTC inputs.

### Bug Fixes
- Doctrine Ships row resolution now uses pandas `index` (not `iloc`).
- `pd.read_sql_query` syntax updated for list parameters.
- Replaced deprecated `use_container_width` calls with Streamlit native formats.

## version 0.5.0 / 0.5.1
### New Features
- **Market Dashboard**: New default landing page (`pages/market_dashboard.py`) with at-a-glance Doctrine Ships, Popular Modules, Minerals, and Isotopes tables. Rows are clickable -- ships jump to Doctrine Status filtered by ship; modules/minerals/isotopes jump to Market Stats with the item pre-selected via query parameter.
- **Target % progress bars**: Doctrine Ships table now shows `% target` (fits_on_mkt / ship_target) as an inline progress bar; Popular Modules table shows `target %` and `qty needed` derived from doctrine requirements.
- **Module equivalents on Dashboard**: Dashboard fits-on-market calculations apply the module-equivalents aggregation and use bottleneck (lowest-availability module) instead of hull count, matching Doctrine Status semantics.
- **x47 market hub**: Added as a third selectable hub alongside 4-HWWF and B-9C24; deployment switched to 4-HWWF Sotiyo with the new keepstar.
- **Low-stock doctrine market export**: New CSV export on the Downloads page that joins low-stock items with their doctrine usage.
- **Time-to-update progress bar**: Sidebar replaces text countdown with a progress bar; balloons fire when less than 5 minutes remain before the next scheduled update.

### Improvements
- **Doctrine IDs as state**: Doctrine selectboxes now key on integer doctrine IDs (not display strings) for robust localization; `fit_name` added to all doctrine exports.
- **Active-market correctness**: Downloads page, doctrine downloads, and download section descriptions now respect the active market hub. Architecture rule added: never silently display data from the wrong market context -- fail with empty results instead.
- **Sync simplification**: Removed parallel sync validation paths; `local_matches_remote()` is now the single source of truth for sync freshness. `time_until_next_db_update` correctly handles tz-aware non-UTC inputs.
- **Cache hygiene**: Downloads page CSV caches and sidebar update times refresh after DB sync; the manual sync button was renamed for clarity.
- **Dashboard polish**: Full-width layout, mid-luminance colors that stay readable in dark mode, third neutral color for small positive deltas, surfaced missing `ship_targets` rows, and hardened error handling for uninitialized DB access.
- **Performance**: Smaller `wclogo` for faster page load; deferred remote sync check until `check_update` runs; eliminated duplicate localization calls on Market Stats.
- **Pricer/Market Stats**: Auxiliary pricing table added to the Market Stats view with adjusted column sizing; import helper now filters zero-volume rows.

## version 0.4.2
- performance improvements to Jita price fetching, UI updates to import helper to indicate derived estimated values and refinement of calculations. Various other improvements to code quality, testing, and performance. 

## version 0.4.0 / 0.4.1
### New Features
- **8-Language UI Translation**: Full UI translation in EN, ZH, DE, FR, RU, ES, JP, and KR via `ui/i18n.py`; ~132 translation keys covering navigation, labels, tooltips, and column headers
- **Language Selector**: Top-right selectbox with flag emoji labels; selection persists via URL query parameter (`?lang=xx`) for bookmarkable links
- **Localized Item Names**: `services/type_name_localization.py` uses the SDE `localizations` table (~210k rows) to display item and ship names in the selected language with automatic English fallback
- **Category ID Filtering**: Market Stats, Low Stock, and Doctrine Status now filter by `category_id` (int) instead of `category_name` for robustness across all languages
- **Configurable Shipping Cost (Import Helper)**: User-facing number input for shipping cost per m³ (default 450 ISK/m³)

### Improvements
- Type ID refactor in Doctrine Report: module selection state uses `set[int]` of type_ids instead of string names
- Localized data table column headers
- English-language optimization: SDE localization queries skipped when `language_code="en"`
- Test suite grown to ~191 tests with new i18n, language state, and type name localization coverage

## version 0.3.1
### New Features
- **Multi-Market Hub Support**: Selectable market hubs (4-HWWF and B-9C24) with per-market database configuration and UI toggle
- **Import Helper Page**: Compare local market prices against Jita sell/buy to spot import opportunities, including shipping cost, profit margin, and capital utilisation analysis (PR #32, contributed by MrDiao)
- **CLI Database Sync**: Sync databases from the command line with `uv run python config.py <alias>`
- **Module Equivalents Overhaul**: Renamed schema, added faction filter, explicit UI indicators, lowest-cost equiv in fit costing, equivalent popovers
- **Doctrine Display Names from DB**: Display names loaded from database instead of hardcoded dictionary

### Improvements
- Dynamic market alias resolution via `_resolve_active_alias()` — deprecated aliases (`wcmkt2`, `wcmkt3`) auto-resolve
- Stale replica metadata detection with automatic retry during sync
- Cold-start guard on all pages against unsynced market databases
- Alphabetized ship selections in doctrine pages
- Per-market cache keying to prevent incorrect module counts across market hubs
- 7-phase code simplification refactor

### Bug Fixes
- Fixed infinite loop from `st.rerun()` in build_costs.py (replaced with `st.stop()`)
- Fixed sync errors for deployment database and SDE/build_cost PRAGMA checks
- Fixed caching per market to avoid incorrect module counts
- Prevented empty db files from bypassing cold-start sync
- Resolved Turso credential mismatch for sde and build_cost aliases
- Synced VALID_SDE_TABLES allowlist with actual sdelite.db tables

## version 0.2.0
### New Features
- **Pricer Page**: Item and fitting price calculator accepting EFT fittings or tab-separated item lists, with Jita and 4-HWWF market prices
- **Downloads Page**: Centralized CSV export for market data, doctrine fits, low stock items, and SDE tables
- **Low Stock Filters**: Doctrine/Fit filtering with ship images, Faction Items checkbox, and Tech2 item filtering
- **Import Helper Page**: Compare local market prices against Jita sell and buy, shipping cost, 30-day volume, and capital utilisation to spot import opportunities
- **Doctrine Display Names**: User-friendly doctrine names across all pages
- **Market Column**: Doctrine ship modules now displayed with fits on market stats

### Layered Architecture Refactoring (Phases 1-13)
- Complete restructuring into layered architecture: domain, repositories, services, UI, state, pages
- New BaseRepository with automatic malformed-DB recovery and remote fallback
- Centralized settings service, session state management, and service registry
- ~128 tests covering repositories, services, and infrastructure

## version 0.1.6
### Interchangeable Faction Module Support
- Added support for equivalent faction modules (e.g., Dark Blood Thermal Armor Hardener and its 5 equivalents)
- Stock levels now aggregate across all interchangeable modules for accurate fit calculations
- Indicator shown next to modules with equivalents in Doctrine Status/Report pages
- Popovers display "Equivalent Modules" section with individual and combined stock
- `module_equivalents` database table owned and managed by the backend repository (mkts_backend)
- `ModuleEquivalentsService` for equivalence lookups and aggregated stock calculations

## version 0.1.5
### Low Stock Page Enhancements
- Added Doctrine/Fit filtering with ship images in sidebar
- Added Faction Items checkbox filter (metaGroupID=4)
- Refactored to use new `LowStockService` for cleaner data operations

### Pricer Page Enhancements
- Added Stock Metrics columns: Avg Daily Volume, Days of Stock
- Added Doctrine Items highlighting with toggle
- Ship image header for EFT fitting inputs

### Doctrine Status/Report Enhancements
- Interactive market data popovers for all items and ships
- Popovers show: item image, 4-HWWF price/stock, Jita price comparison, doctrine usage
- Improved sidebar selections with code block formatting

### New Services
- `LowStockService` - Low stock data operations with filtering
- `SelectionService` - Selection state management for doctrine pages
- `ModuleEquivalentsService` - Equivalence lookups for interchangeable faction modules
- `ui/popovers.py` - Reusable market data popover components

### Bug Fixes (Phase 5)
- Fixed `render_market_popover` TypeError when comparing PriceResult to int
- Fixed doctrine dropdown empty due to database connection scope error

### Ship Role Configuration
- Moved ship role definitions to `settings.toml` for easier management without code changes
- Added support for fit-specific role assignment (e.g. Vulture can be DPS or Links depending on fit)
### SDE Data Access
- Added CSV download capability for SDE data in Market Stats
### Database Updates
- Migrated production market database to `wcmktprod.db`
- Updated database configuration to use `wcmktprod` alias

## version 0.1.4 WCMKTS_North
### Fit Detail View
  - New expandable section showing all items in selected fits
  - Sortable columns with category and stock visibility
  - Helps identify bottleneck items quickly
### Improved Reporting
  - Better table formatting on Doctrine Report with compact number display
  - Role-based categorization (DPS, Logi, Links, Tackle)
  - Enhanced metrics display with proper width constraints
### Enhanced Fit Cost Analysis
  - Total fit cost calculation including all modules and components
  - Multi-level null price handling:
  - Display total cost alongside ship hull cost on Doctrine Status page
  - Optional Jita price delta available through Calculate Jita Price Delta Button
### Display Capital Utilization Ration
- Calculate and display capital utilization ratio in market stats display for a selected ship

## version 0.1.3
- low-stock items are now selectable for csv export

## version 0.1.2
- moves to new versioning scheme to match python standard
- feat: adds Jita price info for selected items
- refactored data displays to handle items when missing from the market
- bumped dependencies and moved to streamlit 1.50
- housekeeping to update syntax planned for deprication

## Previous updated
(*note these version numbers are outdated following shift to standard 0.0.0 versioning*)
*version 0.64* (2025-09-29)
- adds tech 2 filtering to Low Stock tool.
- adds category filtering for Price History charts
- adds 30-day history metrics with daily averages.
*version 0.63*
Adds interactive market ISK volume charting to Market Stats, including moving averages, date aggregation, and configurable outlier handling. Refactors DB read paths for resilience and consistency. Introduces a lightweight pytest suite with docs and coverage config.
- New charting UI: moving average (3/7/14/30), date aggregation, outlier handling (cap/remove/none), and data table
- DB handling: consistent local/remote read helpers with integrity checks + safe fallbacks
- Tests: 24 focused tests with pytest config, coverage setup, and a simple test runner
- Docs: testing guide and coverage config
*version 0.62*
- Adds csv downloads for market data (Market Stats tool)
- Various bug fixes to handle concurrency footguns and prevent null values from getting passed to data display constructors.
*version 0.61*
- Adds csv downloads for doctrine fits (Doctrine Status tool).
- Simplified db update scheduling with periodic checks for updated data. Adds check DB status button to display time since last update.
- Performance enhancements from streamlined data pipelines and better caching design
*version 0.6*
- Introduces the DatabaseConfig class in the config.py file, providing a unified interface for managing multiple database connections (local SQLite, remote Turso, and LibSQL sync operations). See the dedicated section below for more details.
- Market data is now updated more frequently, every two hours.
- Several performance improvements. Among the most significant is a complete  rework of the build cost engine. Calculating build costs for 50+ structures was by far the slowest thing in the app. The new async approach makes this dramatically faster by asyncrously calculating costs for several structures at once. In this update, the async build cost functionality moves out of experimental and is now the default option.
- The app also gets a new backend, which can be found in the seperate [mkts-backend repo][mkts-backend-link] on GitHub. This update moves handling of ESI calls and database updates into automated GitHub actions.
[mkts-backend-link]: https://github.com/OrthelT/mkts_backend
- Known issue: Hurricane Fleet Issue doctrine is not yet configured in Doctrine report. Support ships are the same as CFI, so you can use it as a proxy until I get around to updating it.

*version 0.52*
- introduced experimental async API calls for builds and several other refactors for performance improvement and maintainability. Helpers.py added with useful functions for development and debugging.
- added comparison structure option to build cost tool, automatic calculation of structure tax based on stored data.
- implemented rate limiting and proper user agent headers for API calls
- added support for supercapital construction based on sovreignty upgrades.
- enhanced build cost analysis with profit margin calculations

*version 0.51(beta)*
- added selectable target multiplier to "Doctrine Report" and "Doctrine Status" pages.

*version 0.5(beta)*
- implemented "Doctrine Report" page providing a view of market status by doctrine.
*version 0.42*
- added display of buy orders on market stats page.
*version 0.41*
- simplified sync scheduling with periodic syncs every three hours.

*version 0.4*
- Enhanced doctrine status page with:
  - Advanced filtering (ship status, ship group, module stock levels)
  - Item selection via checkboxes
  - Bulk selection/deselection options
  - CSV export functionality for shopping lists
  - Copy to clipboard feature
- Caching and other performance improvements

*version 0.3*
- added low stock analysis
- added additional filtering and export functionality to doctrine status tool

*version 0.2*
- added fitting information features
- added doctrine metrics
- improved history chart behavior

