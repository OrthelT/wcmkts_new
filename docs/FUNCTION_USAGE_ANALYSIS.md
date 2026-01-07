# Function Usage Analysis Report

## Summary
This analysis covers 7 functions across the codebase with focus on pages/doctrine_status.py and pages/doctrine_report.py refactoring targets.

---

## 1. create_fit_df()

### Definition Locations
- **PRIMARY**: `/home/orthel/workspace/github/refactordoctrines/doctrines.py:29-78`
  - Original implementation: ~175 lines of DataFrame construction logic
  - Uses vectorized operations with groupby/merge patterns

- **WRAPPER**: `/home/orthel/workspace/github/refactordoctrines/services/doctrine_service.py:1010-1019`
  - Backwards-compatible wrapper: delegates to DoctrineService.build_fit_data()
  - Returns: tuple[pd.DataFrame, pd.DataFrame]

### Call Sites (4 locations)

#### In Pages (PRIMARY TARGETS)
1. **doctrine_status.py:26** (in get_fit_summary function)
   ```python
   all_fits_df, summary_df = create_fit_df()
   ```
   - Context: Caches fit summary dataframes
   - Usage: Filters unique fit_ids, processes fit data

2. **doctrine_status.py:271** (in fitting_download_button fragment)
   ```python
   _, summary_data = create_fit_df()
   ```
   - Context: Downloads fit data as CSV
   - Usage: Merges targets into fit data for export

3. **doctrine_status.py:446** (in update_jita_deltas_cache function)
   ```python
   all_fits_df, summary_df = create_fit_df()
   ```
   - Context: Caches Jita price calculations
   - Usage: Extracts type_ids for price lookups

4. **doctrine_report.py:396** (in main display function)
   ```python
   master_df, fit_summary = create_fit_df()
   ```
   - Context: Doctrine report display
   - Usage: Filters by doctrine_id

#### In Tests
5. **tests/test.py:15**
   ```python
   df = create_fit_df()
   ```

### Migration Path to DoctrineFacade
**Current Status**: Already has backwards-compatible wrapper

1. Replace direct calls with facade method:
   ```python
   facade = get_doctrine_facade()
   result = facade.build_fit_data()
   all_fits_df = result.raw_df
   summary_df = result.summary_df
   ```
 
2. Facade already implements via DoctrineService.build_fit_data()
   - Returns FitBuildResult with raw_df, summary_df, summaries, metadata
   - More typed and feature-rich than tuple return

---

## 2. get_fit_name() / get_fit_name_from_db()

### Definition Locations

**DUPLICATES DETECTED** - Two separate implementations in pages:

1. **doctrine_status.py:131-139** (get_fit_name)
   ```python
   def get_fit_name(fit_id: int) -> str:
       df = read_df(mkt_db, text("SELECT fit_name FROM ship_targets WHERE fit_id = ..."), ...)
       return str(df.loc[0, 'fit_name']) if not df.empty else "Unknown Fit"
   ```

2. **doctrine_report.py:62-73** (get_fit_name_from_db)
   ```python
   def get_fit_name_from_db(fit_id: int) -> str:
       df = read_df(mktdb, text("SELECT fit_name FROM ship_targets WHERE fit_id = ..."), ...)
       return str(df.loc[0, 'fit_name']) if not df.empty else "Unknown Fit"
   ```

**CENTRALIZED**:

3. **repositories/doctrine_repo.py:246-274** (get_fit_name)
   - Single source of truth implementation
   - Better error handling, logging

4. **facades/doctrine_facade.py:269-285** (get_fit_name)
   - Delegates to repository
   - Simplified API surface

### Call Sites (2 locations)

#### In Pages
1. **doctrine_status.py:104** (inside get_fit_summary loop)
   ```python
   fit_name = get_fit_name(fit_id)
   ```
   - Called for each fit in the summary loop
   - Assigns to fit_summary dictionary

2. **doctrine_report.py:299** (inside fit display loop)
   ```python
   fit_name = get_fit_name_from_db(fit_id)
   ```
   - Called for each fit in the report display
   - Shows fit name with target info

### Issues
- **Code Duplication**: Identical logic in two files (doctrine_status.py and doctrine_report.py)
- **Different Database Handles**: Uses different mkt_db vs mktdb configs
- **No Caching**: Called repeatedly in loops (N+1 query pattern)

### Migration Path to DoctrineFacade

1. **Replace doctrine_status.py usage**:
   ```python
   # BEFORE:
   fit_name = get_fit_name(fit_id)

   # AFTER:
   facade = get_doctrine_facade()
   fit_name = facade.get_fit_name(fit_id)
   ```

2. **Replace doctrine_report.py usage**:
   ```python
   # BEFORE:
   fit_name = get_fit_name_from_db(fit_id)

   # AFTER:
   facade = get_doctrine_facade()
   fit_name = facade.get_fit_name(fit_id)
   ```

3. **Remove local functions**:
   - Delete doctrine_status.py:131-139 (get_fit_name)
   - Delete doctrine_report.py:62-73 (get_fit_name_from_db)

4. **Add caching** (optional):
   - Facade could cache results in st.session_state to avoid N+1 queries

---

## 3. get_module_stock_list()

### Definition Locations

**DUPLICATES DETECTED** - Two implementations with slightly different logic:

1. **doctrine_status.py:141-221** (81 lines)
   - Includes detailed module usage calculation
   - Joins with ship_targets to show "Used in: fit_name(qty)" format
   - Has extended CSV export with usage data
   - Uses st.session_state for caching

2. **doctrine_report.py:21-51** (31 lines)
   - Simpler basic stock lookup
   - Only returns module info without usage details
   - Also uses st.session_state

**NOT YET CENTRALIZED** - No equivalent in repository or facade

### Call Sites (2 locations)

#### In Pages
1. **doctrine_status.py:897** (inside get_ship_stock_list callback)
   ```python
   get_module_stock_list(module_names)
   ```
   - Context: Module stock display fragment
   - Populates session state for rendering

2. **doctrine_report.py:352** (inside module selection loop)
   ```python
   get_module_stock_list([module_name])
   ```
   - Context: Updates stock when module selected
   - Stores in session state for display

### Issues
- **Code Duplication**: Almost identical queries with minor differences
- **Inconsistent Features**: doctrine_status version includes usage breakdown, doctrine_report doesn't
- **Session State Dependency**: Both tightly coupled to st.session_state
- **No Type Safety**: Returns None, only populates session state side effects

### Migration Path to DoctrineFacade

**RECOMMENDED APPROACH**: Consolidate into facade with both capabilities

1. **Create unified facade method**:
   ```python
   # In facades/doctrine_facade.py:
   def get_module_stock(self, module_name: str) -> Optional[ModuleStock]:
       """Returns typed ModuleStock with stock, usage, and formatted display strings"""
       return self.repository.get_module_stock(module_name)
   ```

2. **Replace doctrine_status.py**:
   ```python
   # BEFORE:
   get_module_stock_list(module_names)
   # Uses st.session_state side effects

   # AFTER:
   facade = get_doctrine_facade()
   for module_name in module_names:
       module = facade.get_module_stock(module_name)
       if module:
           st.session_state.module_list_state[module_name] = module.display_string
   ```

3. **Replace doctrine_report.py**:
   ```python
   # BEFORE:
   get_module_stock_list([module_name])

   # AFTER:
   facade = get_doctrine_facade()
   module = facade.get_module_stock(module_name)
   if module:
       st.session_state.module_list_state[module_name] = module.display_string
   ```

4. **Remove local functions**:
   - Delete doctrine_status.py:141-221
   - Delete doctrine_report.py:21-51

---

## 4. categorize_ship_by_role()

### Definition Locations

**DUPLICATES DETECTED**:

1. **doctrine_report.py:75-106** (original, 32 lines)
   ```python
   def categorize_ship_by_role(ship_name: str, fit_id: int) -> str:
       # Loads settings.toml on EVERY call (inefficient)
       # Returns string ("DPS", "Logi", "Links", "Support")
   ```

2. **services/categorization.py:274-299** (backwards-compatible wrapper)
   ```python
   def categorize_ship_by_role(ship_name: str, fit_id: int) -> str:
       categorizer = get_ship_role_categorizer()
       role = categorizer.categorize(ship_name, fit_id)
       return role.display_name
   ```

3. **facades/doctrine_facade.py:423-444** (typed method)
   ```python
   def categorize_ship(self, ship_name: str, fit_id: int) -> ShipRole:
       return self.categorizer.categorize(ship_name, fit_id)
   ```

### Call Sites (1 location)

#### In Pages
1. **doctrine_report.py:118** (in display_categorized_doctrine_data)
   ```python
   lambda row: categorize_ship_by_role(row['ship_name'], row['fit_id'])
   ```
   - Context: Applied to entire dataframe via apply()
   - Creates 'role' column for grouping display

### Issues
- **Performance**: Loads TOML file on EVERY call in original
- **No Caching**: ConfigBasedCategorizer fixes this, but page still uses old function
- **Type Safety**: Returns string instead of enum

### Migration Path to DoctrineFacade

1. **Replace doctrine_report.py usage**:
   ```python
   # BEFORE:
   selected_data_with_roles['role'] = selected_data_with_roles.apply(
       lambda row: categorize_ship_by_role(row['ship_name'], row['fit_id']),
       axis=1
   )

   # AFTER:
   facade = get_doctrine_facade()
   selected_data_with_roles['role'] = selected_data_with_roles.apply(
       lambda row: facade.categorize_ship(row['ship_name'], row['fit_id']).display_name,
       axis=1
   )
   ```

2. **Remove local function**:
   - Delete doctrine_report.py:75-106 (original)
   - Keep services/categorization.py wrapper for backwards compatibility

3. **Better approach** - vectorized:
   ```python
   facade = get_doctrine_facade()
   # If categorizer could handle Series input, do vectorized operation
   selected_data_with_roles['role'] = vectorized_categorize(...)
   ```

---

## 5. calculate_jita_fit_cost_and_delta()

### Definition Locations

**DUPLICATES DETECTED**:

1. **doctrines.py:177-230** (original, ~50 lines)
   - Manual price fetching with N+1 query pattern
   - Calculates delta percentage

2. **services/price_service.py:802-815** (backwards-compatible wrapper)
   ```python
   def calculate_jita_fit_cost_and_delta(fit_data, current_fit_cost, jita_price_map=None):
       service = get_price_service()
       analysis = service.analyze_fit_cost(fit_data, current_fit_cost, jita_price_map)
       return analysis.jita_cost, analysis.delta_percentage
   ```

3. **services/price_service.py** (full implementation)
   - Better error handling
   - Batch price fetching
   - Supports pre-populated jita_price_map

### Call Sites (1 location)

#### In Pages
1. **doctrine_status.py:479** (in update_jita_deltas_cache function)
   ```python
   jita_fit_cost, jita_cost_delta = calculate_jita_fit_cost_and_delta(
       fit_data, total_cost, jita_price_map
   )
   ```
   - Context: Caches Jita price calculations for all fits
   - Uses pre-fetched jita_price_map for efficiency
   - Stores results in st.session_state

### Issues
- **Already Has Wrapper**: Forwards to PriceService.analyze_fit_cost()
- **Type Safety**: Could return typed FitCostAnalysis instead of tuple
- **API Mismatch**: Facade doesn't expose this directly, only calculate_fit_jita_delta(fit_id)

### Migration Path to DoctrineFacade

1. **Current state**: Service already has wrapper, but page imports from doctrines.py

2. **Add to facade** (if not already present):
   ```python
   def calculate_fit_jita_analysis(self, fit_data: pd.DataFrame,
                                   current_cost: float) -> FitCostAnalysis:
       return self.price_service.analyze_fit_cost(fit_data, current_cost)
   ```

3. **Replace doctrine_status.py usage**:
   ```python
   # BEFORE:
   from doctrines import calculate_jita_fit_cost_and_delta
   jita_fit_cost, jita_cost_delta = calculate_jita_fit_cost_and_delta(
       fit_data, total_cost, jita_price_map
   )

   # AFTER:
   facade = get_doctrine_facade()
   analysis = facade.calculate_fit_jita_analysis(fit_data, total_cost)
   jita_fit_cost = analysis.jita_cost
   jita_cost_delta = analysis.delta_percentage
   ```

---

## 6. get_ship_target()

### Definition Location

**UNIQUE** - Only defined in doctrine_status.py:279-309

```python
def get_ship_target(ship_id: int, fit_id: int) -> int:
    """Get the target for a given ship id or fit id
    if searching by ship_id, enter zero for fit_id
    if searching by fit_id, enter zero for ship_id
    """
    # Handles two different query paths based on which ID is provided
    # Returns int target, default 20
```

### Call Sites (2 locations)

#### In Pages
1. **doctrine_status.py:80** (in get_fit_summary loop)
   ```python
   target = get_ship_target(0, fit_id)
   ```
   - Context: Gets target for each fit
   - Uses fit_id=0 query path
   - Calculates target_percentage

2. **doctrine_status.py:259** (in get_ship_stock_list function)
   ```python
   ship_target = get_ship_target(ship_id, 0)
   ```
   - Context: Gets target for each ship
   - Uses ship_id=0 query path
   - Displays in stock info

### Centralized Implementation

**Repository** has split this into two methods:
- `get_target_by_fit_id(fit_id)` - doctrine_repo.py:185-212
- `get_target_by_ship_id(ship_id)` - doctrine_repo.py:214-239

**Facade** delegates to repository

### Issues
- **Dual-Purpose Function**: Confusing API with magic 0 values
- **Not Yet Moved**: Still defined in doctrine_status.py (should be removed)

### Migration Path to DoctrineFacade

1. **Replace both call sites**:
   ```python
   # BEFORE (fit_id lookup):
   target = get_ship_target(0, fit_id)

   # AFTER:
   facade = get_doctrine_facade()
   target = facade.repository.get_target_by_fit_id(fit_id)

   # OR add convenience method to facade:
   # target = facade.get_fit_target(fit_id)

   # BEFORE (ship_id lookup):
   ship_target = get_ship_target(ship_id, 0)

   # AFTER:
   facade = get_doctrine_facade()
   ship_target = facade.repository.get_target_by_ship_id(ship_id)
   ```

2. **Remove local function**:
   - Delete doctrine_status.py:279-309

3. **Add facade convenience methods** (optional):
   ```python
   class DoctrineFacade:
       def get_fit_target(self, fit_id: int) -> int:
           return self.repository.get_target_by_fit_id(fit_id)

       def get_ship_target(self, ship_id: int) -> int:
           return self.repository.get_target_by_ship_id(ship_id)
   ```

---

## 7. get_doctrine_lead_ship()

### Definition Locations

**DUPLICATES DETECTED**:

1. **doctrine_report.py:53-60** (original)
   ```python
   def get_doctrine_lead_ship(doctrine_id: int) -> int:
       query = text("SELECT lead_ship FROM lead_ships WHERE doctrine_id = ...")
       df = read_df(mktdb, query, {"doctrine_id": doctrine_id})
       return int(lead_ship) if pd.notna(lead_ship) else None
   ```

2. **repositories/doctrine_repo.py:316-341** (centralized)
   - Better error handling, logging
   - Consistent with other repository methods

3. **facades/doctrine_facade.py:400-417** (facade method)
   - Delegates to repository
   - Type-safe Optional[int] return

### Call Sites (1 location)

#### In Pages
1. **doctrine_report.py:432** (in main display)
   ```python
   lead_ship_id = get_doctrine_lead_ship(selected_doctrine_id)
   ```
   - Context: Gets lead ship image for doctrine header
   - Constructs image URL: f"https://images.evetech.net/types/{lead_ship_id}/render?size=256"

### Issues
- **Code Duplication**: Identical SQL query in two locations
- **No Error Handling**: Returns None without logging
- **Type Confusion**: Returns int but could be None (type hint issue)

### Migration Path to DoctrineFacade

1. **Replace doctrine_report.py usage**:
   ```python
   # BEFORE:
   lead_ship_id = get_doctrine_lead_ship(selected_doctrine_id)
   lead_ship_image_url = f"https://images.evetech.net/types/{lead_ship_id}/render?size=256"

   # AFTER:
   facade = get_doctrine_facade()
   lead_ship_id = facade.get_doctrine_lead_ship(selected_doctrine_id)
   if lead_ship_id:
       lead_ship_image_url = f"https://images.evetech.net/types/{lead_ship_id}/render?size=256"
   ```

2. **Remove local function**:
   - Delete doctrine_report.py:53-60

---

## Refactoring Priority Matrix

### HIGH PRIORITY (Quick wins with high impact)

1. **get_fit_name()** / **get_fit_name_from_db()**
   - Impact: 2 duplicate definitions causing inconsistency
   - Effort: Low (2 simple replacements + 2 function deletions)
   - Lines Removed: ~45 total
   - Benefit: Single source of truth, potential for caching

2. **get_doctrine_lead_ship()**
   - Impact: 1 duplicate, used in report generation
   - Effort: Low (1 replacement + 1 deletion)
   - Lines Removed: ~8
   - Benefit: Consistent error handling, logging

3. **get_ship_target()**
   - Impact: Confusing dual-purpose API
   - Effort: Low (2 replacements + 1 deletion)
   - Lines Removed: ~31
   - Benefit: Clearer intent with split methods

### MEDIUM PRIORITY (Requires coordination)

4. **categorize_ship_by_role()**
   - Impact: Performance issue (loads TOML on every call)
   - Effort: Medium (DataFrame.apply refactoring, enum handling)
   - Lines Removed: ~32 (original definition)
   - Benefit: Better performance, type safety

5. **get_module_stock_list()**
   - Impact: ~160 lines of duplicate/inconsistent logic
   - Effort: Medium (consolidate, handle session state differently)
   - Lines Removed: ~110 total
   - Benefit: Single implementation, consistent UI behavior

### LOW PRIORITY (Already refactored)

6. **calculate_jita_fit_cost_and_delta()**
   - Status: Already has backwards-compatible wrapper
   - Effort: Low (1 import change)
   - Benefit: Type safety improvement

7. **create_fit_df()**
   - Status: Already has backwards-compatible wrapper
   - Effort: Low (migrate to FitBuildResult)
   - Benefit: Access to metadata and typed return

---

## Consolidated Migration Checklist

### Phase 1: Eliminate Duplicates (get_fit_name, get_doctrine_lead_ship, get_ship_target)

- [ ] doctrine_status.py:104 - Replace get_fit_name() call
- [ ] doctrine_report.py:299 - Replace get_fit_name_from_db() call
- [ ] doctrine_report.py:432 - Replace get_doctrine_lead_ship() call
- [ ] doctrine_status.py:80 - Replace get_ship_target(0, fit_id) call
- [ ] doctrine_status.py:259 - Replace get_ship_target(ship_id, 0) call
- [ ] Delete doctrine_status.py:131-139 (get_fit_name)
- [ ] Delete doctrine_status.py:279-309 (get_ship_target)
- [ ] Delete doctrine_report.py:53-60 (get_doctrine_lead_ship)
- [ ] Delete doctrine_report.py:62-73 (get_fit_name_from_db)

### Phase 2: Consolidate Complex Functions (get_module_stock_list, categorize_ship_by_role)

- [ ] Add facade.get_module_stock(module_name) method
- [ ] Update doctrine_status.py:897 to use facade
- [ ] Update doctrine_report.py:352 to use facade
- [ ] Add facade.get_fit_target(fit_id) convenience method
- [ ] Add facade.get_ship_target(ship_id) convenience method
- [ ] Update doctrine_report.py:118 apply() to use facade.categorize_ship()
- [ ] Delete doctrine_status.py:141-221 (get_module_stock_list)
- [ ] Delete doctrine_report.py:21-51 (get_module_stock_list)
- [ ] Delete doctrine_report.py:75-106 (categorize_ship_by_role)

### Phase 3: Update Complex Functions (create_fit_df, calculate_jita_fit_cost_and_delta)

- [ ] doctrine_status.py:26 - Replace create_fit_df() with facade.build_fit_data()
- [ ] doctrine_status.py:271 - Replace create_fit_df() with facade.build_fit_data()
- [ ] doctrine_status.py:446 - Replace create_fit_df() with facade.build_fit_data()
- [ ] doctrine_report.py:396 - Replace create_fit_df() with facade.build_fit_data()
- [ ] doctrine_status.py:479 - Replace calculate_jita_fit_cost_and_delta() with facade method

---

## Summary Statistics

### Code Duplication
- **get_fit_name**: 2 implementations (identical logic)
- **get_module_stock_list**: 2 implementations (~160 lines total, slightly different)
- **categorize_ship_by_role**: 2 implementations (original + wrapper)
- **calculate_jita_fit_cost_and_delta**: 2 implementations (original + wrapper)
- **get_doctrine_lead_ship**: 2 implementations (identical logic)

### Total Duplicated Logic
- **Duplicate Lines**: ~275 lines of redundant code
- **Removable Lines**: ~175 lines of local function definitions in pages
- **Consolidatable Lines**: ~110 lines of get_module_stock_list variants

### Migration Impact
- **Files Affected**: doctrine_status.py, doctrine_report.py
- **Total Call Sites**: 12 locations
- **Functions to Remove**: 7 local function definitions
- **Facade Methods to Use**: 8 existing methods

### Expected Improvements
1. Single source of truth for all doctrine queries
2. Consistent error handling and logging
3. Type-safe returns (enums, domain models)
4. Performance improvement (cached categorizer, batched queries)
5. Reduced code duplication (~175 lines removed)
6. Streamlined page code (simpler, more readable)
