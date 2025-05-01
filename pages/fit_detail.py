import streamlit as st
import pandas as pd
import datetime
import pathlib
from sqlalchemy import text
from sqlalchemy.orm import Session

from logging_config import setup_logging
from db_handler import get_local_mkt_engine, get_update_time, get_fitting_data
from pages.doctrine_status import get_targets
from doctrines import create_fit_df

# Insert centralized logging configuration
logger = setup_logging()



# @st.cache_data(ttl=600)
# def get_fit_items(type_id):
#     fitting_df = get_fitting_data(type_id)
#     targets_df = get_targets()
#     ship_fits = fitting_df[fitting_df['category_id'] == 6]
#     merged_df = pd.merge(ship_fits, targets_df, on='ship_id', how='left')
#     merged_df = merged_df.reset_index(drop=True)
    
#     return merged_df

def main():
    st.title("Fit Detail")
    st.write("This is the fit detail page")

    fitting_df = create_fit_df()
    ship_fitting_df = fitting_df[fitting_df['category_id'] == 6]
    ship_fitting_df = ship_fitting_df.sort_values(by='ship_name')
    ship_fitting_df = ship_fitting_df.reset_index(drop=True)
    available_fits = ship_fitting_df['ship_name'].unique().tolist()

    # Item name filter - changed to selectbox for single selection
    selected_ship = st.sidebar.selectbox(
        "Select Ship",
        options=[""] + available_fits,  # Add empty option to allow no selection
        index=0,
        format_func=lambda x: "All Fits" if x == "" else x
    )

    if selected_ship:
        fit_ids = ship_fitting_df[ship_fitting_df['ship_name'] == selected_ship]
        fit_ids = fit_ids['fit_id'].unique().tolist()
 
        engine = get_local_mkt_engine()
        fit_dict = {}
        for fit_id in fit_ids:
            with Session(engine) as session:
                query = text("SELECT fit_name, fit_id FROM ship_targets WHERE fit_id = :fit_id")
                result = session.execute(query, {'fit_id': fit_id})
                df = pd.DataFrame(result.fetchall(), columns=result.keys())
                fit_dict[df['fit_name'][0]] = [df['fit_id'][0]]
        fit_options = [""] + list(fit_dict.keys())
        if len(fit_ids) > 1:
            selected_fit = st.sidebar.selectbox(
                "Select Fit",
                options=fit_options,
                index=0,
                format_func=lambda x: "All Fits" if x == "" else x
            )
        else:
            selected_fit = fit_options[1]
        
        if selected_fit:
            selection = fit_dict[selected_fit]
            fit_id = selection[0]
            fit_items = fitting_df[fitting_df['fit_id'] == fit_id]
            fit_items = fit_items.reset_index(drop=True)
            
            ship_name = fit_items['ship_name'].unique().tolist()[0]
            targets = get_targets()
            targets = targets[targets['fit_id'] == fit_id]
            target = targets['ship_target'].unique().tolist()
            target_qty = target[0]
            
            fit_items.insert(9, 'target_qty', fit_items['fit_qty'] * target_qty)

            # Define a styling function to highlight rows where total_stock < target_qty
            def highlight_low_stock(row):
                if 'total_stock' in row.index and 'target_qty' in row.index:
                    if row['total_stock'] < row['target_qty']:
                        return ['background-color: #eb4034'] * len(row)
                return [''] * len(row)
            
            # Apply the styling to the DataFrame
            styled_df = fit_items.style.apply(highlight_low_stock, axis=1)

            st.header(ship_name, divider='blue')
            st.write(f"Target: {target}")
            st.write(f"Fit ID: {fit_id}")
            st.dataframe(styled_df)
            st.write(targets)
        
if __name__ == "__main__":
    main()
    

