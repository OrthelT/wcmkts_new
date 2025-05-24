import sqlalchemy as sa
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
import json
import pymysql
import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pathlib
from logging_config import setup_logging

from db_handler import get_local_mkt_engine
from doctrines import create_fit_df, get_fit_summary
logger = setup_logging(__name__, log_file="experiments.log")

icon_id = 0
icon_url = f"https://images.evetech.net/types/{icon_id}/render?size=64"

fit_sqlfile = "Orthel:Dawson007!27608@localhost:3306/wc_fitting"
fit_mysqlfile = "mysql+pymysql://Orthel:Dawson007!27608@localhost:3306/wc_fitting"

def get_doctrines_from_db():
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM doctrines", conn)
    return df

def get_doctrine_dict():
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM doctrine_map", conn)

    doctrine_ids = df['doctrine_id'].unique().tolist()
    doctrine_dict = {}
    for id in doctrine_ids:
        df2 = df[df.doctrine_id == id]
        fits = df2['fitting_id'].unique().tolist()
        doctrine_dict[id] = fits
    return doctrine_dict

def get_module_stock_list(module_names: list):
    """Get lists of modules with their stock quantities for display and CSV export."""
    
    # Set the session state variables for the module list and csv module list
    if not st.session_state.get('module_list_state'):
        st.session_state.module_list_state = {}
    if not st.session_state.get('csv_module_list_state'):
        st.session_state.csv_module_list_state = {}

    with Session(get_local_mkt_engine()) as session:
        for module_name in module_names:
            # Check if the module is already in the list, if not, get the data from the database
            if module_name not in st.session_state.module_list_state:
                logger.info(f"Querying database for {module_name}")

                query = f"""
                    SELECT type_name, type_id, total_stock, fits_on_mkt
                    FROM doctrines 
                    WHERE type_name = "{module_name}"
                    LIMIT 1
                """
                result = session.execute(text(query))
                row = result.fetchone()
                if row and row[2] is not None:  # total_stock is now at index 2
                    # Use market stock (total_stock)
                    module_info = f"{module_name} (Total: {int(row[2])} | Fits: {int(row[3])})"
                    csv_module_info = f"{module_name},{row[1]},{int(row[2])},{int(row[3])}\n"
                else:
                    # No quantity if market stock not available
                    module_info = f"{module_name}"
                    csv_module_info = f"{module_name},0,0,0\n"

                # Add the module to the session state list
                st.session_state.module_list_state[module_name] = module_info
                st.session_state.csv_module_list_state[module_name] = csv_module_info

def main():
       # App title and logo
    # Handle path properly for WSL environment
    image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"
    if image_path.exists():
        st.image(str(image_path), width=150)
    else:
        st.warning("Logo image not found")
    
    # Page title
    st.title("Doctrine Report")
    
    # Fetch the data
    master_df, fit_summary = create_fit_df()

    print(master_df.columns)
    print(fit_summary.columns)
    
    if fit_summary.empty:
        st.warning("No doctrine fits found in the database.")
        return
    
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        df = pd.read_sql_query("SELECT * FROM doctrine_fits", conn)

    doctrine_names = df.doctrine_name.unique()

    selected_doctrine = st.sidebar.selectbox("Select a doctrine", doctrine_names)
    selected_doctrine_id = df[df.doctrine_name == selected_doctrine].doctrine_id.unique()[0]

    selected_data = fit_summary[fit_summary['fit_id'].isin(df[df.doctrine_name == selected_doctrine].fit_id.unique())]

    st.subheader(selected_doctrine, divider=True, anchor=selected_doctrine)
    st.dataframe(selected_data)

    # Get module data from master_df for the selected doctrine
    selected_fit_ids = df[df.doctrine_name == selected_doctrine].fit_id.unique()
    doctrine_modules = master_df[master_df['fit_id'].isin(selected_fit_ids)]

    # Initialize session state for selected modules
    if 'selected_modules' not in st.session_state:
        st.session_state.selected_modules = []

    flagships = {}

    with st.form(key="create_low_stock_list"):
        selected_flagship = st.selectbox("Select a flagship", selected_data.ship_name.unique(), key="flagship_select")
        # Get unique module names from the doctrine modules, excluding ship hulls
        available_modules = doctrine_modules[doctrine_modules['type_name'] != doctrine_modules['ship_name']]['type_name'].unique()
        low_stock_modules = st.multiselect("Select modules", available_modules, key="module_select")
        submit_button = st.form_submit_button("Create Low Stock List")

    if submit_button:
        st.write(f"Selected flagship: {selected_flagship}")
        st.write(f"Selected modules: {low_stock_modules}")
        
        # Update session state with selected modules
        st.session_state.selected_modules = low_stock_modules
        
        # Get module stock information
        if low_stock_modules:
            get_module_stock_list(low_stock_modules)

    # Display lowest stock modules with checkboxes
    if not doctrine_modules.empty:
        st.markdown("---")
        st.subheader("Lowest Stock Modules", help="Select modules to add to your low stock list")
        
        # Calculate lowest stock modules for the entire doctrine (excluding ships)
        module_data = doctrine_modules[doctrine_modules['type_name'] != doctrine_modules['ship_name']]
        
        if not module_data.empty:
            # Group by module name and get the minimum stock across all fits
            lowest_modules_summary = module_data.groupby('type_name').agg({
                'fits_on_mkt': 'min',
                'type_id': 'first'
            }).reset_index()
            
            # Sort by lowest stock and take top 10
            lowest_modules = lowest_modules_summary.sort_values('fits_on_mkt').head(10)
            
            # Display in columns
            col1, col2 = st.columns(2)
            
            for i, (_, row) in enumerate(lowest_modules.iterrows()):
                module_name = row['type_name']
                module_stock = int(row['fits_on_mkt'])
                module_key = f"doctrine_module_{i}_{module_name}_{module_stock}"
                
                # Determine which column to use
                target_col = col1 if i % 2 == 0 else col2
                
                with target_col:
                    checkbox_col, text_col = st.columns([0.1, 0.9])
                    
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
                    
                    with text_col:
                        # Color coding based on stock levels
                        if module_stock <= 5:
                            st.markdown(f":red-badge[:material/error: {module_name} ({module_stock})]")
                        elif module_stock <= 20:
                            st.markdown(f":orange-badge[:material/warning: {module_name} ({module_stock})]")
                        else:
                            st.text(f"{module_name} ({module_stock})")

    # Display selected modules if any
    if st.session_state.selected_modules:
        st.markdown("---")
        st.subheader("Low Stock Module List")
        
        # Create columns for display and export
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.markdown("### Selected Modules:")
            
            # Display modules with their stock information
            for module_name in st.session_state.selected_modules:
                if module_name in st.session_state.get('module_list_state', {}):
                    module_info = st.session_state.module_list_state[module_name]
                    st.text(module_info)
                else:
                    st.text(f"{module_name} (Stock info not available)")
        
        with col2:
            st.markdown("### Export Options")
            
            # Prepare export data
            if st.session_state.get('csv_module_list_state'):
                csv_export = "Type,TypeID,Quantity,Fits\n"
                for module_name in st.session_state.selected_modules:
                    if module_name in st.session_state.csv_module_list_state:
                        csv_export += st.session_state.csv_module_list_state[module_name]
                
                # Download button
                st.download_button(
                    label="📥 Download CSV",
                    data=csv_export,
                    file_name="low_stock_modules.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            # Clear selection button
            if st.button("🗑️ Clear Selection", use_container_width=True):
                st.session_state.selected_modules = []
                st.session_state.module_list_state = {}
                st.session_state.csv_module_list_state = {}
                st.rerun()

if __name__ == "__main__":
    main()
 