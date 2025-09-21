# Winter Coalition Market App (v.0.61)
A Streamlit application for viewing EVE Online market statistics for Winter Coalition. This tool provides real-time market data analysis, historical price tracking, and fitting information for various items in EVE Online markets.

SUPPORT: Join the Discord for support https://discord.gg/BxatJE572Y
CONTRIBUTING: Contributors welcome. This project is fully open source under MIT License. Source code and full documentation available on GitHub: https://github.com/OrthelT/wcmkts_new

## UPDATES:
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

## Features

- **Market Data Visualization**
  - Real-time market order distribution
  - Price and volume history charts
  - Interactive data filtering by category and item type

- **Market Metrics**
  - Minimum sell prices
  - Current market stock levels
  - Days of inventory remaining
  - Number of fits available on market

- **Historical Analysis**
  - 30-day average prices
  - 30-day average volumes
  - Detailed price history charts
  - Volume tracking over time

- **Fitting Information**
  - Doctrine fit details
  - Market availability of fit components
  - Last update timestamps
  - Advanced filtering by status, group, and stock levels
  - Export functionality for modules and ships

- **Build Cost Analysis**
  - Real-time build cost calculations across multiple structures
  - Material efficiency (ME) and time efficiency (TE) optimization
  - Multiple material price sources (ESI Average, Jita Sell, Jita Buy)
  - Structure comparison and cost optimization
  - Profit margin analysis against market prices
  - Async API calls for improved performance
  - Support for supercapital construction (Sovereignty Hub)
  - Automatic structure tax calculations
  - Rig effects integration

## Data Updates

The app uses Turso's embedded-replica feature to allow a local SQLlite-libsql database that allows extremely fast data fetches. The application automatically syncs with EVE Online market stored on the parent database daily at 13:00 UTC. Users can also trigger manual updates using the sync button in the sidebar to obtain new data, if it is available.

## Setup

1. Clone the repository:
```bash
git clone https://github.com/wc_mkts_streamlit.git
cd wc_mkts_streamlit
```

2. Install required dependencies:
```bash
uv sync
```

3. Set up environment variables:
Create a `.env` file with the following variables:
```
TURSO_DATABASE_URL=your_turso_database_url
TURSO_AUTH_TOKEN=your_turso_auth_token
SDE_URL=your_sde_url
SDE_AUTH_TOKEN=your_sde_auth_token
```

4. Run the application:
```bash
streamlit run app.py
```

### Local Secrets

For local Streamlit runs, store credentials in `.streamlit/secrets.toml` (git‑ignored). This is the default source for database URLs/tokens used by `DatabaseConfig`. Example structure:

```
[wcmkt2_turso]
url = "libsql://..."
token = "..."

[sde_aws_turso]
url = "libsql://..."
token = "..."

[buildcost_turso]
url = "libsql://..."
token = "..."
```

`.env` variables may be used for other tooling, but the app resolves secrets via Streamlit.

## Usage

1. **Filtering Data**
   - Use the sidebar filters to select specific categories or items
   - Toggle "Show All Data" to view all market orders

2. **Viewing Market Data**
   - Select an item to view detailed market information
   - View price distribution charts
   - Check historical price and volume data

3. **Analyzing Fits**
   - Select a specific item to view available fits
   - Check market availability of fit components

4. **Build Cost Calculations**
   - Select item category, group, and specific item
   - Configure build parameters (runs, ME, TE)
   - Choose material price source (ESI Average, Jita Sell, Jita Buy)
   - Compare costs across different structures
   - Analyze profit margins against market prices
   - Enable async mode for faster calculations

## DatabaseConfig Class

The `DatabaseConfig` class is a centralized configuration manager that handles multiple database connections and operations. It provides a unified interface for working with local SQLite databases, remote Turso databases, and LibSQL synchronization.

### Key Features

- **Multi-Database Support**: Manages connections to multiple databases (market data, SDE, build costs)
- **Dual Environment Support**: Handles both local SQLite and remote Turso database connections
- **Automatic Synchronization**: Provides LibSQL sync capabilities for keeping local and remote databases in sync
- **Lazy Loading**: Database connections are created only when needed using properties
- **Validation**: Includes sync validation to ensure data consistency

### Database Aliases

The class supports the following database aliases:

| Alias | Description | Local File | Purpose |
|-------|-------------|------------|---------|
| `wcmkt2` | Production market database | `wcmkt2.db` | Main market data and orders |
| `sde` | Static Data Export | `sde.db` | EVE Online static data (items, categories) |
| `build_cost` | Build cost calculations | `buildcost.db` | Structure data and industry indexes |

### Usage Examples

#### Basic Initialization
```python
from config import DatabaseConfig

# Create a database configuration
mkt_db = DatabaseConfig("wcmkt2")  # Production market database
sde_db = DatabaseConfig("sde")     # Static data export
build_db = DatabaseConfig("build_cost")  # Build cost database
```

#### Database Connections

The class provides several connection methods through properties:

```python
# Local SQLite connection (SQLAlchemy engine)
local_engine = mkt_db.engine

# Remote Turso connection (SQLAlchemy engine)
remote_engine = mkt_db.remote_engine

# LibSQL local connection
libsql_conn = mkt_db.libsql_local_connect

# LibSQL sync connection (for synchronization)
sync_conn = mkt_db.libsql_sync_connect

# Direct SQLite connection
sqlite_conn = mkt_db.sqlite_local_connect
```

#### Synchronization

```python
# Sync local database with remote Turso database
mkt_db.sync()

# Validate sync was successful
is_valid = mkt_db.validate_sync()
```

#### Database Inspection

```python
# Get list of tables
tables = mkt_db.get_table_list(local_only=True)

# Get column information for a specific table
columns = mkt_db.get_table_columns("marketorders", local_only=True)

# Get detailed column information
detailed_columns = mkt_db.get_table_columns("marketorders", local_only=True, full_info=True)
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `alias` | str | Database alias identifier |
| `path` | str | Local file path to the database |
| `url` | str | SQLAlchemy connection URL for local database |
| `turso_url` | str | Remote Turso database URL |
| `token` | str | Authentication token for Turso |
| `engine` | Engine | SQLAlchemy engine for local database (lazy-loaded) |
| `remote_engine` | Engine | SQLAlchemy engine for remote database (lazy-loaded) |
| `libsql_local_connect` | Connection | LibSQL local connection (lazy-loaded) |
| `libsql_sync_connect` | Connection | LibSQL sync connection (lazy-loaded) |
| `sqlite_local_connect` | Connection | Direct SQLite connection (lazy-loaded) |

### Methods

#### `sync()`
Synchronizes the local database with the remote Turso database using LibSQL's embedded-replica feature.

**Features:**
- Updates local database with latest remote data
- Updates Streamlit session state with sync timestamps
- Validates sync success for market databases
- Updates saved sync state

#### `validate_sync() -> bool`
Validates that the sync was successful by comparing the `last_update` timestamp between local and remote databases.

**Returns:** `True` if sync was successful, `False` otherwise

#### `get_table_list(local_only: bool = True) -> list[str]`
Retrieves a list of table names from the database.

**Parameters:**
- `local_only`: If `True`, uses local database; if `False`, uses remote database

**Returns:** List of table names (excluding SQLite system tables)

#### `get_table_columns(table_name: str, local_only: bool = True, full_info: bool = False) -> list`
Retrieves column information for a specific table.

**Parameters:**
- `table_name`: Name of the table to inspect
- `local_only`: If `True`, uses local database; if `False`, uses remote database
- `full_info`: If `True`, returns detailed column information; if `False`, returns just column names

**Returns:**
- If `full_info=False`: List of column names
- If `full_info=True`: List of dictionaries with column details (cid, name, type, notnull, dflt_value, pk)

### Configuration

The class uses Streamlit secrets for Turso configuration:

```python
# Required secrets in .streamlit/secrets.toml
[wcmkt2_turso]
url = "your_turso_url"
token = "your_auth_token"

[sde_aws_turso]
url = "your_turso_url"
token = "your_auth_token"

[buildcost_turso]
url = "your_turso_url"
token = "your_auth_token"
```

### Error Handling

The class includes proper error handling for:
- Invalid database aliases
- Missing Streamlit secrets
- Database connection failures
- Sync validation failures

### Performance Considerations

- **Lazy Loading**: Database connections are only created when first accessed
- **Connection Reuse**: Connections are cached and reused for subsequent operations
- **Efficient Sync**: Uses LibSQL's optimized sync mechanism for minimal bandwidth usage
- **Validation**: Sync validation is only performed for market databases to avoid unnecessary checks

## Maintenance

The application is maintained by Orthel Toralen (orthel.toralen@gmail.com). For issues or feature requests, please contact the maintainer on Discord at orthel_toralen or create an issue in the github repository.

## License

This project is provided under the MIT public license.
