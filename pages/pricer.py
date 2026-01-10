"""
Pricer Page

Streamlit page for pricing Eve Online items and fittings.
Accepts EFT fittings or tab-separated item lists and displays
both Jita and 4-HWWF market prices.
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
import pandas as pd
from millify import millify
from logging_config import setup_logging
from services import get_pricer_service
from domain import InputFormat

logger = setup_logging(__name__, log_file="pricer.log")


def format_isk(value: float) -> str:
    """Format ISK value with millify for compact display."""
    if value == 0:
        return "0"
    return millify(value, precision=2)


def get_pricer_column_config() -> dict:
    """Get column configuration for the pricer results table."""
    return {
        "type_name": st.column_config.TextColumn(
            "Item",
            help="Item name",
            width="medium",
        ),
        "quantity": st.column_config.NumberColumn(
            "Qty",
            help="Quantity",
            width="small",
        ),
        "slot_type": st.column_config.TextColumn(
            "Slot",
            help="Slot type (for EFT fittings)",
            width="small",
        ),
        "category_name": st.column_config.TextColumn(
            "Category",
            help="Item category",
            width="small",
        ),
        "volume": st.column_config.NumberColumn(
            "Vol (m³)",
            help="Volume per unit in m³",
            format="%.2f",
            width="small",
        ),
        "jita_sell": st.column_config.NumberColumn(
            "Jita Sell",
            help="Jita sell price per unit",
            format="%.2f",
            width="small",
        ),
        "jita_buy": st.column_config.NumberColumn(
            "Jita Buy",
            help="Jita buy price per unit",
            format="%.2f",
            width="small",
        ),
        "jita_sell_total": st.column_config.NumberColumn(
            "Jita Sell Total",
            help="Total Jita sell value",
            format="%.2f",
            width="small",
        ),
        "jita_buy_total": st.column_config.NumberColumn(
            "Jita Buy Total",
            help="Total Jita buy value",
            format="%.2f",
            width="small",
        ),
        "local_sell": st.column_config.NumberColumn(
            "4H Sell",
            help="4-HWWF minimum sell price per unit",
            width="small",
        ),
        "local_buy": st.column_config.NumberColumn(
            "4H Buy",
            help="4-HWWF maximum buy price per unit",
            width="small",
        ),
        "local_sell_total": st.column_config.NumberColumn(
            "4H Sell Total",
            help="Total 4-HWWF sell value",
            format="%.2f",
            width="small",
        ),
        "local_buy_total": st.column_config.NumberColumn(
            "4H Buy Total",
            help="Total 4-HWWF buy value",
            format="%.2f",
            width="small",
        ),
    }


def main():
    st.title("Pricer")
    st.markdown("Price items and fittings using Jita and 4-HWWF market data.")

    # Input section
    st.subheader("Input")

    placeholder_text = """Paste items here in one of these formats:

EFT Fitting:
[Hurricane, PVP Fit]
Damage Control II
1600mm Steel Plates II
...

Tab-separated (item first):
Tritanium\t10000
Pyerite\t5000

Tab-separated (qty first):
10000\tTritanium
5000\tPyerite"""

    input_text = st.text_area(
        "Paste EFT fitting or item list:",
        height=300,
        placeholder=placeholder_text,
        key="pricer_input",
    )

    # Price button
    col1, col2 = st.columns([1, 4])
    with col1:
        price_button = st.button("Price Items", type="primary", use_container_width=True)

    # Results section
    if price_button and input_text.strip():
        with st.spinner("Fetching prices..."):
            try:
                service = get_pricer_service()
                result = service.price_input(input_text)

                # Store result in session state for persistence
                st.session_state.pricer_result = result
                logger.info(f"Priced {len(result.items)} items")

            except Exception as e:
                logger.error(f"Error pricing items: {e}")
                st.error(f"Error pricing items: {e}")
                return

    # Display results from session state
    if 'pricer_result' in st.session_state:
        result = st.session_state.pricer_result

        st.divider()

        # Format info
        format_info = []
        if result.input_type == InputFormat.EFT:
            format_info.append("**Format:** EFT Fitting")
            if result.ship_name:
                format_info.append(f"**Ship:** {result.ship_name}")
            if result.fit_name:
                format_info.append(f"**Fit:** {result.fit_name}")
        else:
            format_info.append("**Format:** Multibuy/Item List")

        st.markdown(" | ".join(format_info))

        # Grand totals metrics
        if result.items:
            st.subheader("Totals")

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric(
                    "Jita Sell",
                    format_isk(result.grand_total_jita_sell),
                    help="Total value at Jita sell prices"
                )
            with col2:
                st.metric(
                    "Jita Buy",
                    format_isk(result.grand_total_jita_buy),
                    help="Total value at Jita buy prices"
                )
            with col3:
                st.metric(
                    "4-HWWF Sell",
                    format_isk(result.grand_total_local_sell),
                    help="Total value at 4-HWWF sell prices"
                )
            with col4:
                st.metric(
                    "4-HWWF Buy",
                    format_isk(result.grand_total_local_buy),
                    help="Total value at 4-HWWF buy prices"
                )

            # Volume metric
            st.caption(f"**Total Volume:** {result.total_volume:,.2f} m³")

            # Results table
            st.subheader("Items")

            df = result.to_dataframe()

            if not df.empty:
                # Reorder columns for better display
                display_columns = [
                    "type_name",
                    "quantity",
                    "slot_type",
                    "category_name",
                    "volume",
                    "jita_sell",
                    "jita_buy",
                    "jita_sell_total",
                    "jita_buy_total",
                    "local_sell",
                    "local_buy",
                    "local_sell_total",
                    "local_buy_total",
                ]

                # Filter to only columns that exist
                available_columns = [c for c in display_columns if c in df.columns]
                df_display = df[available_columns]

                st.dataframe(
                    df_display,
                    hide_index=True,
                    column_config=get_pricer_column_config(),
                    use_container_width=True,
                )

                # Download button
                csv_data = df.to_csv(index=False)
                filename = "priced_items.csv"
                if result.ship_name:
                    filename = f"{result.ship_name.replace(' ', '_')}_priced.csv"

                st.download_button(
                    "Download CSV",
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                )

        # Parse errors
        if result.parse_errors:
            st.subheader("Issues")
            with st.expander(f"⚠️ {len(result.parse_errors)} items could not be priced", expanded=False):
                for error in result.parse_errors:
                    st.warning(error)

    elif price_button:
        st.warning("Please paste some items to price.")


if __name__ == "__main__":
    main()
