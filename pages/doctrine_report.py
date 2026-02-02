
import os
import pathlib
import sys

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from repositories import get_update_time
from domain import StockStatus
from logging_config import setup_logging
from services import get_doctrine_service
from services.categorization import categorize_ship_by_role
from ui.formatters import get_doctrine_report_column_config, get_image_url, get_ship_role_format
from ui.popovers import render_ship_with_popover, render_market_popover, has_equivalent_modules
from state import ss_init, ss_get

logger = setup_logging(__name__, log_file=__name__)

# Initialize service (cached in session state)
service = get_doctrine_service()

icon_id = 0
icon_url = f"https://images.evetech.net/types/{icon_id}/render?size=64"

def get_module_stock_list(module_names: list):
    """Get lists of modules with their stock quantities for display and CSV export using service."""

    # Set the session state variables for the module list and csv module list
    ss_init({
        'module_list_state': {},
        'csv_module_list_state': {},
    })

    for module_name in module_names:
        if module_name not in st.session_state.module_list_state:
            logger.info(f"Querying database for {module_name} via service")

            # Use service repository to get module stock info
            module_stock = service.repository.get_module_stock(module_name)

            if module_stock:
                module_info = f"{module_name} (Total: {module_stock.total_stock} | Fits: {module_stock.fits_on_mkt})"
                csv_module_info = f"{module_name},{module_stock.type_id},{module_stock.total_stock},{module_stock.fits_on_mkt}\n"
            else:
                module_info = f"{module_name}"
                csv_module_info = f"{module_name},0,0,0\n"

            st.session_state.module_list_state[module_name] = module_info
            st.session_state.csv_module_list_state[module_name] = csv_module_info

def display_categorized_doctrine_data(selected_data):
    """Display doctrine data grouped by ship functional roles."""

    if selected_data.empty:
        st.warning("No data to display")
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
        styler = get_ship_role_format(role)

        # Create expandable section for each role
        with st.expander(styler, expanded=True):
            # Create columns for metrics summary
            col1, col2, col3 = st.columns(3, gap="small", width=500)

            with col1:
                total_fits = role_data['fits'].sum() if 'fits' in role_data.columns else 0
                total_fits = 0 if pd.isna(total_fits) else total_fits
                st.metric("Total Fits Available", f"{int(total_fits)}")

            with col2:
                total_hulls = role_data['hulls'].sum() if 'hulls' in role_data.columns else 0
                total_hulls = 0 if pd.isna(total_hulls) else total_hulls
                st.metric("Total Hulls", f"{int(total_hulls)}")

            with col3:
                avg_target_pct = role_data['target_percentage'].mean() if 'target_percentage' in role_data.columns else 0
                avg_target_pct = 0 if pd.isna(avg_target_pct) else avg_target_pct
                st.metric("Avg Target %", f"{int(avg_target_pct)}%")


            df = role_data.copy()
            df = df.drop(columns=['role']).reset_index(drop=True)
            df['ship_target'] = df['ship_target'] * st.session_state.target_multiplier
            df['target_percentage'] = round(df['fits'] / df['ship_target'], 2)

            # padding for the dataframe to avoid cutting off the bottom of small dataframes
            static_height = len(df) * 40 + 50 if len(df) < 10 else 'auto'

            st.dataframe(
                df, 
                column_config=get_doctrine_report_column_config(),
                width='content',
                hide_index=True,
                height=static_height
            )

def display_low_stock_modules(selected_data: pd.DataFrame, doctrine_modules: pd.DataFrame, selected_fit_ids: list, fit_summary: pd.DataFrame, lead_ship_id: int, selected_doctrine_id: int):
    """Display low stock modules for the selected doctrine"""
        # Get module data from master_df for the selected doctrine
    if not doctrine_modules.empty:

        st.subheader("Stock Status",divider="blue")
        st.markdown("*Summary of the stock status of the three lowest stock modules for each ship in the selected doctrine. Numbers in parentheses represent the number of fits that can be supported with the current stock of the item. Use the checkboxes to select items for export to a CSV file.*")
        st.markdown("---")

        exceptions = {21: 123, 75: 473, 84: 494}

        if selected_doctrine_id in exceptions:
            lead_fit_id = exceptions[selected_doctrine_id]
        else:
            lead_fit_id = selected_data[selected_data['ship_id'] == lead_ship_id].fit_id.iloc[0]
 
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
                    st.text(f"Fit ID: {fit_id}")

                with ship_col2:
                    # Get fit name from service
                    fit_name = service.get_fit_name(fit_id)

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
                    st.markdown(f"{fit_name}  (**Target: {ship_target}**)")

                # Track if any module has equivalents for caption
                fit_has_equivalents = False

                # Display the 3 lowest stock modules
                for _, module_row in lowest_modules.iterrows():
                    # Get target for this fit from selected_data
                    fit_target_row = selected_data[selected_data['fit_id'] == fit_id]

                    if not fit_target_row.empty and 'ship_target' in fit_target_row.columns:
                        target = fit_target_row['ship_target'].iloc[0]
                    else:
                        st.write("No target found for this fit")
                        target = 20  # Default target

                    module_name = module_row['type_name']
                    stock = int(module_row['fits_on_mkt']) if pd.notna(module_row['fits_on_mkt']) else 0
                    module_target = int(target) if pd.notna(target) else 0
                    module_key = f"ship_module_{fit_id}_{module_name}_{stock}_{module_target}"

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
                            value=module_name in st.session_state.selected_modules
                        )

                        # Update session state based on checkbox
                        if is_selected and module_name not in st.session_state.selected_modules:
                            st.session_state.selected_modules.append(module_name)
                            # Also update the stock info
                            get_module_stock_list([module_name])
                        elif not is_selected and module_name in st.session_state.selected_modules:
                            st.session_state.selected_modules.remove(module_name)

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
                            module_has_equiv = has_equivalent_modules(type_id) if type_id else False
                            if module_has_equiv:
                                fit_has_equivalents = True
                                display_text = f"🔄 {module_name} ({stock})"
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
                    st.caption("🔄 Stock includes equivalent modules")

                # Add spacing between ships
                st.markdown("<br>", unsafe_allow_html=True)

def main():
    # Initialize session state for target multiplier and selected modules
    ss_init({
        'target_multiplier': 1.0,
        'selected_modules': [],
    })

    # App title and logo
    # Handle path properly for WSL environment
    image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"


    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image(image_path, 150)
    with col2:
        st.title("Doctrine Report")
        st.text("4-HWWF Market Status By Fleet Doctrine")

    # Fetch the data using service
    result = service.build_fit_data()
    master_df = result.raw_df
    fit_summary = result.summary_df

    if fit_summary.empty:
        st.warning("No doctrine fits found in the database.")
        return

    df = service.repository.get_all_doctrine_compositions()

    doctrine_names = df.doctrine_name.unique()

    selected_doctrine = st.sidebar.selectbox("Select a doctrine", doctrine_names)
    selected_doctrine_id = df[df.doctrine_name == selected_doctrine].doctrine_id.unique()[0]

    selected_data = fit_summary[fit_summary['fit_id'].isin(df[df.doctrine_name == selected_doctrine].fit_id.unique())]

    # Get module data from master_df for the selected doctrine
    selected_fit_ids = df[df.doctrine_name == selected_doctrine].fit_id.unique()
    doctrine_modules = master_df[master_df['fit_id'].isin(selected_fit_ids)]

    # Add Target Multiplier expander to sidebar
    st.sidebar.markdown("---")

    target_multiplier = st.sidebar.slider(
            "Target Multiplier",
            min_value=0.5,
            max_value=2.0,
            value=st.session_state.target_multiplier,
            step=0.1,
            help="This is a multiplier that is applied to the target value for each fit. It is used to adjust the target value for each fit to be more or less aggressive. The default value is 1.0, which means that the target value is the same as the target value in the database."
        )

    st.session_state.target_multiplier = target_multiplier
    st.sidebar.markdown(f"Current Target Multiplier: {target_multiplier}")

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
            st.text("🚀 Ship Image Not Available")

    with header_col2:
        st.markdown("&nbsp;")  # Add some spacing
        st.subheader(selected_doctrine, anchor=selected_doctrine, divider=True)
        st.markdown("&nbsp;")  # Add some spacing

    st.write(f"Doctrine ID: {selected_doctrine_id}")
    st.markdown("---")

    # Display categorized doctrine data instead of simple dataframe
    display_categorized_doctrine_data(selected_data)

    # Display lowest stock modules by ship with checkboxes
    display_low_stock_modules(selected_data, doctrine_modules, selected_fit_ids, fit_summary, lead_ship_id, selected_doctrine_id)

    # Display selected modules if any
    st.sidebar.markdown("---")


    st.sidebar.header("Selected Items", divider="blue")

    # Format selected items using code block for cleaner display
    if st.session_state.selected_modules:
        selection_lines = ["Modules:"]
        for item_name in st.session_state.selected_modules:
            if item_name in st.session_state.get('module_list_state', {}):
                item_info = st.session_state.module_list_state[item_name]
                # Extract stock from the info string
                try:
                    stock = item_info.split('(')[1].split(')')[0]
                    selection_lines.append(f"  {item_name} ({stock})")
                except (IndexError, ValueError):
                    selection_lines.append(f"  {item_name}")
            else:
                selection_lines.append(f"  {item_name} (N/A)")

        st.sidebar.code("\n".join(selection_lines), language=None)
    else:
        st.sidebar.info("No items selected")

    st.sidebar.markdown("### Export Options")

        # Prepare export data
    if st.session_state.get('csv_module_list_state'):
        csv_export = "Type,TypeID,Quantity,Fits\n"
        for module_name in st.session_state.selected_modules:
            if module_name in st.session_state.csv_module_list_state:
                csv_export += st.session_state.csv_module_list_state[module_name]

        # Download button
        st.sidebar.download_button(
            label="📥 Download CSV",
            data=csv_export,
            file_name="low_stock_list.csv",
            mime="text/csv",
            width='content'
        )

    # Clear selection button
    if st.sidebar.button("🗑️ Clear Selection", width='content'):
        st.session_state.selected_modules = []
        st.session_state.module_list_state = {}
        st.session_state.csv_module_list_state = {}
        st.rerun()

    last_esi_update = get_update_time()
    st.sidebar.markdown("---")
    st.sidebar.write(f"Last ESI Update: {last_esi_update}")
if __name__ == "__main__":
    main()
