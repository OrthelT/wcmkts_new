
import os
import pathlib
import sys

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from domain import StockStatus
from logging_config import setup_logging
from services import get_doctrine_service
from services.categorization import categorize_ship_by_role
from ui.formatters import get_doctrine_report_column_config, get_image_url
from services.doctrine_service import format_doctrine_name
from services.type_name_localization import (
    apply_localized_names,
    apply_localized_type_names,
    get_localized_name,
)
from repositories import get_sde_repository
from ui.popovers import render_ship_with_popover, render_market_popover
from services.module_equivalents_service import get_module_equivalents_service
from state import get_active_language, ss_init
from ui.i18n import translate_text
from ui.market_selector import render_market_selector
from init_db import ensure_market_db_ready
from ui.sync_display import display_sync_status
logger = setup_logging(__name__, log_file="doctrine_report.log")

icon_id = 0
icon_url = f"https://images.evetech.net/types/{icon_id}/render?size=64"

def _drop_localized_backup_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove helper columns that should not appear in display tables."""
    return df.drop(columns=["type_name_en", "ship_name_en"], errors="ignore")


def _localize_doctrine_df(
    df: pd.DataFrame,
    sde_repo,
    language_code: str,
    include_type_names: bool = False,
) -> pd.DataFrame:
    """Localize doctrine dataframe display columns."""
    localized_df = df
    if include_type_names:
        localized_df = apply_localized_type_names(localized_df, sde_repo, language_code, logger)

    return apply_localized_names(
        localized_df,
        sde_repo,
        language_code,
        id_column="ship_id",
        name_column="ship_name",
        logger=logger,
        english_name_column="ship_name_en",
    )


def get_module_stock_list(type_ids: list[int], sde_repo, language_code: str):
    """Get lists of modules with their stock quantities for display and CSV export using service.

    Args:
        type_ids: List of EVE type IDs to query stock for
        sde_repo: SDE repository for localized name lookups
        language_code: Active language code for display names
    """

    # Set the session state variables for the module list and csv module list
    ss_init({
        'module_list_state': {},
        'csv_module_list_state': {},
    })

    for type_id in type_ids:
        if type_id not in st.session_state.module_list_state:
            logger.info(f"Querying database for type_id={type_id} via service")

            # Use service repository to get module stock info
            svc = get_doctrine_service()
            module_stock = svc.repository.get_module_stock(type_id)

            if module_stock:
                display_name = get_localized_name(
                    module_stock.type_id,
                    module_stock.type_name,
                    sde_repo,
                    language_code,
                    logger,
                )
                module_info = {
                    "display_name": display_name,
                    "total_stock": module_stock.total_stock,
                    "fits_on_mkt": module_stock.fits_on_mkt,
                }
                csv_module_info = (
                    f"{module_stock.type_name},{module_stock.type_id},"
                    f"{module_stock.total_stock},{module_stock.fits_on_mkt}\n"
                )
            else:
                module_info = {
                    "display_name": f"Unknown ({type_id})",
                    "total_stock": 0,
                    "fits_on_mkt": 0,
                }
                csv_module_info = f"Unknown ({type_id}),{type_id},0,0\n"

            st.session_state.module_list_state[type_id] = module_info
            st.session_state.csv_module_list_state[type_id] = csv_module_info

def _get_role_label(role: str, language_code: str) -> str:
    role_key = f"doctrine_report.role_{role.lower()}"
    return translate_text(language_code, role_key)


def display_categorized_doctrine_data(selected_data, language_code: str):
    """Display doctrine data grouped by ship functional roles."""

    if selected_data.empty:
        st.warning(translate_text(language_code, "doctrine_report.no_data"))
        return

    # Create a proper copy of the DataFrame to avoid SettingWithCopyWarning
    selected_data_with_roles = selected_data.copy()
    selected_data_with_roles['role'] = selected_data_with_roles.apply(
        lambda row: categorize_ship_by_role(row['ship_name'], row['fit_id']),
        axis=1
    )

    # Remove fit_id 474 using loc
    selected_data_with_roles = selected_data_with_roles.loc[selected_data_with_roles['fit_id'] != 474]

    # Group by role and display each category
    roles_present = selected_data_with_roles['role'].unique()

    for role in ["DPS", "Logi", "Links", "Support"]:  # Display in logical order
        if role not in roles_present:
            continue

        role_data = selected_data_with_roles[selected_data_with_roles['role'] == role]
        styler = _get_role_label(role, language_code)

        # Create expandable section for each role
        with st.expander(styler, expanded=True):
            # Create columns for metrics summary
            col1, col2, col3 = st.columns(3, gap="small", width=500)

            with col1:
                total_fits = role_data['fits'].sum() if 'fits' in role_data.columns else 0
                total_fits = 0 if pd.isna(total_fits) else total_fits
                st.metric(translate_text(language_code, "doctrine_report.metric_total_fits"), f"{int(total_fits)}")

            with col2:
                total_hulls = role_data['hulls'].sum() if 'hulls' in role_data.columns else 0
                total_hulls = 0 if pd.isna(total_hulls) else total_hulls
                st.metric(translate_text(language_code, "doctrine_report.metric_total_hulls"), f"{int(total_hulls)}")

            with col3:
                avg_target_pct = role_data['target_percentage'].mean() if 'target_percentage' in role_data.columns else 0
                avg_target_pct = 0 if pd.isna(avg_target_pct) else avg_target_pct
                st.metric(
                    translate_text(language_code, "doctrine_report.metric_avg_target_pct"),
                    f"{int(avg_target_pct)}%",
                )


            df = role_data.copy()
            df = df.drop(columns=['role']).reset_index(drop=True)
            df['ship_target'] = df['ship_target'] * st.session_state.target_multiplier
            df['target_percentage'] = round(df['fits'] / df['ship_target'], 2)

            # padding for the dataframe to avoid cutting off the bottom of small dataframes
            static_height = len(df) * 40 + 50 if len(df) < 10 else 'auto'

            st.dataframe(
                _drop_localized_backup_columns(df),
                column_config=get_doctrine_report_column_config(language_code),
                width='content',
                hide_index=True,
                height=static_height
            )

def display_low_stock_modules(
    selected_data: pd.DataFrame,
    doctrine_modules: pd.DataFrame,
    selected_fit_ids: list,
    fit_summary: pd.DataFrame,
    lead_ship_id: int,
    selected_doctrine_id: int,
    sde_repo,
    language_code: str,
):
    """Display low stock modules for the selected doctrine"""
        # Get module data from master_df for the selected doctrine
    if not doctrine_modules.empty:

        # Pre-fetch set of type_ids with equivalents
        type_ids_with_equivs: set[int] = set()
        try:
            from settings_service import SettingsService
            if SettingsService().use_equivalents:
                equiv_svc = get_module_equivalents_service()
                type_ids_with_equivs = equiv_svc.get_type_ids_with_equivalents()
        except Exception:
            pass

        st.subheader(translate_text(language_code, "doctrine_report.stock_status"), divider="blue")
        st.markdown(translate_text(language_code, "doctrine_report.stock_status_summary"))
        st.markdown("---")

        exceptions = {21: 123, 75: 473, 84: 494}

        if selected_doctrine_id in exceptions:
            lead_fit_id = exceptions[selected_doctrine_id]
        else:
            lead_matches = selected_data[selected_data['ship_id'] == lead_ship_id]
            if not lead_matches.empty:
                lead_fit_id = lead_matches.fit_id.iloc[0]
            else:
                lead_fit_id = selected_data.fit_id.iloc[0] if not selected_data.empty else selected_fit_ids[0]

        # Create two columns for display
        col1, col2 = st.columns(2)

        # Get unique fit_ids and process each ship
        for i, fit_id in enumerate(selected_fit_ids):

            if i == 0:
                fit_id = lead_fit_id
                fit_data = doctrine_modules[doctrine_modules['fit_id'] == fit_id]
            elif i > 0 and fit_id != lead_fit_id:
                fit_data = doctrine_modules[doctrine_modules['fit_id'] == fit_id]
            else:
                continue

            if fit_data.empty:
                continue

            # Get ship information
            ship_data = fit_data.iloc[0]
            ship_name = ship_data['ship_name']
            ship_id = ship_data['ship_id']
            # Get modules only (exclude the ship hull)
            module_data = fit_data[fit_data['type_id'] != ship_id]
            ship_data = fit_data[fit_data['type_id'] == ship_id]

            if module_data.empty:
                continue

            # Get the 3 lowest stock modules for this ship
            lowest_modules = module_data.sort_values('fits_on_mkt').head(3)
            lowest_modules = pd.concat([ship_data,lowest_modules])

            # Determine which column to use
            target_col = col1 if i % 2 == 0 else col2

            with target_col:
                # Create ship header section
                ship_col1, ship_col2 = st.columns([0.2, 0.8])

                with ship_col1:
                    try:
                        st.image(get_image_url(ship_id, 64), width=64)
                    except Exception:
                        st.text("🚀")
                    st.text(f"{translate_text(language_code, 'doctrine_report.fit_id')}: {fit_id}")

                with ship_col2:
                    # Get fit name from service
                    fit_name = get_doctrine_service().get_fit_name(fit_id)

                    ship_target = fit_summary[fit_summary['fit_id'] == fit_id]['ship_target'].iloc[0]
                    if pd.notna(ship_target):
                        ship_target = int(ship_target * st.session_state.target_multiplier)
                    else:
                        ship_target = 0

                    # Ship name with market data popover
                    render_ship_with_popover(
                        ship_id=ship_id,
                        ship_name=ship_name,
                        fits=int(fit_summary[fit_summary['fit_id'] == fit_id]['fits'].iloc[0]) if not fit_summary[fit_summary['fit_id'] == fit_id].empty else 0,
                        hulls=int(fit_summary[fit_summary['fit_id'] == fit_id]['hulls'].iloc[0]) if not fit_summary[fit_summary['fit_id'] == fit_id].empty else 0,
                        target=ship_target,
                        key_suffix=f"dr_{fit_id}"
                    )
                    st.markdown(
                        f"{fit_name}  (**{translate_text(language_code, 'doctrine_report.target')}: {ship_target}**)"
                    )

                # Track if any module has equivalents for caption
                fit_has_equivalents = False

                # Display the 3 lowest stock modules
                for _, module_row in lowest_modules.iterrows():
                    # Get target for this fit from selected_data
                    fit_target_row = selected_data[selected_data['fit_id'] == fit_id]

                    if not fit_target_row.empty and 'ship_target' in fit_target_row.columns:
                        target = fit_target_row['ship_target'].iloc[0]
                    else:
                        st.write(translate_text(language_code, "doctrine_report.no_target_found"))
                        target = 20  # Default target

                    module_name = module_row['type_name']
                    type_id = int(module_row['type_id']) if pd.notna(module_row['type_id']) else 0
                    stock = int(module_row['fits_on_mkt']) if pd.notna(module_row['fits_on_mkt']) else 0
                    module_target = int(target) if pd.notna(target) else 0
                    module_key = f"ship_module_{fit_id}_{type_id}"

                    stock_status = StockStatus.from_stock_and_target(stock, module_target)
                    badge_status = stock_status.display_name
                    badge_color = stock_status.display_color

                    # Create checkbox and module info
                    checkbox_col, badge_col, text_col = st.columns([0.1, 0.2, 0.7])

                    with checkbox_col:
                        is_selected = st.checkbox(
                            "x",
                            key=module_key,
                            label_visibility="hidden",
                            value=type_id in st.session_state.selected_modules
                        )

                        # Update session state based on checkbox
                        if is_selected and type_id not in st.session_state.selected_modules:
                            st.session_state.selected_modules.add(type_id)
                            st.session_state.module_id_info[type_id] = module_name
                            # Also update the stock info
                            get_module_stock_list([type_id], sde_repo, language_code)
                        elif not is_selected and type_id in st.session_state.selected_modules:
                            st.session_state.selected_modules.discard(type_id)

                    with badge_col:
                        # Show badge for all modules to indicate their status
                        st.badge(badge_status, color=badge_color)

                    with text_col:
                        # Display with market data popover
                        type_id = int(module_row['type_id']) if pd.notna(module_row['type_id']) else 0
                        if type_id == ship_id:
                            # It's the ship hull
                            render_ship_with_popover(
                                ship_id=ship_id,
                                ship_name=ship_name,
                                fits=stock,
                                hulls=stock,
                                target=module_target,
                                key_suffix=f"dr_hull_{fit_id}"
                            )
                        else:
                            # It's a module - check for equivalents
                            module_has_equiv = type_id in type_ids_with_equivs if type_id else False
                            if module_has_equiv:
                                fit_has_equivalents = True
                                display_text = f"🔄 {module_name} ({stock} combined)"
                            else:
                                display_text = f"{module_name} ({stock})"

                            render_market_popover(
                                type_id=type_id,
                                type_name=module_name,
                                quantity=stock,
                                display_text=display_text,
                                key_suffix=f"dr_mod_{fit_id}_{type_id}"
                            )

                # Show caption if any module has equivalents
                if fit_has_equivalents:
                    st.caption(translate_text(language_code, "doctrine_report.equivalent_stock_caption"))

                # Add spacing between ships
                st.markdown("<br>", unsafe_allow_html=True)

def main():
    language_code = get_active_language()
    market = render_market_selector()
    sde_repo = get_sde_repository()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

    # Initialize service (cached in session state via get_service)
    service = get_doctrine_service()

    # Initialize session state for target multiplier and selected module type_ids
    ss_init({
        'target_multiplier': 1.0,
        'selected_modules': set(),
        'module_id_info': {},
    })
    # Coerce legacy list state from pre-deploy sessions to set
    if isinstance(st.session_state.selected_modules, list):
        st.session_state.selected_modules = set()

    # App title and logo
    # Handle path properly for WSL environment
    image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"


    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image(image_path, 150)
    with col2:
        st.title(translate_text(language_code, "nav.page.doctrine_report").lstrip("📝"))
        st.text(translate_text(language_code, "doctrine_report.subtitle", market_name=market.name))

    # Fetch the data using service
    result = service.build_fit_data()
    master_df = result.raw_df
    fit_summary = result.summary_df

    if fit_summary.empty:
        st.warning(translate_text(language_code, "doctrine_report.no_fits"))
        return

    df = service.repository.get_all_doctrine_compositions()

    doctrine_df = (
        df[["doctrine_id", "doctrine_name"]]
        .drop_duplicates()
        .sort_values("doctrine_name")
        .reset_index(drop=True)
    )
    doctrine_name_map = {
        int(row["doctrine_id"]): str(row["doctrine_name"])
        for _, row in doctrine_df.iterrows()
    }
    doctrine_ids = sorted(doctrine_name_map, key=lambda did: format_doctrine_name(doctrine_name_map[did]))

    selected_doctrine_id = st.sidebar.selectbox(
        translate_text(language_code, "doctrine_report.select_doctrine"),
        doctrine_ids,
        format_func=lambda did: format_doctrine_name(doctrine_name_map[did]),
    )
    selected_doctrine = doctrine_name_map[selected_doctrine_id]

    selected_data = fit_summary[
        fit_summary["fit_id"].isin(df[df["doctrine_id"] == selected_doctrine_id].fit_id.unique())
    ]

    # Get module data from master_df for the selected doctrine
    selected_fit_ids = df[df["doctrine_id"] == selected_doctrine_id].fit_id.unique()
    doctrine_modules = master_df[master_df['fit_id'].isin(selected_fit_ids)]
    display_selected_data = _localize_doctrine_df(
        selected_data,
        sde_repo,
        language_code,
    )
    display_doctrine_modules = _localize_doctrine_df(
        doctrine_modules,
        sde_repo,
        language_code,
        include_type_names=True,
    )

    # Add Target Multiplier expander to sidebar
    st.sidebar.markdown("---")

    target_multiplier = st.sidebar.slider(
            translate_text(language_code, "doctrine_report.target_multiplier"),
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.target_multiplier,
            step=0.1,
            help=translate_text(language_code, "doctrine_report.target_multiplier_help"),
        )

    st.session_state.target_multiplier = target_multiplier
    st.sidebar.markdown(
        translate_text(language_code, "doctrine_report.current_target_multiplier", value=target_multiplier)
    )

    # Create enhanced header with lead ship image
    # Get lead ship image for this doctrine
    lead_ship_id = service.repository.get_doctrine_lead_ship(selected_doctrine_id)
    lead_ship_image_url = get_image_url(lead_ship_id, 256)

    # Create two-column layout for doctrine header
    header_col1, header_col2 = st.columns([0.2, 0.8], gap="small", vertical_alignment="center")

    with header_col1:
        try:
            st.image(lead_ship_image_url, width=128)
        except Exception:
            st.text(translate_text(language_code, "doctrine_report.ship_image_not_available"))

    with header_col2:
        st.markdown("&nbsp;")  # Add some spacing
        st.subheader(format_doctrine_name(selected_doctrine), anchor=selected_doctrine, divider=True)
        st.markdown("&nbsp;")  # Add some spacing

    st.write(translate_text(language_code, "doctrine_report.doctrine_id", doctrine_id=selected_doctrine_id))
    st.markdown("---")

    # Display categorized doctrine data instead of simple dataframe
    display_categorized_doctrine_data(display_selected_data, language_code)

    # Display lowest stock modules by ship with checkboxes
    display_low_stock_modules(
        display_selected_data,
        display_doctrine_modules,
        selected_fit_ids,
        fit_summary,
        lead_ship_id,
        selected_doctrine_id,
        sde_repo,
        language_code,
    )

    # Display selected modules if any
    st.sidebar.markdown("---")


    st.sidebar.header(translate_text(language_code, "doctrine_report.selected_items"), divider="blue")

    # Format selected items using code block for cleaner display
    if st.session_state.selected_modules:
        selection_lines = [translate_text(language_code, "doctrine_report.modules_label")]
        for tid in sorted(st.session_state.selected_modules):
            display_name = st.session_state.module_id_info.get(tid, f"Unknown ({tid})")
            if tid in st.session_state.get('module_list_state', {}):
                item_info = st.session_state.module_list_state[tid]
                total_stock = item_info.get("total_stock", 0)
                fits_on_mkt = item_info.get("fits_on_mkt", 0)
                selection_lines.append(
                    f"  {display_name} (Total: {total_stock} | Fits: {fits_on_mkt})"
                )
            else:
                selection_lines.append(f"  {display_name} (N/A)")

        st.sidebar.code("\n".join(selection_lines), language=None)
    else:
        st.sidebar.info(translate_text(language_code, "doctrine_report.no_items_selected"))

    st.sidebar.markdown(f"### {translate_text(language_code, 'doctrine_report.export_options')}")

        # Prepare export data
    if st.session_state.get('csv_module_list_state'):
        csv_export = "Type,TypeID,Quantity,Fits\n"
        for tid in st.session_state.selected_modules:
            if tid in st.session_state.csv_module_list_state:
                csv_export += st.session_state.csv_module_list_state[tid]

        # Download button
        st.sidebar.download_button(
            label=translate_text(language_code, "doctrine_report.download_csv"),
            data=csv_export,
            file_name="low_stock_list.csv",
            mime="text/csv",
            width='content'
        )

    # Clear selection button
    if st.sidebar.button(translate_text(language_code, "doctrine_report.clear_selection"), width='content'):
        st.session_state.selected_modules = set()
        st.session_state.module_id_info = {}
        st.session_state.module_list_state = {}
        st.session_state.csv_module_list_state = {}
        st.rerun()

    display_sync_status(language_code=language_code)
    st.sidebar.markdown("---")
if __name__ == "__main__":
    main()
