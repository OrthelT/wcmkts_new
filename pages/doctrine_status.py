import streamlit as st
import pandas as pd
import datetime
import pathlib
from sqlalchemy import text
from sqlalchemy.orm import Session

from logging_config import setup_logging
from db_handler import get_local_mkt_engine, get_update_time
from doctrines import create_fit_df

# Insert centralized logging configuration
logger = setup_logging()

@st.cache_data(ttl=600, show_spinner="Loading cacheddoctrine fits...")
def get_fit_summary():
    """Get a summary of all doctrine fits"""
    logger.info("Getting fit summary")
    
    # Get the raw data with all fit details
    all_fits_data = create_fit_df()
    
    if all_fits_data.empty:
        return pd.DataFrame()
    
    # Get unique fit_ids
    fit_ids = all_fits_data['fit_id'].unique()
    
    # Create a summary dataframe
    fit_summary = []
    
    # Create a summary row for each fit_id
    targets_df = get_targets()

    for fit_id in fit_ids:
        # Filter data for this fit
        fit_data = all_fits_data[all_fits_data['fit_id'] == fit_id]
        
        if fit_data.empty:
            continue
        
        # Get the first row for fit metadata
        first_row = fit_data.iloc[0]
        
        # Get basic information
        ship_id = first_row['ship_id']
        ship_name = first_row['ship_name']
        hulls = first_row['hulls']
        
        # Extract ship group from the data
        ship_group = "Ungrouped"  # Default
        # Find the row that matches the ship_id
        ship_rows = fit_data[fit_data['type_id'] == ship_id]
        if not ship_rows.empty and 'group_name' in ship_rows.columns:
            ship_group = ship_rows['group_name'].iloc[0]
        
        # Calculate minimum fits (how many complete fits can be made)
        min_fits = fit_data['fits_on_mkt'].min()
        
        # Get target value from database if available, otherwise use default
        target = 20  # Default
        if targets_df is not None:
            target_row = targets_df[targets_df['fit_id'] == fit_id]
            if not target_row.empty:
                target = target_row.iloc[0]['ship_target']
        
        # Calculate target percentage
        if target > 0:
            target_percentage = min(100, int((min_fits / target) * 100))
        else:
            target_percentage = 0
        
        # Get the lowest stocked modules (exclude the ship itself)
        ship_type_id = first_row['ship_id']
        module_data = fit_data[fit_data['type_id'] != ship_type_id]
        lowest_modules = module_data.sort_values('fits_on_mkt').head(3)
        
        lowest_modules_list = []
        for _, row in lowest_modules.iterrows():
            module_name = row['type_name']
            module_stock = row['fits_on_mkt']
            if not pd.isna(module_name):
                lowest_modules_list.append(f"{module_name} ({int(module_stock)})")
        
        # Get daily average volume if available
        daily_avg = fit_data['avg_vol'].mean() if 'avg_vol' in fit_data.columns else 0
        
        # Get fit name from the ship_targets table if available
        fit_name = f"{ship_name} Fit"  # Default fallback

        if targets_df is not None:
            target_row = targets_df[targets_df['fit_id'] == fit_id]
            if not target_row.empty and 'fit_name' in target_row.columns and not pd.isna(target_row.iloc[0]['fit_name']):
                fit_name = target_row.iloc[0]['fit_name']
        
        # Add to summary list
        fit_summary.append({
            'fit_id': fit_id,
            'ship_id': ship_id,
            'ship_name': ship_name,
            'fit': fit_name,
            'ship': ship_name,
            'fits': min_fits,
            'hulls': hulls,
            'target': target,
            'target_percentage': target_percentage,
            'lowest_modules': lowest_modules_list,
            'daily_avg': daily_avg,
            'ship_group': ship_group
        })
    
    return pd.DataFrame(fit_summary)

def format_module_list(modules_list):
    """Format the list of modules for display"""
    if not modules_list:
        return ""
    return "<br>".join(modules_list)

@st.cache_data(ttl=600)
def get_targets()->pd.DataFrame:
    """Get the targets dataframe"""
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        # Get the fit data directly from the database
        df = pd.read_sql_query("SELECT * FROM ship_targets", conn)
        targets_df = df if not df.empty else None
    return targets_df

def main():
    # App title and logo
    # Handle path properly for WSL environment
    image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"
    if image_path.exists():
        st.image(str(image_path), width=150)
    else:
        st.warning("Logo image not found")
    
    # Page title
    st.title("Doctrine Status")
    
    # Fetch the data
    fit_summary = get_fit_summary()
    
    if fit_summary.empty:
        st.warning("No doctrine fits found in the database.")
        return
    
    # Add filters in the sidebar
    st.sidebar.header("Filters")
    
    # Status filter
    status_options = ["All", "Critical", "Needs Attention", "Good"]
    selected_status = st.sidebar.selectbox("Doctrine Status:", status_options)
    
    # Ship group filter
    ship_groups = ["All"] + sorted(fit_summary["ship_group"].unique().tolist())
    selected_group = st.sidebar.selectbox("Ship Group:", ship_groups)
    
    # Get unique ship names for selection
    unique_ships = sorted(fit_summary["ship_name"].unique().tolist())
    
    # Initialize session state for ship selection if not exists
    if 'selected_ships' not in st.session_state:
        st.session_state.selected_ships = []
        
    # Initialize session state for ship display (showing all ships)
    if 'displayed_ships' not in st.session_state:
        st.session_state.displayed_ships = unique_ships.copy()
    
    # Module status filter
    st.sidebar.subheader("Module Filters")
    module_status_options = ["All", "Critical (< 20%)", "Low (< 100%)", "Sufficient"]
    selected_module_status = st.sidebar.selectbox("Module Status:", module_status_options)
    
    # Apply filters
    filtered_df = fit_summary.copy()
    
    # Apply status filter
    if selected_status != "All":
        if selected_status == "Good":
            filtered_df = filtered_df[filtered_df['target_percentage'] > 90]
        elif selected_status == "Needs Attention":
            filtered_df = filtered_df[(filtered_df['target_percentage'] > 40) & (filtered_df['target_percentage'] <= 90)]
        elif selected_status == "Critical":
            filtered_df = filtered_df[filtered_df['target_percentage'] <= 40]
    
    # Apply ship group filter
    if selected_group != "All":
        filtered_df = filtered_df[filtered_df['ship_group'] == selected_group]
    
    # Update the displayed ships based on filters
    st.session_state.displayed_ships = filtered_df['ship_name'].unique().tolist()
    
    if filtered_df.empty:
        st.info(f"No fits found with the selected filters.")
        return
    
    # Initialize module selection for export
    if 'selected_modules' not in st.session_state:
        st.session_state.selected_modules = []
    
    # Group the data by ship_group
    grouped_fits = filtered_df.groupby('ship_group')
    
    # Iterate through each group and display fits
    for group_name, group_data in grouped_fits:
        # Display group header
        st.subheader(body=f"{group_name}", help="Ship doctrine group", divider="orange")
        # Add divider between groups
        # st.markdown("<hr style='margin: 1.5em 0; border-width: 3px'>", unsafe_allow_html=True)
    
        
        # Display the fits in this group
        for i, row in group_data.iterrows():
            # Create a more compact horizontal section for each fit
            col1, col2, col3 = st.columns([1, 3, 2])
            
            target_pct = row['target_percentage']
            target = int(row['target'])
            fits = int(row['fits'])
            hulls = int(row['hulls'])
            
            with col1:
                # Ship image and ID info
                try:
                    st.image(f"https://images.evetech.net/types/{row['ship_id']}/render?size=64", width=64)
                except:
                    st.text("Image not available")
                
                if target_pct > 90:
                    color = "green"
                    status = "Good"
                elif target_pct > 40:
                    color = "orange"
                    status = "Needs Attention"
                else:
                    color = "red"
                    status = "Critical"

                st.badge(status, color=color)
                st.text(f"ID: {row['fit_id']}")
                st.text(f"Fit: {row['fit']}")
            
            with col2:
                # Ship name with checkbox and metrics in a more compact layout
                ship_cols = st.columns([0.05, 0.95])
                
                with ship_cols[0]:
                    # Add checkbox next to ship name with unique key using fit_id and ship_name
                    unique_key = f"ship_{row['fit_id']}_{row['ship_name']}"
                    ship_selected = st.checkbox("x", key=unique_key, 
                                             value=row['ship_name'] in st.session_state.selected_ships, label_visibility="hidden")
                    if ship_selected and row['ship_name'] not in st.session_state.selected_ships:
                        st.session_state.selected_ships.append(row['ship_name'])
                    elif not ship_selected and row['ship_name'] in st.session_state.selected_ships:
                        st.session_state.selected_ships.remove(row['ship_name'])
                
                with ship_cols[1]:
                    st.markdown(f"### {row['ship_name']}")
                
                # Display metrics in a single row
                metric_cols = st.columns(3)
                fits_delta = fits-target
                hulls_delta = hulls-target

                with metric_cols[0]:
                    # Format the delta values
                    if fits:
                        st.metric(label="Fits", value=f"{int(fits)}", delta=fits_delta)
                    else:
                        st.metric(label="Fits", value=f"0", delta=fits_delta)

                with metric_cols[1]:
                    if hulls:
                        st.metric(label="Hulls", value=f"{int(hulls)}", delta=hulls_delta)
                    else:
                        st.metric(label="Hulls", value=f"0", delta=hulls_delta)

                with metric_cols[2]:
                    if target:
                        st.metric(label="Target", value=f"{int(target)}")
                    else:
                        st.metric(label="Target", value=f"0")
                
                # Progress bar for target percentage
                target_pct = row['target_percentage']
                color = "green" if target_pct >= 90 else "orange" if target_pct >= 50 else "red"
                if target_pct == 0:
                    color2 = "#5c1f06"
                else:
                    color2 = "#333"

                st.markdown(
                    f"""
                    <div style="margin-top: 5px;">
                        <div style="background-color: {color2}; width: 100%; height: 20px; border-radius: 3px;">
                            <div style="background-color: {color}; width: {target_pct}%; height: 20px; border-radius: 3px; text-align: center; line-height: 20px; color: white; font-weight: bold;">
                                {target_pct}%
                            </div>
                        </div>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            
            with col3:
                # Low stock modules with selection checkboxes
                st.markdown(":blue[**Low Stock Modules:**]")
                for i, module in enumerate(row['lowest_modules']):
                    module_qty = module.split("(")[1].split(")")[0]
                    module_name = module.split(" (")[0]
                    # Make each key unique by adding fit_id and index to avoid duplicates
                    module_key = f"{row['fit_id']}_{i}_{module_name}_{module_qty}"
                    display_key = f"{module_name}"
                    
                    # Determine module status
                    if int(module_qty) <= row['target'] * 0.2:
                        module_status = "Critical (< 20%)"
                    elif int(module_qty) <= row['target']:
                        module_status = "Low (< 100%)"
                    else:
                        module_status = "Sufficient"
                    
                    # Apply module status filter
                    if selected_module_status != "All" and selected_module_status != module_status:
                        continue
                    
                    col_a, col_b = st.columns([0.1, 0.9])
                    with col_a:
                        is_selected = st.checkbox("1", key=module_key, label_visibility="hidden", 
                                               value=display_key in st.session_state.selected_modules)
                        if is_selected and display_key not in st.session_state.selected_modules:
                            st.session_state.selected_modules.append(display_key)
                        elif not is_selected and display_key in st.session_state.selected_modules:
                            st.session_state.selected_modules.remove(display_key)
                    
                    with col_b:
                        if int(module_qty) <= row['target'] * 0.2:
                            st.markdown(f":red-badge[:material/error: {module}]")
                        elif int(module_qty) <= row['target']:
                            st.markdown(f":orange-badge[:material/error: {module}]")
                        else:
                            st.text(module)
            
            # Add a thinner divider between fits
            st.markdown("<hr style='margin: 0.5em 0; border-width: 1px'>", unsafe_allow_html=True)
        
        # Add divider between groups
        # st.markdown("<hr style='margin: 1.5em 0; border-width: 2px'>", unsafe_allow_html=True)
    
    # Ship and Module Export Section
    st.sidebar.markdown("---")
    st.sidebar.header("🔄 Export")
    
    # Ship selection
    st.sidebar.subheader("Ship Selection")
    ship_col1, ship_col2 = st.sidebar.columns(2)
    
    # Add "Select All Ships" button
    if ship_col1.button("📋 Select All Ships", use_container_width=True):
        st.session_state.selected_ships = st.session_state.displayed_ships.copy()
        st.rerun()
    
    # Add "Clear Ship Selection" button
    if ship_col2.button("🗑️ Clear Ships", use_container_width=True):
        st.session_state.selected_ships = []
        st.rerun()
    
    # Module selection
    st.sidebar.subheader("Module Selection")
    col1, col2 = st.sidebar.columns(2)
    
    # Add "Select All Modules" functionality
    if col1.button("📋 Select All Modules", use_container_width=True):
        # Create a list to collect all module keys that are currently visible based on filters
        visible_modules = []
        for _, group_data in grouped_fits:
            for _, row in group_data.iterrows():
                # Only include ships that are displayed (match filters)
                if row['ship_name'] not in st.session_state.displayed_ships:
                    continue
                    
                for module in row['lowest_modules']:
                    module_qty = module.split("(")[1].split(")")[0]
                    module_name = module.split(" (")[0]
                    display_key = f"{module_name}_{module_qty}"
                    
                    # Determine module status for filtering
                    if int(module_qty) <= row['target'] * 0.2:
                        module_status = "Critical (< 20%)"
                    elif int(module_qty) <= row['target']:
                        module_status = "Low (< 100%)"
                    else:
                        module_status = "Sufficient"
                    
                    # Apply module status filter
                    if selected_module_status != "All" and selected_module_status != module_status:
                        continue
                    
                    visible_modules.append(display_key)
        
        # Update session state with all visible modules
        st.session_state.selected_modules = list(set(visible_modules))
        st.rerun()
    
    # Clear module selection button
    if col2.button("🗑️ Clear Modules", use_container_width=True):
        st.session_state.selected_modules = []
        st.rerun()
    
    # Display selected ships if any
    if st.session_state.selected_ships:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Selected Ships:")
        
        # Create a scrollable container for selected ships
        with st.sidebar.container(height=100):
        
            for ship in st.session_state.selected_ships:
                with Session(get_local_mkt_engine()) as session:
                    query = f"""
                        SELECT type_name, total_stock 
                        FROM doctrines 
                        WHERE type_name = '{ship}'
                        LIMIT 1
                    """
                    result = session.execute(text(query))
                    row = result.fetchone()
                    if row and row[1] is not None:
                        st.text(f"{ship} ({int(row[1])})")
                    else:
                        st.text(ship)
    
    # Display selected modules if any
    if st.session_state.selected_modules:
        # Get module names
        module_names = [display_key.rsplit("_", 1)[0] for display_key in st.session_state.selected_modules]
        module_names = list(set(module_names))

        logger.info(f"Module names: {module_names}")
        
        # Query market stock (total_stock) for these modules
        module_list = []
        with Session(get_local_mkt_engine()) as session:
            for module_name in module_names:
                query = f"""
                    SELECT type_name, total_stock 
                    FROM doctrines 
                    WHERE type_name = '{module_name}'
                    LIMIT 1
                """
                result = session.execute(text(query))
                row = result.fetchone()
                if row and row[1] is not None:
                    # Use market stock (total_stock)
                    module_list.append(f"{module_name} ({int(row[1])})")
                else:
                    # No quantity if market stock not available
                    module_list.append(module_name)
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Selected Modules:")
        
        # Create a scrollable container for selected modules
        with st.sidebar.container(height=200):
            for module in module_list:
                st.text(module)
    
    # Show export options if anything is selected
    if st.session_state.selected_ships or st.session_state.selected_modules:
        st.sidebar.markdown("---")
        
        # Export options in columns
        col1, col2 = st.sidebar.columns(2)
        
        # Prepare export text
        export_text = ""
        if st.session_state.selected_ships:
            export_text += "SHIPS:\n" + "\n".join(st.session_state.selected_ships)
            if st.session_state.selected_modules:
                export_text += "\n\n"
                
        if st.session_state.selected_modules:
            # Get module names
            module_names = [display_key.rsplit("_", 1)[0] for display_key in st.session_state.selected_modules]
            
            # Query market stock (total_stock) for these modules
            module_list = []
            with Session(get_local_mkt_engine()) as session:
                for module_name in module_names:
                    query = f"""
                        SELECT type_name, total_stock 
                        FROM doctrines 
                        WHERE type_name = '{module_name}'
                        LIMIT 1
                    """
                    result = session.execute(text(query))
                    row = result.fetchone()
                    if row and row[1] is not None:
                        # Use market stock (total_stock)
                        module_list.append(f"{module_name} ({int(row[1])})")
                    else:
                        # No quantity if market stock not available
                        module_list.append(module_name)
            
            export_text += "MODULES:\n" + "\n".join(module_list)
        
        # Download button
        col1.download_button(
            label="📥 Download List",
            data=export_text,
            file_name="doctrine_export.txt",
            mime="text/plain",
            use_container_width=True
        )
        
        # Copy to clipboard button
        if col2.button("📋 Copy to Clipboard", use_container_width=True):
            st.sidebar.code(export_text, language="")
            st.sidebar.success("Copied to clipboard! Use Ctrl+C to copy the text above.")
    else:
        st.sidebar.info("Select ships and modules to export by checking the boxes next to them.")
    
    # Display last update timestamp
    st.sidebar.markdown("---")
    st.sidebar.write(f"Last ESI update: {get_update_time()}")
    st.sidebar.write(f"Page updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()
