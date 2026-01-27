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

## Tasks

### Refactor low-stock.py
- Review the code and identify functions that can be replaced by calls to the current service-layer architecture.
- Refactor operations to use existing services directly or with minimal changes. Do not add new complexity.
- Add functionality (if not already available in the architecture) to:
  - Filter faction items (identified by metagroup=7) like we do for tech II and doctrines.
  - Conditionally format or filter items based on user selections. This logic should also support the pricer page.
  - Filter by doctrine or fit. When filtering, display an image of the doctrine lead ship or selected ship, with the doctrine name prominently displayed.

## Enhance Pricer

### pricer.py
- Add columns for:
  - average sales per day
  - days of stock remaining
- Add highlighting by doctrine and fit toggled on and off with checkboxes.
- Display a heading identifying the selected doctrine or ship.

## Enhance Low Stock

### Market Data Popovers (Doctrine Pages)
Enable ships and items to be clickable on `doctrine_status` and `doctrine_report`.

On click, show a popover card with basic market stats:

- **Item Name**
- id: `<type_id>`
- quantity on market
- current price
- average price
- average daily volume
- fits: comma-separated list of ship names

## Enhance Doctrine Stats and Doctrine Report

### Business Logic
Abstract status-determination logic out of the UI layer. Move all business rules into the categorization service within the new architecture.

### Merge Sidebar Selections
Unify selected ships and selected modules into a single workflow. Harmonize the CSV export schema to support both, leaving non-applicable columns null.

### Sidebar Selection Text Layout
Generate the selection text only once using `st.sidebar.code`. Remove the separate container and the custom copy-to-clipboard functionality, since `st.code` already provides native copy support.

### Abstract Formatting Logic
Move all formatting logic into a dedicated service layer.

Design this layer to be extensible so future selectable formatting options can be added without refactoring.

### Apply to Doctrine Stats
Apply these same architectural patterns to `pages/doctrine_stats.py` where appropriate.
