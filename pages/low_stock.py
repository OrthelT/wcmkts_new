import streamlit as st
import pandas as pd
import plotly.express as px
from io import StringIO
from db_handler import get_update_time, read_df
from logging_config import setup_logging
from config import DatabaseConfig
# Insert centralized logging configuration
logger = setup_logging(__name__)

# Import from the root directory

mktdb = DatabaseConfig("wcmkt")
sde_db = DatabaseConfig("sde")

@st.cache_data(ttl=600)
def get_filter_options(selected_categories=None):
    try:
        # Get data from marketstats table
        query = """
        SELECT DISTINCT type_id, type_name, category_id, category_name, group_id, group_name
        FROM marketstats
        """

        df = read_df(mktdb, query)
        df = df.rename(columns={
            # Ensure expected column names if the database returns different casing
            'typeID': 'type_id', 'typeName': 'type_name',
            'categoryID': 'category_id', 'categoryName': 'category_name',
            'groupID': 'group_id', 'groupName': 'group_name'
        })

        if df.empty:
            return [], []

        categories = sorted(df['category_name'].unique())

        if selected_categories:
            df = df[df['category_name'].isin(selected_categories)]

        items = sorted(df['type_name'].unique())
        logger.info(f"items: {len(items)} categories: {len(categories)}")

        return categories, items


    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return [], []

@st.cache_data(ttl=600)
def get_market_stats(selected_categories=None, selected_items=None, max_days_remaining=None, doctrine_only=False, tech2_only=False):

    if tech2_only:
        tech2_query = """
        SELECT typeID FROM sdetypes WHERE metaGroupID = 2
        """
        tech2_type_ids = read_df(sde_db, tech2_query)['typeID'].tolist()

    # Start with base query for marketstats
    query = """
    SELECT ms.*,
           CASE WHEN d.type_id IS NOT NULL THEN 1 ELSE 0 END as is_doctrine,
           d.ship_name,
           d.fits_on_mkt
    FROM marketstats ms
    LEFT JOIN doctrines d ON ms.type_id = d.type_id
    """

    # Get market stats data
    df = read_df(mktdb, query)

    # Apply filters
    if selected_categories:
        df = df[df['category_name'].isin(selected_categories)]

    if selected_items:
        df = df[df['type_name'].isin(selected_items)]

    if doctrine_only:
        df = df[df['is_doctrine'] == 1]

    # Apply days_remaining filter
    if max_days_remaining is not None:
        df = df[df['days_remaining'] <= max_days_remaining]

    # Group by item and aggregate ship information
    if not df.empty:
        # Create a list of ships for each item
        ship_groups = df.groupby('type_id', group_keys=False).apply(
            lambda x: [f"{row['ship_name']} ({int(row['fits_on_mkt'])})"
                      for _, row in x.iterrows()
                      if pd.notna(row['ship_name']) and pd.notna(row['fits_on_mkt'])], include_groups = False
        ).to_dict()

        # Keep only one row per item
        df = df.drop_duplicates(subset=['type_id'])

        # Add the ships column
        df['ships'] = df['type_id'].map(ship_groups)

    if tech2_only:
        df = df[df['type_id'].isin(tech2_type_ids)]

    return df

def create_days_remaining_chart(df):
    # Create bar chart for days remaining
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

    # Update layout for better readability
    fig.update_layout(
        xaxis_title="Item",
        yaxis_title="Days Remaining",
        xaxis={'tickangle': 45},
        height=500
    )

    # Add a horizontal line at days_remaining = 3
    fig.add_hline(y=3, line_dash="dash", line_color="red", annotation_text="Critical Level (3 days)")

    return fig


def main():
    # Title
    col1, col2 = st.columns([0.2, 0.8], vertical_alignment="bottom")
    with col1:
        wclogo = "images/wclogo.png"
        st.image(wclogo, width=125)
    with col2:
        st.title("Low Stock Tool")
    
    st.markdown("""
    This page shows items that are running low on the market. The **Days Remaining** column shows how many days of sales
    can be sustained by the current stock based on historical average sales. Items with fewer days remaining need attention. The **Used In Fits** column shows the doctrine ships that use the item (if any) and the number of fits that the current market stock of the item can support.
    """)

    # Sidebar filters
    st.sidebar.header("Filters")
    st.sidebar.markdown("Use the filters below to customize your view of low stock items.")

    # Doctrine items filter
    doctrine_only = st.sidebar.checkbox("Show Doctrine Items Only", value=False, help="Show only items that are used in a doctrine fit, the fits used are shown in the 'Used In Fits' column")
    tech2_only = st.sidebar.checkbox("Show Tech 2 Items Only", value=False, help="Show only items that are in the Tech 2 group")

    # Get initial categories
    categories, _ = get_filter_options()


    st.sidebar.subheader("Category Filter")
    st.sidebar.multiselect(
        "Select Categories",
        options=categories,
        key="multiselect_categories",
        help="Select one or more categories to filter the data"
    )

    if st.session_state.get('multiselect_categories'):
        selected_categories = st.session_state.multiselect_categories
    else:
        selected_categories = []

    # Days remaining filter
    st.sidebar.subheader("Days Remaining Filter")
    max_days_remaining = st.sidebar.slider(
        "Maximum Days Remaining",
        min_value=0.0,
        max_value=30.0,
        value=7.0,
        step=0.5,
        help="Show only items with days remaining less than or equal to this value"
    )

    # Get filtered data
    df = get_market_stats(selected_categories, None, max_days_remaining, doctrine_only, tech2_only)

    if not df.empty:
        # Sort by days_remaining (ascending) to show most critical items first
        df = df.sort_values('days_remaining')

        # Display metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            critical_items = len(df[df['days_remaining'] <= 3])
            st.metric("Critical Items (≤3 days)", critical_items)
        with col2:
            low_items = len(df[(df['days_remaining'] > 3) & (df['days_remaining'] <= 7)])
            st.metric("Low Stock Items (3-7 days)", low_items)
        with col3:
            total_items = len(df)
            st.metric("Total Filtered Items", total_items)

        st.divider()

        # Format the DataFrame for display
        display_df = df.copy()
        display_df = display_df.drop(columns=['min_price', 'avg_price', 'category_id', 'group_id'])

        # Select and rename columns - add checkbox column
        columns_to_show = ['select', 'type_id', 'type_name', 'price', 'days_remaining', 'total_volume_remain', 'avg_volume', 'category_name', 'group_name', 'ships']

        # Initialize checkbox column with False
        display_df['select'] = False
        display_df = display_df[columns_to_show]


        numeric_formats = {
            'select': st.column_config.CheckboxColumn('Select', help='Check items you want to include in the CSV download', default=False, width='small'),
            'type_id': st.column_config.NumberColumn('Type ID', help='type ID of the item', width='small'),
            'type_name': st.column_config.TextColumn('Item', help='name of the item', width='medium'),
            'total_volume_remain': st.column_config.NumberColumn('Volume Remaining',  format='localized', help='total items currently available on the market', width='small'),
            'price': st.column_config.NumberColumn('Price', format='localized', help='lowest 5-percentile price of current sell orders, or if no sell orders, the historical average price'),
            'days_remaining': st.column_config.NumberColumn('Days', format='localized', help='days of stock remaining based on historical average sales for the last 30 days', width='small'),
            'avg_volume': st.column_config.NumberColumn('Avg Vol', format='localized', help='average volume over the last 30 days', width='small'),
            'ships': st.column_config.ListColumn('Used In Fits', help='number of fits available on the market', width='large'),
            'category_name': st.column_config.TextColumn('Category', help='category of the item'),
            'group_name': st.column_config.TextColumn('Group', help='group of the item'),
        }

        # manual column config replaced with st.column_config

        # Rename columns
        # column_renames = {
        #     'type_name': 'Item',
        #     'group_name': 'Group',
        # }
        # display_df = display_df.rename(columns=column_renames)

        # Reorder columns
        # column_order = ['Item', 'days_remaining', 'price', 'total_volume_remain', 'avg_volume', 'Used In Fits', 'Category', 'Group']
        # display_df = display_df[column_order]

        # Add a color indicator for critical items
        def highlight_critical(val):
            try:
                val = float(val)
                if val <= 3:
                    return 'background-color: #fc4103'  # Light red for critical
                elif val <= 7:
                    return 'background-color: #c76d14'  # Light yellow for low
                else:
                    return ''
            except Exception:
                return ''

        # Add a color indicator for doctrine items
        def highlight_doctrine(row):
            # Check if the "Used In Fits" column has data
            try:
                # Check if the value is not empty and not NaN
                if isinstance(row['ships'], list) and len(row['ships']) > 0:
                    # Create a list of empty strings for all columns
                    styles = [''] * len(row)
                    # Apply highlighting only to the "Item" column (index 0)
                    styles[2] = 'background-color: #328fed'
                    return styles
            except Exception:
                pass
            return [''] * len(row)

        # Apply the styling - updated from applymap to map
        styled_df = display_df.style.map(highlight_critical, subset=['days_remaining'])

        # Add doctrine highlighting
        styled_df = styled_df.apply(highlight_doctrine, axis=1)

        # Display the dataframe with editable checkbox column
        st.subheader("Low Stock Items")
        edited_df = st.data_editor(
            styled_df,
            hide_index=True,
            column_config=numeric_formats,
            disabled=[col for col in display_df.columns if col != 'select'],
            key='low_stock_editor'
        )

        # Download CSV button
        selected_rows = edited_df[edited_df['select'] == True]
        if len(selected_rows) > 0:
            # Prepare CSV data - remove the select column
            csv_df = selected_rows.drop(columns=['select'])

            # Convert to CSV
            csv_buffer = StringIO()
            csv_df.to_csv(csv_buffer, index=False)
            csv_data = csv_buffer.getvalue()

            st.download_button(
                label=f"Download {len(selected_rows)} selected items as CSV",
                data=csv_data,
                file_name="low_stock_items.csv",
                mime="text/csv",
                use_container_width=True
            )

        # Display charts
        st.subheader("Days Remaining by Item")
        days_chart = create_days_remaining_chart(df)
        st.plotly_chart(days_chart)

    else:
        st.warning("No items found with the selected filters.")

    # Display last update timestamp
    st.sidebar.markdown("---")
    st.sidebar.write(f"Last ESI update: {get_update_time()}")

if __name__ == "__main__":
    main()
