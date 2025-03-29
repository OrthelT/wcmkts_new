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
        
        # Calculate minimum fits (how many complete fits can be made)
        min_fits = fit_data['fits_on_mkt'].min()
        
        # Get target value from database if available, otherwise use default
        target = 20  # Default
        if targets_df is not None:
            target_row = targets_df[targets_df['ship_name'] == ship_name]
            if not target_row.empty:
                target = target_row.iloc[0]['target']
        
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
        
        # Prepare the fit display name
        fit_name = f"{ship_name} Fit"
        if 'fit' in fit_data.columns and not pd.isna(fit_data['fit'].iloc[0]):
            fit_name = fit_data['fit'].iloc[0]
        
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
            'daily_avg': daily_avg
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
    st.title("Winter Coalition Doctrine Fits")
    
    # Fetch the data
    fit_summary = get_fit_summary()
    
    if fit_summary.empty:
        st.warning("No doctrine fits found in the database.")
        return
    
    # Display the data in a format similar to the Excel sheet
    for i, row in fit_summary.iterrows():
        # Create a horizontal section for each fit
        col1, col2, col3, col4, col5, col6, col7 = st.columns([1, 1, 1.5, 1, 1, 2, 1])
        
        with col1:
            # Display fit ID and ship ID
            st.subheader(f"Fit #{row['fit_id']}")
            st.text(f"Ship ID: {row['ship_id']}")
            try:
                # Display ship image
                st.image(f"https://images.evetech.net/types/{row['ship_id']}/render?size=128", width=100)
            except:
                st.text("Image not available")
        
        with col2:
            # Display fit name
            st.subheader("Fit")
            st.write(row['fit'])
        
        with col3:
            # Display ship name
            st.subheader("Ship")
            st.write(row['ship'])
            
            # Display fits and hulls
            col3a, col3b = st.columns(2)
            with col3a:
                st.metric("Fits", f"{int(row['fits'])}")
            with col3b:
                st.metric("Hulls", f"{int(row['hulls'])}")
        
        with col4:
            # Display target percentage
            st.subheader("Target (%)")
            
            # Create a progress bar
            target_pct = row['target_percentage']
            color = "green" if target_pct >= 90 else "orange" if target_pct >= 50 else "red"
            st.markdown(
                f"""
                <div style="margin-top: 37px;">
                    <div style="background-color: #333; width: 100%; height: 30px; border-radius: 5px;">
                        <div style="background-color: {color}; width: {target_pct}%; height: 30px; border-radius: 5px; text-align: center; line-height: 30px; color: white; font-weight: bold;">
                            {target_pct}%
                        </div>
                    </div>
                </div>
                """, 
                unsafe_allow_html=True
            )
        
        with col5:
            # Display daily average
            st.subheader("Daily Avg")
            st.metric("", f"{row.get('daily_avg', 0):.1f}")
        
        with col6:
            # Display lowest stocked modules
            st.subheader("3 Lowest Stock Modules")
            for module in row['lowest_modules']:
                st.text(module)
        
        with col7:
            # Display target and percentage
            st.subheader("Target")
            st.metric("", f"{int(row['target'])}")
            st.metric("% Target", f"{row['target_percentage']}%")
        
        # Add a divider between fits
        st.divider()
    
    # Display last update timestamp
    st.sidebar.write(f"Last ESI update: {get_update_time()}")
    st.sidebar.write(f"Page updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")

if __name__ == "__main__":
    main() 