# Module Equivalents Feature

## Overview

The module equivalents feature identifies and aggregates stock for interchangeable faction modules in EVE Online. Some faction modules have identical stats but different faction names (e.g., Dark Blood Thermal Armor Hardener, Federation Navy Thermal Armor Hardener, etc.). Instead of showing separate stock levels for each variant, the system aggregates their combined stock to provide a more accurate picture of doctrine fit availability.

**Key Benefits:**
- More accurate doctrine fit calculations (shows combined stock across all equivalent modules)
- Better inventory management (identifies total available stock for interchangeable items)
- Improved low stock alerts (accounts for all equivalent variants)

**Example:**
- Without equivalents: "Dark Blood Thermal Armor Hardener" shows stock = 25
- With equivalents: "Dark Blood Thermal Armor Hardener" shows stock = 150 (combined across 6 faction variants)

**Configuration:**
The feature is controlled by the `use_equivalent` setting in `settings.toml`:

```toml
[module_strategy]
  use_equivalent = true
```

## Architecture

The module equivalents feature is split across two repositories:

### Backend (mkts_backend) - Data Management

The backend repository owns the `module_equivalents` table and provides tools for managing equivalence groups.

**Key Files:**
- `db/models.py` - `ModuleEquivalents` ORM model
- `db/equiv_handlers.py` - CRUD operations (list, add, remove groups)
- `cli_tools/equiv_manager.py` - CLI interface for managing equivalents
- `cli_tools/args_parser.py` - CLI routing

**Table Schema:**
```sql
CREATE TABLE module_equivalents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equiv_group_id INTEGER NOT NULL,  -- Groups equivalent modules together
    type_id INTEGER NOT NULL,          -- EVE type ID
    type_name TEXT NOT NULL,           -- Module name from SDE
    UNIQUE(type_id)                    -- Each module can only be in one group
);
```

**Important:** The column is named `equiv_group_id` (not `group_id`) to avoid confusion with EVE's static data `invGroups.groupID`.

### Frontend (this repository) - Stock Aggregation

The frontend reads the `module_equivalents` table (synced from Turso) and uses it to aggregate stock when building doctrine fit data.

**Key Files:**

| File | Purpose |
|------|---------|
| `models.py` | `ModuleEquivalents` ORM model for local database |
| `services/module_equivalents_service.py` | Service with cached lookups and faction filtering |
| `services/doctrine_service.py` | `FitDataBuilder.apply_module_equivalents()` pipeline step |
| `repositories/sde_repo.py` | `get_faction_type_ids()` for MetaGroup 4 filter |
| `pages/doctrine_status.py` | UI indicators (🔄 prefix, combined label) |
| `pages/doctrine_report.py` | UI indicators with per-module breakdown |
| `ui/popovers.py` | Popover displays combined stock and per-module details |
| `settings.toml` | `[module_strategy] use_equivalent = true` config |

## Backend CLI Commands

All commands are run via the `mkts-backend` CLI tool in the backend repository. Operations apply to ALL markets by default (since module equivalents are universal EVE game data). Use `--market=<alias>` to target a specific market database.

### List Equivalence Groups

```bash
mkts-backend equiv list
```

Shows all equivalence groups with their member modules.

### Add New Group

```bash
mkts-backend equiv add --type-ids=13984,17838,15705,28528,14065,13982
```

Creates a new equivalence group containing the specified type IDs.

**Features:**
- Resolves type IDs to names from the SDE
- Validates that type IDs exist
- Guards against duplicates (prevents adding type IDs already in another group)
- Auto-assigns the next available `equiv_group_id`

**Duplicate Protection:**
If you try to add a type ID that's already in an equivalence group, the command will fail with an error. You must remove the old group first.

### Remove Group

```bash
mkts-backend equiv remove --id=1
```

Removes all modules from the equivalence group with the specified `equiv_group_id`.

### Sync to Remote

After making changes, sync the local database to Turso so the frontend can pick up the updates:

```bash
mkts-backend sync
```

The frontend will receive the changes on its next Turso sync operation.

## How Aggregation Works

The aggregation happens during the doctrine fit build pipeline in `FitDataBuilder`:

1. **Load Raw Data** - Fetch all doctrine items from database (`load_raw_data()`)

2. **Apply Module Equivalents** - `apply_module_equivalents()` step:
   - Check if `use_equivalent = true` in `settings.toml`
   - Get set of all type_ids that have equivalents via `ModuleEquivalentsService`
   - For each module in doctrine fits that has equivalents:
     - Get aggregated stock across all equivalent modules
     - Recalculate `fits_on_mkt = total_stock // fit_qty`
     - Update the module's `total_stock` and `fits_on_mkt` in the raw DataFrame

3. **Aggregate Summaries** - Group by fit_id, taking minimum `fits_on_mkt` across all modules (bottleneck item determines fit count)

4. **Build Domain Models** - Create `FitSummary` objects with the adjusted stock levels

**Example:**

```
Before aggregation:
  - Dark Blood Thermal Armor Hardener: stock=25, fit_qty=2, fits_on_mkt=12

After aggregation (6 equivalent variants):
  - Dark Blood Thermal Armor Hardener: stock=150, fit_qty=2, fits_on_mkt=75
```

## Faction Module Filtering (Performance Optimization)

Only faction modules (metaGroupID=4) can have equivalents. The service implements an early-exit optimization:

1. On initialization, `ModuleEquivalentsService` loads all faction type IDs from the SDE
2. Before database lookups, checks if type_id is in the faction set
3. If not faction → returns immediately without querying the database
4. If faction → proceeds with equivalence lookup

This prevents unnecessary database queries for the vast majority of modules (T1, T2, storyline, officer, etc.).

**Implementation:**
- `SDERepository.get_faction_type_ids()` - Cached query: `SELECT typeID FROM invTypes WHERE metaGroupID = 4`
- `ModuleEquivalentsService._is_faction()` - O(1) set membership check
- Falls back gracefully if SDE not available (treats all modules as potentially faction)

## UI Indicators

Modules with equivalents are visually distinguished in the UI:

### Doctrine Status Page

- **🔄 Prefix** - Shows 🔄 icon before module name
- **(combined) Label** - Appended to module name
- **Pre-fetched Set** - Uses `get_type_ids_with_equivalents()` for O(1) lookup in render loops

Example: `🔄 Dark Blood Thermal Armor Hardener (combined)`

### Doctrine Report Page

- Same **🔄 prefix** and **(combined) label** as status page
- **Caption** - Shows "🔄 Stock includes equivalent modules" below module list
- **Breakdown** - Popover shows per-module stock levels

### Popovers

When clicking a module name with equivalents:

1. **Combined Stock Metric** - Shows total stock across all equivalents
2. **Equivalent Modules Section** - Lists each variant with:
   - Module name
   - Individual stock
   - Fits that use this specific variant
   - **► Indicator** - Shows current module in the list
3. **Total Caption** - Shows combined stock total

**Batch Prefetch Pattern:**
Popovers execute on every page rerun (even when closed). To avoid repeated API calls, pages pre-fetch Jita prices and equivalents sets before rendering loops:

```python
# Pre-fetch before render loop
equiv_service = get_module_equivalents_service()
type_ids_with_equivs = equiv_service.get_type_ids_with_equivalents()

# O(1) lookup in render loop
for module in modules:
    has_equiv = module.type_id in type_ids_with_equivs
    if has_equiv:
        display_text = f"🔄 {module.name} (combined)"
```

## Adding New Equivalence Groups

### 1. Identify Interchangeable Modules

Find faction modules with identical stats (same attributes, different faction names). You can use:
- EVE University wiki
- Third-party fitting tools (Pyfa, EFT)
- In-game "Show Info" comparison

### 2. Get Type IDs

Query the SDE database or use tools like:
- https://everef.net/
- https://www.fuzzwork.co.uk/

Example type IDs for Thermal Armor Hardeners (faction):
- 13984 (Dark Blood)
- 17838 (True Sansha)
- 15705 (Caldari Navy)
- 28528 (Republic Fleet)
- 14065 (Imperial Navy)
- 13982 (Federation Navy)

### 3. Add to Backend

```bash
mkts-backend equiv add --type-ids=13984,17838,15705,28528,14065,13982
```

### 4. Sync to Remote

```bash
mkts-backend sync
```

### 5. Frontend Picks Up Changes

On the frontend's next Turso sync (manual or scheduled), the new equivalence group will be loaded and used in doctrine calculations.

**Validation:**
The CLI validates:
- All type IDs exist in the SDE
- No type ID is already in another equivalence group
- Type names are resolved from the SDE

**Duplicate Guard:**
If you try to add a type ID that already exists in an equivalence group, the command will fail:

```
Error: Type ID 13984 is already in equivalence group 1
```

Remove the old group first if you need to restructure:

```bash
mkts-backend equiv remove --id=1
mkts-backend equiv add --type-ids=13984,17838,15705,28528,14065,13982,<new_id>
```

## Caching Strategy

The service uses Streamlit's caching with tiered TTLs:

| Function | TTL | Purpose |
|----------|-----|---------|
| `_get_equivalent_type_ids_cached()` | 3600s (1h) | Type ID lookups change rarely |
| `_get_equivalence_group_cached()` | 600s (10m) | Includes stock data (more volatile) |
| `_get_all_equivalence_groups_cached()` | 3600s (1h) | Full group list for batch operations |
| `SDERepository.get_faction_type_ids()` | No TTL | Static data, immutable across app lifecycle |

**Cache Invalidation:**
- Market data caches are cleared after Turso sync (`invalidate_market_caches()`)
- Service caches persist across sync (equivalence mappings don't change from backend updates alone)
- Full app restart clears all caches

## Settings Configuration

The feature respects the `use_equivalent` setting in `settings.toml`:

```toml
[module_strategy]
  use_equivalent = true
```

**When enabled (true):**
- `FitDataBuilder.apply_module_equivalents()` runs during pipeline
- Stock is aggregated across equivalent modules
- UI shows 🔄 indicators

**When disabled (false):**
- Aggregation step is skipped
- Each module variant shows individual stock
- No 🔄 indicators

**Default:** `true` (feature enabled)

## Database Table Details

### Frontend Table: `module_equivalents`

This table is **read-only** on the frontend. It is synced from Turso, which is updated by the backend repository.

**Columns:**
- `id` (INTEGER PRIMARY KEY) - Auto-increment unique identifier
- `equiv_group_id` (INTEGER, indexed) - Groups equivalent modules together
- `type_id` (INTEGER, indexed, unique) - EVE type ID
- `type_name` (TEXT) - Module name from SDE

**Indexes:**
- Primary key on `id`
- Index on `equiv_group_id` (for group lookups)
- Index on `type_id` (for type lookups)
- Unique constraint on `type_id` (each module in one group only)

**Sample Data:**

```
id | equiv_group_id | type_id | type_name
---|----------------|---------|--------------------------------------------
1  | 1              | 13984   | Dark Blood Thermal Armor Hardener I
2  | 1              | 17838   | True Sansha Thermal Armor Hardener
3  | 1              | 15705   | Caldari Navy Thermal Armor Hardener
4  | 1              | 28528   | Republic Fleet Thermal Armor Hardener
5  | 1              | 14065   | Imperial Navy Thermal Armor Hardener
6  | 1              | 13982   | Federation Navy Thermal Armor Hardener
```

**Query Patterns:**

```sql
-- Get all equivalents for a specific type_id
SELECT me2.type_id
FROM module_equivalents me1
JOIN module_equivalents me2 ON me1.equiv_group_id = me2.equiv_group_id
WHERE me1.type_id = 13984;

-- Get equivalence group with stock data
SELECT me.equiv_group_id, me.type_id, me.type_name,
       COALESCE(ms.total_volume_remain, 0) as stock,
       COALESCE(ms.price, 0) as price
FROM module_equivalents me
LEFT JOIN marketstats ms ON me.type_id = ms.type_id
WHERE me.equiv_group_id = (
    SELECT equiv_group_id FROM module_equivalents WHERE type_id = 13984
);
```

## Troubleshooting

### Equivalents Not Showing in UI

**Check:**
1. Is `use_equivalent = true` in `settings.toml`?
2. Has the frontend synced from Turso recently?
3. Are the modules actually in the `module_equivalents` table?

```bash
# Backend - verify group exists
mkts-backend equiv list

# Backend - sync to Turso
mkts-backend sync
```

### Stock Not Aggregating

**Check:**
1. Are the modules faction (metaGroupID=4)? Only faction modules can have equivalents
2. Is the `ModuleEquivalentsService` faction filter working? Check logs for errors loading SDE
3. Is the aggregation step running? Check `BuildMetadata` in logs

### Duplicate Type ID Error

**Problem:** Trying to add a type ID that's already in another group

**Solution:**
```bash
# Find which group it's in
mkts-backend equiv list

# Remove old group
mkts-backend equiv remove --id=<old_group_id>

# Add new group
mkts-backend equiv add --type-ids=<all_type_ids>
```

### Frontend Not Picking Up Changes

**Check:**
1. Did backend sync to Turso? (`mkts-backend sync`)
2. Did frontend sync from Turso? (Manual sync button or scheduled sync)
3. Clear browser cache and refresh

## Technical Implementation Notes

### Service Layer Design

`ModuleEquivalentsService` follows the standard service pattern:

- **Dependency Injection** - Receives `DatabaseConfig` and optional `faction_type_ids` set
- **Factory Method** - `create_default()` for standard instantiation
- **Caching** - Uses `@st.cache_data` for repeated lookups
- **Faction Filtering** - Early-exit optimization for non-faction modules

### Domain Models

The service defines two domain models:

**`EquivalentModule`** - Represents a single module with stock:
```python
@dataclass(frozen=True)
class EquivalentModule:
    type_id: int
    type_name: str
    stock: int = 0
    price: float = 0.0
```

**`EquivalenceGroup`** - Represents a group of equivalent modules:
```python
@dataclass
class EquivalenceGroup:
    equiv_group_id: int
    modules: list[EquivalentModule]

    @property
    def total_stock(self) -> int:
        return sum(m.stock for m in self.modules)
```

### Pipeline Integration

The aggregation is a step in the `FitDataBuilder` pipeline:

```python
result = (FitDataBuilder(repo, price_service, logger)
    .load_raw_data()
    .apply_module_equivalents()  # ← Equivalents step
    .fill_null_prices()
    .aggregate_summaries()
    .calculate_costs()
    .merge_targets()
    .finalize_columns()
    .build())
```

The step is optional and controlled by the `use_equivalent` setting.

## Related Documentation

- **Architecture Reference** (`architecture_reference.md`) - Overall system architecture
- **Database Config** (`database_config.md`) - Turso sync and database management
- **Backend Repository** (https://github.com/OrthelT/mkts_backend) - Module equivalents management CLI
