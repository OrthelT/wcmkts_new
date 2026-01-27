"""
Pricer Page

Streamlit page for pricing Eve Online items and fittings.
Accepts EFT fittings or tab-separated item lists and displays
both Jita and 4-HWWF market prices.

Includes:
- Average daily volume and days of stock remaining
- Doctrine/fit highlighting
- Ship image display for EFT fittings
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
from state import ss_get, ss_has, ss_init
from ui.formatters import get_image_url

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
        "Slot": st.column_config.TextColumn(
            "Slot",
            help="Slot type",
            width="small",
        ),
        "4-HWWF Sell": st.column_config.NumberColumn(
            "4H Sell",
            help="4-HWWF minimum sell price per unit",
            format="localized",
        ),
        "4-HWWF Sell Vol": st.column_config.NumberColumn(
            "4H Vol",
            help="4-HWWF sell volume",
            format="localized",
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
            "Vol (m\u00b3)",
            help="Volume per unit in m\u00b3",
            format="localized",
        ),
        "Total Volume": st.column_config.NumberColumn(
            "Total Vol (m\u00b3)",
            help="Total volume (Qty \u00d7 Volume)",
            format="localized",
        ),
        "Category": st.column_config.TextColumn(
            "Category",
            help="Item category",
        ),
        "Avg Daily Vol": st.column_config.NumberColumn(
            "Avg/Day",
            help="Average daily sales volume (30-day)",
            format="localized",
        ),
        "Days of Stock": st.column_config.NumberColumn(
            "Days Stock",
            help="Days of stock remaining based on avg sales",
            format="%.1f",
        ),
        "Is Doctrine": st.column_config.CheckboxColumn(
            "Doctrine",
            help="Item is used in doctrine fits",
            width="small",
        ),
        "Doctrine Ships": st.column_config.ListColumn(
            "Used In Fits",
            help="Doctrine ships that use this item",
            width="medium",
        ),
    }


def highlight_doctrine_rows(row):
    """Style function to highlight doctrine items."""
    if row.get('Is Doctrine', False):
        return ['background-color: rgba(50, 143, 237, 0.3)'] * len(row)
    return [''] * len(row)


def highlight_low_stock(val):
    """Style function for low stock days."""
    try:
        val = float(val)
        if val <= 3:
            return 'background-color: #fc4103'  # Red for critical
        elif val <= 7:
            return 'background-color: #c76d14'  # Orange for low
        return ''
    except Exception:
        return ''


def render_header():
    """Render the Winter Coalition header with panda logo."""
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image("images/wclogo.png", width=125)
    with col2:
        st.title("Winter Coalition Pricer")


def render_fit_header(result):
    """Render the header for an EFT fit result with ship image."""
    if result.input_type != InputFormat.EFT:
        return

    # Get ship type_id from the first item (hull)
    ship_type_id = None
    for item in result.items:
        if item.item.category_name == "Ship":
            ship_type_id = item.type_id
            break

    col1, col2 = st.columns([0.15, 0.85])

    with col1:
        if ship_type_id:
            st.image(get_image_url(ship_type_id, 128, isship=True), width=128)

    with col2:
        if result.ship_name:
            st.subheader(result.ship_name)
        if result.fit_name:
            st.caption(result.fit_name)


def main():
    # Initialize session state
    ss_init({
        'pricer_show_jita': True,
        'pricer_show_doctrine': True,
        'pricer_highlight_doctrine': True,
        'pricer_show_stock_metrics': True,
    })

    render_header()
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

        # Render fit header with ship image for EFT fittings
        if result.input_type == InputFormat.EFT:
            render_fit_header(result)
        else:
            st.markdown("**Format:** Multibuy/Item List")

        # Grand totals metrics
        if result.items:
            st.subheader("Totals")

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    "4-HWWF Sell",
                    format_isk(result.local_sell_grand_total),
                    help="Total value at 4-HWWF sell prices"
                )
            with col2:
                st.metric(
                    "4-HWWF Buy",
                    format_isk(result.local_buy_grand_total),
                    help="Total value at 4-HWWF buy prices"
                )
            col3, col4 = st.columns(2)
            with col3:
                st.metric(
                    "Jita Sell",
                    format_isk(result.jita_sell_grand_total),
                    help="Total value at Jita sell prices"
                )
            with col4:
                st.metric(
                    "Jita Buy",
                    format_isk(result.jita_buy_grand_total),
                    help="Total value at Jita buy prices"
                )

            # Volume metric
            st.caption(f"**Total Volume:** {result.total_volume:,.2f} m\u00b3")

            # Results table
            st.subheader("Items")

            df = result.to_dataframe()

            # Add calculated columns
            df["Total Volume"] = df["Qty"] * df["Volume"]

            # Define column groups
            static_columns = ["image_url", "type_id", "Item", "Qty"]
            price_columns_all = ["4-HWWF Sell", "4-HWWF Buy", "4-HWWF Sell Vol", "Jita Sell", "Jita Buy"]
            price_columns_4hwwf = ["4-HWWF Sell", "4-HWWF Buy", "4-HWWF Sell Vol"]
            stock_columns = ["Avg Daily Vol", "Days of Stock"]
            doctrine_columns = ["Is Doctrine", "Doctrine Ships"]
            always_show_columns = ["Volume", "Category"]

            # Display options
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                display_selector = st.pills(
                    label="Display",
                    options=["item prices", "total prices"],
                    default="item prices",
                    key="display_pill",
                    help="Toggle between per-unit prices and totals"
                )
            with col2:
                show_jita = st.checkbox(
                    "Show Jita Prices",
                    value=ss_get('pricer_show_jita', True),
                    key="show_jita_prices"
                )
                st.session_state.pricer_show_jita = show_jita
            with col3:
                show_stock = st.checkbox(
                    "Show Stock Metrics",
                    value=ss_get('pricer_show_stock_metrics', True),
                    key="show_stock_metrics",
                    help="Show average daily volume and days of stock"
                )
                st.session_state.pricer_show_stock_metrics = show_stock
            with col4:
                highlight_doctrine = st.checkbox(
                    "Highlight Doctrine Items",
                    value=ss_get('pricer_highlight_doctrine', True),
                    key="highlight_doctrine",
                    help="Highlight items used in doctrine fits"
                )
                st.session_state.pricer_highlight_doctrine = highlight_doctrine

            # Build column list based on selections
            price_columns = price_columns_all if show_jita else price_columns_4hwwf

            if not df.empty:
                # Build column order
                column_order = static_columns.copy()
                column_order.extend(price_columns)

                if show_stock:
                    column_order.extend(stock_columns)

                if highlight_doctrine:
                    column_order.extend(doctrine_columns)

                column_order.extend(always_show_columns)

                # Filter to only columns that exist
                column_order = [c for c in column_order if c in df.columns]

                # Apply styling
                styled_df = df.copy()

                if highlight_doctrine and 'Is Doctrine' in styled_df.columns:
                    styled_df = styled_df.style.apply(highlight_doctrine_rows, axis=1)

                    if show_stock and 'Days of Stock' in df.columns:
                        styled_df = styled_df.map(highlight_low_stock, subset=['Days of Stock'])
                elif show_stock and 'Days of Stock' in df.columns:
                    styled_df = styled_df.style.map(highlight_low_stock, subset=['Days of Stock'])

                st.data_editor(
                    styled_df,
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
            with st.expander(f"\u26a0\ufe0f {len(result.parse_errors)} items could not be priced", expanded=False):
                for error in result.parse_errors:
                    st.warning(error)

    elif price_button:
        st.warning("Please paste some items to price.")


if __name__ == "__main__":
    main()
