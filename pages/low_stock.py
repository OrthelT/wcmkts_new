"""
Low Stock Page

Displays items that are running low on the 4-HWWF market with filtering
options for categories, doctrines, fits, and item meta types.

Uses LowStockService for all data operations.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from repositories import get_update_time
from logging_config import setup_logging
from services import get_low_stock_service, LowStockFilters
from ui.formatters import get_image_url
from state import ss_init, ss_get

logger = setup_logging(__name__, log_file="low_stock.log")

# Initialize service (cached in session state)
service = get_low_stock_service()


def create_days_remaining_chart(df: pd.DataFrame):
    """Create a bar chart showing days of stock remaining."""
    if df.empty:
        return None

    fig = px.bar(
        df,
        x='type_name',
        y='days_remaining',
        title='Days of Stock Remaining',
        labels={
            'days_remaining': 'Days Remaining',
            'type_name': 'Item'
        },
        color='category_name',
        color_discrete_sequence=px.colors.qualitative.Set3
    )

    fig.update_layout(
        xaxis_title="Item",
        yaxis_title="Days Remaining",
        xaxis={'tickangle': 45},
        height=500
    )

    # Add a horizontal line at critical level
    fig.add_hline(
        y=3,
        line_dash="dash",
        line_color="red",
        annotation_text="Critical Level (3 days)"
    )

    return fig


def highlight_critical(val):
    """Style function for critical days remaining values."""
    try:
        val = float(val)
        if val <= 3:
            return 'background-color: #fc4103'  # Red for critical
        elif val <= 7:
            return 'background-color: #c76d14'  # Orange for low
        return ''
    except Exception:
        return ''


def highlight_doctrine(row):
    """Style function to highlight doctrine items."""
    try:
        if isinstance(row.get('ships'), list) and len(row['ships']) > 0:
            styles = [''] * len(row)
            # Highlight the type_name column
            if 'type_name' in row.index:
                idx = row.index.get_loc('type_name')
                styles[idx] = 'background-color: #328fed'
            return styles
    except Exception:
        pass
    return [''] * len(row)


def main():
    # Initialize session state
    ss_init({
        'ls_selected_categories': [],
        'ls_selected_doctrine': None,
        'ls_selected_fit': None,
        'ls_doctrine_only': False,
        'ls_tech2_only': False,
        'ls_faction_only': False,
        'ls_max_days': 7.0,
    })

    # Title and logo
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        st.image("images/wclogo.png", width=125)
    with col2:
        st.title("4-HWWF Low Stock Tool")

    st.markdown("""
    This page shows items that are running low on the market. The **Days Remaining** column shows how many days of sales
    can be sustained by the current stock based on historical average sales. Items with fewer days remaining need attention.
    The **Used In Fits** column shows the doctrine ships that use the item (if any) and the number of fits that the current
    market stock of the item can support.
    """)

    # Sidebar filters
    st.sidebar.header("Filters")
    st.sidebar.markdown("Use the filters below to customize your view of low stock items.")

    # Item type filters
    st.sidebar.subheader("Item Type Filters")

    doctrine_only = st.sidebar.checkbox(
        "Doctrine Items Only",
        value=ss_get('ls_doctrine_only', False),
        help="Show only items that are used in a doctrine fit"
    )
    st.session_state.ls_doctrine_only = doctrine_only

    tech2_only = st.sidebar.checkbox(
        "Tech II Items Only",
        value=ss_get('ls_tech2_only', False),
        help="Show only Tech II items (metaGroupID=2)"
    )
    st.session_state.ls_tech2_only = tech2_only

    faction_only = st.sidebar.checkbox(
        "Faction Items Only",
        value=ss_get('ls_faction_only', False),
        help="Show only Faction items (metaGroupID=4)"
    )
    st.session_state.ls_faction_only = faction_only

    # Category filter
    st.sidebar.subheader("Category Filter")
    categories = service.get_category_options()

    selected_categories = st.sidebar.multiselect(
        "Select Categories",
        options=categories,
        default=ss_get('ls_selected_categories', []),
        help="Select one or more categories to filter the data"
    )
    st.session_state.ls_selected_categories = selected_categories

    # Doctrine/Fit filter section
    st.sidebar.subheader("Doctrine/Fit Filter")

    # Get doctrine options
    doctrine_options = service.get_doctrine_options()
    doctrine_names = ["All"] + [d.doctrine_name for d in doctrine_options]

    selected_doctrine_name = st.sidebar.selectbox(
        "Select Doctrine",
        options=doctrine_names,
        index=0,
        help="Filter to show only items from a specific doctrine"
    )

    selected_doctrine = None
    selected_fit = None
    fit_ids = []

    if selected_doctrine_name != "All":
        # Find the doctrine info
        selected_doctrine = next(
            (d for d in doctrine_options if d.doctrine_name == selected_doctrine_name),
            None
        )

        if selected_doctrine:
            # Display doctrine image
            if selected_doctrine.lead_ship_id:
                st.sidebar.image(
                    selected_doctrine.lead_ship_image_url,
                    width=128,
                    caption=selected_doctrine_name
                )

            # Get fit options for this doctrine
            fit_options = service.get_fit_options(selected_doctrine.doctrine_id)
            fit_names = ["All Fits"] + [f.ship_name for f in fit_options]

            selected_fit_name = st.sidebar.selectbox(
                "Select Fit",
                options=fit_names,
                index=0,
                help="Filter to show only items from a specific fit"
            )

            if selected_fit_name != "All Fits":
                selected_fit = next(
                    (f for f in fit_options if f.ship_name == selected_fit_name),
                    None
                )
                if selected_fit:
                    fit_ids = [selected_fit.fit_id]
                    # Display fit ship image
                    st.sidebar.image(
                        selected_fit.ship_image_url,
                        width=128,
                        caption=f"{selected_fit.ship_name}\n{selected_fit.fit_name}"
                    )
            else:
                # All fits in this doctrine
                fit_ids = selected_doctrine.fit_ids

    # Days remaining filter
    st.sidebar.subheader("Days Remaining Filter")
    max_days_remaining = st.sidebar.slider(
        "Maximum Days Remaining",
        min_value=0.0,
        max_value=30.0,
        value=ss_get('ls_max_days', 7.0),
        step=0.5,
        help="Show only items with days remaining less than or equal to this value"
    )
    st.session_state.ls_max_days = max_days_remaining

    # Build filters
    filters = LowStockFilters(
        categories=selected_categories,
        max_days_remaining=max_days_remaining,
        doctrine_only=doctrine_only,
        tech2_only=tech2_only,
        faction_only=faction_only,
        fit_ids=fit_ids,
    )

    # Get filtered data using service
    df = service.get_low_stock_items(filters)

    if not df.empty:
        # Sort by days_remaining (ascending) to show most critical items first
        df = df.sort_values('days_remaining')

        # Get statistics
        stats = service.get_stock_statistics(df)

        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Critical Items (\u22643 days)", stats["critical"])
        with col2:
            st.metric("Low Stock Items (3-7 days)", stats["low"])
        with col3:
            st.metric("Total Filtered Items", stats["total"])

        st.divider()

        # Display header with selected filter info
        if selected_doctrine:
            header_col1, header_col2 = st.columns([0.15, 0.85])
            with header_col1:
                if selected_fit and selected_fit.ship_id:
                    st.image(get_image_url(selected_fit.ship_id, 64, isship=True), width=64)
                elif selected_doctrine.lead_ship_id:
                    st.image(get_image_url(selected_doctrine.lead_ship_id, 64, isship=True), width=64)
            with header_col2:
                if selected_fit:
                    st.subheader(f"Low Stock: {selected_fit.ship_name}")
                    st.caption(selected_fit.fit_name)
                else:
                    st.subheader(f"Low Stock: {selected_doctrine_name}")
        else:
            st.subheader("Low Stock Items")

        # Format the DataFrame for display
        display_df = df.copy()

        # Drop columns not needed for display
        columns_to_drop = ['min_price', 'avg_price', 'category_id', 'group_id', 'is_doctrine',
                          'ship_name', 'fits_on_mkt', 'last_update']
        display_df = display_df.drop(
            columns=[c for c in columns_to_drop if c in display_df.columns],
            errors='ignore'
        )

        # Prepare columns for display
        columns_to_show = [
            'select', 'type_id', 'type_name', 'price', 'days_remaining',
            'total_volume_remain', 'avg_volume', 'category_name', 'group_name', 'ships'
        ]

        # Initialize checkbox column
        display_df['select'] = False

        # Ensure all columns exist
        for col in columns_to_show:
            if col not in display_df.columns:
                display_df[col] = None

        display_df = display_df[columns_to_show]

        # Column configuration
        column_config = {
            'select': st.column_config.CheckboxColumn(
                'Select',
                help='Check items you want to include in the CSV download',
                default=False,
                width='small'
            ),
            'type_id': st.column_config.NumberColumn(
                'Type ID',
                help='Type ID of the item',
                width='small'
            ),
            'type_name': st.column_config.TextColumn(
                'Item',
                help='Name of the item',
                width='medium'
            ),
            'total_volume_remain': st.column_config.NumberColumn(
                'Volume Remaining',
                format='localized',
                help='Total items currently available on the market',
                width='small'
            ),
            'price': st.column_config.NumberColumn(
                'Price',
                format='localized',
                help='Lowest 5-percentile price of current sell orders'
            ),
            'days_remaining': st.column_config.NumberColumn(
                'Days',
                format='localized',
                help='Days of stock remaining based on historical average sales',
                width='small'
            ),
            'avg_volume': st.column_config.NumberColumn(
                'Avg Vol',
                format='localized',
                help='Average volume over the last 30 days',
                width='small'
            ),
            'ships': st.column_config.ListColumn(
                'Used In Fits',
                help='Doctrine ships that use this item',
                width='large'
            ),
            'category_name': st.column_config.TextColumn(
                'Category',
                help='Category of the item'
            ),
            'group_name': st.column_config.TextColumn(
                'Group',
                help='Group of the item'
            ),
        }

        # Apply styling
        styled_df = display_df.style.map(highlight_critical, subset=['days_remaining'])
        styled_df = styled_df.apply(highlight_doctrine, axis=1)

        # Display the dataframe with editable checkbox column
        edited_df = st.data_editor(
            styled_df,
            hide_index=True,
            column_config=column_config,
            disabled=[col for col in display_df.columns if col != 'select'],
            key='low_stock_editor'
        )

        # Selected items info
        selected_rows = edited_df[edited_df['select'] == True]
        if len(selected_rows) > 0:
            st.info(f"{len(selected_rows)} items selected. Visit the **Downloads** page for bulk CSV exports.")

        # Display chart
        st.subheader("Days Remaining by Item")
        days_chart = create_days_remaining_chart(df)
        if days_chart:
            st.plotly_chart(days_chart)

    else:
        st.warning("No items found with the selected filters.")

    # Display last update timestamp
    st.sidebar.markdown("---")
    st.sidebar.write(f"Last ESI update: {get_update_time()}")


if __name__ == "__main__":
    main()
