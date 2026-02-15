import sys
import os
import pathlib

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from millify import millify
from logging_config import setup_logging
from repositories import get_update_time
from services import get_doctrine_service
from domain import StockStatus
from ui import get_fitting_column_config, render_progress_bar_html, format_doctrine_name
from services import get_status_filter_options
from state import ss_init, ss_get
from ui.market_selector import render_market_selector
from init_db import ensure_market_db_ready

# DISABLED: Jita prices - restore when backend caching implemented
# from services import get_price_service
# DISABLED: Popovers - removed for performance (execute on every rerun even when closed)
# from ui.popovers import render_ship_with_popover, render_market_popover, has_equivalent_modules

# Insert centralized logging configuration
logger = setup_logging(__name__, log_file="doctrine_status.log")

# Initialize service (cached in session state)
service = get_doctrine_service()
fit_build_result = service.build_fit_data()
all_fits_df = fit_build_result.raw_df
summary_df = fit_build_result.summary_df

# get_fit_summary() REMOVED - now using summary_df directly from FitBuildResult
# summary_df already contains: fit_id, ship_name, ship_id, hulls, fits, ship_group,
# price, total_cost, ship_target, target_percentage, daily_avg, fit_name, lowest_modules


def render_export_data():
    """Query market stock data for all selected type_ids. Stores results in session state."""
    ss_init({"rendered_export_data": {}})

    for type_id in st.session_state.selected_type_ids:
        if type_id in st.session_state.rendered_export_data:
            continue

        info = st.session_state.type_id_info.get(type_id, {})
        name = info.get("module_name", f"Unknown ({type_id})")

        try:
            module_stock = service.repository.get_module_stock(name)
            if module_stock:
                st.session_state.rendered_export_data[type_id] = {
                    "name": name,
                    "type_id": type_id,
                    "total_stock": module_stock.total_stock,
                    "fits_on_mkt": module_stock.fits_on_mkt,
                    "qty_needed": info.get("qty_needed", 0),
                }
            else:
                st.session_state.rendered_export_data[type_id] = {
                    "name": name,
                    "type_id": type_id,
                    "total_stock": 0,
                    "fits_on_mkt": 0,
                    "qty_needed": info.get("qty_needed", 0),
                }
        except Exception as e:
            logger.error(f"Error querying stock for {name} (type_id={type_id}): {e}")
            st.session_state.rendered_export_data[type_id] = {
                "name": name,
                "type_id": type_id,
                "total_stock": 0,
                "fits_on_mkt": 0,
                "qty_needed": info.get("qty_needed", 0),
            }


def _add_selection(type_id: int, module_name: str, fits_on_market: int, qty_needed: int):
    """Add a type_id to the unified selection, keeping max qty_needed."""
    st.session_state.selected_type_ids.add(type_id)
    existing = st.session_state.type_id_info.get(type_id, {})
    st.session_state.type_id_info[type_id] = {
        "module_name": module_name,
        "fits_on_market": fits_on_market,
        "qty_needed": max(qty_needed, existing.get("qty_needed", 0)),
    }


def _remove_selection(type_id: int):
    """Remove a type_id from the unified selection."""
    st.session_state.selected_type_ids.discard(type_id)


def _rebuild_selections():
    """Rebuild selected_type_ids from all checkbox states.

    Fixes the multi-fit bug: when the same type_id appears in multiple fits,
    incremental add/remove causes the last-processed unchecked checkbox to win.
    Instead, we scan all checkbox keys after rendering to determine the true set.
    """
    checked_type_ids = set()
    for key, value in st.session_state.items():
        if key.startswith("mod_"):
            if value is not True:
                continue
            # Format: mod_{fit_id}_{position}_{type_id}
            parts = key.split("_")
            if len(parts) >= 4:
                try:
                    checked_type_ids.add(int(parts[-1]))
                except ValueError:
                    pass
        elif key.startswith("ship_"):
            if value is not True:
                continue
            # Format: ship_{fit_id}_{ship_id}
            parts = key.split("_")
            if len(parts) >= 3:
                try:
                    checked_type_ids.add(int(parts[-1]))
                except ValueError:
                    pass

    st.session_state.selected_type_ids = checked_type_ids
    # Remove type_id_info entries for unchecked items
    st.session_state.type_id_info = {
        tid: info
        for tid, info in st.session_state.type_id_info.items()
        if tid in checked_type_ids
    }


# DISABLED: Jita prices - restore when backend caching implemented
# def fetch_jita_prices_for_types(type_ids: tuple[int, ...]) -> dict[int, float]:
# def calculate_all_jita_deltas(force_refresh: bool = False):

# DISABLED: Popovers - removed for performance (execute on every rerun even when closed)
# def prefetch_popover_data(filtered_df: pd.DataFrame) -> tuple[dict[str, int], dict[int, float]]:


def main():
    market = render_market_selector()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    # App title and logo
    col1, col2, col3 = st.columns([0.2, 0.5, 0.3])
    with col1:
        image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"
        if image_path.exists():
            st.image(str(image_path), width=150)
        else:
            st.warning("Logo image not found")

    with col2:
        st.markdown("&nbsp;")
        st.title(f"{market.name} Doctrine Status")
    with col3:
        # Use summary_df directly from FitBuildResult (no redundant get_fit_summary call)
        if summary_df.empty:
            st.warning("No doctrine fits found in the database.")
            return
        fit_summary = summary_df.copy()
        st.markdown("&nbsp;")
        st.markdown("&nbsp;")
        st.markdown(
            "<span style='font-size: 12px; color: #666;'>*Use Downloads page for full data export*</span>",
            unsafe_allow_html=True,
        )

    # Add filters in the sidebar
    st.sidebar.header("Filters")

    # Target multiplier
    ds_target_multiplier = 1.0
    ss_init({"ds_target_multiplier": ds_target_multiplier})
    with st.sidebar.expander("Target Multiplier"):
        ds_target_multiplier = st.slider(
            "Target Multiplier", min_value=0.5, max_value=2.0, value=1.0, step=0.1
        )
        st.session_state.ds_target_multiplier = ds_target_multiplier
        st.sidebar.write(f"Target Multiplier: {ds_target_multiplier}")

    # Doctrine filter - filter by fleet doctrine composition
    doctrine_comps = service.repository.get_all_doctrine_compositions()
    doctrine_names = (
        ["All"] + sorted(doctrine_comps["doctrine_name"].unique().tolist())
        if not doctrine_comps.empty
        else ["All"]
    )
    selected_doctrine = st.sidebar.selectbox("Doctrine:", doctrine_names, format_func=format_doctrine_name)

    # Stock Status filter (renamed from "Doctrine Status" for clarity - single unified filter)
    status_options = get_status_filter_options()
    selected_status = st.sidebar.selectbox("Stock Status:", status_options)

    # Ship group filter
    ship_groups = ["All"] + sorted(fit_summary["ship_group"].unique().tolist())
    selected_group = st.sidebar.selectbox("Ship Group:", ship_groups)

    # Get unique ship names for selection
    unique_ships = sorted(fit_summary["ship_name"].unique().tolist())

    # Initialize session state
    ss_init(
        {
            "displayed_ships": unique_ships.copy(),
            "selected_type_ids": set(),
            "type_id_info": {},
            "export_data_rendered": False,
        }
    )

    # Apply filters - summary_df uses 'ship_target' column
    filtered_df = fit_summary.copy()
    filtered_df["ship_target"] = filtered_df["ship_target"] * ds_target_multiplier

    # Recalculate target_percentage with multiplier (capped at 100)
    filtered_df["target_percentage"] = (
        (filtered_df["fits"] / filtered_df["ship_target"] * 100)
        .clip(upper=100)
        .fillna(0)
        .astype(int)
    )

    # Apply status filter using StockStatus thresholds (Critical: <=20%, Good: >90%)
    if selected_status != "All":
        if selected_status == "Good":
            filtered_df = filtered_df[filtered_df["target_percentage"] > 90]
        elif selected_status == "All Low Stock":
            filtered_df = filtered_df[filtered_df["target_percentage"] <= 90]
        elif selected_status == "Needs Attention":
            filtered_df = filtered_df[
                (filtered_df["target_percentage"] > 20)
                & (filtered_df["target_percentage"] <= 90)
            ]
        elif selected_status == "Critical":
            filtered_df = filtered_df[filtered_df["target_percentage"] <= 20]

    # Apply ship group filter
    if selected_group != "All":
        filtered_df = filtered_df[filtered_df["ship_group"] == selected_group]

    # Apply doctrine filter
    if selected_doctrine != "All":
        doctrine_fit_ids = doctrine_comps[
            doctrine_comps["doctrine_name"] == selected_doctrine
        ]["fit_id"].unique()
        filtered_df = filtered_df[filtered_df["fit_id"].isin(doctrine_fit_ids)]

    # Update the displayed ships based on filters
    st.session_state.displayed_ships = filtered_df["ship_name"].unique().tolist()

    if filtered_df.empty:
        st.info("No fits found with the selected filters.")
        return

    # Group the data by ship_group
    grouped_fits = filtered_df.groupby("ship_group")

    # Iterate through each group and display fits
    for group_name, group_data in grouped_fits:
        # Display group header
        st.subheader(body=f"{group_name}", help="Ship doctrine group", divider="orange")

        # Display the fits in this group
        for i, row in group_data.iterrows():
            # Create a more compact horizontal section for each fit
            col1, col2, col3 = st.columns([1, 3, 2])

            target_pct = row["target_percentage"]
            target = int(row["ship_target"]) if pd.notna(row["ship_target"]) else 0
            fits = int(row["fits"]) if pd.notna(row["fits"]) else 0
            hulls = int(row["hulls"]) if pd.notna(row["hulls"]) else 0
            ship_id = int(row["ship_id"])
            fit_id = int(row["fit_id"])
            fit_cost = (
                millify(int(row["total_cost"]), precision=2)
                if pd.notna(row["total_cost"])
                else "N/A"
            )

            with col1:
                # add space
                st.space("stretch")
                # Ship image and ID info
                try:
                    st.image(
                        f"https://images.evetech.net/types/{ship_id}/render?size=64",
                        width=64,
                    )
                except Exception:
                    st.text("Image not available")

                # Use StockStatus for consistent categorization
                stock_status = StockStatus.from_percentage(target_pct)
                color = stock_status.display_color
                status = stock_status.display_name
                fit_name = row["fit_name"]
                st.badge(status, color=color)
                st.text(f"ID: {fit_id}")
                st.text(f"Fit: {fit_name}")

            with col2:
                tab1, tab2 = st.tabs(
                    ["Market Stock", "Fit Details"], default="Market Stock"
                )
                with tab1:
                    # Ship name with checkbox and metrics in a more compact layout
                    ship_cols = st.columns([0.05, 0.95])

                    with ship_cols[0]:
                        # Ship checkbox — keyed by type_id (ship_id)
                        ship_cb_key = f"ship_{fit_id}_{ship_id}"
                        if ship_cb_key not in st.session_state:
                            st.session_state[ship_cb_key] = (
                                ship_id in st.session_state.selected_type_ids
                            )
                        ship_selected = st.checkbox(
                            "x", key=ship_cb_key, label_visibility="hidden"
                        )
                        hull_qty_needed = max(0, target - hulls)
                        if ship_selected:
                            _add_selection(ship_id, row["ship_name"], hulls, hull_qty_needed)

                    with ship_cols[1]:
                        st.markdown(f"**{row['ship_name']}**")

                    # Display metrics in a single row
                    metric_cols = st.columns(4)
                    fits_delta = fits - target
                    hulls_delta = hulls - target

                    with metric_cols[0]:
                        if fits:
                            st.metric(
                                label="Fits", value=f"{int(fits)}", delta=fits_delta
                            )
                        else:
                            st.metric(label="Fits", value="0", delta=fits_delta)

                    with metric_cols[1]:
                        if hulls:
                            st.metric(
                                label="Hulls", value=f"{int(hulls)}", delta=hulls_delta
                            )
                        else:
                            st.metric(label="Hulls", value="0", delta=hulls_delta)

                    with metric_cols[2]:
                        if target:
                            st.metric(label="Target", value=f"{int(target)}")
                        else:
                            st.metric(label="Target", value="0")

                    with metric_cols[3]:
                        if fit_cost and fit_cost != "N/A":
                            st.metric(label="Fit Cost", value=f"{fit_cost}")
                        else:
                            st.metric(label="Fit Cost", value="N/A")

                    # Progress bar for target percentage (uses ui.formatters)
                    target_pct = row["target_percentage"]
                    st.markdown(
                        render_progress_bar_html(target_pct), unsafe_allow_html=True
                    )

                    with col3:
                        # Low stock modules with selection checkboxes
                        st.markdown(":blue[**Low Stock Modules:**]")

                        for mod in row["lowest_modules"]:
                            mod_type_id = mod["type_id"]
                            mod_name = mod["module_name"]
                            mod_fits = mod["fits_on_market"]
                            mod_qty_needed = mod["qty_needed"]
                            mod_position = mod["position"]

                            # Display string for the module
                            display_text = f"{mod_name} ({mod_fits})"

                            # Unique checkbox key using fit_id + position
                            module_cb_key = f"mod_{fit_id}_{mod_position}_{mod_type_id}"

                            # Use StockStatus for consistent module categorization
                            mod_stock_status = StockStatus.from_stock_and_target(
                                mod_fits, target
                            )

                            col_a, col_b = st.columns([0.1, 0.9])
                            with col_a:
                                if module_cb_key not in st.session_state:
                                    st.session_state[module_cb_key] = (
                                        mod_type_id in st.session_state.selected_type_ids
                                    )
                                is_selected = st.checkbox(
                                    "1", key=module_cb_key, label_visibility="hidden"
                                )
                                if is_selected:
                                    _add_selection(mod_type_id, mod_name, mod_fits, mod_qty_needed)

                            with col_b:
                                if mod_stock_status == StockStatus.CRITICAL:
                                    st.markdown(
                                        f":red-badge[:material/error:] {display_text}",
                                        help="Critical stock level",
                                    )
                                elif mod_stock_status == StockStatus.NEEDS_ATTENTION:
                                    st.markdown(
                                        f":orange-badge[:material/error:] {display_text}",
                                        help="Low stock",
                                    )
                                else:
                                    st.text(display_text)

                    with tab2:
                        ship_name = row["ship_name"]
                        st.write(f"{ship_name} - Fit {fit_id}")

                        # Lazy-load: only fetch fit details when user explicitly requests
                        tab2_key = f"tab2_data_{fit_id}"

                        if tab2_key not in st.session_state:
                            if st.button(
                                "Load Fit Details",
                                key=f"load_tab2_{fit_id}",
                                type="secondary",
                            ):
                                fit_detail_df = service.repository.get_fit_by_id(
                                    fit_id=fit_id
                                )
                                st.session_state[tab2_key] = fit_detail_df
                                st.rerun()

                        if tab2_key in st.session_state:
                            fit_detail_df = st.session_state[tab2_key]
                            if not fit_detail_df.empty:
                                col_config = get_fitting_column_config()
                                st.dataframe(
                                    fit_detail_df,
                                    hide_index=True,
                                    column_config=col_config,
                                    width="stretch",
                                )
                            else:
                                st.info(
                                    "No detailed fitting data available for this fit."
                                )

                        # Add a thinner divider between fits
                        st.markdown(
                            "<hr style='margin: 0.5em 0; border-width: 1px'>",
                            unsafe_allow_html=True,
                        )

    # Rebuild selections from checkbox states after all checkboxes have rendered
    _rebuild_selections()

    # =========================================================================
    # Sidebar Export Section — unified for ships and modules
    # =========================================================================
    st.sidebar.markdown("---")
    st.sidebar.header("Export")

    col1, col2 = st.sidebar.columns(2)

    # Select All — adds all visible ships + modules
    if col1.button("📋 Select All", width="content"):
        for _, group_data in grouped_fits:
            for _, row in group_data.iterrows():
                if row["ship_name"] not in st.session_state.displayed_ships:
                    continue
                sid = int(row["ship_id"])
                t = int(row["ship_target"]) if pd.notna(row["ship_target"]) else 0
                h = int(row["hulls"]) if pd.notna(row["hulls"]) else 0
                _add_selection(sid, row["ship_name"], h, max(0, t - h))
                for mod in row["lowest_modules"]:
                    _add_selection(
                        mod["type_id"], mod["module_name"],
                        mod["fits_on_market"], mod["qty_needed"],
                    )
        st.session_state.export_data_rendered = False
        # Clear checkbox states so they reinitialize
        keys_to_clear = [
            k for k in st.session_state.keys()
            if k.startswith("ship_") or k.startswith("mod_")
        ]
        for k in keys_to_clear:
            del st.session_state[k]
        st.rerun()

    # Clear All
    if col2.button("🗑️ Clear All", width="content"):
        st.session_state.selected_type_ids = set()
        st.session_state.type_id_info = {}
        st.session_state.rendered_export_data = {}
        st.session_state.export_data_rendered = False
        keys_to_clear = [
            k for k in st.session_state.keys()
            if k.startswith("ship_") or k.startswith("mod_")
        ]
        for k in keys_to_clear:
            del st.session_state[k]
        logger.info("Cleared all selections")
        st.rerun()

    # Display lightweight selection list (no DB queries)
    selected = st.session_state.selected_type_ids
    if selected:
        st.sidebar.markdown("---")
        st.sidebar.header("Selected Items", divider="blue")

        selection_lines = []
        for tid in sorted(selected):
            info = st.session_state.type_id_info.get(tid, {})
            name = info.get("module_name", f"Unknown ({tid})")
            qty = info.get("qty_needed", 0)
            selection_lines.append(f"{name} {qty}")
        st.sidebar.code("\n".join(selection_lines), language=None)

        # Render market data button — triggers DB queries only when clicked
        if st.sidebar.button("📊 Render market data for export", type="primary"):
            render_export_data()
            st.session_state.export_data_rendered = True
            st.rerun()

        # Show rendered market data and export options
        if ss_get("export_data_rendered", False):
            st.sidebar.markdown("---")
            st.sidebar.subheader("Market Data")

            detail_lines = []
            rendered = st.session_state.get("rendered_export_data", {})
            for tid in sorted(selected):
                data = rendered.get(tid, {})
                name = data.get("name", st.session_state.type_id_info.get(tid, {}).get("module_name", f"Unknown ({tid})"))
                stock = data.get("total_stock", 0)
                fits_mkt = data.get("fits_on_mkt", 0)
                qty = data.get("qty_needed", 0)
                detail_lines.append(f"  {name} (Stock: {stock} | Fits: {fits_mkt} | Need: {qty})")
            st.sidebar.code("\n".join(detail_lines), language=None)

            # Build CSV export
            csv_lines = ["Name,TypeID,TotalStock,FitsOnMkt,QtyNeeded\n"]
            for tid in sorted(selected):
                data = rendered.get(tid, {})
                name = data.get("name", "")
                stock = data.get("total_stock", 0)
                fits_mkt = data.get("fits_on_mkt", 0)
                qty = data.get("qty_needed", 0)
                csv_lines.append(f"{name},{tid},{stock},{fits_mkt},{qty}\n")

            csv_export = "".join(csv_lines)

            st.sidebar.download_button(
                label="Download CSV",
                data=csv_export,
                file_name="doctrine_export.csv",
                mime="text/csv",
            )
    else:
        st.sidebar.info(
            "Select ships and modules to export by checking the boxes next to them."
        )

    # Display last update timestamp
    st.sidebar.markdown("---")
    st.sidebar.write(f"Last ESI update: {get_update_time()}")


if __name__ == "__main__":
    main()
