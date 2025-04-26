# Winter Coalition Market Stats Viewer - User Guide

## Introduction
The Winter Coalition Market Stats Viewer is a Streamlit application that provides near real-time market data analysis for EVE Online items, specifically for the Winter Coalition. This tool helps monitor market conditions, track prices, analyze inventory levels, and manage doctrine ship fittings.

## Installation and Setup

### System Requirements
- Python 3.8 or higher
- Internet connection for syncing with remote database
- Turso database credentials (for production environments)

### Installation Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/wc_mkts_streamlit.git
   cd wc_mkts_streamlit
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   Create a `.env` file with the following:
   ```
   TURSO_DATABASE_URL=your_turso_database_url
   TURSO_AUTH_TOKEN=your_turso_auth_token
   SDE_URL=your_sde_url
   SDE_AUTH_TOKEN=your_sde_auth_token
   ```

4. Run the application:
   ```bash
   streamlit run app.py
   ```

## Pages and Features

### 1. Market Stats Page
![Market Stats](images/wclogo.png)

**Purpose:** Provides detailed market information for EVE Online items.

**Key Features:**
- **Item Selection:** Filter by category and specific items using the sidebar filters
- **Market Metrics:** View minimum sell prices, current stock levels, and days of inventory
- **Price Distribution Chart:** Visual representation of market orders by price
- **Price History Chart:** Track price and volume trends over time
- **Fitting Information:** For ship items, see compatible doctrine fits

**How to Use:**
1. Use the sidebar filters to select a category and/or specific item
2. View the market metrics at the top of the page
3. Examine the price distribution chart to understand current market conditions
4. Check the price history chart for trends over the past 30 days
5. For ships, review doctrine fitting information

### 2. Low Stock Alert Page
**Purpose:** Identifies items that are running low on the market, helping prioritize restocking.

**Key Features:**
- **Days Remaining Filter:** Set maximum days of stock remaining to view
- **Doctrine Items Filter:** Focus only on items used in doctrine fits
- **Category Filter:** Filter by item category
- **Critical Item Highlights:** Color-coded to emphasize urgency (red for critical, orange for low)
- **Visual Chart:** Bar chart showing days remaining by item

**How to Use:**
1. Adjust the "Maximum Days Remaining" slider to focus on items below a certain threshold
2. Check "Show Doctrine Items Only" to focus on important doctrine components
3. Select categories to narrow the results
4. Examine the metrics showing critical items (≤3 days) and low stock items (3-7 days)
5. Review the detailed table showing inventory levels and forecasted days remaining
6. Check the "Used In Fits" column to see which doctrine ships use a particular item

### 3. Doctrine Status Page
**Purpose:** Monitors the availability of doctrine ship fits and their components.

**Key Features:**
- **Doctrine Groups:** Ships organized by group (e.g., Battlecruisers, Frigates)
- **Status Indicators:** Color-coded badges (green for Good, orange for Needs Attention, red for Critical)
- **Progress Bars:** Visual representation of availability against targets
- **Low Stock Module Tracking:** Identifies modules that are limiting available fits
- **Export Features:** Create shopping lists in CSV format or copy to clipboard
- **Advanced Filtering:** Filter by ship status, ship group, and module stock levels
- **Bulk Selection:** Options to select/deselect all ships or modules

**How to Use:**
1. Use the sidebar filters to focus on specific doctrine statuses, ship groups, or module stock levels
2. Browse ships by doctrine group
3. Check the progress bars to see how current stock compares to target levels
4. Examine low stock modules highlighted in red (critical) or orange (low)
5. Select ships and modules by clicking the checkboxes
6. Use the "Select All Ships/Modules" buttons to quickly select multiple items
7. Export your selections as CSV using the "Download CSV" button
8. Copy selections to clipboard using the "Copy to Clipboard" button

## Database Synchronization

The application automatically syncs with the remote EVE Online market database daily at 13:00 UTC. You can also trigger a manual sync using the "Sync Now" button in the sidebar.

**Sync Status Indicators:**
- Last ESI Update: Shows when market data was last updated from ESI
- Last Sync: Shows when the local database was last synchronized with the remote database
- Next Scheduled Sync: Shows when the next automatic sync will occur
- Status: Indicates success or failure of the most recent sync

## Tips and Best Practices

### For Market Analysis
- Check the "Days Remaining" metric to identify items that need immediate attention
- Use the price history chart to identify trends and price fluctuations
- Compare market stock with "Fits on Market" to understand if stock levels are adequate

### For Doctrine Management
- Focus on ships marked as "Critical" on the Doctrine Status page
- Pay attention to the "Low Stock Modules" section to identify bottlenecks
- Use the export feature to create shopping lists for restocking

### Performance Tips
- The application caches data for 60 seconds to improve performance
- Database syncs are scheduled to minimize disruption
- Large data queries are processed in batches to prevent timeouts

## Troubleshooting

**Sync Fails:**
- Check your internet connection
- Verify Turso credentials are correct in your environment variables
- Check the logs directory for detailed error messages

**No Data Appears:**
- Confirm the database has been synced at least once
- Check filters to ensure they're not too restrictive
- Verify that the selected items exist in the market database

**Slow Performance:**
- Large datasets may take longer to process
- Consider using more specific filters
- Wait for the initial data load to complete before changing filters

## Support and Feedback

For issues or feature requests, please contact the maintainer:
- Email: orthel.toralen@gmail.com
- Discord: orthel_toralen
