# AGENTS.md

This file provides comprehensive guidance for LLM assistants (like Claude Code) when helping developers work with the Winter Coalition Market Stats Viewer codebase.

## Project Overview

Winter Coalition Market Stats Viewer is a Streamlit web application for EVE Online market analysis. It provides real-time market data visualization, doctrine analysis, and inventory management tools for the Winter Coalition.
The web app can be found here: https://wcmkts.streamlit.app/
It also has a sister application, Winter Coalition Northern Supply, which supports a different market hub managed in a separate repository. 

**Important:** ESI calls to update market data in wcmktprod.db are handled in a separate repository: https://github.com/OrthelT/mkts_backend

## Quick Start Commands

### Installation and Setup
```bash
# Install dependencies using uv (preferred package manager for Python 3.12)
uv sync

# Alternative: install via pip if uv is not available
pip install -e .
```

### Running the Application
```bash
# Start the Streamlit application
uv run streamlit run app.py

# Development mode with file watching
uv run streamlit run app.py --server.runOnSave true
```

### Database Operations
```bash
# Test database sync functionality
uv run python -c "
from config import DatabaseConfig
db = DatabaseConfig()
db.sync()
"

# Check database integrity
uv run python -c "
from config import DatabaseConfig
db = DatabaseConfig()
print('Integrity check:', db.integrity_check())
"
```

### Linting and Formatting
```bash
# Check code style with Ruff
uvx ruff check .

# Auto-format code with Ruff
uvx ruff format .
```

### Testing
```bash
# Run all tests with pytest
uv run pytest -q

# Run with coverage
uv run pytest --cov
```

## Project Structure & Module Organization

### Application Entry Point
- **`app.py`**: Streamlit entry point with page routing to 7 main pages across 2 sections ("Market Stats" and "Analysis Tools")

### UI Pages (`pages/` directory)
All pages follow consistent patterns with Streamlit best practices:

1. **`market_stats.py`** (📈 Market Stats) - Primary market data visualization with interactive Plotly charts, market orders, statistics, and historical data
2. **`doctrine_status.py`** (⚔️ Doctrine Status) - Doctrine fit status tracking with stock levels, costs, and market availability
3. **`doctrine_report.py`** (📝 Doctrine Report) - Detailed doctrine analysis and reporting
4. **`low_stock.py`** (⚠️ Low Stock) - Low inventory alerting system with category filtering
5. **`build_costs.py`** (🏗️ Build Costs) - Manufacturing cost analysis with structure/rig configuration and industry indices
6. **`downloads.py`** (📥 Downloads) - Centralized CSV export for market data, doctrine fits, low stock items, and SDE tables. Uses Streamlit's callable pattern for lazy data loading.
7. **`pricer.py`** (💰 Pricer) - Item and fitting price calculator similar to [Janice](https://janice.e-351.com/). Accepts EFT fittings or tab-separated item lists and displays both Jita and 4-HWWF market prices.
8. **`import_helper.py`** (Import Helper) - A visualisation tool helps discovering items with significantly large price margin compared with Jita sell. This feature helps importers to quickly spot price hikes to under cut.

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
- **`services/build_cost_service.py`**: BuildCostService for async cost fetching (httpx), URL construction, and BuildCostJob dataclass
- **`services/price_service.py`**: PriceService with provider chain (Fuzzwork → Janice) for Jita price lookups with caching
- **`services/pricer_service.py`**: PricerService orchestrates parsing and price lookups from Jita (via Janice API or Fuzzworks) and 4-HWWF (local market database)
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
- **`domain/pricer.py`**: Domain models including `PricedItem`, `PricingResult`, and `InputFormat` enum for EFT vs multibuy detection
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

**Primary Databases:**
- **`wcmktprod.db`**: Market orders and statistics (synced from Turso via backend repo)
- **`sdelite.db`**: EVE Online Static Data Export (lightweight version)
- **`buildcost.db`**: Manufacturing and structure data

**Database Tables:**

*wcmktprod.db tables:*
- `marketorders`: Individual buy/sell orders
- `marketstats`: Aggregated market statistics
- `market_history`: Historical price/volume data
- `doctrines`: Fleet doctrine configurations
- `doctrine_fits`: Doctrine fitting details
- `ship_targets`: Target inventory levels
- `lead_ships`: Leadership ship configurations
- `watchlist`: Market watchlist items
- `updatelog`: Database update tracking
- `module_equivalents`: Interchangeable faction module mappings for aggregated stock calculations

*sdelite.db tables:*
- `invTypes`: EVE Online item definitions
- `invGroups`: Item group classifications
- `invCategories`: High-level item categories
- `localizations`: Localized item names for 8 languages (de, en, es, fr, ja, ko, ru, zh). ~210k rows. Accessed via `SDERepository.get_localized_name()`, `get_localized_names()`, `get_all_translations()`. Falls back to English for items without a translation in the requested language (~20 en-only items).

*buildcost.db tables:*
- `structures`: Manufacturing structure data
- `industry_index`: Industry cost indices
- `rigs`: Structure rig configurations

### Configuration Files

- **`config.toml`**: Streamlit theme and UI configuration
- **`settings.toml`**: Application settings including ship role definitions, special cases, `[db_paths]` alias-to-file mappings, `[db_turso_keys]` alias-to-secret overrides, and `[env] local_only` toggle for running without Turso
- **`.streamlit/secrets.toml`**: Turso credentials (local only, git-ignored; not needed when `local_only = true`)
- **`pyproject.toml`**: Project metadata, dependencies, dev tools config

### Other Directories

- **`docs/`**: Admin guides, database documentation, walkthroughs
- **`tests/`**: pytest unit tests for database operations, logging, market data
- **`depreciated-code/`**: Legacy code archive
- **`logs/`**: Application logs (git-ignored)
- **`images/`**: UI assets and images
- **`dev_files/`**: Development-specific files
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

## Environment Setup

### Required Secrets (Streamlit Cloud & Local Development)

Create `.streamlit/secrets.toml` (section-per-database format):
```toml
[wcmktprod_turso]
url = "libsql://your-database.turso.io"
token = "your_turso_auth_token"

[wcmktnorth_turso]
url = "libsql://your-north-database.turso.io"
token = "your_turso_auth_token"

[sdelite_turso]
url = "libsql://your-sde.turso.io"
token = "your_sde_auth_token"

[buildcost_turso]
url = "libsql://your-buildcost.turso.io"
token = "your_buildcost_auth_token"

[janice]
api_key = "your_janice_api_key"  # For Pricer page Jita price lookups
```

### Local Development Notes
- Ensure local database files exist: `wcmktprod.db`, `sdelite.db`, `buildcost.db`
- The application will use local SQLite files if sync credentials are not available
- Database files are git-ignored (*.db, *.db-shm, *.db-wal)
- Logs are stored in `logs/` directory (git-ignored)

### Local-Only Mode (for contributors without Turso access)
Contributors can run the app without Turso cloud credentials:
1. Download database files from: https://drive.google.com/drive/folders/1Hwx28Imyvc10jXcdKtLftZNi994AKKsq
2. Place `.db` files (`wcmktprod.db`, `wcmktnorth2.db`, `sdelite.db`, `buildcost.db`) in the project root
3. Set `local_only = true` in `settings.toml` under `[env]`
4. No `.streamlit/secrets.toml` is needed — all sync operations are skipped
5. The sidebar shows "Local-only mode — sync disabled" instead of update timestamps

## Development Guidelines

### Data Integrity Rule
**Never return incorrect data. Return no data rather than defaulting to the wrong data. We NEVER lie to the user.**

If a context lookup fails (e.g. active market key, hub selection, language), return empty results (`pd.DataFrame()`, `None`, `[]`) and log at ERROR — do not silently fall back to a default that serves data from a different context. Users make real decisions based on this data. Empty results are obviously wrong and prompt investigation; wrong data looks correct and causes harm silently.

The only acceptable default is when the context module is genuinely unavailable (`ImportError` in test/CLI environments), not as a catch-all for unexpected runtime errors.

### Coding Style & Naming Conventions
- **Python style**: PEP 8, 4-space indents, max line length 100
- **Naming conventions**:
  - Modules/functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Type hints**: Use type annotations on function signatures
- **Docstrings**: Include concise docstrings on public functions
- **Logging**: Use `logging` module with `logging_config.py`; avoid `print()` in production code

### Adding New Pages

1. Create new page file in `pages/` directory with emoji prefix (e.g., `📊_new_page.py`)
2. Add page registration in `app.py` pages dictionary
3. Use services and repositories via factory functions -- do not access `DatabaseConfig` directly
4. Use centralized logging from `logging_config.py`
5. Follow existing page patterns for consistency

Example:
```python
import streamlit as st
from services import get_market_service
from logging_config import setup_logging

logger = setup_logging("new_page")

def main():
    st.title("New Page")
    service = get_market_service()
    df = service.get_market_data(type_id)

if __name__ == "__main__":
    main()
```

### Database Operations

**Best Practices:**
- Access data through repository and service layers, not direct `DatabaseConfig`
- Use context managers for database sessions
- Implement proper error handling and logging
- Use targeted cache invalidation after sync (e.g., `invalidate_market_caches()`), not global `st.cache_data.clear()`

**Example:**
```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from config import DatabaseConfig
from models import MarketStats

# Reading data via DatabaseConfig
mkt_db = DatabaseConfig("wcmktprod")
with Session(mkt_db.engine) as session:
    stmt = select(MarketStats).where(MarketStats.type_id == 34)
    results = session.execute(stmt).scalars().all()

# Or use repository cached methods (preferred)
from repositories import get_market_repository
repo = get_market_repository()
df = repo.get_all_stats()  # Returns cached pandas DataFrame
```

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

### Current Test Coverage
The test suite covers repositories, services, database config, i18n, and infrastructure:
- ~191 tests passing (`uv run pytest -q`)

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

## Troubleshooting

### Database Connection Issues
- **Local files missing**: Run `init_db.py` to initialize databases
- **Sync failures**: Check Turso credentials in `.streamlit/secrets.toml`
- **Integrity errors**: DatabaseConfig will auto-recover with `integrity_check()` and sync
- **Malformed database**: Repository functions auto-detect and fallback to remote queries
- **Connection errors**: Review logs in `logs/` directory
- **Empty db file on cold start**: `libsql.connect()` creates the `.db` file before syncing. If credentials are missing or sync fails, the empty file persists and causes "no such table" errors on subsequent runs. `init_db.py` detects this via `verify_db_content()` and removes empty files before re-syncing. If `.db-info` exists alongside an empty `.db`, it indicates a prior interrupted sync.
- **Credential naming mismatch**: Database aliases in `[db_paths]` (e.g., `sde`, `build_cost`) may not match Turso secret section names (e.g., `sdelite_turso`, `buildcost_turso`). Use `[db_turso_keys]` in `settings.toml` to map aliases to their correct secret section names. When adding a new database, ensure its turso key is either `{alias}_turso` or has an override in `[db_turso_keys]`.

### Performance Issues
- **Slow queries**: Use targeted cache invalidation (e.g., `invalidate_market_caches()`)
- **Outdated data**: Check database sync status and last update time
- **Memory usage**: Monitor during large data operations, consider pagination

### Data Quality Issues
- **Missing data**: Check if backend repository (mkts_backend) is running and updating remote DB
- **Incorrect prices**: Verify Jita prices are current, check Fuzzworks API fallback
- **Missing types**: Check SDE database is current and complete

## Security & Configuration Tips

- **Secrets management**: Store Turso URLs/tokens in `.streamlit/secrets.toml`; NEVER hard-code
- **Environment variables**: `.env` supported via `python-dotenv`
- **Git hygiene**: Database files (`*.db*`) and logs (`*.log`) are git-ignored
- **API keys**: ESI API is public, but rate-limit aware code is in backend repo
- **Authentication**: Turso auth tokens required for remote sync

## Architecture Summary

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                              Streamlit Frontend (app.py)                               │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┬───────────┬───────────────┐ │
│  │ Market   │ Doctrine │ Doctrine │ Low      │ Build    │ Downloads │ Pricer        │ │
│  │ Stats    │ Status   │ Report   │ Stock    │ Costs    │           │               │ │
│  └────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬─────┴─────┬─────┴───────┬───────┘ │
│       └──────────┴──────────┴──────────┴──────────┴───────────┴─────────────┘         │
│                                        │                                               │
│                              services/ + repositories/                                 │
└───────────────────────────────────────┬───────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────┐
│              DatabaseConfig (config.py)                      │
│  ┌──────────┬──────────┬──────────┐                         │
│  │ wcmktprod│ sdelite  │buildcost │                         │
│  │ .db      │ .db      │.db       │                         │
│  └────┬─────┴──────────┴──────────┘                         │
│       │ Sync (libsql, _SYNC_LOCK)                           │
└───────┼─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│           Turso Cloud Database (Remote)                     │
│                                                             │
│  Updated by: mkts_backend repo (ESI API calls)             │
│  https://github.com/OrthelT/mkts_backend                   │
└─────────────────────────────────────────────────────────────┘
```

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
│    build_cost_service.py → BuildCostService, async fetching │
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

## Version Information

- **Current version**: 0.4.1
- **Python version**: 3.12+
- **Package manager**: uv (preferred)
- **Main branch**: main

## Additional Resources & Documentation Index

### Documentation (`docs/` directory)

**User Documentation:**
- `docs.md` - End-user guide for the application
- `docs_cn.md` - Chinese translation of user guide

**Technical Reference:**
- `architecture_reference.md` - Definitive technical reference for the current architecture
- `change_log.md` - Change log covering v0.2.0 refactoring (Phases 1-13) through v0.4.0 releases
- `database_config.md` - Database configuration and Turso sync details
- `module_equivalents.md` - Module equivalents feature architecture, CLI usage, and aggregation pipeline
- `testing.md` - Testing guidelines and pytest patterns

**Guides:**
- `admin_guide.md` - Administrative guide for managing the application
- `quick_reference.md` - Quick reference for common tasks
- `walkthrough.md` - Step-by-step walkthroughs

### Project Directories
- **`domain/`**: Core business models (FitItem, FitSummary, StockStatus, ShipRole, PricedItem, MarketConfig, converters)
- **`repositories/`**: Database access layer (BaseRepository, DoctrineRepository, MarketRepository, BuildCostRepository, SDERepository)
- **`services/`**: Business logic (DoctrineService, MarketService, BuildCostService, PriceService, PricerService, ImportHelperService, LowStockService, SelectionService, ModuleEquivalentsService, TypeResolutionService, TypeNameLocalization, categorization)
- **`state/`**: Session state management (ss_get, ss_has, ss_set, ss_init, get_service, language_state, market_state)
- **`ui/`**: UI formatting utilities, column configurations, reusable popover components, i18n translations, market selector
- **`pages/`**: Streamlit application pages
- **`pages/components/`**: Extracted Streamlit rendering components (market_components)
- **`parser/`**: EFT fitting and item list parser (open source contribution)
- **`tests/`**: pytest unit tests (~191 tests)
- **`docs/`**: Documentation
- **`logs/`**: Application logs (git-ignored)
- **`images/`**: UI assets
- **`depreciated-code/`**: Legacy code archive

### External Resources
- **Backend repository**: https://github.com/OrthelT/mkts_backend (ESI API integration, market data updates)
