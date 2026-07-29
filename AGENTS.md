# AGENTS.md

This file provides comprehensive guidance for LLM assistants (like Claude Code) when helping developers work with the Winter Coalition Market Stats Viewer codebase.

## Project Overview

Winter Coalition Market Stats Viewer is a Streamlit web application for EVE Online market analysis. It provides real-time market data visualization, doctrine analysis, and inventory management tools for the Winter Coalition.
The web app can be found here: https://wcmkts.streamlit.app/
It also has a sister application, Winter Coalition Northern Supply, which supports a different market hub managed in a separate repository. 

**Important:** ESI calls to update market data in wcmktprod.db are handled in a separate repository: https://github.com/OrthelT/mkts_backend

## Project Structure & Module Organization

### Application Entry Point
- **`app.py`**: Streamlit entry point with page routing to 10 pages across 2 sections ("Market Stats" and "Analysis Tools")

### UI Pages (`pages/` directory)
All pages follow consistent patterns with Streamlit best practices:

1. **`market_dashboard.py`** (🏠 Market Dashboard, default landing page) - Doctrine Ships, Popular Modules, Minerals, and Isotopes tables with checkbox-driven deep links into Doctrine Status / Market Stats. Constrained to low-stock doctrine items by default (toggle to view all). KPIs sourced from the marketorders order book (matches Market Stats sell-order value).
2. **`market_stats.py`** (📈 Market Stats) - Primary market data visualization with interactive Plotly charts, market orders, statistics, and historical data. 30-Day stats expander includes category pills (all/ships/doctrine ships/modules/materials, shuttles excluded from ships) and a daily ISK+volume activity chart.
3. **`doctrine_status.py`** (⚔️ Doctrine Status) - Doctrine fit status tracking with stock levels, costs, and market availability. Supports `module_id` query param for module-filtered deep links from the dashboard.
4. **`doctrine_report.py`** (📝 Doctrine Report) - Detailed doctrine analysis and reporting
5. **`low_stock.py`** (⚠️ Low Stock) - Low inventory alerting system with category filtering
6. **`build_costs.py`** (🏗️ Build Costs) - Manufacturing cost analysis sourced from the synced `buildcost.db` catalog with structure/rig configuration and industry indices
7. **`builder_helper.py`** (🛠️ Builder Helper) - Per-item manufacturing profitability table with ROI, ISK/hour, 30-day profit, and turnover, plus market-supply columns (current stock, days of cover, doctrine `target_qty`, and a suggested build `need`). Price-basis toggle (30-day avg / current) and stock filters (min-days / below-target / doctrine-only). Selected rows export to an EVE-Multibuy `st.code` block and CSV. Sourced from synced builder-cost catalog.
8. **`downloads.py`** (📥 Downloads) - Centralized CSV export for market data, doctrine fits, low stock items, and SDE tables. Uses Streamlit's callable pattern for lazy data loading.
9. **`pricer.py`** (💰 Pricer) - Item and fitting price calculator similar to [Janice](https://janice.e-351.com/). EFT input renders a Janice-style fit availability hero (focal fits-available count, bottleneck callout, faction-equivalent aggregation toggle); tab- or space-separated multibuy renders a per-item grid with local + Jita totals.
10. **`import_helper.py`** (Import Helper) - A visualisation tool to discover items with significantly larger price margin compared with Jita sell. Helps importers quickly spot price hikes to undercut.

### Core Modules

**Database Layer:**
- **`config.py`**: DatabaseConfig class managing SQLite/LibSQL connections with Turso cloud sync
  - Uses `_SYNC_LOCK` to serialize sync operations; SQLite handles reader concurrency
  - Manages 3 databases: wcmktprod (market), sdelite (static data), buildcost (manufacturing)
  - `sync()` returns bool -- callers handle UI feedback and targeted cache invalidation
  - Methods: `integrity_check()`, `sync()`, `local_matches_remote()`, `get_most_recent_update()`
- **`models.py`**: SQLAlchemy ORM models using modern `mapped_column()` syntax
  - MarketStats, MarketOrders, MarketHistory, Doctrines, ShipTargets, DoctrineFits, ModuleEquivalents, etc.
- **`sdemodels.py`**: SDE (Static Data Export) ORM models for InvTypes, InvGroups, InvCategories, Localization
- **`build_cost_models.py`**: Manufacturing models for Structures, IndustryIndex, Rigs

**Pricer Module (`parser/` directory):**
- **`parser.py`**: Input parsing for EFT fittings and tab-separated item lists (contributed open source code)
- **`model.py`**: Data models for the parser
- **`sample_eft-fit.txt`**: Example EFT fitting for testing
- **`items.txt`**: Sample tab-separated item list for testing

**Service Layer (`services/` directory):**
- **`services/doctrine_service.py`**: DoctrineService and FitDataBuilder for doctrine fit aggregation
- **`services/market_service.py`**: MarketService for 30-day metrics, ISK volume calculations, outlier handling, and Plotly chart creation
- **`services/build_cost_service.py`**: BuildCostService for stored build-cost catalog browsing and per-item snapshot summaries
- **`services/builder_helper_service.py`**: BuilderHelperService for the Builder Helper profitability table — joins synced `buildcost.db` catalog with watchlist metadata and market prices; supports 30-day-avg / current price-basis toggle and computes market-supply columns (current stock, days of cover, doctrine `target_qty` via `DoctrineRepository.get_target_quantities()`, and a `min_days`-aware build `need` from the pure `_compute_need()` helper)
- **`services/price_service.py`**: JitaPriceService with provider chain (DB cache → Fuzzwork → Janice) for Jita price lookups with caching. Sole batch entry point is `get_jita_prices(type_ids) -> BatchPriceResult`; use `.prices` (dict[TypeID, PriceResult]) or `.to_dict()` (dict[TypeID, Price]).
- **`services/pricer_service.py`**: PricerService orchestrates EFT/multibuy parsing, SDE resolution, Jita + local market lookups, fit availability computation (via `compute_fit_availability`), and doctrine cross-references for the Pricer page
- **`services/low_stock_service.py`**: LowStockService for low stock analysis with filtering (categories, doctrines, fits, tech2/faction items)
- **`services/import_helper_service.py`**: ImportHelperService for computing local-vs-Jita price comparisons including shipping cost, profit margin, 30-day turnover, and capital utilisation
- **`services/categorization.py`**: ConfigBasedCategorizer for ship role categorization via Strategy pattern
- **`services/selection_service.py`**: SelectionService for managing item selections on doctrine pages with sidebar rendering
- **`services/module_equivalents_service.py`**: ModuleEquivalentsService for looking up equivalent/interchangeable faction modules and calculating aggregated stock levels
- **`services/type_resolution_service.py`**: TypeResolutionService for type name/ID resolution with SDE + Fuzzworks/ESI API fallbacks
- **`services/type_name_localization.py`**: Applies localized item/ship names to DataFrames using SDE translations; skips work when language is English

**Domain Models (`domain/` directory):**
- **`domain/models.py`**: Core models: `FitItem`, `FitSummary`, `ModuleStock`, `Doctrine`
- **`domain/enums.py`**: `StockStatus`, `ShipRole` enums with display formatting
- **`domain/converters.py`**: Centralized `safe_int()`, `safe_float()`, `safe_str()` type conversion
- **`domain/pricer.py`**: Domain models including `PricedItem`, `PricerResult`, `FitAvailabilitySummary`, `ItemAvailability`, and `InputFormat` enum for EFT vs multibuy detection. `FitAvailabilitySummary` derives `bottleneck_items`, `counted_item_count`, `used_equivalents`, and `stock_unknown_count` as `@property` from `items`.
- **`domain/doctrine_names.py`**: Passthrough for doctrine name resolution; DB-backed lookup lives in `DoctrineRepository`
- **`domain/market_config.py`**: `MarketConfig` frozen dataclass representing a market hub's configuration (key, name, short_name, region_id, database_alias)

**UI Components (`ui/` directory):**
- **`ui/popovers.py`**: Reusable market data popover components with item images, market stats, Jita prices, and doctrine usage. Pass pre-fetched `jita_prices` dict to avoid per-popover API calls (Jita fetching is disabled by default)
- **`ui/formatters.py`**: Pure formatting functions for prices, percentages, image URLs
- **`ui/column_definitions.py`**: Streamlit column_config definitions for data tables; supports localized column headers via `get_doctrine_report_column_config(language_code)` and friends
- **`ui/i18n.py`**: Lightweight UI translation system with ~132 keys covering navigation, labels, tooltips, and column headers across 8 languages (EN, ZH, DE, FR, RU, ES, JP, KR). Used via `translate_text(language_code, key)`.
- **`ui/market_selector.py`**: Sidebar pill toggle for switching between market hubs; returns active `MarketConfig`

**Initialization & State:**
- **`init_db.py`**: Database initialization with path verification and auto-sync for missing files
- **`sync_state.py`**: Updates session state with local/remote database update times for sync tracking (uses `ss_set()`)
- **`settings_service.py`**: Module-level settings cache (stdlib only, no Streamlit dependency). Lives at root level, not in `services/`, to avoid circular imports
- **`logging_config.py`**: Centralized logging setup with rotating file handlers to `./logs/`
- **`state/language_state.py`**: Manages active UI language in session state and URL query parameter (`?lang=xx`) for bookmarkable language links
- **`state/market_state.py`**: Manages the active market hub selection in session state; clears market-specific services and caches on hub switch

### Local Databases

Three synced SQLite replicas: **`wcmktprod.db`** (market orders/stats),
**`sdelite.db`** (EVE Static Data Export, lightweight), **`buildcost.db`** (manufacturing).
Schemas are defined in `models.py`, `sdemodels.py`, and `build_cost_models.py`.

Non-obvious: `sdelite.db.localizations` holds ~210k localized item names for 8 languages
(de, en, es, fr, ja, ko, ru, zh), accessed via `SDERepository.get_localized_name()` /
`get_localized_names()` / `get_all_translations()`. It falls back to English for the ~20
items with no translation in the requested language.

## Database Architecture

### Turso Embedded Replica Pattern

The application uses Turso's embedded-replica feature for optimal performance:
- Local SQLite databases (`wcmktprod.db`, `sdelite.db`) provide fast reads
- Automatic synchronization with remote Turso database via libsql
- Sync serialized via `_SYNC_LOCK` (simple `threading.Lock`). SQLite handles its own reader concurrency
- Integrity checks with `PRAGMA integrity_check` after sync
- Malformed database auto-recovery with remote fallback via `BaseRepository.read_df()`
- `sync()` returns bool -- callers handle UI feedback (toasts) and targeted cache invalidation

**Note:** Market data updates come from the separate backend repository (mkts_backend) which handles ESI API calls and populates the Turso remote database. This frontend application only reads and syncs from Turso.

### Database Configuration

Databases are managed via the `DatabaseConfig` class in `config.py`. Each instance represents one named database (alias-based):
```python
from config import DatabaseConfig

mkt_db = DatabaseConfig("wcmktprod")   # wcmktprod.db — main market data
sde_db = DatabaseConfig("sde")         # sdelite.db — static data
bc_db  = DatabaseConfig("build_cost")  # buildcost.db — manufacturing

# Access engines
engine = mkt_db.engine        # SQLAlchemy engine (local file)
remote = mkt_db.remote_engine # SQLAlchemy engine (Turso remote)

# Sync from remote — returns bool; caller handles UI feedback
ok = mkt_db.sync()

# Check integrity
mkt_db.integrity_check()

# CLI sync (from terminal)
# uv run python config.py wcmktprod
```

## Development Guidelines

### Data Integrity Rule
**Never return incorrect data. Return no data rather than defaulting to the wrong data. We NEVER lie to the user.**

If a context lookup fails (e.g. active market key, hub selection, language), return empty results (`pd.DataFrame()`, `None`, `[]`) and log at ERROR — do not silently fall back to a default that serves data from a different context. Users make real decisions based on this data. Empty results are obviously wrong and prompt investigation; wrong data looks correct and causes harm silently.

The only acceptable default is when the context module is genuinely unavailable (`ImportError` in test/CLI environments), not as a catch-all for unexpected runtime errors.

### Global Configuration Rule
**For global configuration parameters, always use the `settings.toml` → `settings_service` path unless there is a strong reason to configure it separately.** Do not introduce a parallel config mechanism (a hard-coded constant, a second mapping, an env-only switch) when the value belongs alongside the rest of app config. Parallel mechanisms drift: the config the app reasons about and the config that actually drives behavior diverge, and the gap is invisible until something silently breaks.

Concretely, a config value should have a single source of truth that every consumer reads. For market hubs this means `DatabaseConfig` resolves Turso credentials from the same `MarketConfig.turso_secret_key` the rest of the app reads (see `config._resolve_turso_section`), rather than a separate `{alias}_turso` convention that can disagree with the market config. Add a `SettingsService` accessor for new global params; don't scatter `settings_dict[...]` reads or second copies of a default.

### Coding Style
- Max line length 100 (wider than ruff's default 88)
- **Logging**: Use `logging` module with `logging_config.py`; avoid `print()` in production code

### Database Operations

**Best Practices:**
- Access data through repository and service layers, not direct `DatabaseConfig`
- Implement proper error handling and logging
- Use targeted cache invalidation after sync (e.g., `invalidate_market_caches()`), not global `st.cache_data.clear()`

#### Read Convention: raw SQL via `text()`, executed through `read_df()`

This app is **read-only analytics**: its job is `SELECT … GROUP BY` feeding pandas
DataFrames. We deliberately do **not** use the SQLAlchemy ORM for reads — the
ORM's value (identity map, unit-of-work, lazy relationships, change tracking) is
about object writes and graphs, none of which apply when the output is a
DataFrame. The ORM models in `models.py` / `sdemodels.py` / `build_cost_models.py`
exist for **schema definition/seeding** (`demo_data.py`), the **one write path**
(`admin_repo.py`'s `sqlite_insert(Watchlist)`), and as living schema docs — not
for queries. Don't grow ORM into reads.

The convention for every read is:

1. Express the query as raw SQL with `sqlalchemy.text(...)`.
2. Use **named** params, and `bindparam("ids", expanding=True)` for `IN` clauses
   (never string-interpolate values into SQL).
3. Execute it through **`BaseRepository.read_df()`** — the single chokepoint that
   provides malformed-DB recovery → sync-and-retry → remote fallback. A bare
   `db.engine.connect()` + `pd.read_sql_query` gets **none** of that resilience,
   so a corrupt local `.db` makes those queries throw "no such table" instead of
   self-healing.

```python
from sqlalchemy import text, bindparam
from config import DatabaseConfig
from repositories.base import BaseRepository

# CORRECT — raw SQL through read_df() (recovery + remote fallback included)
repo = BaseRepository(DatabaseConfig("wcmktprod"))
query = text(
    "SELECT type_id, min_price FROM marketstats WHERE type_id IN :ids"
).bindparams(bindparam("ids", expanding=True))
df = repo.read_df(query, params={"ids": [34, 35]})

# Or, preferred at call sites, a cached repository method
from repositories import get_market_repository
df = get_market_repository().get_all_stats()  # cached DataFrame
```

```python
# AVOID — bypasses read_df(), so no malformed-DB recovery / remote fallback
with DatabaseConfig("wcmktprod").engine.connect() as conn:
    df = pd.read_sql_query(query, conn, params={"ids": [34, 35]})
```

> **Known drift (future refactor):** many existing read sites still use the
> bare-`engine.connect()` form. See `docs/read_df_consolidation.md` for the full
> inventory and migration plan. New reads should follow the convention above.

### Performance Considerations

- **Caching**: Use `@st.cache_data` for volatile data with TTL tiers (600s/1800s/3600s). Use `@st.cache_resource` for immutable data (SDE lookups, no TTL)
- **Database connections**: Use `@st.cache_resource` for database engines
- **Cache invalidation**: Use targeted invalidation (e.g., `invalidate_market_caches()`) after sync, not global clears
- **Connection pooling**: DatabaseConfig manages connection pooling automatically
- **Malformed DB recovery**: Built into `BaseRepository.read_df()` and repository `_impl()` functions
- **Lazy download generation**: Use `st.download_button(data=callable)` pattern for on-demand data generation. Pass a function reference (not the result) to defer data loading until user clicks download. See `pages/downloads.py` for examples.
- **Batch API fetching for popovers**: Streamlit popover content executes on every page rerun even when closed. Avoid API calls inside popovers by batch-fetching data before render loops. See `prefetch_popover_data()` in `pages/doctrine_status.py` for the pattern.

### Data Synchronization

- **Manual sync**: Available via sidebar button in Streamlit UI
- **Automatic sync**: Scheduled for 13:00 UTC daily (managed by sync scheduler)
- **Programmatic sync**: Use `DatabaseConfig.sync()` method
- **Integrity validation**: Automatic PRAGMA integrity_check before/after sync
- **Remote fallback**: Auto-fallback to remote queries if local DB is malformed
- **Cold-start safety**: `init_db.py` validates database *content* (not just file existence) via `verify_db_content()`. Empty or corrupt files are removed and re-synced. `sync()` validates credentials before `libsql.connect()` and cleans up artifacts (`.db`, `-shm`, `-wal`, `-info`) on failure.

**Important:** This application does NOT write market data. Market data updates are handled by the separate backend repository (mkts_backend) which calls ESI APIs and updates the Turso remote database.

**Critical:** Databases must only be created through `DatabaseConfig.sync()`. `libsql.connect()` creates the local `.db` file as a side effect before syncing — if sync fails, the empty file will pass naive existence checks and cause "no such table" errors. Never use `os.path.exists()` alone to determine if a database is initialized; always check for actual table content.

## Testing Guidelines

### Framework
- **Test framework**: pytest with pytest-cov for coverage
- **Test location**: `tests/` directory with files named `test_*.py`
- **Running tests**: `uv run pytest -q` or `uv run pytest --cov`

### What to Test
- Repository `_impl()` functions: mock the SQLAlchemy engine with `MagicMock()`
- Services: mock the repository, use `patch()` for HTTP calls
- Data shape/columns validation
- Query correctness and error handling
- Sync operations and integrity checks

## Commit & Pull Request Guidelines

### Commit Messages
Follow Conventional Commits format:
- `feat:` - New features
- `fix:` - Bug fixes
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks
- `test:` - Test additions/changes

Keep commits focused and use imperative mood (e.g., "add feature" not "added feature")

### Pull Requests
Include in PR description:
- Clear summary of changes
- Linked issues (if applicable)
- Steps to validate/test
- Screenshots/GIFs for UI changes
- Notes on any database schema or configuration impacts
- Performance implications (if any)

## Architecture Summary

**Data Flow:**
1. Backend repo (mkts_backend) fetches market data from ESI API
2. Backend updates Turso remote database
3. Frontend (this repo) syncs from Turso to local SQLite files
4. Streamlit pages query local databases via services and repositories
5. `_SYNC_LOCK` serializes sync operations; SQLite handles reader concurrency

**Key Principles:**
- Frontend is read-only for market data
- Local SQLite replicas provide fast reads
- Turso sync provides data freshness
- Targeted cache invalidation after sync (market caches only)
- Automatic recovery from database corruption
- Separation of concerns: backend handles ESI, frontend handles UI/analysis

### Layered Architecture & Module Dependencies

The codebase follows a strict layered architecture. Dependencies must flow **downward only** - upper layers may import from lower layers, but never the reverse.

```
┌─────────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                         │
│  pages/              → Streamlit pages (UI entry points)    │
│  app.py              → Application entry point              │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  STATE LAYER (Presentation)                                 │
│  state/              → Session state management             │
│    session_state.py  → ss_get, ss_has, ss_init utilities    │
│    service_registry.py → get_service singleton management   │
│    language_state.py → active language + URL query param    │
│    market_state.py   → active market hub + cache cleanup    │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  UI LAYER                                                   │
│  ui/                 → Formatting, column configs, display  │
│    formatters.py     → Pure formatting functions            │
│    column_definitions.py → st.column_config definitions     │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  SERVICE LAYER                                              │
│  services/           → Business logic orchestration         │
│    doctrine_service.py   → FitDataBuilder, DoctrineService  │
│    market_service.py     → MarketService, chart creation    │
│    build_cost_service.py → BuildCostService, stored costs   │
│    price_service.py      → Price fetching with fallbacks    │
│    categorization.py     → Ship role categorization         │
│    + pricer, low_stock, selection, equivalents, type_resolution │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  REPOSITORY LAYER                                           │
│  repositories/       → Database access abstraction          │
│    base.py           → BaseRepository with read_df()        │
│    doctrine_repo.py  → DoctrineRepository                   │
│    market_repo.py    → MarketRepository                     │
│    market_orders_repo.py → MarketOrdersRepository           │
│    build_cost_repo.py → BuildCostRepository                 │
│    sde_repo.py       → SDERepository                        │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  DOMAIN LAYER                                               │
│  domain/             → Core business models (no deps)       │
│    models.py         → FitItem, FitSummary, ModuleStock     │
│    enums.py          → StockStatus, ShipRole                │
│    converters.py     → Type conversion utilities            │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE LAYER                                       │
│  config.py           → DatabaseConfig, _SYNC_LOCK           │
│  models.py           → SQLAlchemy ORM models                │
│  settings_service.py → Centralized settings (stdlib only)   │
└─────────────────────────────────────────────────────────────┘
```

**Dependency Rules (CRITICAL):**

| Layer | May Import From | Must NOT Import From |
|-------|-----------------|----------------------|
| `pages/` | `state/`, `ui/`, `services/`, `domain/`, `repositories/` | - |
| `state/` | `streamlit`, `typing`, `domain/` (type hints only) | `services/`, `repositories/`, `ui/`, `pages/`, `config` |
| `ui/` | `domain/` only | `services/`, `pages/`, `app.py`, `state/` |
| `services/` | `repositories/`, `domain/`, `config` (NO streamlit†) | `ui/`, `pages/` |
| `repositories/` | `domain/`, `config`, `models` (NO streamlit†) | `services/`, `ui/`, `pages/` |
| `domain/` | Python stdlib only | Everything else |

†Services and repositories use try/except imports from `state/` only in factory functions to maintain testability outside Streamlit.

‡**`ui/sync_display.py` and `ui/market_selector.py` exceptions:** These modules import from `state/` and `config` because they are shared presentation components that cannot live in `pages/` (Streamlit auto-discovers `pages/` subdirectories as navigation entries). The layer violation is accepted to avoid Streamlit side effects.

§**`state/sync_state.py` exception:** This module imports `DatabaseConfig` from `config` to query database update timestamps and populate session state. The bidirectional dependency (`state/ → config` here, `config → state/` via deferred import in `DatabaseConfig`) is safe because both sides use deferred or function-scoped imports that prevent circular import at runtime.

**Common Circular Import Causes:**
1. **UI importing from services** - UI layer should only use domain enums/models
2. **Importing from `app.py`** - Entry point should never be imported
3. **State importing from services/repositories** - Since services and repositories import from `state/` in their factory functions, the `state/` module must NOT import from them (would cause circular dependency)

**Example - Correct Pattern:**
```python
# ui/formatters.py - CORRECT
from domain.enums import ShipRole, StockStatus  # ✓ domain only

def get_ship_role_format(role: str) -> str:
    ship_role = ShipRole.from_string(role)
    return f"{ship_role.display_emoji} **{ship_role.display_name}**"
```

**Example - Anti-Pattern (causes circular imports):**
```python
# ui/formatters.py - WRONG
from services.categorization import get_ship_role_object  # ✗ services!
from app import logger  # ✗ entry point!
from state.session_state import ss_get  # ✗ state!
```

## External Resources

- **Backend repository**: https://github.com/OrthelT/mkts_backend (ESI API integration, market data updates)
- **Live app**: https://wcmkts.streamlit.app/

## Related Skills

Task-specific guidance lives in `.claude/skills/` and loads on demand:
`wcmkts-setup` (secrets + local dev), `wcmkts-new-page` (adding a Streamlit page),
`wcmkts-troubleshooting` (sync, connection, and data-quality problems).
