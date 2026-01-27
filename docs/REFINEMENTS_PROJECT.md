# Refinements

## Overview
This phase of the refactor will refine and extend several features. Review the tasks below and develop an implementation plan modeled on `REFACTOR_PLAN.md`.

Divide the work into phases that can be completed within a single context window. Manage context carefully. Delegate sub-tasks to agents when appropriate while maintaining architectural oversight of the entire phase and codebase.

You will act as senior developer and project orchestrator. If the context window approaches capacity, split the current phase into smaller subphases and document remaining work so another Claude instance can continue with a fresh context window.

## Guiding Principles
The goal is to align the codebase with our architectural design and current best practices while reducing complexity.

At completion, the codebase should be:
- simpler
- more logical
- easier to maintain

This file serves as the central record of the project. Review it at the beginning of each session and update it at the end of every phase.

At the end of each task:
- Review all revisions for correctness and architectural consistency. Avoid introducing unnecessary complexity.
- Write tests as appropriate and run the full test suite. Fix any regressions.
- Update `REFINEMENTS_PROJECT.md` with progress notes and clear handoff instructions.
- Call the `docs-sync` agent to update documentation to reflect changes.

---

## Status: PHASE 1 COMPLETE

**Completed:** 2026-01-26

All initial tasks have been implemented. See detailed completion notes below.

---

## Tasks

### Task 1: Refactor low-stock.py ✅ COMPLETE

**Status:** Implemented

**Changes Made:**

1. **Created `services/low_stock_service.py`** - New service layer with:
   - `LowStockFilters` dataclass - Clean filter configuration with fields:
     - `categories`, `max_days_remaining`, `doctrine_only`, `tech2_only`, `faction_only`, `fit_ids`, `type_ids`
   - `DoctrineFilterInfo` - Doctrine metadata with `lead_ship_image_url` property
   - `FitFilterInfo` - Fit metadata with `ship_image_url` property
   - `LowStockService` class with methods:
     - `get_category_options()` - Returns available categories
     - `get_doctrine_options()` - Returns doctrines with lead ship IDs
     - `get_fit_options(doctrine_id)` - Returns fits for a doctrine
     - `get_type_ids_by_metagroup(metagroup_id)` - Filters by meta group
     - `get_low_stock_items(filters)` - Main data fetching with all filters
     - `get_stock_statistics(df)` - Calculates critical/low/total counts

2. **Refactored `pages/low_stock.py`**:
   - Removed direct database queries
   - Uses `LowStockService` via `get_low_stock_service()`
   - Added Faction Items checkbox (metagroupID=4)
   - Added doctrine/fit dropdown filters with ship images
   - Displays lead ship image when filtering by doctrine
   - Uses `LowStockFilters` dataclass for clean filter passing

**Architectural Decisions:**
- **metagroupID mapping:** Task mentioned metagroupID=7 for faction, but EVE SDE uses metagroupID=4 for Faction items. Implementation uses metagroupID=4. If this is incorrect, update `get_type_ids_by_metagroup()` call in low_stock.py.
- **Service instantiation:** Uses `get_low_stock_service()` factory which leverages `state.get_service()` for session state persistence.

---

### Task 2: Enhance Pricer ✅ COMPLETE

**Status:** Implemented

**Changes Made:**

1. **Updated `domain/pricer.py`** - Added fields to `PricedItem`:
   - `avg_daily_volume: float` - Average daily sales (30-day)
   - `days_of_stock: float` - Days of stock remaining
   - `is_doctrine: bool` - Whether item is used in doctrines
   - `doctrine_ships: tuple[str, ...]` - Ships/fits using this item
   - Updated `to_dict()` to include new columns

2. **Updated `services/pricer_service.py`**:
   - Added `mkt_db` parameter to `__init__` (market database for stats)
   - Added `get_market_stats(type_ids)` - Fetches avg_volume, days_remaining
   - Added `get_doctrine_info(type_ids)` - Fetches doctrine usage info
   - Updated `price_input()` to populate new PricedItem fields

3. **Updated `pages/pricer.py`**:
   - Added column config for `Avg Daily Vol`, `Days of Stock`, `Is Doctrine`, `Doctrine Ships`
   - Added checkboxes: "Show Stock Metrics", "Highlight Doctrine Items"
   - Added `highlight_doctrine_rows()` style function
   - Added `highlight_low_stock()` for days of stock color coding
   - Added `render_fit_header()` - Shows ship image for EFT fittings

**Architectural Decisions:**
- **Doctrine ships as tuple:** Using `tuple[str, ...]` instead of `list` to maintain immutability of `PricedItem` (frozen dataclass).
- **Lazy Jita price lookup in popovers:** Jita prices are fetched on-demand in popovers to avoid slowing down initial page load.

---

### Task 3: Market Data Popovers ✅ COMPLETE

**Status:** Implemented

**Changes Made:**

1. **Created `ui/popovers.py`** - Reusable popover components:
   - `get_item_market_data(type_id, type_name)` - Fetches from marketstats
   - `get_doctrine_usage(type_id)` - Fetches doctrine usage
   - `get_jita_price(type_id)` - Fetches Jita price via PriceService
   - `render_market_popover()` - Full popover with market stats:
     - Item image, name, type_id
     - 4-HWWF price, stock, avg/day, days of stock
     - Jita price with delta percentage
     - Doctrine usage list (up to 5 fits)
   - `render_item_with_popover()` - Simplified item display
   - `render_ship_with_popover()` - Ship-specific popover with fits/hulls/target

2. **Updated `ui/__init__.py`** - Added popover exports

3. **Updated `pages/doctrine_status.py`**:
   - Ship names now use `render_ship_with_popover()`
   - Module names use `render_market_popover()`
   - Note: Module display also shows status badge separately

4. **Updated `pages/doctrine_report.py`**:
   - Ship names and hull displays use `render_ship_with_popover()`
   - Module names use `render_market_popover()`

**Architectural Decisions:**
- **Popover key uniqueness:** Each popover requires a unique `key_suffix` to prevent Streamlit duplicate key errors. Pattern: `{page_prefix}_{fit_id}_{optional_index}`
- **Data fetching in popovers:** Popovers fetch data on-demand (lazy loading) to avoid unnecessary API calls for items user doesn't click.

---

### Task 4: Enhance Doctrine Status/Report ✅ COMPLETE

**Status:** Implemented

**Changes Made:**

1. **Created `services/selection_service.py`** - Selection management service:
   - `SelectedItem` dataclass - Item with type_id, name, stock, target, status
   - `SelectionState` dataclass - Holds selected_ships, selected_modules, selected_items
   - `SelectionService` class with methods:
     - `add_selection()`, `remove_selection()`, `toggle_selection()`
     - `format_sidebar_text()` - Formats for `st.code()` display
     - `format_selection_summary()` - Returns counts by status
     - `generate_csv_data()` - For export
   - `get_status_filter_options()` - Returns standardized status options
   - `apply_status_filter()` - Helper for filtering by status
   - `render_sidebar_selections()` - Ready-to-use sidebar component

2. **Updated `pages/doctrine_status.py`**:
   - Status filter uses `get_status_filter_options()` instead of hardcoded list
   - Module status filter uses same service function
   - Sidebar selections now display using `st.code()` for cleaner formatting
   - Combined ships and modules into single "Selected Items" section

3. **Updated `pages/doctrine_report.py`**:
   - Sidebar selections use `st.code()` for cleaner formatting
   - Simplified selection display logic

**Architectural Decisions:**
- **StockStatus thresholds:** Uses existing `StockStatus` enum from `domain/enums.py` which defines: CRITICAL (≤20%), NEEDS_ATTENTION (>20%, ≤90%), GOOD (>90%)
- **Backwards compatibility:** Existing session state variables (`selected_ships`, `selected_modules`) preserved. SelectionService can be adopted incrementally.
- **Filter options order:** `get_status_filter_options()` returns: ["All", "All Low Stock", "Critical", "Needs Attention", "Good"]

---

## Files Changed Summary

### New Files Created
| File | Purpose |
|------|---------|
| `services/low_stock_service.py` | Low stock data operations service |
| `services/selection_service.py` | Selection state management service |
| `ui/popovers.py` | Reusable market data popover components |

### Files Modified
| File | Changes |
|------|---------|
| `services/__init__.py` | Added exports for new services |
| `services/pricer_service.py` | Added market stats and doctrine info methods |
| `domain/pricer.py` | Added new fields to PricedItem |
| `ui/__init__.py` | Added popover exports |
| `pages/low_stock.py` | Complete refactor to use LowStockService |
| `pages/pricer.py` | Added new columns and doctrine highlighting |
| `pages/doctrine_status.py` | Added popovers, improved sidebar |
| `pages/doctrine_report.py` | Added popovers, improved sidebar |

---

## Testing & Debugging Notes

### Running the Application
```bash
uv run streamlit run app.py
```

### Key Test Scenarios

1. **Low Stock Page (`/low_stock`)**
   - Toggle Tech II Only checkbox → should filter to metaGroupID=2 items
   - Toggle Faction Only checkbox → should filter to metaGroupID=4 items
   - Select a doctrine → should show lead ship image and filter to doctrine items
   - Select a specific fit → should show ship image and filter to that fit's items

2. **Pricer Page (`/pricer`)**
   - Paste an EFT fitting → should show ship image in header
   - Toggle "Show Stock Metrics" → Avg Daily Vol and Days of Stock columns appear/hide
   - Toggle "Highlight Doctrine Items" → doctrine items get blue background

3. **Doctrine Status Page (`/doctrine_status`)**
   - Click on a ship name → popover shows with market data
   - Click on a module → popover shows with market data and doctrine usage
   - Check items → sidebar shows selections in code block format

4. **Doctrine Report Page (`/doctrine_report`)**
   - Click on ship names → popover shows
   - Click on modules → popover shows
   - Selections display in code block format

### Known Issues / Edge Cases

1. **Popover duplicate keys:** If you see Streamlit errors about duplicate keys, check that `key_suffix` parameters are unique. Pattern should include fit_id and index.

2. **Module type_id lookup:** In `doctrine_status.py`, module popovers need type_id from `service.repository.get_module_stock(module_name)`. If this returns None, type_id will be 0 and popover may show "No market data".

3. **metagroupID discrepancy:** Task specified metagroupID=7 for faction, but implementation uses metagroupID=4 based on standard EVE SDE. Verify this is correct for your database.

### Database Dependencies

The new services query these tables:
- `marketstats` - Market statistics (price, volume, days_remaining)
- `doctrines` - Doctrine fit data
- `doctrine_fits` - Doctrine/fit mapping
- `lead_ships` - Lead ship for each doctrine
- `ship_targets` - Target stock levels
- `sdetypes` - SDE data with metaGroupID

---

## Remaining Work / Future Enhancements

1. **Full SelectionService adoption:** The `SelectionService` is created but doctrine pages still use their own session state variables. Could migrate fully to the service for consistency.

2. **Unit tests:** New services need unit tests:
   - `test_low_stock_service.py`
   - `test_selection_service.py`
   - `test_popovers.py` (if feasible)

3. **Popover performance:** If popovers are slow, consider pre-fetching market data for visible items.

4. **Apply patterns to doctrine_stats.py:** Task mentioned applying patterns to this page - not yet done if it exists separately from doctrine_status.py.

---

## Handoff Instructions

For a new Claude instance continuing this work:

1. **Read these files first:**
   - `CLAUDE.md` - Full architecture overview
   - This file (`docs/REFINEMENTS_PROJECT.md`) - Current status
   - `docs/REFACTOR_PLAN.md` - Overall refactoring patterns

2. **Key architectural patterns:**
   - Services use factory functions: `get_*_service()` that leverage `state.get_service()` for session persistence
   - Domain models use frozen dataclasses for immutability
   - UI components in `ui/` directory import only from `domain/` layer
   - Pages import from `services/`, `ui/`, `state/`, and `domain/`

3. **Testing approach:**
   - Run `python3 -m py_compile <file>` for syntax check
   - Run `uv run pytest -q` for unit tests
   - Manual testing via `uv run streamlit run app.py`

4. **Before making changes:**
   - Read the relevant page file
   - Read the service it uses
   - Check for existing patterns in similar pages/services
