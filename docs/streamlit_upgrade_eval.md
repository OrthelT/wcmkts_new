# Streamlit 1.58 → 1.64 Upgrade Evaluation

_Date: 2026-09-24 · Installed: 1.58.0 (`uv.lock`) · `pyproject.toml` floor: `>=1.52.2` · Latest: 1.64.0 (2026-09-15)_

## Summary

The upgrade is low-risk and worth doing. None of the APIs that 1.59–1.64 removed or deprecated appear in this codebase. The largest gains come from a few targeted changes, not from adopting every new feature.

| Rank | Change | Version | Payoff | Effort |
|---|---|---|---|---|
| 1 | `refresh_mode="background"` on the hot `st.cache_data` functions | 1.61 | Removes the spinner stalls when a cache TTL expires. Costs no correctness (see §2). | S |
| 2 | Dashboard: `ButtonColumn` + `st.switch_page` in the click callback | 1.59 + 1.63 | Deletes the destination toggle, the row-selection plumbing and the positional realignment code | M |
| 3 | Keyed fragment reruns (`@st.fragment(key=…)` + `st.rerun("key")` from callbacks) on doctrine_status, market_stats and pricer | 1.63 | Clicking a checkbox or control reruns one panel instead of the whole page | M |
| 4 | Cache the per-popover SQL in `ui/popovers.py` (no upgrade needed) | n/a | Removes N uncached queries per doctrine_report rerun | S |
| 5 | `@st.fragment(parallel=True)` on the dashboard sections | 1.58 (installed) | Real only on a cold cache; small with a warm one. Measure first. | M |
| 6 | Lazy dataframes | 1.61 | **None.** Our tables are far below the 150k-row auto threshold, and lazy mode disables `on_select`, Styler and CSV export. | Skip |
| 7 | `async`/`await` | 1.64 | **Little.** Page render makes no live HTTP calls. The one async path already works. | Skip |

The recommended order is: upgrade and verify (§1), then #1 and #4 (small and independent), then #2, then #3. Do #5 only after profiling.

## USER COMMENT 
This seems like a solid plan. Proceed with these updates. I have upgraded Streamlit to 1.64 and reinstalled skills. 

---

## 1. Upgrade safety

The breaking and behavior changes from 1.59–1.64 were checked against the code:

| Change | Status here |
|---|---|
| `st.cache` removed (1.62) | Not used |
| `st.image(use_column_width=)` removed (1.61) | Not used |
| `st.html` / `st.iframe` with a string path deprecated (1.61) | Not used |
| `st.pyplot` without a figure, `mapbox.token`, `add_rows`, `bokeh_chart` removed | Not used |
| `use_container_width` | 0 occurrences; `width=` is used throughout |
| `st.rerun()` / `st.switch_page()` inside callbacks now take effect (1.63; previously a no-op with a warning) | Safe. The three existing callbacks (`doctrine_status.py:141, 589`, `low_stock.py:538`) call neither. |
| Widgets after `st.rerun()` keep their user values instead of resetting (1.64) | Recheck doctrine_status select all / clear all (`:931, 946`). They delete the checkbox keys before rerunning, so they should be unaffected. |
| 1.64 installs a persistent event loop on the script thread | `build_cost_service.py:158` calls `asyncio.run(...)`. The 1.64 `script_runner.py` keeps that loop non-running, so `asyncio.run()` still works. **Smoke-test Build Costs → Calculate anyway.** |
| `disabled=` enforced server-side (1.61) | Improves the disabled `data_editor` columns; no change needed |
| Controls placed directly in `st.columns` default to `wrap=False` (1.63) | Possible cosmetic change to button and checkbox labels in columns. Check visually. |
| Query strings capped at 512 KiB / 1,000 fields (1.60) | Deep links use one small param |

**Steps:**
1. Run `uv add "streamlit>=1.64"`. (*USER COMMENT: Already done*)
2. Run `uv run pytest -q`.
3. Click through each page on each hub.
4. Run Build Costs → Calculate.
5. Test the dashboard deep links.
6. Run `streamlit skills` (or reinstall `.claude/skills/developing-with-streamlit`). The copy the project has now is the 1.58 version and does not document 1.59–1.64 features such as ButtonColumn, background refresh and keyed reruns. (*USER COMMENT: Already done*)

**Side finding:** `config.toml` at the repo root (`[theme] base = "dark"`) is dead config. Streamlit reads only `.streamlit/config.toml` and `~/.streamlit/config.toml`. Move it if the dark theme is intended; `.streamlit/config.toml` is also where `runner.cacheBackgroundRefreshTTLMultiplier` would go. (*Resolved 2026-09-26: deleted. The theme keeps following each user's system setting.*)

**Verification results (2026-09-26, Streamlit 1.64.0):**
- `pyproject.toml` floor raised to `streamlit>=1.64.0`. `uv run pytest -q`: 736 passed.
- All 10 pages render with no exceptions on all 3 hubs (4H, X47, BKG).
- Build Costs → Calculate runs the `asyncio.run` path and renders results.
- Dashboard deep links open the correct item from all 4 tables, to both destinations. Browser Back does not re-trigger navigation.
- doctrine_status Select All / Clear All: 0 → 127 → 0 checked. A manual uncheck in between survives.
- `wrap=False` (1.63) did truncate labels at a 1100 px viewport:
  - pricer: the display checkboxes, and the submit button in German.
  - doctrine_report: the item popovers, which cut off the trailing stock count.
  - The "← Dashboard" back button in Japanese.

  Fixed with `wrap=True` in `pages/pricer.py`, `ui/popovers.py` and `pages/components/header.py`. A scan of all pages in all 8 languages now finds no truncated control labels. Two things still truncate, both unrelated to the upgrade: the doctrine_status fit names (their own CSS ellipsis) and the `st.badge` status labels in doctrine_report (not a control).
- Pre-existing issue, not caused by the upgrade: on a cold server process, a direct load of a subpage URL runs the page through legacy `pages/` discovery and skips `app.py`. Reproduced identically on 1.58 with a minimal app.

---

## 2. Background cache refresh (1.61): highest value per line changed

**Current behavior.** All caches refresh in the foreground. When a TTL expires, the next rerun recomputes inline and shows a spinner:
- `_get_all_stats_cached` (600 s), `_get_all_orders_cached` (1800 s, about 34k rows) and `_get_all_history_cached` in `repositories/market_repo.py:492-603`
- The doctrine fits and targets caches (600 s) in `repositories/doctrine_repo.py:576-764`
- The builder cost catalog (600 s) in `repositories/build_cost_repo.py:206`

These run on the dashboard, market_stats, doctrine_status, doctrine_report and builder_helper render paths.

**Key observation.** TTL expiry does not bring new data. New market data arrives only through `DatabaseConfig.sync()`. When a pull changes the replica, `check_db()` explicitly clears the caches through `refresh_market_caches()` / `invalidate_build_cost_caches()` (`db_refresh.py:140-143`), and `st.cache_data` is process-wide. So a TTL-expiry recompute almost always re-reads an **unchanged** replica and returns identical data, while the user waits behind a spinner.

**Change:** add `refresh_mode="background"` to the market, doctrine and build-cost caches above:

```python
@st.cache_data(ttl=600, show_spinner="Loading market stats...", refresh_mode="background")
def _get_all_stats_cached(db_alias: str = "wcmkt") -> pd.DataFrame:
```

**Why this fits the data-integrity rule.** An expired entry is served for at most one extra TTL (configurable with `runner.cacheBackgroundRefreshTTLMultiplier`). That entry reflects the replica as it was when the cache was filled. After a sync that changes data, the explicit `.clear()` still drops the entries, so the next read recomputes in the foreground from fresh data. Stale-while-revalidate therefore never serves data older than what the explicit invalidation already allows.

**Compatibility with our code:**
- **No session-state reads.** The cached functions take `db_alias` / `market_key` as arguments. `get_active_market_key()` is resolved outside the cache in `DoctrineRepository.get_all_fits` (`doctrine_repo.py:114`). This matters because background mode cannot read `st.session_state`.
- **Recovery spinner is safe.** `BaseRepository.read_df()`'s rebuild spinner already checks `get_script_run_ctx()` (`repositories/base.py:57`), so it degrades cleanly in a background thread.
- **Constraints to respect.** Background mode requires a `ttl` and cannot combine with `persist` or `async def`. Neither is used here.

**Verify:** after `.clear()` on a background-mode function, the next call recomputes in the foreground and does not return the cleared value. Add a unit test.

**Implemented (2026-09-27):**
- Background mode on 14 `market_repo` caches, all 8 `doctrine_repo` caches, and the `build_cost_repo` builder catalog.
- Left in foreground mode:
  - `_get_all_history_cached`: downloads only, about 915k rows. Background mode would hold it for 2× TTL.
  - `_get_watchlist_type_ids_cached` and `_get_market_type_ids_cached`: no callers.
  - The SDE category caches: sync does not clear them.
  - The rigs/structures caches: small tables with a 1 h TTL.
- `get_target_quantities_with_cache` and `get_friendly_names_with_cache` read the market DB but were missing from `refresh_market_caches()`, so they could serve pre-sync data for up to one TTL. Both are now cleared.
- Streamlit discards a background refresh whose write lands after a `.clear()` (a generation counter in `cache_utils.py`). A refresh that started before a sync therefore cannot write pre-sync data back after the invalidation.
- `tests/test_cache_refresh_mode.py` checks two things. First, every background-mode cache is cleared by the sync invalidation; removing either new clear fails this test. Second, `.clear()` on an expired background entry recomputes instead of serving it.
- An AppTest run against the real replicas with a 1 s TTL served the stale value. The refresh then ran in `CacheBackgroundRefresh_*` threads with no errors.

---

## 3. Market dashboard: ButtonColumn + callback navigation (1.59 + 1.63)

**Current mechanism.** The old checkbox-column workaround is already gone. The current design still carries overhead (`pages/components/dashboard_components.py`, `pages/market_dashboard.py`):
- `st.dataframe(on_select="rerun", selection_mode="single-row")` on each of the 4 tables.
- A per-table `st.segmented_control` destination toggle, plus a hint caption (`_render_destination_toggle`, `:258-274`).
- `_resolve_selection` / `_get_selected_type_id` (`:163-211`) realign `source_df.loc[display_df.index]` because `on_select` returns a **display-position** index into a filtered and sorted table.
- `st.switch_page` is called **inline** after the table renders. The click therefore costs a full dashboard rerun (KPIs, all 4 tables, Styler, localization) before navigation happens.
- Row selection is persistent state, so a Back navigation can re-trigger it.

**Proposed design.** Add action columns and navigate from the click callback:

```python
display_df["open"] = [[":material/query_stats: Market", ":material/shield: Doctrine"]] * len(display_df)

def _on_open(type_ids: list[int], kind: str):
    click = st.session_state[f"{key}_click"]
    type_id = type_ids[click.row]
    if "Market" in click.label:
        st.switch_page("pages/market_stats.py", query_params={"item_id": str(type_id)})
    else:
        st.switch_page("pages/doctrine_status.py", query_params={f"{kind}_id": str(type_id)})

st.dataframe(styler, column_config={
    "open": st.column_config.ButtonColumn("", type="tertiary", on_click=_on_open,
                                          args=(display_df["type_id"].tolist(), "ship"),
                                          key=f"{key}_click"),
    ...
})
```

A single-action column (two separate `ButtonColumn`s, or one icon button per row) is an alternative if the dropdown feels heavy. Minerals and isotopes need only a single "Market" button.

**What this deletes:**
- `_render_destination_toggle`, `_render_row_open_hint` and the `dash_*_destination` keys, plus their i18n strings if unused elsewhere.
- `_resolve_selection`, `_get_selected_type_id` and the four `if selected: _navigate_...` branches in `_render_commodity_grid`.
- The full-dashboard rerun before each navigation. The callback runs before the script, and `switch_page` inside a callback now takes effect (1.63).

**Why it behaves better:**
- The user picks the destination per click instead of setting a table-level mode first.
- Clicks are transient: `ButtonColumnClickState` resets to `None` after the click rerun, so there is no stale selection on Back.

**Open question: verify with a spike first.** Is `click.row` the index into the **original data order**, or the **visual order after the user clicks a column header to sort**?
- The docs example uses `df.iloc[click['row']]`.
- The 1.64 frontend passes `getOriginalIndex` into the button-cell handler (`DataFrame.*.js`). That suggests the original order, which would make the resolution sort-proof. The server-side row realignment is still needed either way because the filtering happens in pandas.

Confirm with a 10-line test app: sort a column, click a button, check the resolved `type_id`. Also confirm that ButtonColumn renders on a `pandas.Styler` input, since all 4 tables pass Styler objects.

**Implemented (2026-10-01).**

The spike app in the browser (Streamlit 1.64) answered the open questions:
- `click.row` is the row's position in the data passed to `st.dataframe`. After a header sort, visual row 1 resolved to data row 0, which is the correct item. Resolution is therefore sort-proof.
- ButtonColumn renders on a `pandas.Styler`.
- A list value renders as a "⋮" menu, and `click.label` is the full label string.
- `st.switch_page` inside `on_click` navigates directly. Back does not navigate again.

The user chose two pinned icon columns over a menu: 📈 Market Stats, plus ⚔️ Doctrine Status on the ships and modules tables. Hover text gives the translated page name.

Changes:
- `_open_clicked_item` (the callback) and `_with_open_buttons` (which adds the columns) replace `_get_selected_type_id`, `_resolve_selection`, `_render_destination_toggle` and `_render_row_open_hint`.
- The renderers return `None`, and `_render_commodity_grid` only renders.
- The i18n keys `dashboard.row_open_in`, `dashboard.row_open_hint` and `dashboard.hint_click_market_stats` are removed from all 8 languages.
- The ships table displays `fit_id`, so its type_ids come from `result_df.loc[display_df.index]`. A test guards this alignment.

Browser test on the real app (4H): every table/destination pair opened the clicked item. The pairs were minerals, isotopes, ships and modules → Market Stats, and ships and modules → Doctrine Status. The modules case was clicked after a descending sort.

The Back quirk from session 2 is still there and predates this change. After dashboard → market_stats, history keeps an extra `market_stats?item_id=<id>` entry. Back can land on that entry, which shows the all-items view.

---

## 4. Keyed fragment reruns (1.63)

`@st.fragment(key="x")` plus `st.rerun("x")` (or `st.rerun(["x", "y"])`) **from a widget callback** reruns only the named fragments. This fixes the current limitation that a widget outside a fragment always reruns the whole page.

Rules:
- The key form is valid only inside `on_change` / `on_click`.
- The fragment must have rendered in the last full run.
- If another callback in the same interaction does not target a fragment, the rerun escalates to a full rerun.

| Page | Current cost | Change |
|---|---|---|
| **doctrine_status** | Every fit checkbox (`:358`, `:803`) reruns the loop over about 127 fits: columns, images, HTML, progress bars and menu buttons, plus the low-stock popovers. | Give the checkboxes `on_change=lambda: st.rerun("selection_panel")` and wrap the sidebar selection panel (`SelectionService` render) in `@st.fragment(key="selection_panel")`. The checkbox updates itself in the browser, so only the panel reruns. |
| **market_stats** | The top-N pills and number_input (`market_components.py:256`) are outside `top_n_fragment`, so they rerun the whole page. `render_isk_volume_table_ui` (`:128`) reads `chart_days_radio` outside the chart fragment and goes stale until the next full rerun. | Move the top-N controls into the fragment, or key the fragment. Key both the chart and table fragments and have the radio callbacks call `st.rerun(["isk_chart", "isk_table"])`. |
| **pricer** | The 4 display checkboxes (`:469-500`) rerun the whole appraisal render. | Put the results section in a keyed fragment; the checkboxes rerun only it. |
| **builder_helper / low_stock** | The sidebar filters rerun `get_builder_data` / `get_low_stock_items`, and the table is most of the page. | Little to gain from fragments. The cost is the unmemoized service call. Wrap `get_builder_data` in `st.cache_data`, keyed on the filter values plus the cached inputs. Move `low_stock_service.py:~419` from a raw `engine.connect()` to a cached `read_df()` repo method, as the project convention requires. |

**Implemented (2026-10-02)** for doctrine_status, market_stats and pricer. builder_helper and low_stock are item 6.
- **doctrine_status.** The sidebar export section is `_render_selection_panel`, a fragment keyed `selection_panel`. The handoff's `SelectionService` reference was stale: the panel was inline in `main()`. Each fit checkbox has `on_change=_on_fit_checkbox_change`, which updates the selection and calls `st.rerun("selection_panel")`. The callback must update the selection itself, because the main loop's inline `_add_selection` does not run on a fragment rerun. An uncheck calls `_rebuild_selections()`, so a type_id that is still checked in another fit stays selected. Select All and Clear All still call `st.rerun()`, which reruns the whole page because they reset checkbox widgets in the main loop. The `st.rerun()` after "Render market data" is gone: the code below the button reads the flag in the same run, and a rerun from inside the fragment would rerun the whole page.
- **market_stats.** The chart fragment is keyed `isk_chart`. `render_isk_volume_table_ui` is now a fragment keyed `isk_table`. `render_isk_volume_chart_ui(..., with_table=True)` gives the window and period radios `on_change=lambda: st.rerun(["isk_chart", "isk_table"])`, so the table follows the chart. The dashboard renders the chart without the table and passes no flag, because `st.rerun()` raises for a fragment key that did not render. The moving-average radio reruns only the chart. The top-N pills and number input moved inside `top_n_fragment`.
- **pricer.** The results section is `_render_results`, a fragment keyed `pricer_results`. It renders on every full run, even with no result, so the checkbox callbacks can always target it. Each display checkbox has `on_change=_on_display_toggle`, which stores the value in its `pricer_*` key and reruns only the results. Before this change the results rendered above the controls and read a `pricer_*` key that the checkbox body set later in the run. By code reading, the table lagged one click behind the checkbox; this was not reproduced on the old code. Reset, inside the fragment, still calls `st.rerun()` for a full rerun.
- **Verified in the browser (4H) with temporary run markers.** A doctrine_status checkbox click, an uncheck and "Render market data" each reran only `selection_panel`. Select All produced 127 checked and Clear All produced 0, each through a full rerun. A manual uncheck after Select All survived. On market_stats, the window and period changes reran `isk_chart` + `isk_table`, the table's "Window: 90d | Date Period: Weekly" line updated, and the moving average reran only the chart. Top-N pills and count reran only `top_n`. Changing the dashboard chart window raised no exception. On the pricer, one click on Show Jita Prices removed the Jita columns and reran only `pricer_results`. No `StreamlitAPIException` appeared in the page or the server log.

**Related 1.63/1.64 feature:** `on_change="ignore"` on `st.slider`, `st.text_input`, `st.number_input`, `st.select_slider` and `st.selectbox`. It updates the widget without a rerun and applies the value on the next rerun. This gives form-like batching without the `st.form` visual container. It is a candidate for the builder_helper and low_stock filter sidebars if they get an explicit "Apply" button. `st.form` also works today.

**Implemented (2026-10-02): builder_helper and low_stock.** Profiling changed the fix. With every input already cached, a filter change still cost about 350 ms in `get_builder_data` and about 790 ms in `get_low_stock_items`. Nearly all of that was pandas row iteration, not database reads:
- builder_helper: `iterrows()` in `_build_numeric_map`, `_build_metadata_index` and the main loop built about 13k row Series per call.
- low_stock: `groupby("type_id").apply(... iterrows ...)`, which builds the `ships` column, took 1.3 s of a 1.4 s profiled call.

Caching the service output would have hidden that cost instead of removing it. It would also have put `st.cache_data` in the service layer, which the layering rules forbid, and added a new sync-invalidation path. Instead:
- `_build_numeric_map` is vectorized with `pd.to_numeric`. The two row loops iterate `to_dict("records")`.
- The `ships` column is built with one string concatenation plus `groupby().agg(list)`. Items used in no fit still get `[]`.
- The low_stock base query (marketstats LEFT JOIN doctrines) moved from a raw `engine.connect()` to `MarketRepository.get_stats_with_doctrine_usage()`. It runs through `read_df()`, is cached with ttl 600 and background mode, and is cleared by `invalidate_market_caches()`.

Results:

| Call | Before | After |
|---|---|---|
| `get_builder_data`, warm | about 350 ms | about 43 ms |
| `get_low_stock_items`, default filters, warm | about 790 ms | about 72 ms |
| `get_low_stock_items`, tech2 filter, warm | about 290 ms | about 68 ms |

Outputs are unchanged: 18 frames (low_stock with 5 filter sets × en/de, builder_helper with en/de × both price bases × min_days 0/14) are identical before and after, including dtypes and index.

Left alone: `get_category_options`, `get_doctrine_options` and `get_fit_options` are also raw `engine.connect()` reads on the low_stock render path, but each takes 1–8 ms. Moving them is part of the `docs/read_df_consolidation.md` plan, not a performance fix.

---

## 5. Parallel fragments (1.58, already installed)

`@st.fragment(parallel=True)` runs a fragment in a thread pool during **full** reruns. Fragment-scoped reruns stay sequential.

**Where it could apply.** The dashboard has independent sections: KPIs, minerals, isotopes, doctrine ships and popular modules.

**Why it is ranked low:**
- **Warm cache.** Each section is mostly pandas, Styler and localization work on cached frames. That work is CPU-bound and holds the GIL, so threads barely overlap.
- **Cold cache.** Just after a sync invalidation or TTL expiry, the sections do SQLite reads that could overlap. That is a real but narrow window, and §2 already removes the TTL-expiry case.
- **Restrictions.** `st.switch_page`, `st.dialog` and writes to outside containers are forbidden during the initial parallel run. The current inline `switch_page` after table selection would break. §3 removes that inline call, so do §3 first.
- **Thread safety.** `state/service_registry.get_service()` lazily creates singletons in `st.session_state`. Two parallel fragments could both see a missing service and each create one. Pre-create the services in the main script before the fragments are dispatched.

**Recommendation.** Profile a cold dashboard load after a sync, using the same method as the 2026-09-10 startup timings (cold render 2.29 s). Adopt parallel fragments only if the per-section cache-miss times overlap meaningfully.

---

## 6. Features evaluated and not recommended

- **Lazy dataframes (1.61).**
  - The auto threshold is 150k rows in memory. The largest displayed tables are the market_stats order books (thousands of rows) and the builder_helper editor (about 1k), so nothing crosses it.
  - Forcing `lazy=True` disables `on_select`, Styler, search and CSV download, all of which we use.
  - The large frames (915k history rows, 646k SDE rows) are downloads only, never displayed.
- **async/await (1.64).**
  - Jita prices come from the local `jita_prices` table (`price_service.create_default` wires only `DatabasePriceProvider`), so page render makes no live HTTP calls.
  - The only async code (`build_cost_service._get_costs_async` via `asyncio.run`) keeps working.
  - Async would help only if we reintroduced live Fuzzwork/Janice lookups or made several concurrent ESI calls per render. Note: background-refresh caches cannot be `async def`.
- **Dynamic expanders and popovers (`on_change="rerun"` + `.open`, available since 1.55).**
  - Both expanders in the hot path are `expanded=True` (`market_stats.py:524`, `doctrine_report.py:139`), so there is nothing to skip.
  - For the doctrine_report popovers, dynamic mode would turn every popover open into a full rerun. Caching the query is simpler (§7).

## 7. Non-upgrade issues found during the audit

These need no upgrade, but they surfaced during the inventory and are cheap to fix:

1. **`ui/popovers.py:67-95` `get_doctrine_usage`.** It runs an **uncached** `engine.connect()` query per popover, and popover bodies execute on every rerun. doctrine_report renders one per item. Move it to a cached repository method through `read_df()`.
   *Implemented 2026-09-27.* The query is gone. `build_doctrine_usage(raw_df)` in `services/doctrine_service.py` builds a `{type_id: usage}` map once per render (about 7 ms) from the fits frame the page already loads, and doctrine_report passes it into `render_market_popover`. Measured with AppTest on the primary hub, warm render went from 0.51–0.56 s to 0.45–0.46 s. Two behavior changes, both intended:
   - **Market scoping.** The old query read every row of `doctrines`, so a popover also listed fits flagged for another hub. On the deployment hub it showed the primary-only Exequror fit (362) and an orphan Ferox Navy Issue fit (474, no `doctrine_fits` row). The map uses the market-filtered frame, so those fits no longer appear.
   - **Counts for items with equivalents.** "N fits" now uses combined equivalent stock, which matches the popover's "Stock (Combined)" figure. For example, Guardian changed from 50 to 110.
2. **`pages/build_costs.py:43` `requests.head(url)` with no timeout.** It runs on every rerun while results are displayed (`:757`). A hung image host hangs the page. Cache it and add a timeout, or drop the check and let `st.image` fail visibly.
3. **`build_costs.py:301`, inside the materials fragment.** `resolve_type_names` makes an **uncached ESI POST** on every fragment rerun. Cache it by the tuple of `type_ids`.
4. **`build_cost_service.py:310`.** ESI `/industry/systems` `requests.get` has no timeout.
5. **Plotly width in the wrong place.** `market_components.py:119` and `market_stats.py:672` pass `width` inside the plotly `config={}` dict, where it has no effect. Use the `width=` argument, as `market_stats.py:621` does.
6. **Caches missing from `refresh_market_caches()`.** `_get_equivalent_type_ids_cached` (`module_equivalents_service.py:333`) and `_get_category_type_ids*` are not cleared. The category data comes from the SDE, so that is fine. Check whether the equivalents data comes from the market DB. If it does, it can serve pre-sync data for up to 1 h.

## Sources

- [Streamlit 2026 release notes](https://docs.streamlit.io/develop/quick-reference/release-notes/2026) (1.53–1.64)
- API docs: [`st.fragment`](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment), [`st.rerun`](https://docs.streamlit.io/develop/api-reference/execution-flow/st.rerun), [`ButtonColumn`](https://docs.streamlit.io/develop/api-reference/data/st.column_config/st.column_config.buttoncolumn), [`st.cache_data`](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.cache_data), [`st.dataframe`](https://docs.streamlit.io/develop/api-reference/data/st.dataframe)
- The Streamlit 1.64.0 wheel (`script_runner.py` event loop, `layouts.py`, bundled `developing-with-streamlit` skill `performance.md` / `data-display.md`)
- The bundled `developing-with-streamlit` skill (1.58) in `.claude/skills/`
