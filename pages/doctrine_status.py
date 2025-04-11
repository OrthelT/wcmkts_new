import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from dotenv import load_dotenv
from db_handler import get_local_mkt_engine, get_local_sde_engine, get_fitting_data, get_update_time
import sys
import datetime
import millify
import pathlib
import logging

logger = logging.getLogger(__name__)
# Import from the root directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from doctrines import get_doctrine_fits, create_fit_df

# Page configuration
st.set_page_config(
    page_title="WC Doctrine Fits",
    page_icon="📈",
    layout="wide"
)

# Function to get unique fit_ids and their details
def get_fit_summary():
    """Get a summary of all doctrine fits"""
    # Get the raw data with all fit details
    all_fits_data = create_fit_df()
    
    if all_fits_data.empty:
        return pd.DataFrame()
    
    # Get unique fit_ids
    fit_ids = all_fits_data['fit_id'].unique()
    
    # Create a summary dataframe
    fit_summary = []
    
    # Create a summary row for each fit_id
    engine = get_local_mkt_engine()
    with engine.connect() as conn:
        # Get the fit data directly from the database
        df = pd.read_sql_query("SELECT * FROM ship_targets", conn)
        targets_df = df if not df.empty else None
    
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
    
    # Group the data by ship_group
    grouped_fits = fit_summary.groupby('ship_group')
    
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
                # Ship name and metrics in a more compact layout
                st.markdown(f"### {row['ship_name']}")
                logger.info(f"Ship name: {row['ship_name']}")
                
                # Display metrics in a single row
                metric_cols = st.columns(3)
                fits_delta = fits-target
                hulls_delta = hulls-target

                with metric_cols[0]:
                    st.metric(label="Fits", value=f"{int(fits)}", delta=fits_delta)
                with metric_cols[1]:
                    st.metric(label="Hulls", value=f"{int(hulls)}", delta=hulls_delta)
                with metric_cols[2]:
                    st.metric(label="Target", value=f"{int(target)}")
                
                # Progress bar for target percentage
                target_pct = row['target_percentage']
                color = "green" if target_pct >= 90 else "orange" if target_pct >= 50 else "red"
                logger.info(f"Target percentage: {target_pct}, Color: {color}")
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
                # Low stock modules in a more compact format
                
                st.markdown(":blue[**Low Stock Modules:**]")
                for module in row['lowest_modules']:
                    module_qty = module.split("(")[1].split(")")[0]
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
    
    # Display last update timestamp
    st.sidebar.write(f"Last ESI update: {get_update_time()}")
    st.sidebar.write(f"Page updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main()