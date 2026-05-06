from streamlit.elements.lib.layout_utils import Height
import streamlit as st
import pandas as pd
from millify import millify
from logging_config import setup_logging
from services import get_doctrine_service
from domain import StockStatus
from ui import get_fitting_column_config, render_progress_bar_html
from services.doctrine_service import format_doctrine_name
from services.type_name_localization import (
    apply_localized_names,
    apply_localized_names_to_records,
    apply_localized_type_names,
    get_localized_name,
)
from repositories import get_sde_repository
from state import get_active_language, ss_init, ss_get
from ui.i18n import translate_text
from ui.market_selector import render_market_selector
from init_db import ensure_market_db_ready
from ui.sync_display import display_sync_status
from services.module_equivalents_service import get_module_equivalents_service
from ui.formatters import drop_localized_backup_columns
from pages.components.header import render_page_title

# Insert centralized logging configuration
logger = setup_logging(__name__, log_file="doctrine_status.log")


def _localize_summary_df(
    df: pd.DataFrame,
    sde_repo,
    language_code: str,
) -> pd.DataFrame:
    """Localize ship and module display names in doctrine summary data."""
    localized_df = apply_localized_names(
        df,
        sde_repo,
        language_code,
        id_column="ship_id",
        name_column="ship_name",
        logger=logger,
        english_name_column="ship_name_en",
    )
    localized_df["lowest_modules"] = localized_df["lowest_modules"].apply(
        lambda modules: apply_localized_names_to_records(
            modules,
            sde_repo,
            language_code,
            id_key="type_id",
            name_key="module_name",
            logger=logger,
            english_name_key="module_name_en",
        )
        if isinstance(modules, list)
        else modules
    )
    return localized_df


def render_export_data():
    """Query market stock data for all selected type_ids. Stores results in session state."""
    ss_init({"rendered_export_data": {}})
    svc = get_doctrine_service()

    for type_id in st.session_state.selected_type_ids:
        if type_id in st.session_state.rendered_export_data:
            continue

        info = st.session_state.type_id_info.get(type_id, {})
        name = info.get("module_name", f"Unknown ({type_id})")

        try:
            module_stock = svc.repository.get_module_stock(type_id)
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
        key =str(key)
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


def _status_text_color(status: StockStatus) -> str:
    """Return a readable HTML color for compact stock status text."""
    return {
        StockStatus.CRITICAL: "#ef5350",
        StockStatus.NEEDS_ATTENTION: "#d88a22",
        StockStatus.GOOD: "#6abf69",
    }[status]


def _render_actions_menu(
    service,
    fit_id: int,
    language_code: str,
) -> tuple[bool, bool]:
    """Render the per-row actions menu and return (fit_details_visible, low_stock_visible)."""
    fit_details_visible_key = f"fit_details_visible_{fit_id}"
    low_stock_visible_key = f"low_stock_visible_{fit_id}"
    fit_data_key = f"tab2_data_{fit_id}"

    fit_details_label = translate_text(language_code, "doctrine_status.show_fit_details")
    low_stock_label = translate_text(language_code, "doctrine_status.low_stock_modules")

    selection = st.menu_button(
        "Details",
        options=[fit_details_label, low_stock_label],
        key=f"actions_menu_{fit_id}",
        type="secondary",
        help="toggle fit, module stock details",
        
    )

    if selection == fit_details_label:
        if st.session_state.get(fit_details_visible_key, False):
            st.session_state[fit_details_visible_key] = False
        else:
            if fit_data_key not in st.session_state:
                st.session_state[fit_data_key] = service.repository.get_fit_by_id(
                    fit_id=fit_id
                )
            st.session_state[fit_details_visible_key] = True
    elif selection == low_stock_label:
        st.session_state[low_stock_visible_key] = not st.session_state.get(
            low_stock_visible_key, False
        )

    return (
        bool(st.session_state.get(fit_details_visible_key, False)),
        bool(st.session_state.get(low_stock_visible_key, False)),
    )


def _render_low_stock_modules_panel(
    row: pd.Series,
    fit_id: int,
    target: int,
    equiv_groups: dict,
    sde_repo,
    language_code: str,
) -> None:
    """Render the low-stock module list below a compact doctrine row."""
    with st.container(border=True):
        st.caption(translate_text(language_code, "doctrine_status.low_stock_modules"))
        for mod in row["lowest_modules"]:
            mod_type_id = mod["type_id"]
            mod_name = mod["module_name"]
            mod_fits = mod["fits_on_market"]
            mod_qty_needed = mod["qty_needed"]
            mod_position = mod["position"]
            mod_name_en = mod.get("module_name_en", mod_name)

            has_equiv = mod_type_id in equiv_groups
            display_text = (
                f"{mod_name} ({mod_fits} combined)"
                if has_equiv
                else f"{mod_name} ({mod_fits})"
            )
            module_cb_key = f"mod_{fit_id}_{mod_position}_{mod_type_id}"
            mod_stock_status = StockStatus.from_stock_and_target(mod_fits, target)

            col_a, col_b = st.columns([0.08, 0.92])
            with col_a:
                if module_cb_key not in st.session_state:
                    st.session_state[module_cb_key] = (
                        mod_type_id in st.session_state.selected_type_ids
                    )
                is_selected = st.checkbox(
                    "1", key=module_cb_key, label_visibility="hidden"
                )
                if is_selected:
                    _add_selection(
                        mod_type_id,
                        mod_name_en,
                        mod_fits,
                        mod_qty_needed,
                    )

            with col_b:
                equiv_prefix = "🔄 " if has_equiv else ""
                equiv_help = (
                    f" ({translate_text(language_code, 'doctrine_status.includes_equivalent_modules')})"
                    if has_equiv
                    else ""
                )
                if mod_stock_status == StockStatus.CRITICAL:
                    st.markdown(
                        f":red-badge[:material/error:] {equiv_prefix}{display_text}",
                        help=f"{translate_text(language_code, 'doctrine_status.critical_stock_level')}{equiv_help}",
                    )
                elif mod_stock_status == StockStatus.NEEDS_ATTENTION:
                    st.markdown(
                        f":orange-badge[:material/error:] {equiv_prefix}{display_text}",
                        help=f"{translate_text(language_code, 'doctrine_status.low_stock_help')}{equiv_help}",
                    )
                else:
                    st.caption(f"{equiv_prefix}{display_text}")

                equiv_group = equiv_groups.get(mod_type_id)
                if equiv_group:
                    in_stock_modules = [m for m in equiv_group.modules if m.stock > 0]
                    combined_total = sum(m.stock for m in in_stock_modules)
                    with st.popover(
                        translate_text(
                            language_code,
                            "doctrine_status.view_stock_breakdown",
                        ),
                        use_container_width=True,
                    ):
                        st.markdown(f"**{mod_name}**")
                        st.caption(
                            translate_text(
                                language_code,
                                "doctrine_status.combined_stock_caption",
                            )
                        )
                        for em in in_stock_modules:
                            indicator = "► " if em.type_id == mod_type_id else "   "
                            equiv_name = get_localized_name(
                                em.type_id,
                                em.type_name,
                                sde_repo,
                                language_code,
                                logger,
                            )
                            st.text(f"{indicator}{equiv_name}: {em.stock:,}")
                        st.divider()
                        st.markdown(
                            f"**{translate_text(language_code, 'doctrine_status.combined_total', total=f'{combined_total:,}')}**"
                        )


def _render_fit_details_table(
    fit_id: int,
    sde_repo,
    language_code: str,
) -> None:
    """Render loaded fit details below the compact row."""
    fit_detail_df = st.session_state.get(f"tab2_data_{fit_id}")
    if fit_detail_df is None:
        return

    if fit_detail_df.empty:
        st.info(translate_text(language_code, "doctrine_status.no_fit_details"))
        return

    fit_detail_df = apply_localized_type_names(
        fit_detail_df,
        sde_repo,
        language_code,
        logger,
    )
    fit_detail_df = apply_localized_names(
        fit_detail_df,
        sde_repo,
        language_code,
        id_column="ship_id",
        name_column="ship_name",
        logger=logger,
        english_name_column="ship_name_en",
    )
    col_config = get_fitting_column_config(language_code)
    st.dataframe(
        drop_localized_backup_columns(fit_detail_df),
        hide_index=True,
        column_config=col_config,
        width="stretch",
    )


def main():
    language_code = get_active_language()
    market = render_market_selector()
    sde_repo = get_sde_repository()

    # Read deep-link query param from dashboard
    qp_ship_id = None
    if "ship_id" in st.query_params:
        try:
            qp_ship_id = int(st.query_params["ship_id"])
        except (ValueError, TypeError):
            logger.warning("Invalid ship_id query param: %s", st.query_params["ship_id"])
        del st.query_params["ship_id"]

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    # Initialize service (cached in session state via get_service)
    service = get_doctrine_service()
    fit_build_result = service.build_fit_data()
    summary_df = fit_build_result.summary_df

    render_page_title(
        translate_text(language_code, "doctrine_status.title", market_name=market.name),
        subtitle=translate_text(language_code, "doctrine_status.downloads_hint"),
    )

    # Use summary_df directly from FitBuildResult (no redundant get_fit_summary call)
    if summary_df.empty:
        st.warning(translate_text(language_code, "doctrine_status.no_fits"))
        return
    fit_summary = summary_df.copy()

    # Add filters in the sidebar
    st.sidebar.header(translate_text(language_code, "low_stock.filters_header"))

    # Target multiplier
    ds_target_multiplier = 1.0
    ss_init({"ds_target_multiplier": ds_target_multiplier})
    with st.sidebar.expander(translate_text(language_code, "doctrine_report.target_multiplier")):
        ds_target_multiplier = st.slider(
            translate_text(language_code, "doctrine_report.target_multiplier"),
            min_value=0.5,
            max_value=2.0,
            value=1.0,
            step=0.1,
        )
        st.session_state.ds_target_multiplier = ds_target_multiplier
        st.sidebar.write(
            translate_text(
                language_code,
                "doctrine_report.current_target_multiplier",
                value=ds_target_multiplier,
            )
        )

    # Doctrine filter - filter by fleet doctrine composition
    doctrine_comps = service.repository.get_all_doctrine_compositions()
    all_label = "All"
    doctrine_name_map = (
        {
            int(row["doctrine_id"]): str(row["doctrine_name"])
            for _, row in doctrine_comps[["doctrine_id", "doctrine_name"]]
            .drop_duplicates()
            .iterrows()
        }
        if not doctrine_comps.empty
        else {}
    )
    doctrine_ids = sorted(
        doctrine_name_map,
        key=lambda did: format_doctrine_name(doctrine_name_map[did]),
    )
    selected_doctrine_id = st.sidebar.selectbox(
        translate_text(language_code, "doctrine_status.filter_doctrine"),
        [None] + doctrine_ids,
        format_func=lambda did: all_label if did is None else format_doctrine_name(doctrine_name_map[did]),
    )

    # Stock Status filter (renamed from "Doctrine Status" for clarity - single unified filter)
    status_option_labels = {
        "all": all_label,
        "all_low": "All Low Stock",
        "critical": StockStatus.CRITICAL.display_name,
        "needs_attention": StockStatus.NEEDS_ATTENTION.display_name,
        "good": StockStatus.GOOD.display_name,
    }
    selected_status_key = st.sidebar.selectbox(
        translate_text(language_code, "doctrine_status.filter_stock_status"),
        list(status_option_labels.keys()),
        format_func=lambda key: status_option_labels[key],
    )

    # Ship group filter
    ship_group_df = (
        fit_summary[["ship_group_id", "ship_group"]]
        .dropna()
        .drop_duplicates()
        .sort_values("ship_group")
        .reset_index(drop=True)
    )
    ship_group_name_map = {
        int(row["ship_group_id"]): str(row["ship_group"])
        for _, row in ship_group_df.iterrows()
    }
    ship_group_ids = sorted(ship_group_name_map, key=lambda gid: ship_group_name_map[gid])
    selected_group_id = st.sidebar.selectbox(
        translate_text(language_code, "doctrine_status.filter_ship_group"),
        [None] + ship_group_ids,
        format_func=lambda gid: all_label if gid is None else ship_group_name_map[gid],
    )

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
    if selected_status_key != "all":
        if selected_status_key == "good":
            filtered_df = filtered_df[filtered_df["target_percentage"] > 90]
        elif selected_status_key == "all_low":
            filtered_df = filtered_df[filtered_df["target_percentage"] <= 90]
        elif selected_status_key == "needs_attention":
            filtered_df = filtered_df[
                (filtered_df["target_percentage"] > 20)
                & (filtered_df["target_percentage"] <= 90)
            ]
        elif selected_status_key == "critical":
            filtered_df = filtered_df[filtered_df["target_percentage"] <= 20]

    # Apply ship group filter
    if selected_group_id is not None:
        filtered_df = filtered_df[filtered_df["ship_group_id"] == selected_group_id]

    # Apply doctrine filter
    if selected_doctrine_id is not None:
        doctrine_fit_ids = doctrine_comps[
            doctrine_comps["doctrine_id"] == selected_doctrine_id
        ]["fit_id"].unique()
        filtered_df = filtered_df[filtered_df["fit_id"].isin(doctrine_fit_ids)]

    # Apply deep-link filter from dashboard (show only the linked ship)
    if qp_ship_id is not None and "ship_id" in filtered_df.columns:
        ship_match = filtered_df[filtered_df["ship_id"] == qp_ship_id]
        if not ship_match.empty:
            filtered_df = ship_match

    # Update the displayed ships based on filters
    st.session_state.displayed_ships = filtered_df["ship_name"].unique().tolist()

    if filtered_df.empty:
        st.info(translate_text(language_code, "doctrine_status.no_filtered_fits"))
        return

    display_df = _localize_summary_df(filtered_df, sde_repo, language_code)

    # Pre-fetch set of type_ids with equivalents (O(1) lookup per module)
    try:
        from settings_service import SettingsService
        _use_equiv = SettingsService().use_equivalents
    except Exception:
        _use_equiv = False

    type_ids_with_equivs: set[int] = set()
    equiv_groups: dict = {}  # type_id -> EquivalenceGroup
    if _use_equiv:
        try:
            equiv_service = get_module_equivalents_service()
            type_ids_with_equivs = equiv_service.get_type_ids_with_equivalents()
        except Exception:
            pass

    # Pre-fetch equivalence group breakdowns for modules in lowest_modules.
    # Only include groups where at least one *other* equivalent has stock.
    if _use_equiv and type_ids_with_equivs:
        equiv_type_ids_in_fits: set[int] = set()
        for _, row in filtered_df.iterrows():
            for mod in row.get("lowest_modules", []):
                if mod["type_id"] in type_ids_with_equivs:
                    equiv_type_ids_in_fits.add(mod["type_id"])
        for tid in equiv_type_ids_in_fits:
            group = equiv_service.get_equivalence_group(tid)
            if group:
                others_in_stock = [
                    m for m in group.modules if m.stock > 0 and m.type_id != tid
                ]
                if others_in_stock:
                    equiv_groups[tid] = group

    # Group the data by ship_group
    grouped_fits = display_df.groupby("ship_group")

    # Iterate through each group and display fits
    for group_name, group_data in grouped_fits:
        # Display group header
        st.markdown(
            (
                "<div "
                f"title='{translate_text(language_code, 'doctrine_status.ship_group_help')}' "
                "style='margin: 0.2rem 0 0.1rem 0;'>"
                f"<div style='font-size: 1.3rem; font-weight: 600; color: #6b7280; line-height: 1.15;'>{group_name}</div>"
                    "<div style='height: 1.5px; background: rgba(245, 158, 11, 0.55); margin-top: 0.18rem; margin-bottom: 0.2rem;'></div>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        # Display the fits in this group
        for _, row in group_data.iterrows():
            target_pct = (
                int(row["target_percentage"])
                if pd.notna(row["target_percentage"])
                else 0
            )
            target = int(row["ship_target"]) if pd.notna(row["ship_target"]) else 0
            fits = int(row["fits"]) if pd.notna(row["fits"]) else 0
            hulls = int(row["hulls"]) if pd.notna(row["hulls"]) else 0
            ship_id = int(row["ship_id"])
            fit_id = int(row["fit_id"])
            fit_name = row["fit_name"]
            fit_cost = (
                millify(int(row["total_cost"]), precision=2)
                if pd.notna(row["total_cost"])
                else "N/A"
            )
            stock_status = StockStatus.from_percentage(target_pct)
            ship_name_en = row.get("ship_name_en", row["ship_name"])
            fit_details_visible = False
            low_stock_visible = False

            row_cols = st.columns([0.1, 0.4,0.3, 0.2], gap="small", vertical_alignment="center")

            #row_cols1,row_cols2,row_cols3,row_cols4 = st.columns([0.1,0.4,0.4,0.1])

            with row_cols[0]:
                left_cols = st.columns([0.25, 0.75], gap="small", vertical_alignment="center")
                with left_cols[0]:
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
                        _add_selection(
                            ship_id,
                            ship_name_en,
                            hulls,
                            hull_qty_needed,
                        )

                with left_cols[1]:
                    with st.container(height='stretch', vertical_alignment='center', horizontal_alignment='left'):
                        try:
                            st.image(
                                f"https://images.evetech.net/types/{ship_id}/icon",
                                width=42
                            )
                        except Exception:
                            st.caption(
                                translate_text(
                                    language_code,
                                    "doctrine_status.image_not_available",
                                )
                            )

            with row_cols[1]:
                st.markdown(
                    (
                        "<div style='font-size: 1.15rem; line-height: 1.12rem; margin: 0; padding: 0.25rem; "
                        "white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>"
                        f"<span style='color: #3285a8;'>{translate_text(language_code, 'doctrine_status.fit_id_label', fit_id=fit_id)}</span>"
                        f"&nbsp;&nbsp;{translate_text(language_code, 'doctrine_status.fit_name_label', fit_name=fit_name)}"
                        "</div>"
                            #"<div style='font-size: 1rem; line-height: 1; margin: 0.08rem 0 0 0; padding: 0.25rem;'>"
                        f"<span style='color: #688c9c;'>{translate_text(language_code, 'low_stock.column_fits')}: </span>"
                        f"{fits}"
                        f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                            f"<span style='color: grey;'>{translate_text(language_code, 'doctrine_report.metric_total_hulls')}: </span>"
                        f"{hulls}"
                        f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                            f"<span style='color: grey;'>{translate_text(language_code, 'doctrine_report.target')}: </span>"
                        f"{target}"
                        f"&nbsp;&nbsp;|&nbsp;&nbsp;"
                            f"<span style='color: grey;'>{translate_text(language_code, 'doctrine_report.column_total_cost')}: </span>"
                        f"{fit_cost}"
                            #f"&nbsp;&nbsp;|&nbsp;&nbsp;<span style='color: "
                            #f"{_status_text_color(stock_status)}; font-weight: 600;'>"
                            #f"{stock_status.display_name}</span>"
                        "</div>"
                                           ),
                    unsafe_allow_html=True,
                )
            with row_cols[2]:
                st.markdown(render_progress_bar_html(target_pct, height=25), unsafe_allow_html=True)

            with row_cols[3]:
                with st.container(width='stretch', vertical_alignment='center', horizontal_alignment='center'):
                    fit_details_visible, low_stock_visible = _render_actions_menu(
                        service=service,
                        fit_id=fit_id,
                        language_code=language_code,
                    )


            if fit_details_visible:
                _render_fit_details_table(
                    fit_id=fit_id,
                    sde_repo=sde_repo,
                    language_code=language_code,
                )

            if low_stock_visible:
                _render_low_stock_modules_panel(
                    row=row,
                    fit_id=fit_id,
                    target=target,
                    equiv_groups=equiv_groups,
                    sde_repo=sde_repo,
                    language_code=language_code,
                )

            st.markdown(
                "<hr style='margin: 0.05rem 0 0.08rem 0; border-width: 1px'>",
                unsafe_allow_html=True,
            )

    # Rebuild selections from checkbox states after all checkboxes have rendered
    _rebuild_selections()

    # =========================================================================
    # Sidebar Export Section — unified for ships and modules
    # =========================================================================
    st.sidebar.markdown("---")
    st.sidebar.header(translate_text(language_code, "doctrine_report.export_options"))

    col1, col2 = st.sidebar.columns(2)

    # Select All — adds all visible ships + modules
    if col1.button(translate_text(language_code, "doctrine_status.select_all"), width="content"):
        for _, group_data in grouped_fits:
            for _, row in group_data.iterrows():
                if row.get("ship_name_en", row["ship_name"]) not in st.session_state.displayed_ships:
                    continue
                sid = int(row["ship_id"])
                target_count = int(row["ship_target"]) if pd.notna(row["ship_target"]) else 0
                h = int(row["hulls"]) if pd.notna(row["hulls"]) else 0
                _add_selection(
                    sid,
                    row.get("ship_name_en", row["ship_name"]),
                    h,
                    max(0, target_count - h),
                )
                for mod in row["lowest_modules"]:
                    _add_selection(
                        mod["type_id"],
                        mod.get("module_name_en", mod["module_name"]),
                        mod["fits_on_market"], mod["qty_needed"],
                    )
        st.session_state.export_data_rendered = False
        # Clear checkbox states so they reinitialize
        keys_to_clear = [
            k for k in st.session_state.keys()
            if str(k).startswith("ship_") or str(k).startswith("mod_")
        ]
        for k in keys_to_clear:
            del st.session_state[k]
        st.rerun()

    # Clear All
    if col2.button(translate_text(language_code, "doctrine_status.clear_all"), width="content"):
        st.session_state.selected_type_ids = set()
        st.session_state.type_id_info = {}
        st.session_state.rendered_export_data = {}
        st.session_state.export_data_rendered = False
        keys_to_clear = [
            k for k in st.session_state.keys()
            if str(k).startswith("ship_") or str(k).startswith("mod_")
        ]
        for k in keys_to_clear:
            del st.session_state[k]
        logger.info("Cleared all selections")
        st.rerun()

    # Display lightweight selection list (no DB queries)
    selected = st.session_state.selected_type_ids
    if selected:
        st.sidebar.markdown("---")
        st.sidebar.header(translate_text(language_code, "doctrine_status.selected_items"), divider="blue")
        help_msg = translate_text(language_code, "doctrine_status.selected_items_help")
        st.sidebar.caption(f"*{help_msg}*")

        selection_lines = []
        for tid in sorted(selected):
            info = st.session_state.type_id_info.get(tid, {})
            name = info.get("module_name", f"Unknown ({tid})")
            qty = info.get("qty_needed", 0)
            display_name = get_localized_name(tid, name, sde_repo, language_code, logger)
            selection_lines.append(f"{display_name} {qty}")
        st.sidebar.code("\n".join(selection_lines), language=None)

        # Render market data button — triggers DB queries only when clicked
        if st.sidebar.button(
            translate_text(language_code, "doctrine_status.render_market_data"),
            type="primary",
        ):
            render_export_data()
            st.session_state.export_data_rendered = True
            st.rerun()
        # Show rendered market data and export options
        if ss_get("export_data_rendered"):
            st.sidebar.markdown("---")
            st.sidebar.subheader(translate_text(language_code, "doctrine_status.market_data"))

            detail_lines = []
            rendered = st.session_state.get("rendered_export_data", {})
            for tid in sorted(selected):
                data = rendered.get(tid, {})
                name = data.get("name", st.session_state.type_id_info.get(tid, {}).get("module_name", f"Unknown ({tid})"))
                display_name = get_localized_name(tid, name, sde_repo, language_code, logger)
                stock = data.get("total_stock", 0)
                fits_mkt = data.get("fits_on_mkt", 0)
                qty = data.get("qty_needed", 0)
                detail_lines.append(
                    translate_text(
                        language_code,
                        "doctrine_status.market_data_line",
                        name=display_name,
                        stock=stock,
                        fits=fits_mkt,
                        need=qty,
                    )
                )
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
                label=translate_text(language_code, "doctrine_report.download_csv"),
                data=csv_export,
                file_name="doctrine_export.csv",
                mime="text/csv",
            )
    else:
        st.sidebar.info(
            translate_text(language_code, "doctrine_status.select_items_for_export")
        )

    # Display last update timestamp
    st.sidebar.markdown("---")
    display_sync_status(language_code=language_code)


if __name__ == "__main__":
    main()
