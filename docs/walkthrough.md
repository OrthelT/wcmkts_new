# Winter Coalition Market Stats Viewer - Task Walkthroughs

This guide provides step-by-step instructions for common tasks in the Winter Coalition Market Stats Viewer.

## Task 1: Checking Price History for a Specific Ship

1. Navigate to the **Market Stats** page (📈Market Stats)
2. In the sidebar, select the "Ship" category from the dropdown
3. In the "Select Item" dropdown, choose your ship of interest (e.g., "Hurricane")
4. View the price metrics at the top of the page
5. Scroll down to see the "Price History" chart
6. Examine the dual chart showing price (top) and volume (bottom)
7. Look at the "Average Price (30 days)" and "Average Volume (30 days)" metrics below the chart

## Task 2: Finding Items That Need Restocking

1. Navigate to the **Low Stock** page (⚠️Low Stock)
2. Use the "Maximum Days Remaining" slider to set your threshold (e.g., 5 days)
3. Check "Show Doctrine Items Only" if you only want to see doctrine components
4. Select relevant categories in the "Category Filter" if needed
5. Review the table, focusing on items with red highlighting (critical - ≤3 days)
6. Look at the "Used In Fits" column to understand which ships use each item
7. Use the bar chart at the bottom to visualize which items are most critical

## Task 3: Creating a Shopping List for Restocking

1. Navigate to the **Doctrine Status** page (⚔️Doctrine Status)
2. Use the filters in the sidebar to focus on critical ships or specific groups:
   - Select "Critical" from "Doctrine Status" dropdown
   - Choose a specific "Ship Group" if needed
   - Select "Critical (< 20%)" from "Module Status" to focus on urgent needs
3. Select ships to restock by clicking the checkboxes next to ship names
4. Select modules to restock by clicking the checkboxes next to module names
5. Use the "Select All Ships" or "Select All Modules" buttons for bulk selection
6. Review your selections in the sidebar under "Selected Ships" and "Selected Modules"
7. Click "Download CSV" to save a shopping list for importing to other tools
8. Alternatively, click "Copy to Clipboard" to copy the list for sharing

## Task 4: Analyzing a Doctrine's Current Status

1. Navigate to the **Doctrine Status** page (⚔️Doctrine Status)
2. Browse through the ship groups to find your doctrine of interest
3. For each ship, check:
   - Status badge (Green = Good, Orange = Needs Attention, Red = Critical)
   - Fits and Hulls metrics (showing available quantity and delta from target)
   - Target value (number of ships required by doctrine)
   - Progress bar (percentage of target currently available)
4. Look at the "Low Stock Modules" section to identify bottlenecks
   - Red items are critical (< 20% of target)
   - Orange items are low (< 100% of target)
5. Take note of which modules are limiting the number of complete fits

## Task 5: Checking Market Availability for a Module

1. Navigate to the **Market Stats** page (📈Market Stats)
2. In the sidebar, select the relevant category for your module
3. In the "Select Item" dropdown, choose your module of interest
4. View the metrics at the top of the page:
   - Sell Price: Current minimum price
   - Market Stock: Total volume available
   - Days Remaining: Estimated time until depletion
5. Scroll down to see the detailed market orders in the table
6. Check the "Doctrine" section to see which ships use this module
7. Examine the price distribution chart to understand price stratification
8. Review the price history to identify trends and volatility

## Task 6: Syncing the Database

1. Look at the sidebar section showing "Database Sync Status"
2. Check the "Last sync" timestamp to see when data was last updated
3. Note the "Next scheduled sync" to know when data will update automatically
4. If you need the latest data immediately, click the "Sync Now" button
5. Wait for the sync to complete (indicated by "Status: Success" in green)
6. The page will automatically refresh with the latest data
7. If the sync fails, check the error message for troubleshooting

## Task 7: Filtering Market Data by Category

1. Navigate to the **Market Stats** page (📈Market Stats)
2. In the sidebar, uncheck "Show All Data" if it's checked
3. Select a category of interest from the "Select Category" dropdown
4. The page will update to show only items in that category
5. You can further refine by selecting a specific item
6. The table below will show all sell orders for items in your selected category
7. To reset filters, select "All Categories" from the dropdown