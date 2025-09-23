import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from sqlalchemy import text
from config import DatabaseConfig
from pages.low_stock import get_market_stats

mktdb = DatabaseConfig("wcmkt")

from doctrines import create_fit_df, get_fit_info

def test_create_fit_df():
    df = create_fit_df()
    assert not df.empty
    assert df.shape[0] > 0
    assert df.shape[1] > 0
    assert df.columns.tolist() == ['fit_id', 'ship_name', 'ship_id', 'hulls', 'fits', 'ship_group', 'price', 'ship_target', 'target_percentage', 'daily_avg', 'doctrine_name', 'doctrine_id']

def test_get_market_stats():
    df = get_market_stats()
    assert not df.empty
    assert df.shape[0] > 0
    assert df.shape[1] > 0
    assert df.columns.tolist() == ['type_name', 'type_id', 'group_id', 'group_name', 'category_id', 'category_name']


if __name__ == "__main__":
    pass