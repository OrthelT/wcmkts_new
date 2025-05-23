import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
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
    
    st.dataframe(fit_summary)
    


if __name__ == "__main__":
    main()
 