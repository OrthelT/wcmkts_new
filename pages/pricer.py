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

def round_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Round columns."""
    df2 = df.copy()
    round_columns = [col for col in df2.columns if df2[col].dtype == "float64"]
    for column in round_columns:
        df2[column] = df2[column].apply(lambda x: round(x, 1) if x < 1000 else round(x, 0))
    return df2

def get_pricer_column_config() -> dict:
    """Get column configuration for the pricer results table."""
    return {
        "image_url": st.column_config.ImageColumn(
            "Icon",
            help="Item icon",
            width="small",
        ),
        "type_id": st.column_config.NumberColumn(
            "Type ID",
            help="Type ID",
            width="small",
        ),
        "Item": st.column_config.TextColumn(
            "Item",
            help="Item name",
            width="medium",
        ),
        "Qty": st.column_config.NumberColumn(
            "Qty",
            help="Quantity",
            format="localized"
        ),
        "Jita Sell": st.column_config.NumberColumn(
            "Jita Sell",
            help="Jita sell price per unit",
            format="localized",
        ),
        "Jita Buy": st.column_config.NumberColumn(
            "Jita Buy",
            help="Jita buy price per unit",
            format="localized",
        ),
        "Jita Sell Total": st.column_config.NumberColumn(
            "Jita Sell Total",
            help="Total Jita sell value",
            format="localized",
        ),
        "Jita Buy Total": st.column_config.NumberColumn(
            "Jita Buy Total",
            help="Total Jita buy value",
            format="localized",
        ),
        "4-HWWF Sell": st.column_config.NumberColumn(
            "4H Sell",
            help="4-HWWF minimum sell price per unit",
            format="localized",
        ),
        "4-HWWF Buy": st.column_config.NumberColumn(
            "4H Buy",
            help="4-HWWF maximum buy price per unit",
            format="localized",
        ),
        "4-HWWF Sell Total": st.column_config.NumberColumn(
            "4H Sell Total",
            help="Total 4-HWWF sell value",
            format="localized",
        ),
        "4-HWWF Buy Total": st.column_config.NumberColumn(
            "4H Buy Total",
            help="Total 4-HWWF buy value",
            format="localized",
        ),

        "Volume": st.column_config.NumberColumn(
            "Vol (m³)",
            help="Volume per unit in m³",
            format="localized",
        ),
        "Total Volume": st.column_config.NumberColumn(
            "Total Vol (m³)",
            help="Total volume (Qty × Volume)",
            format="localized",
        ),
        "Category": st.column_config.TextColumn(
            "Category",
            help="Item category",
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
                    format_isk(result.jita_sell_grand_total),
                    help="Total value at Jita sell prices"
                )
            with col2:
                st.metric(
                    "Jita Buy",
                    format_isk(result.jita_buy_grand_total),
                    help="Total value at Jita buy prices"
                )
            with col3:
                st.metric(
                    "4-HWWF Sell",
                    format_isk(result.local_sell_grand_total),
                    help="Total value at 4-HWWF sell prices"
                )
            with col4:
                st.metric(
                    "4-HWWF Buy",
                    format_isk(result.local_buy_grand_total),
                    help="Total value at 4-HWWF buy prices"
                )

            # Volume metric
            st.caption(f"**Total Volume:** {result.total_volume:,.2f} m³")

            # Results table
            st.subheader("Items")

            df = result.to_dataframe()

            # Add calculated columns
            df["Total Volume"] = df["Qty"] * df["Volume"]

            # Define column groups
            static_columns = ["image_url", "type_id", "Item", "Qty"]
            item_price_columns = ["Jita Sell", "Jita Buy", "4-HWWF Sell", "4-HWWF Buy", "Volume"]
            total_price_columns = ["Jita Sell Total", "Jita Buy Total", "4-HWWF Sell Total", "4-HWWF Buy Total", "Total Volume"]
            always_show_columns = ["Category"]

            display_selector = st.pills(
                label="Display",
                options=["item prices", "total prices"],
                default="item prices",
                key="display_pill",
                help="Toggle between per-unit prices and totals"
            )

            # Select price columns based on toggle
            if display_selector == "total prices":
                price_columns = total_price_columns
            else:
                price_columns = item_price_columns

            if not df.empty:
                # Round numeric columns for display
                df = round_columns(df, price_columns)

                # Build column order: static + selected prices + always-show
                column_order = static_columns + price_columns + always_show_columns
                column_order = [c for c in column_order if c in df.columns]
                
                st.data_editor(
                    df,
                    hide_index=True,
                    column_config=get_pricer_column_config(),
                    width="content",
                    column_order=column_order,
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
