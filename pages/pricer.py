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
from state import get_active_language, ss_get, ss_has, ss_init, ss_set
from ui.formatters import get_image_url
from ui.i18n import translate_text
from ui.market_selector import render_market_selector
from init_db import ensure_market_db_ready

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


def get_pricer_column_config(short_name: str = "4H", language_code: str = "en") -> dict:
    """Get column configuration for the pricer results table."""
    return {
        "image_url": st.column_config.ImageColumn(
            translate_text(language_code, "pricer.column_icon"),
            help=translate_text(language_code, "pricer.column_icon_help"),
            width="small",
        ),
        "type_id": st.column_config.NumberColumn(
            translate_text(language_code, "common.type_id"),
            help=translate_text(language_code, "pricer.column_type_id_help"),
            width="small",
        ),
        "Item": st.column_config.TextColumn(
            translate_text(language_code, "common.item"),
            help=translate_text(language_code, "pricer.column_item_help"),
            width="medium",
        ),
        "Qty": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_qty"),
            help=translate_text(language_code, "pricer.column_qty_help"),
            format="localized"
        ),
        "Slot": st.column_config.TextColumn(
            translate_text(language_code, "pricer.column_slot"),
            help=translate_text(language_code, "pricer.column_slot_help"),
            width="small",
        ),
        "Local Sell": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_local_sell", market_name=short_name),
            help=translate_text(language_code, "pricer.column_local_sell_help", market_name=short_name),
            format="localized",
        ),
        "Local Sell Vol": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_local_sell_volume", market_name=short_name),
            help=translate_text(language_code, "pricer.column_local_sell_volume_help", market_name=short_name),
            format="localized",
        ),
        "Jita Sell": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_sell"),
            help=translate_text(language_code, "pricer.column_jita_sell_help"),
            format="localized",
        ),
        "Jita Buy": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_buy"),
            help=translate_text(language_code, "pricer.column_jita_buy_help"),
            format="localized",
        ),
        "Jita Sell Total": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_sell_total"),
            help=translate_text(language_code, "pricer.column_jita_sell_total_help"),
            format="localized",
        ),
        "Jita Buy Total": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_jita_buy_total"),
            help=translate_text(language_code, "pricer.column_jita_buy_total_help"),
            format="localized",
        ),
        "Local Buy": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_local_buy", market_name=short_name),
            help=translate_text(language_code, "pricer.column_local_buy_help", market_name=short_name),
            format="localized",
        ),
        "Local Sell Total": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_local_sell_total", market_name=short_name),
            help=translate_text(language_code, "pricer.column_local_sell_total_help", market_name=short_name),
            format="localized",
        ),
        "Local Buy Total": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_local_buy_total", market_name=short_name),
            help=translate_text(language_code, "pricer.column_local_buy_total_help", market_name=short_name),
            format="localized",
        ),
        "Volume": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_volume"),
            help=translate_text(language_code, "pricer.column_volume_help"),
            format="localized",
        ),
        "Total Volume": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_total_volume"),
            help=translate_text(language_code, "pricer.column_total_volume_help"),
            format="localized",
        ),
        "Category": st.column_config.TextColumn(
            translate_text(language_code, "low_stock.column_category"),
            help=translate_text(language_code, "pricer.column_category_help"),
        ),
        "Avg Daily Vol": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_avg_daily_volume"),
            help=translate_text(language_code, "pricer.column_avg_daily_volume_help"),
            format="localized",
        ),
        "Days of Stock": st.column_config.NumberColumn(
            translate_text(language_code, "pricer.column_days_of_stock"),
            help=translate_text(language_code, "pricer.column_days_of_stock_help"),
            format="%.1f",
        ),
        "Is Doctrine": st.column_config.CheckboxColumn(
            translate_text(language_code, "nav.page.doctrine_status").lstrip("⚔️"),
            help=translate_text(language_code, "pricer.column_is_doctrine_help"),
            width="small",
        ),
        "Doctrine Ships": st.column_config.ListColumn(
            translate_text(language_code, "low_stock.column_used_in_fits"),
            help=translate_text(language_code, "pricer.column_doctrine_ships_help"),
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


def render_header(language_code: str):
    """Render the Winter Coalition header with panda logo."""
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image("images/wclogo.png", width=125)
    with col2:
        st.title(translate_text(language_code, "pricer.title"))


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
    language_code = get_active_language()
    market = render_market_selector(label=translate_text(language_code, "common.market_hub"))

    if not ensure_market_db_ready(market.database_alias):
        st.error(translate_text(language_code, "error.market_db_unavailable", market_name=market.name))
        st.stop()

    # Initialize session state
    ss_init({
        'pricer_show_jita': True,
        'pricer_show_doctrine': True,
        'pricer_highlight_doctrine': True,
        'pricer_show_stock_metrics': True,
    })

    render_header(language_code)
    st.markdown(translate_text(language_code, "pricer.description", market_name=market.name))

    # Input section
    st.subheader(translate_text(language_code, "pricer.input_section"))

    placeholder_text = translate_text(language_code, "pricer.input_placeholder")

    input_text = st.text_area(
        translate_text(language_code, "pricer.input_label"),
        height=300,
        placeholder=placeholder_text,
        key="pricer_input",
    )

    # Price button
    col1, col2 = st.columns([1, 4])
    with col1:
        price_button = st.button(
            translate_text(language_code, "pricer.price_items"),
            type="primary",
            use_container_width=True,
        )

    # Results section
    if price_button and input_text.strip():
        with st.spinner(translate_text(language_code, "pricer.fetching_prices")):
            try:
                service = get_pricer_service()
                result = service.price_input(input_text)

                # Store result in session state for persistence
                ss_set('pricer_result', result)
                logger.info(f"Priced {len(result.items)} items")

            except Exception as e:
                logger.error(f"Error pricing items: {e}")
                st.error(translate_text(language_code, "pricer.error_pricing", error=e))
                return

    # Display results from session state
    if ss_has('pricer_result'):
        result = ss_get('pricer_result')

        st.divider()

        # Render fit header with ship image for EFT fittings
        if result.input_type == InputFormat.EFT:
            render_fit_header(result)
        else:
            st.markdown(f"**{translate_text(language_code, 'pricer.format_label')}:** {translate_text(language_code, 'pricer.format_multibuy')}")

        # Grand totals metrics
        if result.items:
            st.subheader(translate_text(language_code, "pricer.totals"))

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    translate_text(language_code, "pricer.column_local_sell", market_name=market.short_name),
                    format_isk(result.local_sell_grand_total),
                    help=translate_text(language_code, "pricer.metric_local_sell_help", market_name=market.short_name),
                )
            with col2:
                st.metric(
                    translate_text(language_code, "pricer.column_local_buy", market_name=market.short_name),
                    format_isk(result.local_buy_grand_total),
                    help=translate_text(language_code, "pricer.metric_local_buy_help", market_name=market.short_name),
                )
            col3, col4 = st.columns(2)
            with col3:
                st.metric(
                    translate_text(language_code, "pricer.column_jita_sell"),
                    format_isk(result.jita_sell_grand_total),
                    help=translate_text(language_code, "pricer.metric_jita_sell_help"),
                )
            with col4:
                st.metric(
                    translate_text(language_code, "pricer.column_jita_buy"),
                    format_isk(result.jita_buy_grand_total),
                    help=translate_text(language_code, "pricer.metric_jita_buy_help"),
                )

            # Volume metric
            st.caption(
                f"**{translate_text(language_code, 'pricer.total_volume_label')}:** {result.total_volume:,.2f} m\u00b3"
            )

            # Results table
            st.subheader(translate_text(language_code, "pricer.items"))

            df = result.to_dataframe()

            # Add calculated columns
            df["Total Volume"] = df["Qty"] * df["Volume"]

            # Define column groups
            static_columns = ["image_url", "type_id", "Item", "Qty"]
            price_columns_all = ["Local Sell", "Local Buy", "Local Sell Vol", "Jita Sell", "Jita Buy"]
            price_columns_local = ["Local Sell", "Local Buy", "Local Sell Vol"]
            stock_columns = ["Avg Daily Vol", "Days of Stock"]
            doctrine_columns = ["Is Doctrine", "Doctrine Ships"]
            always_show_columns = ["Volume", "Category"]

            # Display options
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.pills(
                    label=translate_text(language_code, "pricer.display"),
                    options=[
                        translate_text(language_code, "pricer.display_item_prices"),
                        translate_text(language_code, "pricer.display_total_prices"),
                    ],
                    default=translate_text(language_code, "pricer.display_item_prices"),
                    key="display_pill",
                    help=translate_text(language_code, "pricer.display_help"),
                )
            with col2:
                show_jita = st.checkbox(
                    translate_text(language_code, "pricer.show_jita_prices"),
                    value=ss_get('pricer_show_jita', True),
                    key="show_jita_prices"
                )
                ss_set('pricer_show_jita', show_jita)
            with col3:
                show_stock = st.checkbox(
                    translate_text(language_code, "pricer.show_stock_metrics"),
                    value=ss_get('pricer_show_stock_metrics', True),
                    key="show_stock_metrics",
                    help=translate_text(language_code, "pricer.show_stock_metrics_help"),
                )
                ss_set('pricer_show_stock_metrics', show_stock)
            with col4:
                highlight_doctrine = st.checkbox(
                    translate_text(language_code, "pricer.highlight_doctrine_items"),
                    value=ss_get('pricer_highlight_doctrine', True),
                    key="highlight_doctrine",
                    help=translate_text(language_code, "pricer.highlight_doctrine_items_help"),
                )
                ss_set('pricer_highlight_doctrine', highlight_doctrine)

            # Build column list based on selections
            price_columns = price_columns_all if show_jita else price_columns_local

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
                    column_config=get_pricer_column_config(market.short_name, language_code),
                    width="content",
                    column_order=column_order,
                )

                # Download button
                csv_data = df.to_csv(index=False)
                filename = "priced_items.csv"
                if result.ship_name:
                    filename = f"{result.ship_name.replace(' ', '_')}_priced.csv"

                st.download_button(
                    translate_text(language_code, "doctrine_report.download_csv"),
                    data=csv_data,
                    file_name=filename,
                    mime="text/csv",
                )

        # Parse errors
        if result.parse_errors:
            st.subheader(translate_text(language_code, "pricer.issues"))
            with st.expander(
                translate_text(
                    language_code,
                    "pricer.unpriced_items",
                    count=len(result.parse_errors),
                ),
                expanded=False,
            ):
                for error in result.parse_errors:
                    st.warning(error)

    elif price_button:
        st.warning(translate_text(language_code, "pricer.paste_items_warning"))


if __name__ == "__main__":
    main()
