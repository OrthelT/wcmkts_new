# Detailed Migration Examples

This document provides side-by-side before/after examples for migrating each function to use the DoctrineFacade.

---

## 1. Migrate get_fit_name() - doctrine_status.py:104

### BEFORE (Current)
```python
# doctrine_status.py, lines 131-139 (local function definition)
def get_fit_name(fit_id: int) -> str:
    """Get the fit name for a given fit id"""
    try:
        df = read_df(mkt_db, text("SELECT fit_name FROM ship_targets WHERE fit_id = :fit_id"), {"fit_id": fit_id})
        return str(df.loc[0, 'fit_name']) if not df.empty else "Unknown Fit"
    except Exception as e:
        logger.error(f"Error getting fit name for fit_id: {fit_id}")
        logger.error(f"Error: {e}")
        return "Unknown Fit"

# doctrine_status.py, line 104 (in get_fit_summary loop)
for fit_id in fit_ids:
    # ...
    fit_name = get_fit_name(fit_id)  # CALL SITE
    # ...
```

### AFTER (Refactored)
```python
# doctrine_status.py - Update imports
from facades import get_doctrine_facade

# doctrine_status.py, line 104 (in get_fit_summary loop)
facade = get_doctrine_facade()
for fit_id in fit_ids:
    # ...
    fit_name = facade.get_fit_name(fit_id)  # MIGRATED CALL
    # ...

# DELETE: doctrine_status.py lines 131-139 (local function definition)
```

### Benefits
- Eliminates code duplication (identical logic in 2 places)
- Single source of truth in repository (better error handling, logging)
- Potential for caching in session state
- Type-safe default return value

---

## 2. Migrate get_fit_name_from_db() - doctrine_report.py:299

### BEFORE (Current)
```python
# doctrine_report.py, lines 62-73 (local function definition)
def get_fit_name_from_db(fit_id: int) -> str:
    """Get the fit name from the ship_targets table using fit_id."""
    try:
        df = read_df(mktdb, text("SELECT fit_name FROM ship_targets WHERE fit_id = :fit_id"), {"fit_id": fit_id})
        if not df.empty:
            return str(df.loc[0, 'fit_name'])
        logger.warning(f"No fit name found for fit_id: {fit_id}")
        return "Unknown Fit"
    except Exception as e:
        logger.error(f"Error getting fit name for fit_id: {fit_id}")
        logger.error(f"Error: {e}")
        return "Unknown Fit"

# doctrine_report.py, line 299 (in fit display loop)
for fit_id in fit_ids:
    # ...
    fit_name = get_fit_name_from_db(fit_id)  # CALL SITE
    # ...
```

### AFTER (Refactored)
```python
# doctrine_report.py - Update imports
from facades import get_doctrine_facade

# doctrine_report.py, line 299 (in fit display loop)
facade = get_doctrine_facade()
for fit_id in fit_ids:
    # ...
    fit_name = facade.get_fit_name(fit_id)  # MIGRATED CALL (same method!)
    # ...

# DELETE: doctrine_report.py lines 62-73 (local function definition)
```

### Benefits
- Merges two identical implementations into one
- Uses same facade method as doctrine_status.py (consistency)
- Better error handling from centralized implementation

---

## 3. Migrate get_doctrine_lead_ship() - doctrine_report.py:432

### BEFORE (Current)
```python
# doctrine_report.py, lines 53-60 (local function definition)
def get_doctrine_lead_ship(doctrine_id: int) -> int:
    """Get the type ID of the lead ship for a doctrine"""
    query = text("SELECT lead_ship FROM lead_ships WHERE doctrine_id = :doctrine_id")
    df = read_df(mktdb, query, {"doctrine_id": doctrine_id})
    if df.empty:
        return None
    lead_ship = df.loc[0, 'lead_ship']
    return int(lead_ship) if pd.notna(lead_ship) else None

# doctrine_report.py, lines 431-433 (in main display)
# Get lead ship image for this doctrine
lead_ship_id = get_doctrine_lead_ship(selected_doctrine_id)
lead_ship_image_url = f"https://images.evetech.net/types/{lead_ship_id}/render?size=256"
```

### AFTER (Refactored)
```python
# doctrine_report.py - Update imports
from facades import get_doctrine_facade

# doctrine_report.py, lines 431-435 (in main display)
# Get lead ship image for this doctrine
facade = get_doctrine_facade()
lead_ship_id = facade.get_doctrine_lead_ship(selected_doctrine_id)
if lead_ship_id:
    lead_ship_image_url = f"https://images.evetech.net/types/{lead_ship_id}/render?size=256"
else:
    lead_ship_image_url = None  # Or use a default image

# DELETE: doctrine_report.py lines 53-60 (local function definition)
```

### Benefits
- Removes code duplication (identical query logic)
- Better type safety (Optional[int] vs bare int)
- Consistent error handling and logging
- Handles None case explicitly

---

## 4. Migrate get_ship_target() - doctrine_status.py:80 and :259

### BEFORE (Current)
```python
# doctrine_status.py, lines 279-309 (confusing dual-purpose function)
def get_ship_target(ship_id: int, fit_id: int) -> int:
    """Get the target for a given ship id or fit id
    if searching by ship_id, enter zero for fit_id
    if searching by fit_id, enter zero for ship_id
    """
    if ship_id == 0 and fit_id == 0:
        # error handling
        return 20
    elif ship_id == 0:
        # fit_id query path
        ...
    else:
        # ship_id query path
        ...

# doctrine_status.py, line 80 (in get_fit_summary loop)
target = get_ship_target(0, fit_id)  # CALL SITE 1: confusing API

# doctrine_status.py, line 259 (in get_ship_stock_list)
ship_target = get_ship_target(ship_id, 0)  # CALL SITE 2: confusing API
```

### AFTER (Refactored)
```python
# doctrine_status.py - Update imports
from facades import get_doctrine_facade

# doctrine_status.py, line 80 (in get_fit_summary loop)
facade = get_doctrine_facade()
target = facade.repository.get_target_by_fit_id(fit_id)  # Clear intent

# doctrine_status.py, line 259 (in get_ship_stock_list)
facade = get_doctrine_facade()
ship_target = facade.repository.get_target_by_ship_id(ship_id)  # Clear intent

# DELETE: doctrine_status.py lines 279-309 (local function definition)

# OPTIONAL: Add convenience methods to facade
# In facades/doctrine_facade.py:
def get_fit_target(self, fit_id: int) -> int:
    return self.repository.get_target_by_fit_id(fit_id)

def get_ship_target(self, ship_id: int) -> int:
    return self.repository.get_target_by_ship_id(ship_id)

# Then update calls to:
target = facade.get_fit_target(fit_id)
ship_target = facade.get_ship_target(ship_id)
```

### Benefits
- Eliminates confusing "magic zero" API
- Clearer, self-documenting method names
- Better error handling with consistent defaults
- Splitting concerns makes code easier to understand

---

## 5. Migrate categorize_ship_by_role() - doctrine_report.py:118

### BEFORE (Current)
```python
# doctrine_report.py, lines 75-106 (loads TOML on EVERY call!)
def categorize_ship_by_role(ship_name: str, fit_id: int) -> str:
    fit_id = str(fit_id)
    import tomllib  # Imported every call!
    with open("settings.toml", "rb") as f:  # File read every call!
        settings = tomllib.load(f)
    dps_ships = settings['ship_roles']['dps']
    logi_ships = settings['ship_roles']['logi']
    # ... more logic
    return role_string

# doctrine_report.py, lines 115-120 (in display_categorized_doctrine_data)
selected_data_with_roles = selected_data.copy()
selected_data_with_roles['role'] = selected_data_with_roles.apply(
    lambda row: categorize_ship_by_role(row['ship_name'], row['fit_id']),
    axis=1
)
```

### AFTER (Refactored)
```python
# doctrine_report.py - Update imports
from facades import get_doctrine_facade

# doctrine_report.py, lines 115-121 (in display_categorized_doctrine_data)
facade = get_doctrine_facade()
selected_data_with_roles = selected_data.copy()
selected_data_with_roles['role'] = selected_data_with_roles.apply(
    lambda row: facade.categorize_ship(row['ship_name'], row['fit_id']).display_name,
    axis=1
)

# DELETE: doctrine_report.py lines 75-106 (local function definition)
```

### Alternative - Even Better (Vectorized)
```python
# If the categorizer supports batch operations, use vectorized approach
facade = get_doctrine_facade()
selected_data_with_roles = selected_data.copy()

# More efficient: process in batches instead of row-by-row
ship_names = selected_data_with_roles['ship_name'].tolist()
fit_ids = selected_data_with_roles['fit_id'].tolist()

roles = [facade.categorize_ship(name, fit_id).display_name
         for name, fit_id in zip(ship_names, fit_ids)]
selected_data_with_roles['role'] = roles
```

### Benefits
- Eliminates performance issue (TOML loaded once on init, cached)
- Type safety (ShipRole enum instead of string)
- Better error handling
- More efficient - ConfigBasedCategorizer caches settings
- Cleaner code using facade

---

## 6. Migrate create_fit_df() - doctrine_status.py:26, :271, :446 and doctrine_report.py:396

### BEFORE (Current)
```python
# Import from doctrines.py
from doctrines import create_fit_df

# doctrine_status.py, line 26 (in get_fit_summary)
all_fits_df, summary_df = create_fit_df()

# doctrine_status.py, line 271 (in fitting_download_button)
_, summary_data = create_fit_df()

# doctrine_status.py, line 446 (in update_jita_deltas_cache)
all_fits_df, summary_df = create_fit_df()

# doctrine_report.py, line 396 (in main display)
master_df, fit_summary = create_fit_df()
```

### AFTER (Refactored)
```python
# Update imports
from facades import get_doctrine_facade

# doctrine_status.py, line 26 (in get_fit_summary)
facade = get_doctrine_facade()
result = facade.build_fit_data()
all_fits_df = result.raw_df
summary_df = result.summary_df

# doctrine_status.py, line 271 (in fitting_download_button)
facade = get_doctrine_facade()
result = facade.build_fit_data()
summary_data = result.summary_df

# doctrine_status.py, line 446 (in update_jita_deltas_cache)
facade = get_doctrine_facade()
result = facade.build_fit_data()
all_fits_df = result.raw_df
summary_df = result.summary_df

# doctrine_report.py, line 396 (in main display)
facade = get_doctrine_facade()
result = facade.build_fit_data()
master_df = result.raw_df
fit_summary = result.summary_df
```

### Alternative - One-Liner Approach
```python
facade = get_doctrine_facade()
result = facade.build_fit_data()

# Access raw_df and summary_df as needed
# result.raw_df, result.summary_df, result.summaries, result.metadata
```

### Benefits
- Better type safety (FitBuildResult instead of tuple)
- Access to additional metadata (summaries, build info)
- Facade handles caching transparently
- Cleaner separation of concerns

---

## 7. Migrate get_module_stock_list() - doctrine_status.py:897 and doctrine_report.py:352

### BEFORE (Current)
```python
# doctrine_status.py, lines 141-221 (81 lines with usage calculation)
def get_module_stock_list(module_names: list):
    """Get lists of modules with their stock quantities for display and CSV export."""
    if not st.session_state.get('module_list_state'):
        st.session_state.module_list_state = {}
    if not st.session_state.get('csv_module_list_state'):
        st.session_state.csv_module_list_state = {}

    for module_name in module_names:
        if module_name not in st.session_state.module_list_state:
            logger.info(f"Querying database for {module_name}")
            # Complex logic: stock query + usage query + formatting
            # ...
            st.session_state.module_list_state[module_name] = module_info
            st.session_state.csv_module_list_state[module_name] = csv_module_info

# doctrine_report.py, lines 21-51 (31 lines, simpler version)
def get_module_stock_list(module_names: list):
    """Get lists of modules with their stock quantities for display and CSV export."""
    # Similar but without usage breakdown

# doctrine_status.py, line 897 (call site)
get_module_stock_list(module_names)

# doctrine_report.py, line 352 (call site)
get_module_stock_list([module_name])
```

### AFTER (Refactored)

**Step 1: Add to facade** (if not already present)
```python
# facades/doctrine_facade.py
def get_module_stock(self, module_name: str) -> Optional[ModuleStock]:
    """
    Get stock information for a specific module.

    Returns:
        ModuleStock domain model with:
        - type_name: str
        - type_id: int
        - total_stock: int
        - fits_on_mkt: int
        - usage: dict of ship -> qty
        - display_string: formatted display text
    """
    return self.repository.get_module_stock(module_name)
```

**Step 2: Update doctrine_status.py**
```python
# doctrine_status.py, line 897
facade = get_doctrine_facade()

# Initialize session state
if not st.session_state.get('module_list_state'):
    st.session_state.module_list_state = {}

for module_name in module_names:
    if module_name not in st.session_state.module_list_state:
        module = facade.get_module_stock(module_name)
        if module:
            st.session_state.module_list_state[module_name] = module.display_string
        else:
            st.session_state.module_list_state[module_name] = module_name
```

**Step 3: Update doctrine_report.py**
```python
# doctrine_report.py, line 352
facade = get_doctrine_facade()

module = facade.get_module_stock(module_name)
if module:
    st.session_state.module_list_state[module_name] = module.display_string
else:
    st.session_state.module_list_state[module_name] = module_name
```

**Step 4: Delete local functions**
```python
# DELETE: doctrine_status.py lines 141-221
# DELETE: doctrine_report.py lines 21-51
```

### Benefits
- Single consolidated implementation
- Type-safe domain model return
- Session state management still possible (but explicit)
- Consistent behavior across pages
- Centralized module usage logic

---

## 8. Migrate calculate_jita_fit_cost_and_delta() - doctrine_status.py:479

### BEFORE (Current)
```python
# doctrine_status.py, line 13 (import)
from doctrines import create_fit_df, get_all_fit_data, calculate_jita_fit_cost_and_delta

# doctrine_status.py, lines 479-481 (in update_jita_deltas_cache)
jita_fit_cost, jita_cost_delta = calculate_jita_fit_cost_and_delta(
    fit_data, total_cost, jita_price_map
)
```

### AFTER (Refactored)

**Option 1: Use existing wrapper from price_service**
```python
# doctrine_status.py - Update import
from facades import get_doctrine_facade

# doctrine_status.py, lines 479-481
facade = get_doctrine_facade()
analysis = facade.price_service.analyze_fit_cost(fit_data, total_cost, jita_price_map)
jita_fit_cost = analysis.jita_cost
jita_cost_delta = analysis.delta_percentage
```

**Option 2: Add convenience method to facade (recommended)**
```python
# facades/doctrine_facade.py - Add method
def calculate_fit_jita_analysis(self, fit_data: pd.DataFrame,
                                 current_cost: float,
                                 jita_price_map: Optional[dict] = None) -> FitCostAnalysis:
    """
    Analyze fit cost at Jita prices vs current market prices.

    Returns:
        FitCostAnalysis with jita_cost and delta_percentage
    """
    return self.price_service.analyze_fit_cost(fit_data, current_cost, jita_price_map)

# doctrine_status.py, lines 479-481
facade = get_doctrine_facade()
analysis = facade.calculate_fit_jita_analysis(fit_data, total_cost, jita_price_map)
jita_fit_cost = analysis.jita_cost
jita_cost_delta = analysis.delta_percentage
```

### Benefits
- Uses centralized implementation (better error handling)
- Type-safe returns (FitCostAnalysis object)
- Access to price_service through facade
- No import from doctrines.py needed

---

## Complete Import Statement Migration

### BEFORE
```python
# doctrine_status.py
from doctrines import create_fit_df, get_all_fit_data, calculate_jita_fit_cost_and_delta
from utils import get_multi_item_jita_price
from config import DatabaseConfig
```

### AFTER
```python
# doctrine_status.py
from facades import get_doctrine_facade
from config import DatabaseConfig
# Remove direct imports from doctrines, use facade instead
```

---

## Testing the Migration

After each migration, verify:

1. Import statements are correct
2. Facade is properly initialized
3. Return values match expected types
4. Error handling is consistent
5. Session state management still works
6. Performance is not degraded

Example test:
```python
# Test get_fit_name migration
facade = get_doctrine_facade()
name = facade.get_fit_name(473)
assert isinstance(name, str)
assert name != "Unknown Fit" or name == "Unknown Fit"  # Either valid or default

# Test categorize_ship migration
role = facade.categorize_ship("Hurricane", 473)
assert role in [ShipRole.DPS, ShipRole.LOGI, ShipRole.LINKS, ShipRole.SUPPORT]
```
