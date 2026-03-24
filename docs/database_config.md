# DatabaseConfig Class Documentation

## Overview

The `DatabaseConfig` class is a comprehensive database management system designed to handle multiple database connections, synchronization, and operations within the Winter Coalition Market Stats application. It provides a unified interface for working with local SQLite databases, remote Turso databases, and LibSQL synchronization.

## Architecture

The class follows a lazy-loading pattern where database connections are only established when first accessed, improving performance and resource utilization. It supports both local and remote database operations with automatic synchronization capabilities.

All database aliases and file paths are defined in `settings.toml` under `[db_paths]`. The active market alias is resolved dynamically from `settings.toml` via `env_db_aliases[env.env]` — it is not hardcoded.

## Class Structure

```python
class DatabaseConfig:
    # Class variables (populated from settings.toml at import time)
    wcdbmap = settings["env_db_aliases"][settings["env"]["env"]]  # e.g. "wcmktprod"

    _db_paths = {...}              # From [db_paths] in settings.toml
    _db_turso_urls = {...}         # Remote Turso URLs (from .streamlit/secrets.toml)
    _db_turso_auth_tokens = {...}  # Authentication tokens

    def __init__(self, alias: str, dialect: str = "sqlite+libsql")

    # Properties (lazy-loaded, shared across instances per-alias)
    @property engine              # SQLAlchemy engine (local file)
    @property remote_engine       # SQLAlchemy engine (Turso remote)
    @property ro_engine           # Read-only SQLAlchemy engine (NullPool)
    @property libsql_local_connect
    @property libsql_sync_connect
    @property sqlite_local_connect
    @property has_remote_credentials -> bool

    # Methods
    def sync() -> bool
    def integrity_check() -> bool
    def local_matches_remote() -> bool
    def get_most_recent_update(table_name: str, remote: bool = False) -> datetime
    def get_time_since_update(table_name: str, remote: bool = False)
    def get_table_list(local_only: bool = True) -> list[str]
    def get_table_columns(table_name, local_only, full_info) -> list

    # Internal methods
    def _resolve_active_alias() -> str       # Resolves deprecated aliases
    def _dispose_local_connections()          # Cleanup before sync
    def _sync_once() -> bool                 # Single sync attempt
    def _local_matches_remote() -> bool      # Post-sync validation
    def _cleanup_empty_db_file()             # Remove artifacts after failed sync
    def _has_marketstats_table() -> bool
```

## Database Aliases

Aliases are defined in `settings.toml` under `[db_paths]`:

| Alias | Description | Local File | Purpose |
|-------|-------------|------------|---------|
| `wcmktprod` | Production market database | `wcmktprod.db` | Main market data and orders (4-HWWF) |
| `wcmktnorth` | Deployment market database | `wcmktnorth2.db` | Northern market data (B-9C24) |
| `sde` | Static Data Export | `sdelite.db` | EVE Online static data |
| `build_cost` | Build cost calculations | `buildcost.db` | Structure data and industry indexes |
| `wcmkttest` | Test database | `wcmkttest.db` | Testing |

### Multi-Market Support

The application supports multiple market hubs, configured in `settings.toml`:

```toml
[markets.primary]
    name = "4-HWWF Keepstar"
    short_name = "4H"
    database_alias = "wcmktprod"
    database_file = "wcmktprod.db"
    turso_secret_key = "wcmktprod_turso"

[markets.deployment]
    name = "B-9C24 Keepstar"
    short_name = "B9"
    database_alias = "wcmktnorth"
    database_file = "wcmktnorth2.db"
    turso_secret_key = "wcmktnorth_turso"
```

The active market alias is resolved at runtime via `_resolve_active_alias()`, which reads session state to determine the user's selected market hub.

### Deprecated Alias Handling

Legacy aliases `wcmkt`, `wcmkt2`, and `wcmkt3` are all accepted by the constructor but resolve dynamically via `_resolve_active_alias()` to the currently active market. A warning is logged for `wcmkt2` and `wcmkt3`.

## Initialization

### Constructor

```python
def __init__(self, alias: str, dialect: str = "sqlite+libsql")
```

**Parameters:**
- `alias` (str): Database alias identifier (from `[db_paths]` in settings.toml)
- `dialect` (str): SQLAlchemy dialect (default: "sqlite+libsql")

**Behavior:**
- Deprecated aliases (`wcmkt`, `wcmkt2`, `wcmkt3`) are resolved to the active market via `_resolve_active_alias()`
- Validates alias against `[db_paths]` in settings.toml
- Raises `ValueError` for invalid aliases
- Initializes connection properties (lazy-loaded)

**Example:**
```python
# Valid initializations
mkt_db = DatabaseConfig("wcmktprod")   # Production market database (4-HWWF)
north_db = DatabaseConfig("wcmktnorth") # Northern market database (B-9C24)
sde_db = DatabaseConfig("sde")         # Static data export
build_db = DatabaseConfig("build_cost") # Build cost database

# Deprecated alias — resolves to the active market
mkt_db = DatabaseConfig("wcmkt")       # Resolves via _resolve_active_alias()
```

## Properties

### Basic Properties

| Property | Type | Description |
|----------|------|-------------|
| `alias` | str | Database alias identifier |
| `path` | str | Local file path to the database |
| `url` | str | SQLAlchemy connection URL for local database |
| `turso_url` | str \| None | Remote Turso database URL |
| `token` | str \| None | Authentication token for Turso |
| `has_remote_credentials` | bool | True when Turso URL and token are both available |

### Connection Properties (Lazy-Loaded)

All connection properties are cached at the class level per-alias, so multiple `DatabaseConfig` instances for the same alias share the same underlying connection.

#### `engine`
SQLAlchemy engine for local database operations.

```python
engine = mkt_db.engine
```

#### `remote_engine`
SQLAlchemy engine for remote Turso database operations. Raises `ValueError` if Turso credentials are missing.

```python
remote_engine = mkt_db.remote_engine
```

#### `ro_engine`
Read-only SQLAlchemy engine with `NullPool` (no long-lived pooled handles). Uses SQLite URI mode with `?mode=ro`.

```python
ro_engine = mkt_db.ro_engine
```

#### `libsql_local_connect`
Direct LibSQL connection to local database.

#### `libsql_sync_connect`
LibSQL sync connection configured with sync URL and auth token.

#### `sqlite_local_connect`
Direct `sqlite3` connection for raw SQLite access.

## Methods

### `sync() -> bool`

Synchronizes the local database with the remote Turso database.

```python
ok = mkt_db.sync()
# Caller handles UI feedback and cache invalidation
if ok:
    invalidate_market_caches()
```

**Returns:** `True` if sync and integrity check succeeded, `False` otherwise. Callers are responsible for cache invalidation and UI feedback (e.g. `st.toast()`).

**Raises:** `ValueError` if Turso credentials are missing (fails fast before `libsql.connect()` can create an empty db file).

**Process:**
1. Acquires `_SYNC_LOCK` to serialize sync operations
2. Calls `_dispose_local_connections()` to close all handles
3. Calls `_sync_once()` to perform the sync
4. Calls `_local_matches_remote()` to verify data currency
5. If data mismatch (stale replica metadata), deletes local file and retries fresh
6. Runs `integrity_check()` post-sync

### `integrity_check() -> bool`

Runs `PRAGMA integrity_check` on the local database.

```python
ok = mkt_db.integrity_check()  # True if result is "ok"
```

### `local_matches_remote() -> bool`

Validates sync by comparing `updatelog` timestamps between local and remote databases. Uses a plain sqlite3 read-only connection for the local read to avoid SQLAlchemy caching issues.

### `get_most_recent_update(table_name: str, remote: bool = False) -> datetime`

Queries the `UpdateLog` table for the most recent update timestamp for a given table.

```python
last_update = mkt_db.get_most_recent_update("marketstats")
```

### `get_table_list(local_only: bool = True) -> list[str]`

Returns table names from the database (excluding SQLite system tables).

### `get_table_columns(table_name, local_only=True, full_info=False) -> list`

Returns column information for a specific table. With `full_info=True`, returns list of dicts with `cid`, `name`, `type`, `notnull`, `dflt_value`, `pk`.

## Internal Methods

### `_resolve_active_alias() -> str`
Static method that reads the active market from session state and returns its `database_alias`. Falls back to `wcdbmap` (from settings.toml) when session state is unavailable (tests, CLI).

### `_dispose_local_connections()`
Disposes/closes all local connections and engines for this alias. Called before sync to prevent file corruption from open handles.

### `_sync_once() -> bool`
Executes a single sync attempt. Creates a fresh `libsql.connect()` with sync credentials, calls `.sync()`, logs timing, and closes the connection. If sync fails and the db file didn't exist before, calls `_cleanup_empty_db_file()`.

### `_local_matches_remote() -> bool`
Compares `MAX(last_update)` from `marketstats` between local (via raw `sqlite3`) and remote (via Turso engine). Returns `True` unconditionally for databases without a `marketstats` table (e.g. sde, build_cost).

### `_cleanup_empty_db_file()`
Removes the `.db` file and associated `-shm`, `-wal`, `-info` artifacts left by a failed sync.

## Configuration

### Streamlit Secrets

The class requires Turso credentials in `.streamlit/secrets.toml`. Secret section names follow the `{alias}_turso` pattern by default, with overrides in `[db_turso_keys]` for non-standard names:

```toml
[wcmktprod_turso]
url = "libsql://your-database.turso.io"
token = "your-auth-token"

[wcmktnorth_turso]
url = "libsql://your-north-database.turso.io"
token = "your-auth-token"

[sdelite_turso]
url = "libsql://your-sde-database.turso.io"
token = "your-auth-token"

[buildcost_turso]
url = "libsql://your-buildcost-database.turso.io"
token = "your-auth-token"
```

Note: `sde` maps to `sdelite_turso` and `build_cost` maps to `buildcost_turso` via the `[db_turso_keys]` override in `settings.toml`:
```toml
[db_turso_keys]
    "sde" = "sdelite_turso"
    "build_cost" = "buildcost_turso"
```

## Error Handling

### Invalid Alias
```python
try:
    db = DatabaseConfig("invalid_alias")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Unknown database alias 'invalid_alias'.
    # Available: ['wcmktprod', 'wcmktnorth', 'sde', 'build_cost', 'wcmkttest']
```

### Missing Credentials
`sync()` raises `ValueError` immediately if Turso credentials are missing, before `libsql.connect()` can create an empty db file.

### Failed Sync Cleanup
If sync fails and the db file didn't exist before, `_cleanup_empty_db_file()` removes the empty file and WAL artifacts to prevent "no such table" errors on subsequent runs.

## Performance Considerations

### Lazy Loading
- Database connections are only created when first accessed
- Reduces startup time and memory usage
- Connections are cached at the class level per-alias

### Connection Sharing
- Multiple `DatabaseConfig` instances for the same alias share connections
- Prevents multiple connection overhead

### Sync Optimization
- Uses `_SYNC_LOCK` (threading.Lock) to serialize sync operations
- `_dispose_local_connections()` ensures no open handles during file operations
- Stale replica metadata detection with automatic retry
- Only validates `marketstats` timestamps for market databases

## Usage Patterns

### Basic Database Operations
```python
from config import DatabaseConfig

# Initialize database
mkt_db = DatabaseConfig("wcmktprod")

# Query local database
with mkt_db.engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM marketorders LIMIT 10"))
    data = result.fetchall()

# Query remote database
with mkt_db.remote_engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM marketorders"))
    count = result.scalar()

# Check if remote is available before using it
if mkt_db.has_remote_credentials:
    with mkt_db.remote_engine.connect() as conn:
        ...
```

### Synchronization
```python
# Sync database — returns bool, caller handles UI
ok = mkt_db.sync()
if ok:
    invalidate_market_caches()
    st.toast("Sync complete")
else:
    st.toast("Sync failed", icon="!")

# Separate validation
if mkt_db.local_matches_remote():
    print("Sync validated")
```

### Database Inspection
```python
# Get all tables
tables = mkt_db.get_table_list()
print(f"Available tables: {tables}")

# Get column information
columns = mkt_db.get_table_columns("marketorders")
print(f"Market orders columns: {columns}")

# Get detailed column info
detailed = mkt_db.get_table_columns("marketorders", full_info=True)
for col in detailed:
    print(f"Column: {col['name']}, Type: {col['type']}, PK: {col['pk']}")
```

### CLI Usage
```bash
# Sync a database from the command line
uv run python config.py wcmktprod
uv run python config.py sde
```

## Troubleshooting

### Common Issues

1. **Invalid Alias Error**
   - Check that the alias is defined in `[db_paths]` in `settings.toml`
   - Note: `wcmkt2` is deprecated — use `wcmktprod` or `wcmktnorth`

2. **Connection Failures**
   - Verify Streamlit secrets are configured correctly
   - Check that secret section names match (use `[db_turso_keys]` overrides if needed)
   - Ensure database files exist for local operations

3. **Sync Validation Failures**
   - Check that both local and remote databases are accessible
   - Verify that the `marketstats` table exists and has data
   - Check `logs/` directory for detailed error information

4. **Empty DB File After Failed Sync**
   - `libsql.connect()` creates the `.db` file before syncing
   - If sync fails, `_cleanup_empty_db_file()` removes the empty file
   - `init_db.py` also detects this via `verify_db_content()`
