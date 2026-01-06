import sys
import os
import pathlib

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from sqlalchemy import text
from millify import millify
from logging_config import setup_logging
from db_handler import get_update_time  # Keep only non-doctrine utilities
from utils import get_multi_item_jita_price
from config import DatabaseConfig
from services import get_doctrine_service, get_price_service
from services.categorization import get_ship_role_categorizer

# Insert centralized logging configuration
logger = setup_logging(__name__, log_file="doctrine_status.log")
mkt_db = DatabaseConfig("wcmkt")

# Initialize service (cached in session state)
service = get_doctrine_service()
fit_build_result = service.build_fit_data()
all_fits_df = fit_build_result.raw_df
summary_df = fit_build_result.summary_df

def get_fit_summary() -> pd.DataFrame:
    """Get a summary of all doctrine fits using service."""
    logger.info("Getting fit summary via service")

    # Use service to get all fit summaries as domain models
    summaries = service.get_all_fit_summaries()

    if not summaries:
        return pd.DataFrame()

    # Convert domain models to DataFrame for compatibility with existing UI code
    fit_summary = []
    for summary in summaries:
        # lowest_modules is already a tuple of formatted strings
        lowest_modules_list = list(summary.lowest_modules)

        fit_summary.append({
            'fit_id': summary.fit_id,
            'ship_id': summary.ship_id,
            'ship_name': summary.ship_name,
            'fit': summary.fit_name,
            'ship': summary.ship_name,
            'fits': summary.fits,
            'hulls': summary.hulls,
            'target': summary.ship_target,
            'target_percentage': summary.target_percentage,
            'lowest_modules': lowest_modules_list,
            'daily_avg': summary.daily_avg,
            'ship_group': summary.ship_group,
            'total_cost': summary.total_cost
        })

    return pd.DataFrame(fit_summary)

def format_module_list(modules_list):
    """Format the list of modules for display"""
    if not modules_list:
        return ""
    return "<br>".join(modules_list)

def get_module_stock_list(module_names: list):
    """Get lists of modules with their stock quantities for display and CSV export using service."""

    # Set the session state variables for the module list and csv module list
    if not st.session_state.get('module_list_state'):
        st.session_state.module_list_state = {}
    if not st.session_state.get('csv_module_list_state'):
        st.session_state.csv_module_list_state = {}

    for module_name in module_names:
        if module_name not in st.session_state.module_list_state:
            logger.info(f"Querying database for {module_name} via service")

            # Use service repository to get module stock info
            module_stock = service.repository.get_module_stock(module_name)

            if module_stock:
                # Format usage information
                usage_parts = []
                for usage_item in module_stock.usage:
                    modules_needed = usage_item.ship_target * usage_item.fit_qty
                    usage_parts.append(f"{usage_item.ship_name}({modules_needed})")
                usage_display = ", ".join(usage_parts) if usage_parts else ""

                # Format display info
                module_info = f"{module_name} (Total: {module_stock.total_stock} | Fits: {module_stock.fits_on_mkt})"
                if usage_display:
                    module_info = f"{module_info} | Used in: {usage_display}"
                csv_module_info = f"{module_name},{module_stock.type_id},{module_stock.total_stock},{module_stock.fits_on_mkt},,{usage_display}\n"
            else:
                module_info = f"{module_name}"
                csv_module_info = f"{module_name},0,0,0,,\n"

            st.session_state.module_list_state[module_name] = module_info
            st.session_state.csv_module_list_state[module_name] = csv_module_info

def get_ship_stock_list(ship_names: list):
    if not st.session_state.get('ship_list_state'):
        st.session_state.ship_list_state = {}
    if not st.session_state.get('csv_ship_list_state'):
        st.session_state.csv_ship_list_state = {}

    logger.info(f"Ship names: {ship_names}")
    for ship in ship_names:
        if ship not in st.session_state.ship_list_state:
            logger.info(f"Querying database for {ship}")
            params = {"ship": ship}
            extra = ""
            if ship == "Ferox Navy Issue":
                extra = " AND fit_id = :fit_id"
                params["fit_id"] = 473
            elif ship == "Hurricane Fleet Issue":
                extra = " AND fit_id = :fit_id"
                params["fit_id"] = 494

            query = text(
                f"""
                SELECT type_name, type_id, total_stock, fits_on_mkt, fit_id
                FROM doctrines
                WHERE type_name = :ship{extra}
                LIMIT 1
                """
            )
            df = read_df(mkt_db, query, params)
            if not df.empty and pd.notna(df.loc[0, 'total_stock']) and pd.notna(df.loc[0, 'type_id']) and pd.notna(df.loc[0, 'fits_on_mkt']):
                ship_id = int(df.loc[0, 'type_id'])
                ship_stock = int(df.loc[0, 'total_stock'])
                ship_fits = int(df.loc[0, 'fits_on_mkt'])
                ship_target = service.repository.get_target_by_ship_id(ship_id)
                ship_info = f"{ship} (Qty: {ship_stock} | Fits: {ship_fits} | Target: {ship_target})"
                csv_ship_info = f"{ship},{ship_id},{ship_stock},{ship_fits},{ship_target},\n"
            else:
                ship_info = ship
                csv_ship_info = f"{ship},0,0,0,0,\n"

            st.session_state.ship_list_state[ship] = ship_info
            st.session_state.csv_ship_list_state[ship] = csv_ship_info

def fitting_download_button():
    targets = service.repository.get_all_targets()
    data = all_fits_df.merge(targets, on='fit_id', how='left')
    data = data.reset_index(drop=True)

    if st.download_button("Download Data", data=data.to_csv(index=False), file_name="wc_doctrine_fits.csv", help="Download all doctrine fit information as a CSV file", mime="text/csv"):
        st.toast("Data downloaded successfully", icon="✅")

def get_fit_detail_data(fit_id: int) -> pd.DataFrame:
    """
    Get detailed fitting data for a specific fit_id.
    Returns a DataFrame with all modules/items for the fit.
    """
    try:
        df = service.repository.get_all_fits()
        if df.empty:
            return pd.DataFrame()
        
        # Filter by fit_id
        fit_df = df[df['fit_id'] == fit_id].copy()
        
        if fit_df.empty:
            return pd.DataFrame()
        
        # Drop unnecessary columns (keep category_id for sorting)
        columns_to_drop = ['ship_id', 'hulls', 'group_id', 'category_name', 'id', 'timestamp']
        fit_df.drop(columns=[col for col in columns_to_drop if col in fit_df.columns], inplace=True)
        
        # Format numeric columns
        fit_df['type_id'] = round(fit_df['type_id'], 0).astype(int)
        fit_df['fit_id'] = round(fit_df['fit_id'], 0).astype(int)
        
        # Rename for better display
        if 'fits_on_mkt' in fit_df.columns:
            fit_df.rename(columns={'fits_on_mkt': 'Fits on Market'}, inplace=True)
        
        # Sort by category_id first (ships are category 6, lowest used, so ship hull appears first)
        # Then by fits on market (ascending) to show bottlenecks
        if 'category_id' in fit_df.columns and 'Fits on Market' in fit_df.columns:
            fit_df = fit_df.sort_values(by=['category_id', 'Fits on Market'], ascending=[True, True])
        elif 'Fits on Market' in fit_df.columns:
            fit_df = fit_df.sort_values(by='Fits on Market', ascending=True)
        
        fit_df.reset_index(drop=True, inplace=True)
        
        return fit_df
        
    except Exception as e:
        logger.error(f"Error getting fit detail data for fit_id {fit_id}: {e}")
        return pd.DataFrame()

def get_fitting_column_config() -> dict:
    """Get column configuration for fitting data display"""
    return {
        'fit_id': st.column_config.NumberColumn(
            "Fit ID",
            help="WC Doctrine Fit ID"
        ),
        'ship_name': st.column_config.TextColumn(
            "Ship Name",
            help="Ship Name",
            width="medium"
        ),
        'type_id': st.column_config.NumberColumn(
            "Type ID",
            help="Type ID"
        ),
        'type_name': st.column_config.TextColumn(
            "Type Name",
            help="Type Name",
            width="medium"
        ),
        'fit_qty': st.column_config.NumberColumn(
            "Qty/fit",
            help="Quantity of this item per fit",
            width="small"
        ),
        'Fits on Market': st.column_config.NumberColumn(
            "Fits",
            help="Total fits available on market for this item",
            width="small"
        ),
        'total_stock': st.column_config.NumberColumn(
            "Stock",
            help="Total stock of this item",
            width="small"
        ),
        'price': st.column_config.NumberColumn(
            "Price",
            help="Price of this item",
            format="localized"
        ),
        'avg_vol': st.column_config.NumberColumn(
            "Avg Vol",
            help="Average volume over the last 30 days",
            width="small"
        ),
        'days': st.column_config.NumberColumn(
            "Days",
            help="Days remaining (based on historical average)",
            width="small"
        ),
        'group_name': st.column_config.Column(
            "Group",
            help="Group of this item",
            width="small"
        ),
        'category_id': st.column_config.NumberColumn(
            "Category ID",
            help="Category ID (ships are 6)",
            width="small"
        ),
    }

def fetch_jita_prices_for_types(type_ids: tuple[int, ...]) -> dict[int, float]:
    """
    Fetch Jita prices for a set of type_ids using a single API call.
    Cached for 1 hour to reduce external requests.
    """
    if not type_ids:
        return {}
    price_service = PriceService.create_default()
    prices = price_service.get_jita_prices(list(type_ids))
    return prices.prices

def calculate_all_jita_deltas(force_refresh: bool = False):
    """
    Calculate Jita price deltas for all fits in the background.
    Stores results in session state for display.

    Args:
        force_refresh: If True, bypasses cache and fetches fresh prices
    """
    import datetime

    if 'jita_deltas' not in st.session_state:
        st.session_state.jita_deltas = {}

    # Use service to calculate all jita deltas
    try:
        st.session_state.jita_deltas = service.calculate_all_jita_deltas()
        st.session_state.jita_deltas_last_updated = datetime.datetime.now()
        logger.info(f"Calculated Jita deltas for {len(st.session_state.jita_deltas)} fits at {st.session_state.jita_deltas_last_updated}")
    except Exception as e:
        logger.error(f"Error calculating Jita deltas: {e}")
        st.session_state.jita_deltas = {}
        st.session_state.jita_deltas_last_updated = datetime.datetime.now()

def main():
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
        st.title("4-HWWF Doctrine Status")
    with col3:
        try:
            fit_summary = get_fit_summary()
            st.markdown("&nbsp;")
            st.markdown("&nbsp;")
            fitting_download_button()
            st.markdown("<span style='font-size: 12px; color: #666;'>*Download all doctrine fit data*</span>", unsafe_allow_html=True)

        except Exception as e:
            logger.error(f"Error getting fit summary: {e}")
            st.warning("No doctrine fits found in the database.")
            return

    # Add filters in the sidebar
    st.sidebar.header("Filters")

    # Target multiplier
    ds_target_multiplier = 1.0
    if 'ds_target_multiplier' not in st.session_state:
        st.session_state.ds_target_multiplier = ds_target_multiplier
    with st.sidebar.expander("Target Multiplier"):
        ds_target_multiplier = st.slider("Target Multiplier", min_value=0.5, max_value=2.0, value=1.0, step=0.1)
        st.session_state.ds_target_multiplier = ds_target_multiplier
        st.sidebar.write(f"Target Multiplier: {ds_target_multiplier}")

    # Status filter
    status_options = ["All", "Critical", "Needs Attention", "All Low Stock", "Good"]
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
    module_status_options = ["All", "Critical", "Needs Attention", "All Low Stock", "Good"]
    selected_module_status = st.sidebar.selectbox("Module Status:", module_status_options)

    # Apply filters
    filtered_df = fit_summary.copy()
    filtered_df['target'] = filtered_df['target'] * ds_target_multiplier

    # Apply status filter
    if selected_status != "All":
        if selected_status == "Good":
            filtered_df = filtered_df[filtered_df['target_percentage'] > 90]
        elif selected_status == "All Low Stock":
            filtered_df = filtered_df[filtered_df['target_percentage'] <= 90]
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
        st.info("No fits found with the selected filters.")
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

        # Display the fits in this group
        for i, row in group_data.iterrows():
            # Create a more compact horizontal section for each fit
            col1, col2, col3 = st.columns([1, 3, 2])

            target_pct = row['target_percentage']
            target = int(row['target']) if pd.notna(row['target']) else 0
            fits = int(row['fits']) if pd.notna(row['fits']) else 0
            hulls = int(row['hulls']) if pd.notna(row['hulls']) else 0
            fit_cost = millify(int(row['total_cost']), precision=2) if pd.notna(row['total_cost']) else 'N/A'

            with col1:
                # Ship image and ID info
                try:
                    st.image(f"https://images.evetech.net/types/{row['ship_id']}/render?size=64", width=64)
                except Exception:
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

                    # Initialize checkbox state from selected_ships if not already set
                    if unique_key not in st.session_state:
                        st.session_state[unique_key] = row['ship_name'] in st.session_state.selected_ships

                    ship_selected = st.checkbox("x", key=unique_key, label_visibility="hidden")

                    # Sync checkbox state with selected_ships list
                    if ship_selected and row['ship_name'] not in st.session_state.selected_ships:
                        st.session_state.selected_ships.append(row['ship_name'])
                    elif not ship_selected and row['ship_name'] in st.session_state.selected_ships:
                        st.session_state.selected_ships.remove(row['ship_name'])

                with ship_cols[1]:
                    st.markdown(f"### {row['ship_name']}")

                # Display metrics in a single row
                metric_cols = st.columns(4)
                fits_delta = fits-target
                hulls_delta = hulls-target

                with metric_cols[0]:
                    # Format the delta values
                    if fits:
                        st.metric(label="Fits", value=f"{int(fits)}", delta=fits_delta)
                    else:
                        st.metric(label="Fits", value="0", delta=fits_delta)

                with metric_cols[1]:
                    if hulls:
                        st.metric(label="Hulls", value=f"{int(hulls)}", delta=hulls_delta)
                    else:
                        st.metric(label="Hulls", value="0", delta=hulls_delta)

                with metric_cols[2]:
                    if target:
                        st.metric(label="Target", value=f"{int(target)}")
                    else:
                        st.metric(label="Target", value="0")

                with metric_cols[3]:
                    if fit_cost and fit_cost != 'N/A':
                        # Get the Jita cost delta from session state
                        jita_delta = None
                        if 'jita_deltas' in st.session_state and row['fit_id'] in st.session_state.jita_deltas:
                            jita_delta = st.session_state.jita_deltas[row['fit_id']]
                        
                        if jita_delta is not None and pd.notna(jita_delta):
                            # Format delta as percentage with 2 decimal places
                            delta_str = f"{jita_delta:.2f}%"
                            st.metric(label="Fit Cost", value=f"{fit_cost}", delta=delta_str)
                        else:
                            st.metric(label="Fit Cost", value=f"{fit_cost}")
                    else:
                        st.metric(label="Fit Cost", value="N/A")
                        
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
                
                with st.popover("📋 View Full Fitting Details"):
                    with st.spinner("Loading fitting data..."):
                        fit_detail_df = service.repository.get_fit_by_id(fit_id=row['fit_id'])
                        
                        if not fit_detail_df.empty:
                            st.dataframe(fit_detail_df, hide_index=True, width='stretch')
                            
                        if not fit_detail_df.empty:
                            # Display summary info
                            fit_info_col1, fit_info_col2, fit_info_col3 = st.columns(3)
                            
                            with fit_info_col1:
                                st.metric("Total Items", len(fit_detail_df))
                            
                            with fit_info_col2:
                                if 'total_stock' in fit_detail_df.columns:
                                    total_value = (fit_detail_df['price'] * fit_detail_df['total_stock']).sum()
                                    st.metric("Total Stock Value", f"{millify(total_value, precision=2)}")
                            
                            with fit_info_col3:
                                if 'Fits on Market' in fit_detail_df.columns:
                                    bottleneck = fit_detail_df['Fits on Market'].min()
                                    st.metric("Bottleneck (Min Fits)", int(bottleneck))
                            
                            # Display the fitting dataframe
                            col_config = get_fitting_column_config()
                            st.dataframe(
                                fit_detail_df,
                                hide_index=True,
                                column_config=col_config,
                                width='stretch'
                            )
                            
                            # Download button for this specific fit
                            csv = fit_detail_df.to_csv(index=False)
                            st.download_button(
                                label=f"📥 Download Fit {row['fit_id']} Data",
                                data=csv,
                                file_name=f"fit_{row['fit_id']}_{row['ship_name'].replace(' ', '_')}.csv",
                                mime="text/csv",
                                key=f"download_fit_{row['fit_id']}"
                            )
                        else:
                            st.info("No detailed fitting data available for this fit.")

            with col3:
                # Low stock modules with selection checkboxes
                st.markdown(":blue[**Low Stock Modules:**]")
                for i, module in enumerate(row['lowest_modules']):
                    module_qty = module.split("(")[1].split(")")[0]
                    module_name = module.split(" (")[0]
                    # Make each key unique by adding fit_id and index to avoid duplicates
                    module_key = f"{row['fit_id']}_{i}_{module_name}_{module_qty}"
                    display_key = f"{module_name}_{module_qty}"

                    # Determine module status
                    if int(module_qty) <= row['target'] * 0.2:
                        module_status = "Critical"
                    elif int(module_qty) <= row['target']:
                        module_status = "Needs Attention"
                    else:
                        module_status = "Good"

                    # Apply module status filter
                    if selected_module_status == "All Low Stock":
                        if int(module_qty) <= row['target'] * 0.9:
                            module_status = "All Low Stock"
                    if selected_module_status != "All" and selected_module_status != module_status:
                        continue

                    col_a, col_b = st.columns([0.1, 0.9])
                    with col_a:
                        # Initialize checkbox state from selected_modules if not already set
                        if module_key not in st.session_state:
                            st.session_state[module_key] = display_key in st.session_state.selected_modules

                        is_selected = st.checkbox("1", key=module_key, label_visibility="hidden")

                        # Sync checkbox state with selected_modules list
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
    if ship_col1.button("📋 Select All Ships", width='content'):
        st.session_state.selected_ships = st.session_state.displayed_ships.copy()
        # Clear all ship checkbox states so they reinitialize on next render
        keys_to_clear = [key for key in st.session_state.keys() if key.startswith("ship_")]
        for key in keys_to_clear:
            del st.session_state[key]
        st.rerun()

    # Add "Clear Ship Selection" button
    if ship_col2.button("🗑️ Clear Ships", width='content'):
        st.session_state.selected_ships = []
        st.session_state.ship_list_state = {}
        st.session_state.csv_ship_list_state = {}
        # Clear all ship checkbox states
        keys_to_clear = [key for key in st.session_state.keys() if key.startswith("ship_")]
        for key in keys_to_clear:
            del st.session_state[key]
        logger.info("Cleared ship selection and session state")
        logger.info(f"Session state ship list: {st.session_state.ship_list_state}")
        logger.info(f"Session state csv ship list: {st.session_state.csv_ship_list_state}")
        logger.info(f"\n{"-"*60}\n")
        st.rerun()

    # Module selection
    st.sidebar.subheader("Module Selection")
    col1, col2 = st.sidebar.columns(2)

    # Add "Select All Modules" functionality
    if col1.button("📋 Select All Modules", width='content'):
        # Create a list to collect all module keys that are currently visible based on filters
        visible_modules = []
        low_stock_modules = []
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
                    if selected_module_status == "All Low Stock":
                        if int(module_qty) <= row['target'] * 0.9:
                            low_stock_modules.append(display_key)
                    elif int(module_qty) <= row['target'] * 0.2:
                        module_status = "Critical"
                    elif int(module_qty) <= row['target']:
                        module_status = "Needs Attention"
                    else:
                        module_status = "Good"

                    # Apply module status filter
                    if selected_module_status != "All" and selected_module_status != module_status:
                        continue

                    logger.info(f"Module status: {module_status}")
                    logger.info(f"Module qty: {display_key}")

                    visible_modules.append(display_key)

        # Update session state with all visible modules
        if selected_module_status == "All Low Stock":
            st.session_state.selected_modules = list(set(low_stock_modules))
        else:
            st.session_state.selected_modules = list(set(visible_modules))
        # Clear all module checkbox states so they reinitialize on next render
        keys_to_clear = [key for key in st.session_state.keys() if "_" in key and key.split("_")[0].isdigit()]
        for key in keys_to_clear:
            # Only clear keys that look like module checkboxes (fit_id_index_module_qty pattern)
            if len(key.split("_")) >= 3:
                del st.session_state[key]
        st.rerun()

    # Clear module selection button
    if col2.button("🗑️ Clear Modules", width='content'):
        st.session_state.selected_modules = []
        st.session_state.module_list_state = {}
        st.session_state.csv_module_list_state = {}
        # Clear all module checkbox states
        keys_to_clear = [key for key in st.session_state.keys() if "_" in key and key.split("_")[0].isdigit()]
        for key in keys_to_clear:
            # Only clear keys that look like module checkboxes (fit_id_index_module_qty pattern)
            if len(key.split("_")) >= 3:
                del st.session_state[key]
        logger.info("Cleared module selection and session state")
        logger.info(f"Session state module list: {st.session_state.module_list_state}")
        logger.info(f"Session state csv module list: {st.session_state.csv_module_list_state}")
        logger.info(f"\n{"-"*60}\n")
        st.rerun()

    # Display selected ships if any
    if st.session_state.selected_ships:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### Selected Ships:")
        num_selected_ships = len(st.session_state.selected_ships)
        ship_container_height = 100 if num_selected_ships <= 2 else num_selected_ships * 50

        # Create a scrollable container for selected ships
        with st.sidebar.container(height=ship_container_height):
            get_ship_stock_list(st.session_state.selected_ships)
            ship_list = [st.session_state.ship_list_state[ship] for ship in st.session_state.selected_ships]
            csv_ship_list = [st.session_state.csv_ship_list_state[ship] for ship in st.session_state.selected_ships]
            for ship in ship_list:
                st.text(ship)
    # Display selected modules if any
    if st.session_state.selected_modules:
        # Get module names
        module_names = [display_key.rsplit("_", 1)[0] for display_key in st.session_state.selected_modules]
        module_names = list(set(module_names))
        # Query market stock (total_stock) for these modules
        get_module_stock_list(module_names)

        st.sidebar.markdown("---")
        st.sidebar.markdown("### Selected Modules:")
        num_selected_modules = len(st.session_state.selected_modules)
        module_container_height =  100 if num_selected_modules <= 2 else num_selected_modules * 50


        module_list = [st.session_state.module_list_state[module] for module in module_names]
        csv_module_list = [st.session_state.csv_module_list_state[module] for module in module_names]

        # Create a scrollable container for selected modules
        with st.sidebar.container(height=module_container_height):
            for module in module_list:
                st.text(module)

    # Show export options if anything is selected
    if st.session_state.selected_ships or st.session_state.selected_modules:
        st.sidebar.markdown("---")

        # Export options in columns
        col1, col2 = st.sidebar.columns(2)

        # Prepare export text
        export_text = ""
        csv_export = ""

        if st.session_state.selected_ships:
            export_text += "SHIPS:\n" + "\n".join(ship_list)
            csv_export += "Type,TypeID,Quantity,Fits,Target,Usage\n"
            csv_export += "".join(csv_ship_list)

            if st.session_state.selected_modules:
                export_text += "\n\n"

        if st.session_state.selected_modules:
            # Get module names
            module_names = [display_key.rsplit("_", 1)[0] for display_key in st.session_state.selected_modules]
            module_names = list(set(module_names))

            export_text += "MODULES:\n" + "\n".join(module_list)

            if not st.session_state.selected_ships:
                csv_export += "Type,TypeID,Quantity,Fits,Target,Usage\n"
            csv_export += "".join(csv_module_list)

        # Download button
        col1.download_button(
            label="📥 Download CSV",
            data=csv_export,
            file_name="doctrine_export.csv",
            mime="text/csv",
            width='content'
        )
        # Copy to clipboard button
        if col2.button("📋 Copy to Clipboard", width='content'):
            st.sidebar.code(export_text, language="")
            st.sidebar.success("Copied to clipboard! Use Ctrl+C to copy the text above.")
    else:
        st.sidebar.info("Select ships and modules to export by checking the boxes next to them.")


    
    # Jita Price Delta Section
    st.sidebar.markdown("---")
    st.sidebar.subheader("Jita Price Comparison")

    jita_deltas = st.session_state.get('jita_deltas', {})

    if not jita_deltas:
        if st.sidebar.button(
            "📊 Calculate Jita Price Deltas",
            help="Compare fit costs to Jita prices. Cached for 1 hour via the API response.",
        ):
            calculate_all_jita_deltas()
            st.rerun()
    else:
        st.sidebar.success(f"✓ Jita deltas calculated for {len(jita_deltas)} fits")

        if 'jita_deltas_last_updated' in st.session_state:
            timestamp = st.session_state.jita_deltas_last_updated
            time_str = timestamp.strftime("%H:%M:%S")
            st.sidebar.caption(f"Last updated: {time_str}")

        if st.sidebar.button("🔄 Refresh Jita Prices", help="Fetch latest Jita prices (bypasses cache)"):
            st.session_state.jita_deltas = {}
            calculate_all_jita_deltas(force_refresh=True)
            st.rerun()
    # Display last update timestamp
    st.sidebar.markdown("---")
    st.sidebar.write(f"Last ESI update: {get_update_time()}")
if __name__ == "__main__":
    main()
