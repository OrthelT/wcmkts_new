# Function Usage Analysis - Documentation Index

This directory contains a comprehensive analysis of function usage across the refactordoctrines codebase, with a focus on refactoring opportunities within `pages/doctrine_status.py` and `pages/doctrine_report.py`.

## Documents

### 1. ANALYSIS_SUMMARY.txt
**Executive Summary and Checklists**

- High-level overview of all 7 functions analyzed
- Key findings highlighting critical issues
- Refactoring priorities organized by phase (HIGH/MEDIUM/LOW)
- Facade readiness assessment
- Implementation checklist for each phase
- Risk assessment and testing strategy

**Start here** if you want a quick overview or to understand priorities.

### 2. FUNCTION_USAGE_ANALYSIS.md
**Detailed Technical Analysis**

Comprehensive analysis of each function including:

1. **create_fit_df()**
   - Definition locations (original + wrapper)
   - 4 call sites in pages, 1 in tests
   - Migration path to FitBuildResult

2. **get_fit_name() / get_fit_name_from_db()**
   - DUPLICATE: Identical logic in 2 files
   - Centralized implementation exists in repository/facade
   - 2 call sites, N+1 query pattern identified

3. **get_module_stock_list()**
   - DUPLICATE: 2 implementations with inconsistent features
   - NOT YET CENTRALIZED - needs facade implementation
   - 2 call sites, session state dependency

4. **categorize_ship_by_role()**
   - DUPLICATE: Original has TOML loading inefficiency
   - Wrapper exists with caching fix
   - 1 call site with DataFrame.apply()

5. **calculate_jita_fit_cost_and_delta()**
   - Wrapper exists, already refactored
   - 1 call site in Jita delta calculation
   - Could return typed object instead of tuple

6. **get_ship_target()**
   - UNIQUE: Only defined in doctrine_status.py
   - Confusing dual-purpose API with "magic zeros"
   - Split into repository methods: get_target_by_fit_id() and get_target_by_ship_id()
   - 2 call sites needing refactor

7. **get_doctrine_lead_ship()**
   - DUPLICATE: Identical query logic in 2 files
   - Centralized implementation exists
   - 1 call site in report header

**Use this** for detailed understanding of each function's status and migration path.

### 3. MIGRATION_EXAMPLES.md
**Side-by-Side Code Examples**

Practical before/after examples for each function migration:

1. get_fit_name() - doctrine_status.py:104
2. get_fit_name_from_db() - doctrine_report.py:299
3. get_doctrine_lead_ship() - doctrine_report.py:432
4. get_ship_target() - doctrine_status.py:80 & :259
5. categorize_ship_by_role() - doctrine_report.py:118
6. create_fit_df() - doctrine_status.py:26, :271, :446 & doctrine_report.py:396
7. get_module_stock_list() - doctrine_status.py:897 & doctrine_report.py:352
8. calculate_jita_fit_cost_and_delta() - doctrine_status.py:479

Each example shows:
- Original code with locations
- Refactored code using facade
- Benefits of migration
- Optional improvements

**Use this** when implementing the actual refactoring.

## Quick Navigation

### By Priority

**HIGH PRIORITY (Phase 1)** - ~84 lines saved, 5 call sites
- [get_fit_name()](FUNCTION_USAGE_ANALYSIS.md#2-get_fit_name--get_fit_name_from_db)
- [get_doctrine_lead_ship()](FUNCTION_USAGE_ANALYSIS.md#7-get_doctrine_lead_ship)
- [get_ship_target()](FUNCTION_USAGE_ANALYSIS.md#6-get_ship_target)

**MEDIUM PRIORITY (Phase 2)** - ~142 lines saved, 3 call sites
- [get_module_stock_list()](FUNCTION_USAGE_ANALYSIS.md#3-get_module_stock_list)
- [categorize_ship_by_role()](FUNCTION_USAGE_ANALYSIS.md#4-categorize_ship_by_role)

**LOW PRIORITY (Phase 3)** - Already refactored
- [create_fit_df()](FUNCTION_USAGE_ANALYSIS.md#1-create_fit_df)
- [calculate_jita_fit_cost_and_delta()](FUNCTION_USAGE_ANALYSIS.md#5-calculate_jita_fit_cost_and_delta)

### By File

**doctrine_status.py** (13 instances across 5 call sites, 3 function deletions)
- Line 26: create_fit_df()
- Line 80: get_ship_target(0, fit_id)
- Line 104: get_fit_name()
- Line 131-139: DELETE get_fit_name() function
- Line 141-221: DELETE get_module_stock_list() function
- Line 259: get_ship_target(ship_id, 0)
- Line 271: create_fit_df()
- Line 279-309: DELETE get_ship_target() function
- Line 446: create_fit_df()
- Line 479: calculate_jita_fit_cost_and_delta()
- Line 897: get_module_stock_list()

**doctrine_report.py** (10 instances across 4 call sites, 4 function deletions)
- Line 21-51: DELETE get_module_stock_list() function
- Line 53-60: DELETE get_doctrine_lead_ship() function
- Line 62-73: DELETE get_fit_name_from_db() function
- Line 75-106: DELETE categorize_ship_by_role() function
- Line 118: categorize_ship_by_role() in apply()
- Line 299: get_fit_name_from_db()
- Line 352: get_module_stock_list()
- Line 396: create_fit_df()
- Line 432: get_doctrine_lead_ship()

### By Status

**DUPLICATES (Must consolidate)**
- get_fit_name (2 files, identical)
- get_fit_name_from_db (1 file, identical to above)
- get_module_stock_list (2 files, slightly different)
- categorize_ship_by_role (2 implementations, performance issue)
- get_doctrine_lead_ship (1 file, needs facade)

**ALREADY CENTRALIZED (Ready to use)**
- create_fit_df (wrapper in services/doctrine_service.py:1010)
- calculate_jita_fit_cost_and_delta (wrapper in services/price_service.py:802)
- categorize_ship_by_role (wrapper in services/categorization.py:274)
- get_fit_name (in repository.py:246, facade.py:269)
- get_doctrine_lead_ship (in repository.py:316, facade.py:400)
- get_ship_target (split: repository.py:185 & :214)

**NOT YET CENTRALIZED (Needs work)**
- get_module_stock_list (needs facade.get_module_stock method)

## Key Statistics

- **Total Functions Analyzed**: 7
- **Code Duplication**: ~275 lines
- **Lines Removable**: ~175 lines
- **Lines Consolidated**: ~226 lines
- **Total Call Sites**: 13 locations
- **Functions to Delete**: 7 local definitions
- **Files Affected**: 2 primary (doctrine_status.py, doctrine_report.py)
- **Facade Methods Ready**: 6+
- **Facade Methods Needed**: 1

## Implementation Path

### Phase 1: HIGH PRIORITY
Expected duration: 2-3 hours
- Migrate get_fit_name() (2 call sites, 2 function deletions)
- Migrate get_doctrine_lead_ship() (1 call site, 1 function deletion)
- Migrate get_ship_target() (2 call sites, 1 function deletion)

### Phase 2: MEDIUM PRIORITY
Expected duration: 3-4 hours
- Add facade.get_module_stock() method
- Migrate get_module_stock_list() (2 call sites, 2 function deletions)
- Migrate categorize_ship_by_role() (1 call site, 1 function deletion)

### Phase 3: LOW PRIORITY
Expected duration: 1-2 hours
- Migrate create_fit_df() (4 call sites, no deletions)
- Migrate calculate_jita_fit_cost_and_delta() (1 call site, no deletions)

## Facade Readiness Matrix

| Function | Facade Method | Status | Notes |
|----------|---------------|--------|-------|
| get_fit_name | facade.get_fit_name() | READY | Uses repository.py:246 |
| get_fit_name_from_db | facade.get_fit_name() | READY | Same as above |
| get_doctrine_lead_ship | facade.get_doctrine_lead_ship() | READY | Uses repository.py:316 |
| get_ship_target (fit) | facade.repository.get_target_by_fit_id() | READY | Could add convenience method |
| get_ship_target (ship) | facade.repository.get_target_by_ship_id() | READY | Could add convenience method |
| get_module_stock_list | facade.get_module_stock() | NEEDS ADD | Must implement |
| categorize_ship_by_role | facade.categorize_ship() | READY | Returns ShipRole enum |
| create_fit_df | facade.build_fit_data() | READY | Returns FitBuildResult |
| calculate_jita_fit_cost_and_delta | facade.price_service.analyze_fit_cost() | READY | Could add convenience method |

## Related Documents

- `REFACTOR_PLAN.md` - Overall refactoring strategy
- `PHASE_6_PROMPT.md` - Phase 6 specific tasks
- `simplification_options.md` - Alternative approaches discussed
- `domain/models.py` - Domain model definitions
- `repositories/doctrine_repo.py` - Centralized database access
- `facades/doctrine_facade.py` - Facade implementation
- `services/doctrine_service.py` - Business logic services

## Recommendations

1. **Start with Phase 1** - Quick wins with minimal risk
   - All methods already exist and are tested
   - Clear direct replacements
   - No new facade methods needed

2. **Batch migration** - Don't mix with other refactoring
   - Each phase should be isolated
   - One commit per function group
   - Test after each phase

3. **Update tests** - Add facade usage tests
   - Move test imports from pages to facade
   - Add integration tests for pages
   - Verify session state handling

4. **Consider caching** - Future improvement
   - get_fit_name could cache in session state
   - Would eliminate N+1 query pattern
   - Could be added after consolidation

5. **Performance testing** - Especially for categorize_ship_by_role
   - Verify TOML caching works as expected
   - Benchmark before/after
   - Test with large datasets

## Questions?

For detailed information about a specific function, see:
- `FUNCTION_USAGE_ANALYSIS.md` - Technical details
- `MIGRATION_EXAMPLES.md` - Code examples
- `ANALYSIS_SUMMARY.txt` - Quick reference

For implementation guidance:
- `MIGRATION_EXAMPLES.md` - Before/after code
- `ANALYSIS_SUMMARY.txt` - Checklists and tasks
- Repository source code - Actual implementations
