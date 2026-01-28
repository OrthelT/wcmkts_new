# Phase 8 Progress Tracker

## Status: PLANNING COMPLETE - AWAITING APPROVAL

**Created:** 2026-01-28
**Last Updated:** 2026-01-28

---

## Sub-Phase Status

| Sub-Phase | Description | Status | Notes |
|-----------|-------------|--------|-------|
| 8A | Remove Popovers | NOT STARTED | Highest priority - performance |
| 8B | Fix Data Flow | NOT STARTED | High priority - eliminate redundancy |
| 8C | Merge Filters + Doctrine Filter | NOT STARTED | Simplicity |
| 8D | Implement Forms | NOT STARTED | UX - prevent checkbox reruns |
| 8E | Merge Selection Lists | NOT STARTED | Simplicity |

---

## Handoff Instructions

### For New Claude Instance Starting Phase 8

1. **Read these files first:**
   - `CLAUDE.md` - Architecture overview
   - `docs/REFINEMENTS_PROJECT.md` - Project context and prior phases
   - `docs/PHASE8_PROGRESS.md` (this file) - Current status

2. **Current state of codebase:**
   - Phase 7 complete (module_equivalents table + popover prefetching)
   - But popover approach has fundamental Streamlit limitation
   - doctrine_status.py has redundant data flow (builds summary twice)
   - Tests: 37 passing

3. **Key architectural patterns:**
   - Services use factory functions: `get_*_service()`
   - Domain models are frozen dataclasses
   - Layered architecture: pages → services → repositories → domain

4. **Start with Sub-Phase 8A** (remove popovers) - it's the quickest win

---

## Detailed Progress Log

### Sub-Phase 8A: Remove Popovers

**Status:** NOT STARTED

**Tasks:**
- [ ] Remove popover imports from doctrine_status.py (line 15)
- [ ] Delete `prefetch_popover_data()` function (lines ~211-263)
- [ ] Replace `render_ship_with_popover()` calls with simple text
- [ ] Replace `render_market_popover()` calls with simple text
- [ ] Remove `has_equivalent_modules()` calls
- [ ] Verify syntax: `python -m py_compile pages/doctrine_status.py`
- [ ] Run tests: `uv run pytest -q`
- [ ] Manual test: page loads, ships/modules display correctly

---

### Sub-Phase 8B: Fix Data Flow

**Status:** NOT STARTED

**Tasks:**
- [ ] In doctrine_service.py `merge_targets()`: include fit_name column
- [ ] In doctrine_service.py `finalize_columns()`: add fit_name to expected_columns
- [ ] In doctrine_service.py `build()`: add lowest_modules to summary_df
- [ ] In doctrine_status.py: delete `get_fit_summary()` function
- [ ] In doctrine_status.py: use summary_df directly
- [ ] Fix row['fit'] → row['fit_name'] access
- [ ] Verify fit names display correctly (not blank)
- [ ] Run tests: `uv run pytest -q`

---

### Sub-Phase 8C: Merge Filters + Doctrine Filter

**Status:** NOT STARTED

**Tasks:**
- [ ] Add doctrine filter selectbox in sidebar
- [ ] Apply doctrine filter to filtered_df
- [ ] Remove "Module Status" selectbox
- [ ] Rename "Doctrine Status" to "Stock Status"
- [ ] Remove all `selected_module_status` filtering logic
- [ ] Run tests and manual verification

---

### Sub-Phase 8D: Implement Forms

**Status:** NOT STARTED

**Tasks:**
- [ ] Wrap main fit display loop in `st.form()`
- [ ] Restructure to 3 columns: col1 (image), col2 (tabs), col3 (checkboxes)
- [ ] Move ship name above ship image in col1
- [ ] Move ship checkbox to col3 (top of selection list)
- [ ] Remove "Low Stock Module" label
- [ ] Add form submit button
- [ ] Process all checkbox states on submit
- [ ] Test that checkbox clicks don't cause immediate reruns
- [ ] Run tests and manual verification

---

### Sub-Phase 8E: Merge Selection Lists

**Status:** NOT STARTED

**Tasks:**
- [ ] Import SelectionService
- [ ] Replace selected_ships/selected_modules with SelectionService
- [ ] Update checkbox handling to use SelectedItem
- [ ] Update sidebar to use render_sidebar_selections()
- [ ] Update export to use SelectionService.generate_csv_data()
- [ ] Run tests and manual verification

---

## Post-Phase 8 Cleanup

After all sub-phases complete:
- [ ] Update `docs/REFINEMENTS_PROJECT.md` with Phase 8 completion notes
- [ ] Run docs-sync agent to update documentation
- [ ] Consider applying similar refactor to doctrine_report.py
- [ ] Consider deleting unused popover functions from ui/popovers.py

---

## Testing Commands

```bash
# Syntax check
uv run python -m py_compile pages/doctrine_status.py
uv run python -m py_compile services/doctrine_service.py

# Full test suite
uv run pytest -q

# Run application
uv run streamlit run app.py
```

---

## Files to Modify

| File | Sub-Phases | Description |
|------|------------|-------------|
| `pages/doctrine_status.py` | 8A, 8B, 8C, 8D, 8E | Main page - all changes |
| `services/doctrine_service.py` | 8B | FitDataBuilder pipeline |
| `ui/popovers.py` | (reference only) | Functions being removed from usage |
| `services/selection_service.py` | (reference only) | Pattern for 8E |


# USER COMMENTS/Instructions

## Sub-Phase 8D

### st.form() Implementation
- this approach will substitute full page reload on a checkbox interaction for a full page reload on form submit.
- This will offer only very modest performance gains and does not fully take advantage of the isolation from the execution flow that st.form is designed to provide.
- Explore using @st.fragment or a callback:
  - st.form_submit_button accepts a callback with "on_click" that can be passed args or kwargs. Review the documentation here: https://docs.streamlit.io/develop/api-reference/execution-flow/st.form_submit_button
  - Or abstract the checkbox form rendering to a function decorated by @st.fragment to isolate form submission from the execution flow. https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment
- Interaction should only trigger an update to the st.session_state, not a full app re-run. 

### Sidebar refactor
- st.sidebar cannot be isolated from code execution. If writing to the selected items code block will cause a full re-run, reconfigure the UI to display it in the main bod instead. 

### Formatting
- Display the ship name checkbox label in a way that distinguishes it clearly from the modules. 

## Sub-Phase 8F (new)

### Remove Jita Prices

- Jita price API calls are too expensive. We will need to rework our backend to capture Jita Prices in our database. Disable this feature for now. But ensure that it can be restored later with a more performant Implementation.  

