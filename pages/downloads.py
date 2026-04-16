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

import pathlib

import streamlit as st
import pandas as pd

from logging_config import setup_logging
from config import DatabaseConfig
from services.doctrine_service import DoctrineService, format_doctrine_name
from repositories import get_sde_repository
from repositories.market_repo import MarketRepository
from repositories.base import BaseRepository
from ui.market_selector import render_market_selector
from init_db import ensure_market_db_ready

logger = setup_logging(__name__, log_file="downloads.log")

# =============================================================================
# Lazy Data Loading Functions
# =============================================================================


@st.cache_data(ttl=1800, show_spinner=False)
def _get_market_orders_csv(db_alias: str) -> bytes:
    """Lazily load and convert market orders to CSV bytes."""
    repo = MarketRepository(DatabaseConfig(db_alias))
    df = repo.get_all_orders()
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=1800, show_spinner=False)
def _get_market_stats_csv(db_alias: str) -> bytes:
    """Lazily load and convert market stats to CSV bytes."""
    repo = MarketRepository(DatabaseConfig(db_alias))
    df = repo.get_all_stats()
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=1800, show_spinner=False)
def _get_market_history_csv(db_alias: str) -> bytes:
    """Lazily load and convert market history to CSV bytes."""
    repo = MarketRepository(DatabaseConfig(db_alias))
    df = repo.get_all_history()
    return df.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=600, show_spinner=False)
def _get_all_doctrine_fits_csv(db_alias: str) -> bytes:
    """Lazily load all doctrine fits data as CSV bytes."""
    service = DoctrineService.create_default(db_alias)
    all_fits_df = service.build_fit_data().raw_df
    if all_fits_df.empty:
        logger.warning("No fit data for all-doctrine export (db_alias=%s)", db_alias)
        return b""

    targets = service.repository.get_all_targets()
    if targets.empty:
        logger.warning("No targets data for doctrine export (db_alias=%s)", db_alias)
        return b""
    targets = targets[["fit_id", "fit_name", "ship_target"]].drop_duplicates(
        subset=["fit_id"], keep="first"
    )
    data = all_fits_df.merge(targets, on="fit_id", how="left")

    ship_target = pd.to_numeric(data["ship_target"], errors="coerce").fillna(0)
    fits_on_mkt = pd.to_numeric(data["fits_on_mkt"], errors="coerce").fillna(0)
    fit_qty = pd.to_numeric(data["fit_qty"], errors="coerce").fillna(0)
    data["qty_needed"] = (ship_target - fits_on_mkt).clip(lower=0) * fit_qty

    if "own_fits_on_mkt" in data.columns:
        data = data.drop(columns=["own_fits_on_mkt"])

    # Place fit_name right after fit_id
    cols = data.columns.tolist()
    if "fit_name" in cols:
        cols.remove("fit_name")
        fit_id_idx = cols.index("fit_id")
        cols.insert(fit_id_idx + 1, "fit_name")
        data = data[cols]

    data = data.sort_values(["ship_name", "fit_id", "type_name"])
    data = data.reset_index(drop=True)
    return data.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=600, show_spinner=False)
def _get_low_stock_doctrine_fits_csv(db_alias: str) -> bytes:
    """Lazily load low stock doctrine fits data as CSV bytes."""
    service = DoctrineService.create_default(db_alias)
    df = service.build_fit_data().raw_df
    if df.empty:
        logger.warning("No fit data for low-stock export (db_alias=%s)", db_alias)
        return b""

    targets = service.repository.get_all_targets()
    if targets.empty:
        logger.warning("No targets data for low-stock export (db_alias=%s)", db_alias)
        return b""
    targets = targets[["fit_id", "fit_name", "ship_target"]].drop_duplicates(
        subset=["fit_id"], keep="first"
    )
    data = df.merge(targets, on="fit_id", how="left")

    ship_target = pd.to_numeric(data["ship_target"], errors="coerce").fillna(0)
    fits_on_mkt = pd.to_numeric(data["fits_on_mkt"], errors="coerce").fillna(0)
    fit_qty = pd.to_numeric(data["fit_qty"], errors="coerce").fillna(0)
    data["qty_needed"] = (ship_target - fits_on_mkt).clip(lower=0) * fit_qty
    data = data[data["qty_needed"] > 0]

    if "own_fits_on_mkt" in data.columns:
        data = data.drop(columns=["own_fits_on_mkt"])

    output_columns = [
        "fit_id",
        "fit_name",
        "ship_id",
        "ship_name",
        "ship_target",
        "hulls",
        "type_id",
        "type_name",
        "qty_needed",
        "fit_qty",
        "fits_on_mkt",
        "total_stock",
        "price",
        "item_cost",
        "avg_vol",
        "days",
        "group_id",
        "group_name",
        "category_id",
        "category_name",
        "timestamp",
    ]
    data = data[output_columns]
    data = data.rename(
        columns={
            "total_stock": "qty_on_mkt",
            "item_cost": "cost_per_fit",
        }
    )
    data = data.sort_values(["ship_name", "fit_id"])
    data = data.reset_index(drop=True)
    return data.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=600, show_spinner=False)
def _get_fit_options(db_alias: str) -> list[dict]:
    """Get list of fits for the dropdown."""
    service = DoctrineService.create_default(db_alias)
    summaries = service.get_all_fit_summaries()
    return [
        {"fit_id": s.fit_id, "ship_name": s.ship_name, "fit_name": s.fit_name}
        for s in summaries
    ]


@st.cache_data(ttl=600, show_spinner=False)
def _get_doctrine_options(db_alias: str) -> dict[int, dict]:
    """Get doctrines for filtering, keyed by doctrine_id."""
    service = DoctrineService.create_default(db_alias)
    df = service.repository.get_all_doctrine_compositions()
    if df.empty:
        return {}
    doctrines = (
        df.groupby(["doctrine_id", "doctrine_name"]).agg({"fit_id": list}).reset_index()
    )
    return {
        int(row["doctrine_id"]): {
            "doctrine_name": row["doctrine_name"],
            "fit_ids": row["fit_id"],
        }
        for _, row in doctrines.iterrows()
    }


@st.cache_data(ttl=600, show_spinner=False)
def _get_filtered_doctrine_csv(db_alias: str, fit_ids: tuple) -> bytes:
    """Get doctrine data filtered by fit_ids as CSV bytes."""
    service = DoctrineService.create_default(db_alias)
    all_fits_df = service.build_fit_data().raw_df
    targets = service.repository.get_all_targets()

    # Filter by fit_ids
    filtered_df = all_fits_df[all_fits_df["fit_id"].isin(fit_ids)]
    data = filtered_df.merge(targets, on="fit_id", how="left")
    data = data.reset_index(drop=True)
    return data.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=600, show_spinner=False)
def _get_single_fit_csv(db_alias: str, fit_id: int) -> bytes:
    """Get CSV bytes for a single fit."""
    service = DoctrineService.create_default(db_alias)
    fit_df = service.repository.get_fit_by_id(fit_id)
    if fit_df.empty:
        return b""
    return fit_df.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=600, show_spinner=False)
def _get_low_stock_csv(
    db_alias: str, max_days: float, doctrine_only: bool, tech2_only: bool
) -> bytes:
    """Get low stock items as CSV bytes."""
    mktdb = DatabaseConfig(db_alias)

    tech2_type_ids: list[int] = []
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
        df = df[df["is_doctrine"] == 1]

    if max_days is not None:
        df = df[df["days_remaining"] <= max_days]

    if not df.empty:
        ship_groups: dict[int, list[str]] = {}
        for type_id, group in df.groupby("type_id"):
            ships = [
                f"{row['ship_name']} ({int(row['fits_on_mkt'])})"
                for _, row in group.iterrows()
                if pd.notna(row["ship_name"]) and pd.notna(row["fits_on_mkt"])
            ]
            if ships:
                ship_groups[type_id] = ships  # type: ignore[index]

        df = df.drop_duplicates(subset=["type_id"])
        df["ships"] = df["type_id"].map(ship_groups)

    if tech2_only:
        df = df[df["type_id"].isin(tech2_type_ids)]

    df = df.sort_values("days_remaining")

    # Clean up columns for export
    columns_to_drop = [
        "min_price",
        "avg_price",
        "category_id",
        "group_id",
        "is_doctrine",
    ]
    df = df.drop(
        columns=[c for c in columns_to_drop if c in df.columns], errors="ignore"
    )

    return df.to_csv(index=False).encode("utf-8")


@st.cache_data(ttl=3600, show_spinner=False)
def _get_sde_table_csv(table_name: str) -> bytes:
    """Get SDE table as CSV bytes."""
    df = get_sde_repository().get_sde_table(table_name)
    return df.to_csv(index=False).encode("utf-8")


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
    from state.market_state import get_active_market

    market = get_active_market()
    db_alias = market.database_alias
    short_name = market.short_name

    st.subheader(f"Market Data Downloads — {market.name}", divider="blue")
    st.markdown("Download market orders, statistics, and history data.")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.download_button(
            "Download Market Orders",
            data=lambda a=db_alias: _get_market_orders_csv(a),
            file_name=f"{short_name}_market_orders.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:",
        )

    with col2:
        st.download_button(
            "Download Market Stats",
            data=lambda a=db_alias: _get_market_stats_csv(a),
            file_name=f"{short_name}_market_stats.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:",
        )

    with col3:
        st.download_button(
            "Download Market History",
            data=lambda a=db_alias: _get_market_history_csv(a),
            file_name=f"{short_name}_market_history.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:",
        )


@st.fragment
def doctrine_downloads_section():
    """Fragment for doctrine data downloads with filtering."""
    from state.market_state import get_active_market

    market = get_active_market()
    db_alias = market.database_alias

    st.subheader("Doctrine Data Downloads", divider="orange")
    st.markdown(f"Download doctrine fit data with market data for **{market.name}**.")

    # Filter options
    col1, col2 = st.columns([1, 2])

    with col1:
        filter_type = st.radio(
            "Filter Type",
            ["All Fits", "By Doctrine", "Low Stock Only"],
            key="doctrine_filter_type",
            horizontal=True,
        )

    with col2:
        if filter_type == "By Doctrine":
            doctrine_map = _get_doctrine_options(db_alias)
            doctrine_ids = sorted(
                doctrine_map,
                key=lambda did: format_doctrine_name(doctrine_map[did]["doctrine_name"]),
            )
            selected_doctrine_id = st.selectbox(
                "Select Doctrine",
                [None] + doctrine_ids,
                key="doctrine_select",
                format_func=lambda did: "Select a doctrine..."
                if did is None
                else format_doctrine_name(doctrine_map[did]["doctrine_name"]),
            )
        else:
            selected_doctrine_id = None

    # Download button
    if filter_type == "All Fits":
        st.download_button(
            "Download All Doctrine Fits",
            data=lambda a=db_alias: _get_all_doctrine_fits_csv(a),
            file_name=f"{market.short_name}_doctrine_fits.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:",
        )
    elif filter_type == "Low Stock Only":
        st.download_button(
            "Download Low Stock Doctrine Fits",
            data=lambda a=db_alias: _get_low_stock_doctrine_fits_csv(a),
            file_name=f"{market.short_name}_low_stock_doctrine_fits.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:",
        )
    else:
        if selected_doctrine_id is not None and selected_doctrine_id in doctrine_map:
            doctrine_data = doctrine_map[selected_doctrine_id]
            fit_ids = tuple(doctrine_data["fit_ids"])
            doctrine_name = doctrine_data["doctrine_name"]
            safe_name = doctrine_name.replace(" ", "_").lower()

            st.download_button(
                f"Download {format_doctrine_name(doctrine_name)}",
                data=lambda a=db_alias, fids=fit_ids: _get_filtered_doctrine_csv(
                    a, fids
                ),
                file_name=f"doctrine_{safe_name}.csv",
                mime="text/csv",
                use_container_width=True,
                icon=":material/download:",
            )


@st.fragment
def individual_fit_downloads_section():
    """Fragment for individual fit downloads."""
    from state.market_state import get_active_market

    market = get_active_market()
    db_alias = market.database_alias

    st.subheader("Individual Fit Downloads", divider="green")
    st.markdown(f"Download detailed fit data with market data for **{market.name}**.")

    fits = _get_fit_options(db_alias)
    fit_options = {f"{f['ship_name']} (ID: {f['fit_id']})": f for f in fits}

    selected_fit_label = st.selectbox(
        "Select Fit",
        ["Select a fit..."] + list(fit_options.keys()),
        key="individual_fit_select",
    )

    if selected_fit_label and selected_fit_label != "Select a fit...":
        fit_data = fit_options[selected_fit_label]
        fit_id = fit_data["fit_id"]
        ship_name = fit_data["ship_name"].replace(" ", "_")

        st.download_button(
            f"Download Fit {fit_id}",
            data=lambda a=db_alias, fid=fit_id: _get_single_fit_csv(a, fid),
            file_name=f"fit_{fit_id}_{ship_name}.csv",
            mime="text/csv",
            use_container_width=True,
            icon=":material/download:",
        )


@st.fragment
def low_stock_downloads_section():
    """Fragment for low stock data downloads."""
    from state.market_state import get_active_market

    market = get_active_market()
    db_alias = market.database_alias

    st.subheader("Low Stock Data Downloads", divider="red")
    st.markdown(f"Download items running low on stock at **{market.name}**.")

    col1, col2, col3 = st.columns(3)

    with col1:
        max_days = st.slider(
            "Maximum Days Remaining",
            min_value=0.0,
            max_value=30.0,
            value=7.0,
            step=0.5,
            key="low_stock_max_days",
        )

    with col2:
        doctrine_only = st.checkbox(
            "Doctrine Items Only", key="low_stock_doctrine_only"
        )

    with col3:
        tech2_only = st.checkbox("Tech 2 Items Only", key="low_stock_tech2_only")

    st.download_button(
        "Download Low Stock Items",
        data=lambda a=db_alias, md=max_days, do=doctrine_only, t2=tech2_only: (
            _get_low_stock_csv(a, md, do, t2)
        ),
        file_name=f"{market.short_name}_low_stock_items.csv",
        mime="text/csv",
        use_container_width=True,
        icon=":material/download:",
    )


@st.fragment
def sde_downloads_section():
    """Fragment for SDE table downloads."""
    st.subheader("SDE Table Downloads", divider="violet")
    st.markdown(
        "Download Static Data Export (SDE) tables. The **sdetypes** table combines the most commonly used fields."
    )

    tables = _get_sde_tables()

    if not tables:
        st.warning("No SDE tables available.")
        return

    tables = sorted(tables, key=str.casefold)

    default_index = tables.index("sdetypes") if "sdetypes" in tables else 0

    selected_table = st.selectbox(
        "Select SDE Table", tables, index=default_index, key="sde_table_select"
    )

    st.download_button(
        f"Download {selected_table}",
        data=lambda tbl=selected_table: _get_sde_table_csv(tbl),
        file_name=f"{selected_table}.csv",
        mime="text/csv",
        use_container_width=True,
        icon=":material/download:",
    )


# =============================================================================
# Main Page
# =============================================================================


def main():
    market = render_market_selector()

    if not ensure_market_db_ready(market.database_alias):
        st.error(
            f"Database for **{market.name}** is not available. "
            "Check Turso credentials and network connectivity."
        )
        st.stop()

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
