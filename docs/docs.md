# Winter Coalition Market Stats Viewer - User Guide

## Introduction
The Winter Coalition Market Stats Viewer is a Streamlit application that provides near real-time market data analysis for EVE Online items, specifically for the Winter Coalition. This tool helps monitor market conditions, track prices, analyze inventory levels, and monitor markey availability of doctrine ship fittings. For Chrome users, you can run it on your local machine as a standalone app by clicking on the install stramlet icon. 

**App## URL: https://wcmkts.streamlit.app/

**Support:** This app was developed by Orthel Toralen, who only vaguely knows what he's doing. For support, or to report bugs, please visit my development Discord, OrthelsLab: https://discord.gg/87Tb7YP5 

**How to Contribute:** WCMkts is an open source project written in Python 3.12 and provided under the MIT License. The source code is available on GitHub at https://github.com/OrthelT/wcmkts_new Contributions to this project are very welcome. 

**NOTE:** Note, this app was designed to be used in dark mode. Use the "hamburger" menu in the upper right-hand corner to select Settings -> "Choose app theme, colors and fonts" -> "dark."

**Update Frequency:** While not fully real time, data is refreshed every few hours, with full market history updated each day around 1300 Eve time. This allows for very fast performance, because we handle calls to the Eve ESI and data processing elsewhere. The app uses just a local sqlite database that syncs periodically with a remote master database to generate data displays. Hit the "Sync Now" button on the market stats page to update the app with the most recent data.  

# Pages and Features

### 1. Market Stats Page
![Market Stats](images/wclogo.png)

**Purpose:** Provides detailed market information for current sell orders on the 4-HWWF market. Includes history data for over 800 commonly used items and ships, with more detailed data available for Winter Co. doctrine items.

The central dataframe displays all currently selected items. Currently, only sell orders are displayed however buy orders could be added later if there is interest.

**Key Features:**
- **Item Selection:** Filter by category and specific items using the sidebar filters
- **Data Export:** All dataframes on the site can be downloaded as .csv files suitable for use in your own spreadsheets by clicking the download icon at the top of each table. By default it exports the current view. Select the Show All Data checkbox if you want to make sure you are getting everything in your download. 
- **Market Metrics:** View minimum sell prices, current stock levels, and days of inventory
- **Price Distribution Chart:** Visual representation of market orders by price
- **Price History Chart:** Track price and volume trends over time
- **Fitting Information:** For ships used in Winter Co. doctrines, see market information for items used in that fit. 

**How to Use:**
1. Use the sidebar filters to select a category and/or specific item
2. View the market metrics at the top of the page
3. Examine the price distribution chart to understand current market conditions
4. Check the price history chart for trends over the past 30 days
5. For ships, review doctrine fitting information

### 2. Low Stock Page
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

The application automatically syncs with the remote EVE Online market database daily at 13:00 UTC. You can also trigger a manual sync using the "Sync Now" button in the sidebar. If new data is available, it will update in the app. 

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
- This app was built with performance in mind. It uses Turso Cloud's embedded replica functionality to allow the performance of a locally embedded SQLite database in a production environment, using libSQL, an extremely performant fork of SQLite written in Rust. 
- The application caches data to improve performance
- Database syncs are scheduled to minimize disruption and general take just a couple seconds to complete
- Large data queries are processed in batches to prevent timeouts

## Troubleshooting

- If it is not working properly, it's probably because your humble developer managed to breaj something. Please feel free to send me a DM on Discord and I will try to address the issue. Discord: orthel_toralen

## Support and Feedback

For issues or feature requests, please contact the maintainer:
- Email: orthel.toralen@gmail.com
- Discord: orthel_toralen
