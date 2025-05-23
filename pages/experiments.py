import sqlalchemy as sa
from sqlalchemy import create_engine, inspect
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
    _, fit_summary = create_fit_df()
    
    if fit_summary.empty:
        st.warning("No doctrine fits found in the database.")
        return
    
    st.dataframe(fit_summary)
    
    # Display database tables
    st.subheader("Database Tables")
    engine = get_local_mkt_engine()
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    st.write(tables)

if __name__ == "__main__":
    pass