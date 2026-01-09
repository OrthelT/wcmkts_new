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
uv run ruff check .

# Auto-format code with Ruff
uv run ruff format .
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
- **`app.py`**: Streamlit entry point with page routing to 5 main pages across 2 sections ("Market Stats" and "Analysis Tools")

### UI Pages (`pages/` directory)
All pages follow consistent patterns with Streamlit best practices:

1. **`market_stats.py`** (📈 Market Stats) - Primary market data visualization with interactive Plotly charts, market orders, statistics, and historical data
2. **`doctrine_status.py`** (⚔️ Doctrine Status) - Doctrine fit status tracking with stock levels, costs, and market availability
3. **`doctrine_report.py`** (📝 Doctrine Report) - Detailed doctrine analysis and reporting
4. **`low_stock.py`** (⚠️ Low Stock) - Low inventory alerting system with category filtering
5. **`build_costs.py`** (🏗️ Build Costs) - Manufacturing cost analysis with structure/rig configuration and industry indices

### Core Modules

**Database Layer:**
- **`config.py`**: DatabaseConfig class managing SQLite/LibSQL connections with Turso cloud sync
  - Implements custom RWLock for concurrent read/write access (multiple readers, exclusive writer)
  - Manages 3 databases: wcmktprod (market), sde_lite (static data), buildcost (manufacturing)
  - Methods: `integrity_check()`, `sync()`, `validate_sync()`, `get_most_recent_update()`
  - Automatic malformed database detection and recovery
- **`db_handler.py`**: Database query layer with `read_df()` and `new_read_df()` functions
  - Cached data fetchers: `get_all_mkt_stats()`, `get_all_mkt_orders()`, `get_all_market_history()`
  - Built-in malformed DB recovery with automatic sync + remote fallback
- **`models.py`**: SQLAlchemy ORM models using modern `mapped_column()` syntax
  - MarketStats, MarketOrders, MarketHistory, Doctrines, ShipTargets, DoctrineFits, etc.
- **`sdemodels.py`**: SDE (Static Data Export) ORM models for InvTypes, InvGroups, InvCategories
- **`build_cost_models.py`**: Manufacturing models for Structures, IndustryIndex, Rigs

**Business Logic:**
- **`doctrines.py`**: Doctrine fitting management with target handling, fit data aggregation, cost calculations
- **`utils.py`**: Utility functions including:
  - Industry index fetching from ESI API
  - Jita price lookups with Fuzzworks API fallback
- **`market_metrics.py`**: Market analysis metrics and UI rendering for ISK volume charts, historical metrics
- **`type_info.py`**: Type name/ID resolution with SDE database queries and Fuzzworks API fallback

**Initialization & State:**
- **`init_db.py`**: Database initialization with path verification and auto-sync for missing files
- **`sync_state.py`**: Updates session state with local/remote database update times for sync tracking
- **`set_targets.py`**: Ship target management from database with default fallback
- **`logging_config.py`**: Centralized logging setup with rotating file handlers

### Local Databases

**Primary Databases:**
- **`wcmktprod.db`**: Market orders and statistics (synced from Turso via backend repo)
- **`sdelite2.db`**: EVE Online Static Data Export (lightweight version)
- **`buildcost.db`**: Manufacturing and structure data

**Database Tables:**

*wcmktprod.db tables:*
- `marketorders`: Individual buy/sell orders
- `marketstats`: Aggregated market statistics
- `market_history`: Historical price/volume data
- `region_orders`: Regional market orders
- `region_history`: Regional historical data
- `doctrines`: Fleet doctrine configurations
- `doctrine_fits`: Doctrine fitting details
- `doctrine_info`: Additional doctrine metadata
- `ship_targets`: Target inventory levels
- `lead_ships`: Leadership ship configurations
- `watchlist`: Market watchlist items
- `nakah_watchlist`: Nakah-specific watchlist
- `updatelog`: Database update tracking

*sdelite2.db tables:*
- `invTypes`: EVE Online item definitions
- `invGroups`: Item group classifications
- `invCategories`: High-level item categories

*buildcost.db tables:*
- `structures`: Manufacturing structure data
- `industry_index`: Industry cost indices
- `rigs`: Structure rig configurations

### Configuration Files

- **`config.toml`**: Streamlit theme and UI configuration
- **`settings.toml`**: Application settings including ship role definitions and special cases
- **`.streamlit/secrets.toml`**: Turso credentials (local only, git-ignored)
- **`pyproject.toml`**: Project metadata, dependencies, dev tools config
- **`sync_log_dict.json`**: Detailed sync operation logs

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
- Local SQLite databases (`wcmktprod.db`, `sdelite2.db`) provide fast reads
- Automatic synchronization with remote Turso database via libsql
- Background sync managed by DatabaseConfig with RWLock concurrency control
- Integrity checks with `PRAGMA integrity_check` before and after sync
- Malformed database auto-recovery with remote fallback

**Note:** Market data updates come from the separate backend repository (mkts_backend) which handles ESI API calls and populates the Turso remote database. This frontend application only reads and syncs from Turso.

### Concurrency Model (RWLock)

DatabaseConfig implements a custom RWLock (read-write lock) pattern:
- **Multiple concurrent readers**: Read operations don't block each other
- **Exclusive writer access**: Write/sync operations block all reads and writes
- **Sync operations**: Full exclusive access during database synchronization
- **Thread-safe**: Proper lock acquisition/release with context managers

### Database Configuration

Databases are managed via `DatabaseConfig` class in `config.py`:
```python
from config import DatabaseConfig

db = DatabaseConfig()
# Access engines
mkt_engine = db.mkt_engine  # wcmktprod.db
sde_engine = db.sde_engine  # sdelite2.db
bc_engine = db.bc_engine    # buildcost.db

# Sync from remote
db.sync()

# Check integrity
db.integrity_check()
```

## Environment Setup

### Required Secrets (Streamlit Cloud & Local Development)

Create `.streamlit/secrets.toml`:
```toml
[secrets]
TURSO_DATABASE_URL = "libsql://your-database.turso.io"
TURSO_AUTH_TOKEN = "your_turso_auth_token"
SDE_URL = "libsql://your-sde.turso.io"
SDE_AUTH_TOKEN = "your_sde_auth_token"
```

### Local Development Notes
- Ensure local database files exist: `wcmktprod.db`, `sdelite2.db`, `buildcost.db`
- The application will use local SQLite files if sync credentials are not available
- Database files are git-ignored (*.db, *.db-shm, *.db-wal)
- Logs are stored in `logs/` directory (git-ignored)

## Development Guidelines

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
3. Import required database engines from `config.py` via DatabaseConfig
4. Use centralized logging from `logging_config.py`
5. Follow existing page patterns for consistency

Example:
```python
import streamlit as st
from config import DatabaseConfig
from logging_config import get_logger

logger = get_logger(__name__)
db = DatabaseConfig()

def main():
    st.title("New Page")
    # Your page logic here

if __name__ == "__main__":
    main()
```

### Database Operations

**Best Practices:**
- Always use SQLAlchemy engines from `DatabaseConfig` (via `config.py`)
- Use context managers for database sessions
- Implement proper error handling and logging
- Clear Streamlit cache after database modifications
- Use read locks for queries, write locks for modifications

**Example:**
```python
from sqlalchemy import select
from sqlalchemy.orm import Session
from models import MarketStats

# Reading data
with Session(db.mkt_engine) as session:
    stmt = select(MarketStats).where(MarketStats.type_id == 34)
    results = session.execute(stmt).scalars().all()

# Or use db_handler cached functions
from db_handler import get_all_mkt_stats
df = get_all_mkt_stats()  # Returns cached pandas DataFrame
```

### Performance Considerations

- **Caching**: Use `@st.cache_data` for expensive computations (default TTL: 15 minutes)
- **Database connections**: Use `@st.cache_resource` for database engines
- **Cache clearing**: Clear caches during database sync operations
- **Connection pooling**: DatabaseConfig manages connection pooling automatically
- **Concurrent reads**: Multiple read operations can occur simultaneously thanks to RWLock
- **Malformed DB recovery**: Built into `db_handler.py` read functions

### Data Synchronization

- **Manual sync**: Available via sidebar button in Streamlit UI
- **Automatic sync**: Scheduled for 13:00 UTC daily (managed by sync scheduler)
- **Programmatic sync**: Use `DatabaseConfig.sync()` method
- **Integrity validation**: Automatic PRAGMA integrity_check before/after sync
- **Remote fallback**: Auto-fallback to remote queries if local DB is malformed

**Important:** This application does NOT write market data. Market data updates are handled by the separate backend repository (mkts_backend) which calls ESI APIs and updates the Turso remote database.

## Testing Guidelines

### Framework
- **Test framework**: pytest with pytest-cov for coverage
- **Test location**: `tests/` directory with files named `test_*.py`
- **Running tests**: `uv run pytest -q` or `uv run pytest --cov`

### What to Test
- Data shape/columns validation
- Query correctness and error handling
- Page-level helper functions (mock DB where possible)
- Database concurrency (RWLock behavior)
- Sync operations and integrity checks

### Current Test Coverage
The test suite includes:
- `test_rwlock.py`: RWLock implementation tests (12 tests)
- `test_database_config_concurrency.py`: DatabaseConfig concurrency tests
- Additional tests for database operations, logging, and data fetching
- Current status: 37 tests passing

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
- **Malformed database**: db_handler functions auto-detect and fallback to remote queries
- **Connection errors**: Review logs in `logs/` directory

### Performance Issues
- **Slow queries**: Clear Streamlit cache with `st.cache_data.clear()`
- **Outdated data**: Check database sync status and last update time
- **Memory usage**: Monitor during large data operations, consider pagination
- **Concurrent access**: RWLock handles this automatically, but check logs for contention

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
┌─────────────────────────────────────────────────────────────┐
│                     Streamlit Frontend                      │
│                        (app.py)                             │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │ Market   │ Doctrine │ Doctrine │ Low      │ Build    │  │
│  │ Stats    │ Status   │ Report   │ Stock    │ Costs    │  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              DatabaseConfig (config.py)                     │
   │              RWLock Concurrency Control                     │
   │  ┌──────────┬──────────┬──────────┐                        │
   │  │ wcmktprod│ sdelite2 │buildcost │                        │
   │  │ .db      │ .db      │.db       │                        │
   │  └────┬─────┴──────────┴──────────┘                        │
   │       │ Sync (libsql)                                       │
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
4. Streamlit pages query local databases for fast reads
5. RWLock ensures safe concurrent access during sync operations

**Key Principles:**
- Frontend is read-only for market data
- Local SQLite replicas provide fast reads
- Turso sync provides data freshness
- RWLock enables high concurrency
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
│  UI LAYER                                                   │
│  ui/                 → Formatting, column configs, display  │
│    formatters.py     → Pure formatting functions            │
│    column_definitions.py → st.column_config definitions     │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  FACADE LAYER                                               │
│  facades/            → Simplified API for pages             │
│    doctrine_facade.py → Unified doctrine operations         │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  SERVICE LAYER                                              │
│  services/           → Business logic orchestration         │
│    doctrine_service.py → FitDataBuilder, DoctrineService    │
│    price_service.py    → Price fetching with fallbacks      │
│    categorization.py   → Ship role categorization           │
└─────────────────────────────────────────────────────────────┘
                              │ imports from ↓
┌─────────────────────────────────────────────────────────────┐
│  REPOSITORY LAYER                                           │
│  repositories/       → Database access abstraction          │
│    doctrine_repo.py  → DoctrineRepository (17 methods)      │
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
│  config.py           → DatabaseConfig, RWLock               │
│  models.py           → SQLAlchemy ORM models                │
│  db_handler.py       → Low-level DB queries                 │
└─────────────────────────────────────────────────────────────┘
```

**Dependency Rules (CRITICAL):**

| Layer | May Import From | Must NOT Import From |
|-------|-----------------|----------------------|
| `pages/` | `ui/`, `facades/`, `services/`, `domain/`, `repositories/` | - |
| `ui/` | `domain/` only | `services/`, `facades/`, `pages/`, `app.py` |
| `facades/` | `services/`, `repositories/`, `domain/` | `ui/`, `pages/` |
| `services/` | `repositories/`, `domain/` | `ui/`, `facades/`, `pages/` |
| `repositories/` | `domain/`, `config`, `models` | `services/`, `facades/`, `ui/`, `pages/` |
| `domain/` | Python stdlib only | Everything else |

**Common Circular Import Causes:**
1. **UI importing from services** - UI layer should only use domain enums/models
2. **Importing from `app.py`** - Entry point should never be imported
3. **Services importing from facades** - Facades wrap services, not vice versa

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
```

## Version Information

- **Current version**: 0.1.5
- **Python version**: 3.12+
- **Package manager**: uv (preferred)
- **Main branch**: main
- **Active development**: documentation branch (as of last update)

## Additional Resources & Documentation Index

### Documentation (`docs/` directory)

**User Documentation:**
- `docs.md` - End-user guide for the application
- `docs_cn.md` - Chinese translation of user guide

**Technical Reference:**
- `REFACTOR_PLAN.md` - Comprehensive architecture documentation and refactoring history
- `database_config.md` - Database configuration and Turso sync details
- `concurrency_refactor.md` - RWLock implementation and concurrency patterns
- `testing.md` - Testing guidelines and pytest patterns

**Guides:**
- `admin_guide.md` - Administrative guide for managing the application
- `quick_reference.md` - Quick reference for common tasks
- `walkthrough.md` - Step-by-step walkthroughs
- `worktree_setup.md` - Git worktree setup for parallel development

### Project Directories
- **`domain/`**: Core business models (FitItem, FitSummary, StockStatus, ShipRole)
- **`repositories/`**: Database access layer (DoctrineRepository)
- **`services/`**: Business logic (DoctrineService, PriceService, categorization)
- **`facades/`**: Simplified API layer (DoctrineFacade)
- **`ui/`**: UI formatting utilities and column configurations
- **`pages/`**: Streamlit application pages
- **`tests/`**: pytest unit tests
- **`docs/`**: Documentation
- **`logs/`**: Application logs (git-ignored)
- **`images/`**: UI assets
- **`depreciated-code/`**: Legacy code archive

### External Resources
- **Backend repository**: https://github.com/OrthelT/mkts_backend (ESI API integration, market data updates)
