# DatabaseConfig Class Documentation

## Overview

The `DatabaseConfig` class is a comprehensive database management system designed to handle multiple database connections, synchronization, and operations within the Winter Coalition Market Stats application. It provides a unified interface for working with local SQLite databases, remote Turso databases, and LibSQL synchronization.

## Architecture

The class follows a lazy-loading pattern where database connections are only established when first accessed, improving performance and resource utilization. It supports both local and remote database operations with automatic synchronization capabilities.

## Class Structure

```python
class DatabaseConfig:
    # Class variables
    wcdbmap = "wcmkt2"  # Master config variable

    _db_paths = {...}           # Local database file paths
    _db_turso_urls = {...}      # Remote Turso URLs
    _db_turso_auth_tokens = {...}  # Authentication tokens

    def __init__(self, alias: str, dialect: str = "sqlite+libsql")

    # Properties (lazy-loaded)
    @property engine
    @property remote_engine
    @property libsql_local_connect
    @property libsql_sync_connect
    @property sqlite_local_connect

    # Methods
    def sync()
    def validate_sync() -> bool
    def get_table_list(local_only: bool = True) -> list[str]
    def get_table_columns(table_name: str, local_only: bool = True, full_info: bool = False) -> list
```

## Database Aliases

| Alias | Description | Local File | Purpose |
|-------|-------------|------------|---------|
| `wcmkt2` | Production market database | `wcmkt2.db` | Main market data and orders |
| `sde` | Static Data Export | `sde.db` | EVE Online static data |
| `build_cost` | Build cost calculations | `buildcost.db` | Structure data and industry indexes |

## Initialization

### Constructor

```python
def __init__(self, alias: str, dialect: str = "sqlite+libsql")
```

**Parameters:**
- `alias` (str): Database alias identifier
- `dialect` (str): SQLAlchemy dialect (default: "sqlite+libsql")

**Behavior:**
- Automatically maps "wcmkt" alias to the master config value
- Validates alias against available database configurations
- Raises `ValueError` for invalid aliases
- Initializes connection properties (lazy-loaded)

**Example:**
```python
# Valid initializations
mkt_db = DatabaseConfig("wcmkt2")      # Production market database
sde_db = DatabaseConfig("sde")         # Static data export
build_db = DatabaseConfig("build_cost") # Build cost database

# Automatic alias mapping
mkt_db = DatabaseConfig("wcmkt")       # Maps to "wcmkt2"
```

## Properties

### Basic Properties

| Property | Type | Description |
|----------|------|-------------|
| `alias` | str | Database alias identifier |
| `path` | str | Local file path to the database |
| `url` | str | SQLAlchemy connection URL for local database |
| `turso_url` | str | Remote Turso database URL |
| `token` | str | Authentication token for Turso |

### Connection Properties (Lazy-Loaded)

#### `engine`
SQLAlchemy engine for local database operations.

```python
engine = mkt_db.engine
```

**Features:**
- Created only when first accessed
- Cached for subsequent use
- Uses local SQLite database file

#### `remote_engine`
SQLAlchemy engine for remote Turso database operations.

```python
remote_engine = mkt_db.remote_engine
```

**Features:**
- Created only when first accessed
- Cached for subsequent use
- Uses Turso URL with authentication
- Includes secure connection parameters

#### `libsql_local_connect`
LibSQL local database connection.

```python
conn = mkt_db.libsql_local_connect
```

**Features:**
- Direct LibSQL connection to local database
- Used for LibSQL-specific operations
- Lazy-loaded and cached

#### `libsql_sync_connect`
LibSQL sync connection for database synchronization.

```python
sync_conn = mkt_db.libsql_sync_connect
```

**Features:**
- Configured with sync URL and auth token
- Used for database synchronization operations
- Lazy-loaded and cached

#### `sqlite_local_connect`
Direct SQLite connection for low-level operations.

```python
conn = mkt_db.sqlite_local_connect
```

**Features:**
- Direct SQLite3 connection
- Used for operations requiring raw SQLite access
- Lazy-loaded and cached

## Methods

### `sync()`

Synchronizes the local database with the remote Turso database.

```python
mkt_db.sync()
```

**Process:**
1. Establishes LibSQL sync connection
2. Performs database synchronization
3. Updates Streamlit session state with sync timestamps
4. Validates sync success for market databases
5. Updates saved sync state

**Session State Updates:**
- `last_sync`: Timestamp of last sync
- `next_sync`: Timestamp of next scheduled sync
- `sync_status`: "Success" or "Failed" (market databases only)
- `sync_check`: Set to False

**Validation:**
- Only performed for market databases (`wcmkt2`)
- Compares `last_update` timestamps between local and remote databases

### `validate_sync() -> bool`

Validates that the sync operation was successful.

```python
is_valid = mkt_db.validate_sync()
```

**Process:**
1. Queries `MAX(last_update)` from remote database
2. Queries `MAX(last_update)` from local database
3. Compares timestamps for equality
4. Logs validation results

**Returns:**
- `True`: Sync was successful (timestamps match)
- `False`: Sync failed (timestamps don't match)

### `get_table_list(local_only: bool = True) -> list[str]`

Retrieves a list of table names from the database.

```python
# Get local tables
tables = mkt_db.get_table_list(local_only=True)

# Get remote tables
tables = mkt_db.get_table_list(local_only=False)
```

**Parameters:**
- `local_only` (bool): If `True`, uses local database; if `False`, uses remote database

**Process:**
1. Executes `PRAGMA table_list` query
2. Filters out SQLite system tables
3. Returns list of table names

**Returns:** List of table names (excluding system tables)

### `get_table_columns(table_name: str, local_only: bool = True, full_info: bool = False) -> list`

Retrieves column information for a specific table.

```python
# Get column names only
columns = mkt_db.get_table_columns("marketorders")

# Get detailed column information
detailed = mkt_db.get_table_columns("marketorders", full_info=True)

# Get from remote database
remote_columns = mkt_db.get_table_columns("marketorders", local_only=False)
```

**Parameters:**
- `table_name` (str): Name of the table to inspect
- `local_only` (bool): If `True`, uses local database; if `False`, uses remote database
- `full_info` (bool): If `True`, returns detailed information; if `False`, returns just names

**Process:**
1. Executes `PRAGMA table_info(table_name)` query
2. Processes results based on `full_info` parameter
3. Returns formatted column information

**Returns:**
- If `full_info=False`: List of column names
- If `full_info=True`: List of dictionaries with column details:
  - `cid`: Column ID
  - `name`: Column name
  - `type`: Data type
  - `notnull`: NOT NULL constraint
  - `dflt_value`: Default value
  - `pk`: Primary key flag

## Configuration

### Streamlit Secrets

The class requires specific secrets to be configured in `.streamlit/secrets.toml`:

```toml
[wcmkt2_turso]
url = "libsql://your-database.turso.io"
token = "your-auth-token"

[sde_aws_turso]
url = "libsql://your-sde-database.turso.io"
token = "your-auth-token"

[buildcost_turso]
url = "libsql://your-buildcost-database.turso.io"
token = "your-auth-token"
```

### Environment Variables

The class uses Streamlit's secrets management system, which can be configured through:
- `.streamlit/secrets.toml` (local development)
- Streamlit Cloud secrets (production)
- Environment variables (if configured)

## Error Handling

### Invalid Alias
```python
try:
    db = DatabaseConfig("invalid_alias")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Error: Unknown database alias 'invalid_alias'. Available: ['wcmkt2', 'sde', 'build_cost']
```

### Missing Secrets
The class will raise exceptions if required Streamlit secrets are not configured.

### Connection Failures
Database connection failures are handled gracefully with appropriate error messages and logging.

## Performance Considerations

### Lazy Loading
- Database connections are only created when first accessed
- Reduces startup time and memory usage
- Connections are cached for subsequent use

### Connection Reuse
- Each connection type is created once and reused
- Prevents multiple connection overhead
- Improves performance for repeated operations

### Sync Optimization
- Uses LibSQL's efficient sync mechanism
- Minimal bandwidth usage
- Only validates market databases to avoid unnecessary checks

### Memory Management
- Connections are properly closed after use
- No memory leaks from unclosed connections
- Efficient resource utilization

## Usage Patterns

### Basic Database Operations
```python
from config import DatabaseConfig

# Initialize database
mkt_db = DatabaseConfig("wcmkt2")

# Query local database
with mkt_db.engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM marketorders LIMIT 10"))
    data = result.fetchall()

# Query remote database
with mkt_db.remote_engine.connect() as conn:
    result = conn.execute(text("SELECT COUNT(*) FROM marketorders"))
    count = result.scalar()
```

### Synchronization
```python
# Sync database
mkt_db.sync()

# Check if sync was successful
if mkt_db.validate_sync():
    print("Sync successful")
else:
    print("Sync failed")
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

## Best Practices

1. **Use Appropriate Alias**: Choose the correct database alias for your use case
2. **Handle Exceptions**: Always wrap database operations in try-catch blocks
3. **Close Connections**: Use context managers for automatic connection cleanup
4. **Validate Sync**: Always validate sync operations for critical data
5. **Monitor Performance**: Use logging to monitor database operation performance
6. **Test Thoroughly**: Test both local and remote database operations

## Troubleshooting

### Common Issues

1. **Invalid Alias Error**
   - Check that the alias is one of the supported values
   - Ensure the alias is spelled correctly

2. **Connection Failures**
   - Verify Streamlit secrets are configured correctly
   - Check network connectivity for remote operations
   - Ensure database files exist for local operations

3. **Sync Validation Failures**
   - Check that both local and remote databases are accessible
   - Verify that the `marketstats` table exists and has data
   - Check logs for detailed error information

4. **Performance Issues**
   - Use lazy loading by accessing properties only when needed
   - Reuse connections instead of creating new ones
   - Monitor memory usage for large operations

### Debugging

Enable detailed logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

This will provide detailed information about database operations, connection attempts, and sync processes.
