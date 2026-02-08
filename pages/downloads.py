"""
Downloads Page

Centralized download page for all CSV exports.
Uses Streamlit's callable pattern for lazy data loading - data is only
generated when the user clicks the download button.

Downloads available:
- Market Data: Orders, Stats, History
- Doctrine Data: All fits, filtered by doctrine_fit
- Individual Fit Data: Select specific fit to download
- Low Stock Data: Items below stock threshold
- SDE Tables: Static data export tables
"""

import os
import sys
import pathlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd

from logging_config import setup_logging
from config import DatabaseConfig, get_settings
from services import get_doctrine_service
from ui.formatters import format_doctrine_name
from repositories import get_market_repository, get_sde_repository
from repositories.base import BaseRepository

logger = setup_logging(__name__, log_file="downloads.log")

settings = get_settings()
market_short_name = settings['market']['short_name']

# =============================================================================
# Lazy Data Loading Functions
# =============================================================================


@st.cache_data(ttl=1800, show_spinner=False)
def _get_market_orders_csv() -> bytes:
    """Lazily load and convert market orders to CSV bytes."""
    repo = get_market_repository()
    df = repo.get_all_orders()
    return df.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=1800, show_spinner=False)
def _get_market_stats_csv() -> bytes:
    """Lazily load and convert market stats to CSV bytes."""
    repo = get_market_repository()
    df = repo.get_all_stats()
    return df.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=1800, show_spinner=False)
def _get_market_history_csv() -> bytes:
    """Lazily load and convert market history to CSV bytes."""
    repo = get_market_repository()
    df = repo.get_all_history()
    return df.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=600, show_spinner=False)
def _get_all_doctrine_fits_csv() -> bytes:
    """Lazily load all doctrine fits data as CSV bytes."""
    service = get_doctrine_service()
    all_fits_df = service.build_fit_data().raw_df
    targets = service.repository.get_all_targets()
    data = all_fits_df.merge(targets, on='fit_id', how='left')
    data = data.reset_index(drop=True)
    return data.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=600, show_spinner=False)
def _get_fit_options() -> list[dict]:
    """Get list of fits for the dropdown."""
    service = get_doctrine_service()
    summaries = service.get_all_fit_summaries()
    return [
        {"fit_id": s.fit_id, "ship_name": s.ship_name, "fit_name": s.fit_name}
        for s in summaries
    ]


@st.cache_data(ttl=600, show_spinner=False)
def _get_doctrine_options() -> list[dict]:
    """Get list of doctrines for filtering."""
    service = get_doctrine_service()
    df = service.repository.get_all_doctrine_compositions()
    if df.empty:
        return []
    doctrines = df.groupby(['doctrine_id', 'doctrine_name']).agg({
        'fit_id': list
    }).reset_index()
    return [
        {"doctrine_id": row['doctrine_id'], "doctrine_name": row['doctrine_name'], "fit_ids": row['fit_id']}
        for _, row in doctrines.iterrows()
    ]


@st.cache_data(ttl=600, show_spinner=False)
def _get_filtered_doctrine_csv(fit_ids: tuple) -> bytes:
    """Get doctrine data filtered by fit_ids as CSV bytes."""
    service = get_doctrine_service()
    all_fits_df = service.build_fit_data().raw_df
    targets = service.repository.get_all_targets()

    # Filter by fit_ids
    filtered_df = all_fits_df[all_fits_df['fit_id'].isin(fit_ids)]
    data = filtered_df.merge(targets, on='fit_id', how='left')
    data = data.reset_index(drop=True)
    return data.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=600, show_spinner=False)
def _get_single_fit_csv(fit_id: int) -> bytes:
    """Get CSV bytes for a single fit."""
    service = get_doctrine_service()
    fit_df = service.repository.get_fit_by_id(fit_id)
    if fit_df.empty:
        return b""
    return fit_df.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=600, show_spinner=False)
def _get_low_stock_csv(max_days: float, doctrine_only: bool, tech2_only: bool) -> bytes:
    """Get low stock items as CSV bytes."""
    mktdb = DatabaseConfig("wcmkt")

    if tech2_only:
        tech2_type_ids = get_sde_repository().get_tech2_type_ids()

    query = """
    SELECT ms.*,
           CASE WHEN d.type_id IS NOT NULL THEN 1 ELSE 0 END as is_doctrine,
           d.ship_name,
           d.fits_on_mkt
    FROM marketstats ms
    LEFT JOIN doctrines d ON ms.type_id = d.type_id
    """

    df = BaseRepository(mktdb).read_df(query)

    if doctrine_only:
        df = df[df['is_doctrine'] == 1]

    if max_days is not None:
        df = df[df['days_remaining'] <= max_days]

    if not df.empty:
        ship_groups = df.groupby('type_id', group_keys=False).apply(
            lambda x: [f"{row['ship_name']} ({int(row['fits_on_mkt'])})"
                      for _, row in x.iterrows()
                      if pd.notna(row['ship_name']) and pd.notna(row['fits_on_mkt'])], include_groups=False
        ).to_dict()

        df = df.drop_duplicates(subset=['type_id'])
        df['ships'] = df['type_id'].map(ship_groups)

    if tech2_only:
        df = df[df['type_id'].isin(tech2_type_ids)]

    df = df.sort_values('days_remaining')

    # Clean up columns for export
    columns_to_drop = ['min_price', 'avg_price', 'category_id', 'group_id', 'is_doctrine']
    df = df.drop(columns=[c for c in columns_to_drop if c in df.columns], errors='ignore')

    return df.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=3600, show_spinner=False)
def _get_sde_table_csv(table_name: str) -> bytes:
    """Get SDE table as CSV bytes."""
    df = get_sde_repository().get_sde_table(table_name)
    return df.to_csv(index=False).encode('utf-8')


@st.cache_data(ttl=3600, show_spinner=False)
def _get_sde_tables() -> list[str]:
    """Get list of available SDE tables."""
    db = DatabaseConfig("sde")
    return db.get_table_list()


# =============================================================================
# UI Sections
# =============================================================================

def market_downloads_section():
    """Section for market data downloads."""
    st.subheader("Market Data Downloads", divider="blue")
    st.markdown("Download market orders, statistics, and history data.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "Download Market Orders",
            data=_get_market_orders_csv,
            file_name=f"{market_short_name}_market_orders.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:"
        )

    with col2:
        st.download_button(
            "Download Market Stats",
            data=_get_market_stats_csv,
            file_name=f"{market_short_name}_market_stats.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:"
        )

    with col3:
        st.download_button(
            "Download Market History",
            data=_get_market_history_csv,
            file_name=f"{market_short_name}_market_history.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:"
        )


@st.fragment
def doctrine_downloads_section():
    """Fragment for doctrine data downloads with filtering."""
    st.subheader("Doctrine Data Downloads", divider="orange")
    st.markdown("Download doctrine fit data. Filter by specific doctrine or download all fits.")

    # Filter options
    col1, col2 = st.columns([1, 2])

    with col1:
        filter_type = st.radio(
            "Filter Type",
            ["All Fits", "By Doctrine"],
            key="doctrine_filter_type",
            horizontal=True
        )

    with col2:
        if filter_type == "By Doctrine":
            doctrines = _get_doctrine_options()
            doctrine_names = ["Select a doctrine..."] + [d['doctrine_name'] for d in doctrines]
            selected_doctrine = st.selectbox(
                "Select Doctrine",
                doctrine_names,
                key="doctrine_select",
                format_func=format_doctrine_name,
            )
        else:
            selected_doctrine = None

    # Download button
    if filter_type == "All Fits":
        st.download_button(
            "Download All Doctrine Fits",
            data=_get_all_doctrine_fits_csv,
            file_name="wc_doctrine_fits.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:"
        )
    else:
        if selected_doctrine and selected_doctrine != "Select a doctrine...":
            doctrines = _get_doctrine_options()
            doctrine_data = next((d for d in doctrines if d['doctrine_name'] == selected_doctrine), None)

            if doctrine_data:
                fit_ids = tuple(doctrine_data['fit_ids'])
                safe_name = selected_doctrine.replace(' ', '_').lower()

                st.download_button(
                    f"Download {format_doctrine_name(selected_doctrine)}",
                    data=lambda fids=fit_ids: _get_filtered_doctrine_csv(fids),
                    file_name=f"doctrine_{safe_name}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    icon=":material/download:"
                )


@st.fragment
def individual_fit_downloads_section():
    """Fragment for individual fit downloads."""
    st.subheader("Individual Fit Downloads", divider="green")
    st.markdown("Download detailed data for a specific fit.")

    fits = _get_fit_options()
    fit_options = {f"{f['ship_name']} (ID: {f['fit_id']})": f for f in fits}

    selected_fit_label = st.selectbox(
        "Select Fit",
        ["Select a fit..."] + list(fit_options.keys()),
        key="individual_fit_select"
    )

    if selected_fit_label and selected_fit_label != "Select a fit...":
        fit_data = fit_options[selected_fit_label]
        fit_id = fit_data['fit_id']
        ship_name = fit_data['ship_name'].replace(' ', '_')

        st.download_button(
            f"Download Fit {fit_id}",
            data=lambda fid=fit_id: _get_single_fit_csv(fid),
            file_name=f"fit_{fit_id}_{ship_name}.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:"
        )


@st.fragment
def low_stock_downloads_section():
    """Fragment for low stock data downloads."""
    st.subheader("Low Stock Data Downloads", divider="red")
    st.markdown("Download items that are running low on stock.")

    col1, col2, col3 = st.columns(3)

    with col1:
        max_days = st.slider(
            "Maximum Days Remaining",
            min_value=0.0,
            max_value=30.0,
            value=7.0,
            step=0.5,
            key="low_stock_max_days"
        )

    with col2:
        doctrine_only = st.checkbox("Doctrine Items Only", key="low_stock_doctrine_only")

    with col3:
        tech2_only = st.checkbox("Tech 2 Items Only", key="low_stock_tech2_only")

    st.download_button(
        "Download Low Stock Items",
        data=lambda md=max_days, do=doctrine_only, t2=tech2_only: _get_low_stock_csv(md, do, t2),
        file_name="low_stock_items.csv",
        mime="text/csv",
        use_container_width=True,
        icon=":material/download:"
    )


@st.fragment
def sde_downloads_section():
    """Fragment for SDE table downloads."""
    st.subheader("SDE Table Downloads", divider="violet")
    st.markdown("Download Static Data Export (SDE) tables. The **sdetypes** table combines the most commonly used fields.")

    tables = _get_sde_tables()

    if not tables:
        st.warning("No SDE tables available.")
        return

    default_index = tables.index("sdetypes") if "sdetypes" in tables else 0

    selected_table = st.selectbox(
        "Select SDE Table",
        tables,
        index=default_index,
        key="sde_table_select"
    )

    st.download_button(
        f"Download {selected_table}",
        data=lambda tbl=selected_table: _get_sde_table_csv(tbl),
        file_name=f"{selected_table}.csv",
        mime="text/csv",
        use_container_width=True,
        icon=":material/download:"
    )


# =============================================================================
# Main Page
# =============================================================================

def main():
    # Header
    col1, col2 = st.columns([0.15, 0.85], vertical_alignment="bottom")

    with col1:
        image_path = pathlib.Path(__file__).parent.parent / "images" / "wclogo.png"
        if image_path.exists():
            st.image(str(image_path), width=100)

    with col2:
        st.title("Downloads")
        st.markdown("*Centralized data export for all market and doctrine data*")

    st.divider()

    # Download sections
    market_downloads_section()
    st.divider()

    doctrine_downloads_section()
    st.divider()

    individual_fit_downloads_section()
    st.divider()

    low_stock_downloads_section()
    st.divider()

    sde_downloads_section()


if __name__ == "__main__":
    main()
