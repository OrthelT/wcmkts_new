# Winter Coalition Market App (v.0.7.5)
A Streamlit application for viewing EVE Online market statistics for Winter Coalition. This tool provides real-time market data analysis, historical price tracking, and fitting information for various items in EVE Online markets.

SUPPORT: Join the Discord for support https://discord.gg/BxatJE572Y
CONTRIBUTING: Contributors welcome. This project is fully open source under MIT License. Source code and full documentation available on GitHub: https://github.com/OrthelT/wcmkts_new

[CHANGELOG](changelog.md)

**Note:** Admin pages (watchlist and doctrine management) are currently disabled during the pyturso migration. Re-enabling them requires a local-write-plus-push redesign.

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

- **Import Analysis**
  - Compare local market prices to Jita sell and buy prices
  - Review shipping cost, profit versus Jita sell, and capital utilisation
  - Estimate 30-day market value using local volume and Jita sell price

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

The app keeps a local pyturso-synced SQLite replica for each database, giving extremely fast data fetches. While a session is open the app polls for updates, pulling at most once every 600 seconds (`pages/components/db_refresh.py`); this is hard-coded, not configurable. The sidebar's "next update" countdown is an *estimate* of when the backend next publishes — 60 minutes after the last `updatelog` timestamp (`state/sync_state.py`) — not a schedule the app follows. Users can also trigger manual updates using the sync button in the sidebar to obtain new data, if it is available.

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

3. Set up credentials. Create `.streamlit/secrets.toml` with per-database sections:
```toml
[wcmktnewkeep_turso]
url = "libsql://your-primary-database.turso.io"
token = "your_turso_auth_token"

[wcmktnorth_turso]
url = "libsql://your-deployment-database.turso.io"
token = "your_turso_auth_token"

[market3_turso]
url = "libsql://your-market3-database.turso.io"
token = "your_turso_auth_token"

[sdelite2_turso]
url = "libsql://your-sde.turso.io"
token = "your_sde_auth_token"

[buildcost_turso]
url = "libsql://your-buildcost.turso.io"
token = "your_buildcost_auth_token"
```

4. Run the application:
```bash
uv run streamlit run app.py
```

### Local Secrets

For local Streamlit runs, store credentials in `.streamlit/secrets.toml` (git‑ignored). This is the default source for database URLs/tokens used by `DatabaseConfig`. Example structure:

```
[wcmktnewkeep_turso]
url = "libsql://..."
token = "..."

[wcmktnorth_turso]
url = "libsql://..."
token = "..."

[market3_turso]
url = "libsql://..."
token = "..."

[sdelite2_turso]
url = "libsql://..."
token = "..."

[buildcost_turso]
url = "libsql://..."
token = "..."
```

`.env` variables may be used for other tooling, but the app resolves secrets via Streamlit.

For existing deployments migrating to SDE v2, add `[sdelite2_turso]` with the
new SDE database's URL and a token authorized to access it before deploying
this version. Update `.streamlit/secrets.toml` for local runs or the app's
secrets in Streamlit Community Cloud for the hosted deployment. Restart the
app after updating secrets. On startup, it syncs the new `sdelite2.db` replica;
the old `[sdelite_turso]` section and `sdelite.db` file are no longer used.

### Cursor Agent Worktrees

When using multiple Cursor Agents, worktrees are automatically configured with symlinks for `secrets.toml` and database files. See [docs/worktree_setup.md](docs/worktree_setup.md) for details.

Quick setup for all existing worktrees:
```bash
./scripts/setup_all_worktrees.sh
```

Navigate to worktrees by branch name:
```bash
# Using Git alias
git wt docs-worktree-setup-3mRY9
git wt 3mRY9  # Just the unique ID

# Or directly
./scripts/wt.sh 3mRY9
```

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

The `DatabaseConfig` class (`config.py`) is a centralized configuration manager for the app's pyturso-synced replicas. Each alias gets one local SQLite file kept in sync with its Turso remote via the `sqlite+turso_sync` dialect — there is no separate "remote engine"; reads and the sync pull both go through the same local replica.

### Key Features

- **Multi-Database Support**: Manages connections to multiple databases (market data for each hub, SDE, build costs)
- **Sync Dialect**: Uses the `sqlite+turso_sync` engine when Turso credentials are present; falls back to a plain read-only local SQLite connection when they are not (so the app still runs local-only without secrets)
- **Automatic Synchronization**: `sync()` pulls remote changes into the local replica, retrying via nuke + fresh bootstrap on an integrity-check failure; `sync(force_rebuild=True)` removes the replica first, for callers that have already seen a read fail on it
- **Lazy Loading**: Engines are created only when needed and cached per alias
- **Validation**: `integrity_check()` and `remote_matches_metadata()` guard against a corrupt or wrongly-targeted replica

### Database Aliases

The class supports the following database aliases (from `settings.toml`):

| Alias | Description | Local File | Purpose |
|-------|-------------|------------|---------|
| `wcmktnewkeep` | Primary market database | `wcmktnewkeep.db` | Main market data and orders (4-HWWF) |
| `wcmktnorth` | Deployment market database | `wcmktnorth2.db` | Deployment market data (X47L-Q) |
| `wcmktbkg` | Third market database | `wcmktbkg.db` | BKG-Q2 market data |
| `sde` | Static Data Export | `sdelite2.db` | EVE Online static data (items, categories) |
| `build_cost` | Build cost calculations | `buildcost.db` | Structure data and industry indexes |

### Usage Examples

#### Basic Initialization
```python
from config import DatabaseConfig

# Create a database configuration
mkt_db = DatabaseConfig("wcmktnewkeep")  # Primary market database
sde_db = DatabaseConfig("sde")           # Static data export
build_db = DatabaseConfig("build_cost")  # Build cost database
```

#### Database Connection

```python
# The one engine for this alias (sync dialect if credentials are present,
# otherwise a read-only local SQLite connection)
engine = mkt_db.engine
```

#### Synchronization

```python
# Pull remote changes into the local replica
result = mkt_db.sync()  # SyncResult(ok, changed)

# Check whether this replica was bootstrapped against the currently
# configured Turso remote (True/False/None if unknown)
matches = mkt_db.remote_matches_metadata()
```

#### Database Inspection

```python
# Get list of tables
tables = mkt_db.get_table_list()

# Get column information for a specific table
columns = mkt_db.get_table_columns("marketorders")

# Get detailed column information
detailed_columns = mkt_db.get_table_columns("marketorders", full_info=True)
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `alias` | str | Database alias identifier |
| `path` | str | Local file path to the database |
| `url` | str | SQLAlchemy connection URL for the local replica |
| `turso_url` | str | Configured Turso database URL |
| `token` | str | Authentication token for Turso |
| `has_remote_credentials` | bool | True when both `turso_url` and `token` are available |
| `engine` | Engine | SQLAlchemy engine for this alias (lazy-loaded, cached) |

### Methods

#### `sync(force_rebuild: bool = False) -> SyncResult`
Pulls remote changes into the local replica. Serialized across calls, disposes local connections first, enforces the replica-consistency state machine, and retries once via nuke + fresh bootstrap on a post-sync integrity-check failure.

Pass `force_rebuild=True` to remove the replica before pulling, making the pull a fresh bootstrap. The state machine alone only proves the replica opens — a corrupt data page leaves `sqlite_master` readable — so `read_df()` uses this once a read has actually failed and `integrity_check()` confirms the file is bad.

**Returns:** `SyncResult(ok, changed)` — truthy on success, preserving the legacy bool contract.

**Raises:** `ValueError` if Turso credentials are missing for this alias; network/pull exceptions propagate (a healthy local file is never deleted on a network error).

#### `remote_matches_metadata() -> bool | None`
Whether this replica's `-info` sidecar was bootstrapped against the currently configured Turso remote (compares host + path only). Returns `None` when either side is unknown.

#### `get_table_list() -> list[str]`
Retrieves a list of table names from this alias's replica (excluding SQLite system tables).

#### `get_table_columns(table_name: str, full_info: bool = False) -> list`
Retrieves column information for a specific table.

**Parameters:**
- `table_name`: Name of the table to inspect
- `full_info`: If `True`, returns detailed column information; if `False`, returns just column names

**Returns:**
- If `full_info=False`: List of column names
- If `full_info=True`: List of dictionaries with column details (cid, name, type, notnull, dflt_value, pk)

### Configuration

The class uses Streamlit secrets for Turso configuration, one `[<turso_secret_key>]` section per alias (see `settings.toml`'s `turso_secret_key` / `[db_turso_keys]`):

```python
# Required secrets in .streamlit/secrets.toml
[wcmktnewkeep_turso]
url = "your_turso_url"
token = "your_auth_token"

[wcmktnorth_turso]
url = "your_turso_url"
token = "your_auth_token"

[market3_turso]
url = "your_turso_url"
token = "your_auth_token"

[sdelite2_turso]
url = "your_turso_url"
token = "your_auth_token"

[buildcost_turso]
url = "your_turso_url"
token = "your_auth_token"
```

### Error Handling

The class includes proper error handling for:
- Invalid database aliases
- Missing Streamlit secrets (degrades to local-only, no Turso credentials)
- Database connection failures
- Sync integrity-check failures (nuke + fresh bootstrap retry)

### Performance Considerations

- **Lazy Loading**: Engines are only created when first accessed
- **Connection Reuse**: Engines are cached per alias (keyed by credential mode) and reused for subsequent operations
- **Efficient Sync**: Uses the pyturso sync-dialect's incremental pull for minimal bandwidth usage
- **Validation**: `integrity_check()` runs after every `sync()`; `remote_matches_metadata()` guards against reading a replica bootstrapped against a different Turso remote

## Maintenance

The application is maintained by Orthel Toralen (orthel.toralen@gmail.com). For issues or feature requests, please contact the maintainer on Discord at orthel_toralen or create an issue in the github repository.

## License

This project is provided under the MIT public license.
