# Multi-Market Support Plan

## Context

The Winter Coalition market viewer currently runs as two virtually identical Streamlit apps -- one for the 4-HWWF Keepstar (primary staging) and one for B-9C24 Keepstar (deployment staging in Pure Blind). Each has its own database but identical schemas. This project combines them into a single codebase with a user-selectable market context. The user picks a market from a sidebar dropdown; all pages, titles, column headers, and data queries update accordingly.

**Key data architecture insight:** Doctrine configuration lives in both market databases (synced from Turso) with a `market_flag` column on `doctrine_fits` (`primary`, `deployment`, or `both`). A common set of doctrines can be staged in either market or both. Market data (orders, stats, history) is unique per database. SDE and build_cost databases are shared across all markets.

---

## Phase 1: MarketConfig Domain Model

**Create** `domain/market_config.py`

```python
@dataclass(frozen=True)
class MarketConfig:
    key: str              # "primary" or "deployment"
    name: str             # "4-HWWF Keepstar"
    short_name: str       # "4H"
    region_id: int
    system_id: int
    structure_id: int
    database_alias: str   # "wcmktprod" - passed to DatabaseConfig
    database_file: str    # "wcmktprod.db"
    turso_secret_key: str # "wcmktprod_turso" - section name in secrets.toml

DEFAULT_MARKET_KEY = "primary"
```

Pure Python, no Streamlit dependency. The `key` field matches the `market_flag` values in `doctrine_fits`.

**Modify** `domain/__init__.py` -- export `MarketConfig`, `DEFAULT_MARKET_KEY`.

---

## Phase 2: Settings & Secrets Configuration

### 2a. settings.toml

Add `[markets]` section and `wcmktnorth` to `[db_paths]`. Keep existing `[market]` section temporarily for backward compatibility.

```toml
[markets.primary]
    name = "4-HWWF Keepstar"
    short_name = "4H"
    region_id = 10000003
    system_id = 30000240
    structure_id = 1035466617946
    database_alias = "wcmktprod"
    database_file = "wcmktprod.db"
    turso_secret_key = "wcmktprod_turso"

[markets.deployment]
    name = "B-9C24 Keepstar"
    short_name = "B9"
    region_id = 10000023
    system_id = 30002029
    structure_id = 1046831245129
    database_alias = "wcmktnorth"
    database_file = "wcmktnorth2.db"
    turso_secret_key = "wcmktnorth_turso"

[db_paths]
    "wcmktprod" = "wcmktprod.db"
    "wcmktnorth" = "wcmktnorth2.db"   # NEW
    "sde" = "sdelite.db"
    "build_cost" = "buildcost.db"
    "wcmkttest" = "wcmkttest.db"
```

### 2b. .streamlit/secrets.toml

Add new Turso credentials section (keep existing `[section]` pattern):

```toml
[wcmktnorth_turso]
url = "libsql://..."
token = "..."
```

### 2c. settings_service.py

Add `get_market_configs()` method that reads `[markets]` from settings.toml and returns `dict[str, MarketConfig]`. Also add a module-level `get_all_market_configs()` convenience function.

---

## Phase 3: DatabaseConfig -- Register New Market Database

**Modify** `config.py`

Make `_db_paths`, `_db_turso_urls`, and `_db_turso_auth_tokens` dynamically built from `settings["db_paths"]` instead of hardcoding four aliases. The pattern:

```python
_db_paths = {alias: path for alias, path in settings["db_paths"].items()}

_db_turso_urls = {}
_db_turso_auth_tokens = {}
for _alias in _db_paths:
    _turso_key = f"{_alias}_turso"
    try:
        _db_turso_urls[_turso_key] = st.secrets[_turso_key].url
        _db_turso_auth_tokens[_turso_key] = st.secrets[_turso_key].token
    except (KeyError, AttributeError):
        pass  # Not all aliases need Turso (graceful degradation)
```

This automatically registers `wcmktnorth` once it appears in `[db_paths]`. The `"wcmkt"` alias resolution in `__init__` stays unchanged (maps to the env-default database).

---

## Phase 4: Active Market State Management

**Create** `state/market_state.py`

Core API:
- `get_active_market() -> MarketConfig` -- returns config for currently selected market
- `get_active_market_key() -> str` -- returns `"primary"` or `"deployment"`
- `set_active_market(key: str)` -- switches market, clears market-specific services and caches

The `set_active_market()` function handles all cleanup:
1. Calls `clear_services()` for all market-specific service/repository keys
2. Calls `invalidate_market_caches()` and clears doctrine caches
3. Clears sync state keys (`local_update_status`, `remote_update_status`)

**Modify** `state/__init__.py` -- export the three functions.

---

## Phase 5: Repository & Service Parameterization

### 5a. Cached Repository Functions

All `@st.cache_data` functions in `doctrine_repo.py` and `market_repo.py` that hardcode `DatabaseConfig("wcmkt")` need two changes:
1. Accept `db_alias: str` as a parameter (becomes a cache key discriminator)
2. Use `DatabaseConfig(db_alias)` instead of `DatabaseConfig("wcmkt")`

Example transformation:
```python
# BEFORE
@st.cache_data(ttl=600)
def get_all_fits_with_cache() -> pd.DataFrame:
    db = DatabaseConfig("wcmkt")
    ...

# AFTER
@st.cache_data(ttl=600)
def get_all_fits_with_cache(db_alias: str) -> pd.DataFrame:
    db = DatabaseConfig(db_alias)
    ...
```

The `DoctrineRepository` methods pass `self._db.alias` to the cached function:
```python
def get_all_fits(self) -> pd.DataFrame:
    return get_all_fits_with_cache(self._db.alias)
```

**Files to modify:**
- `repositories/market_repo.py` -- ~9 cached functions + factory function (lines 35, 66, 97, 121, 136, 166, 175, 186, 202, 410)
- `repositories/doctrine_repo.py` -- ~6 cached functions + factory function (lines 599, 614, 637, 660, 678, 700, 720)
- `repositories/market_orders_repo.py` -- factory function

### 5b. Repository Factory Functions

Change all market-related factories to use active market:
```python
def get_market_repository() -> MarketRepository:
    def _create() -> MarketRepository:
        from state.market_state import get_active_market
        db = DatabaseConfig(get_active_market().database_alias)
        return MarketRepository(db)
    try:
        from state import get_service
        from state.market_state import get_active_market_key
        return get_service(f"market_repository_{get_active_market_key()}", _create)
    except ImportError:
        return _create()
```

Service registry keys are now market-prefixed (e.g., `"market_repository_primary"`) so different market instances don't collide.

Apply same pattern to:
- `get_doctrine_repository()` in `doctrine_repo.py`
- `get_market_orders_repository()` in `market_orders_repo.py`

**SDE and build_cost repos: NO CHANGES** -- they are market-independent.

### 5c. Service Factory Functions

All service factories in `services/__init__.py` that create market-specific services need the same treatment:
- `get_market_service()` -- market-keyed
- `get_doctrine_service()` -- market-keyed
- `get_pricer_service()` -- market-keyed
- `get_low_stock_service()` -- market-keyed
- `get_price_service()` -- market-keyed
- `get_module_equivalents_service()` -- market-keyed
- `get_selection_service()` -- market-keyed

The `create_default()` classmethods on services should accept an optional `db_alias` parameter with a fallback for tests:
```python
@classmethod
def create_default(cls, db_alias: str = None) -> "DoctrineService":
    if db_alias is None:
        try:
            from state.market_state import get_active_market
            db_alias = get_active_market().database_alias
        except (ImportError, Exception):
            db_alias = "wcmkt"
    ...
```

---

## Phase 6: Doctrine Market Flag Filtering

The `doctrine_fits` table has `market_flag` = `'primary'`, `'deployment'`, or `'both'`. When the active market is e.g. `"deployment"`, only fits with `market_flag IN ('deployment', 'both')` should display.

### 6a. Doctrine Compositions Query

**Modify** `doctrine_repo.py` `get_all_doctrine_compositions()`:
```python
def get_all_doctrine_compositions(self) -> pd.DataFrame:
    query = "SELECT * FROM doctrine_fits"
    try:
        with self._db.engine.connect() as conn:
            df = pd.read_sql_query(query, conn)
            # Filter by active market's key
            try:
                from state.market_state import get_active_market_key
                market_key = get_active_market_key()
            except (ImportError, Exception):
                market_key = "primary"
            return df[df['market_flag'].isin([market_key, 'both'])]
    except Exception as e:
        ...
```

### 6b. Fit Name Lookups

`get_fit_name_with_cache()` queries `doctrine_fits` -- add `market_flag` filter to the fallback query:
```sql
SELECT fit_name FROM doctrine_fits
WHERE fit_id = :fit_id AND market_flag IN (:market_key, 'both') LIMIT 1
```

### 6c. Downstream Filtering

`get_doctrine_fit_ids()` already filters `get_all_doctrine_compositions()` by doctrine_name, so the market_flag filter propagates automatically. `get_all_fits_with_cache()` reads from the `doctrines` table which has all fits -- downstream service logic (`DoctrineService.build_fit_data()`) uses doctrine_fits to determine which fits are relevant, so the filtering flows through.

---

## Phase 7: UI Market Selector

**Create** `ui/market_selector.py`

A sidebar dropdown component that returns the active `MarketConfig`:
```python
def render_market_selector() -> MarketConfig:
    configs = get_all_market_configs()
    # ... st.sidebar.selectbox with market names
    # On change: set_active_market(new_key) + st.rerun()
    return get_active_market()
```

**Modify** every page's `main()` function to call `render_market_selector()` at the top. The returned `market` object provides `.name` and `.short_name` for dynamic titles/labels.

Pages to modify:
- `pages/market_stats.py`
- `pages/doctrine_status.py`
- `pages/doctrine_report.py`
- `pages/low_stock.py`
- `pages/build_costs.py`
- `pages/pricer.py`
- `pages/downloads.py`

---

## Phase 8: Dynamic Market Labels (Replace "4-HWWF" Hardcodes)

### 8a. Page Titles (6 files)

| File | Current | Replacement |
|------|---------|-------------|
| `pages/market_stats.py:306` | `f"...{market_name} Market"` | `f"...{market.name} Market"` |
| `pages/doctrine_status.py:150` | `"4-HWWF Doctrine Status"` | `f"{market.name} Doctrine Status"` |
| `pages/doctrine_report.py:301` | `"4-HWWF Market Status..."` | `f"{market.name} Market Status..."` |
| `pages/low_stock.py:139` | `"4-HWWF Low Stock Tool"` | `f"{market.name} Low Stock Tool"` |
| `pages/pricer.py:222` | `"...Jita and 4-HWWF..."` | `f"...Jita and {market.name}..."` |
| `pages/build_costs.py:674` | `"4-HWWF price:"` | `f"{market.short_name} price:"` |

### 8b. Pricer Domain Model (domain/pricer.py)

Replace hardcoded "4-HWWF" dict keys with generic "Local" keys:
```python
# In PricedItem.to_dict():
"Local Sell": self.local_sell,
"Local Buy": self.local_buy,
"Local Sell Total": self.local_sell_total,
# etc.
```

Then in `pages/pricer.py`, rename columns after DataFrame creation:
```python
rename_map = {col: col.replace("Local", market.short_name) for col in df.columns if "Local" in col}
df = df.rename(columns=rename_map)
```

And update `st.column_config` definitions to use `f"{market.short_name} Sell"` etc.

Similarly update `PricerResult.get_totals_dict()` keys.

### 8c. UI Components

- `ui/popovers.py:241` -- `st.markdown(f"**{market.name} Market**")` (pass market name as parameter)
- `pages/components/market_components.py:404-415` -- dynamic metric labels
- `pages/downloads.py` -- already reads `short_name` from settings; switch to `market.short_name`

### 8d. Docstrings

Update docstrings in `domain/pricer.py`, `services/pricer_service.py`, `repositories/market_orders_repo.py` etc. to say "local market" instead of "4-HWWF". Non-functional but keeps documentation accurate.

---

## Phase 9: Init & Sync Changes

### 9a. init_db.py

Initialize ALL market databases, not just the env-default:
```python
from settings_service import get_all_market_configs
for key, cfg in get_all_market_configs().items():
    mkt_db = DatabaseConfig(cfg.database_alias)
    # verify/sync same as current logic
    init_module_equivalents(mkt_db) if needed
```

### 9b. sync_state.py

Parameterize `update_wcmkt_state()` to accept a database alias from the active market:
```python
def update_wcmkt_state(db_alias: str = None):
    if db_alias is None:
        from state.market_state import get_active_market
        db_alias = get_active_market().database_alias
    db = DatabaseConfig(db_alias)
    ...
```

### 9c. Sync UI (sidebar sync button in market_stats.py)

Update to sync the active market's database, not hardcoded "wcmkt".

---

## Implementation Order

```
Phase 1  MarketConfig domain model          (0 breaking changes, pure addition)
Phase 2  Settings/secrets restructure       (backward-compatible, old [market] kept)
Phase 3  DatabaseConfig dynamic aliases     (backward-compatible, adds wcmktnorth)
Phase 4  Active market state management     (no consumers yet, pure addition)
Phase 5  Repository/service parameterize    (core functional change)
Phase 6  Doctrine market_flag filtering     (extends Phase 5)
Phase 7  UI market selector                 (user-facing, depends on Phase 4)
Phase 8  Dynamic market labels              (cosmetic, depends on Phase 7)
Phase 9  Init/sync multi-market support     (depends on Phases 3-4)
```

Phases 1-4 can land without visible changes (default market = primary). Phase 5 is the critical functional change. Phases 7-8 are the visible user-facing change.

---

## Files to Create (3)
- `domain/market_config.py`
- `state/market_state.py`
- `ui/market_selector.py`

## Files to Modify (Critical)
- `settings.toml` -- add `[markets]` section and `wcmktnorth` db_path
- `.streamlit/secrets.toml` -- add `[wcmktnorth_turso]`
- `config.py` -- dynamic Turso credential loading
- `settings_service.py` -- `get_market_configs()` method
- `repositories/market_repo.py` -- parameterize all cached functions + factory
- `repositories/doctrine_repo.py` -- parameterize cached functions + factory + market_flag filter
- `repositories/market_orders_repo.py` -- parameterize factory
- `services/__init__.py` -- market-keyed factory functions
- `services/doctrine_service.py` -- `create_default()` accepts alias
- `domain/pricer.py` -- generic "Local" column keys
- `pages/pricer.py` -- dynamic column rename + column_config
- `pages/market_stats.py` -- market selector + dynamic title
- `pages/doctrine_status.py` -- market selector + dynamic title
- `pages/doctrine_report.py` -- market selector + dynamic title
- `pages/low_stock.py` -- market selector + dynamic title
- `pages/build_costs.py` -- dynamic market label
- `pages/downloads.py` -- market selector + dynamic filenames
- `ui/popovers.py` -- dynamic market name parameter
- `pages/components/market_components.py` -- dynamic metric labels
- `init_db.py` -- multi-market initialization
- `sync_state.py` -- parameterized sync state
- `domain/__init__.py` -- export MarketConfig
- `state/__init__.py` -- export market state functions

## Verification Plan

1. **Unit tests**: `uv run pytest -q` -- all ~128 existing tests should pass (fallback `db_alias="wcmkt"` in tests)
2. **Manual: default market**: `uv run streamlit run app.py` -- app loads with "4-HWWF Keepstar" selected, all pages work identically to current behavior
3. **Manual: switch market**: Select "B-9C24 Keepstar" from sidebar dropdown:
   - All page titles update to show "B-9C24 Keepstar"
   - Market data (orders, stats, charts) shows B-9C24 data
   - Doctrine pages show only fits with `market_flag IN ('deployment', 'both')`
   - Pricer columns show "B9 Sell", "B9 Buy" etc.
   - Downloads use "B9" prefix in filenames
4. **Manual: switch back**: Return to "4-HWWF Keepstar", verify data switches back correctly
5. **Sync test**: Trigger sync from sidebar -- confirms active market's database syncs
