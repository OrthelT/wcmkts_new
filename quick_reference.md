# Winter Coalition Market Stats Viewer - Quick Reference

## Getting Started
1. Run the application: `streamlit run app.py`
2. Navigate with the sidebar menu: Market Stats, Low Stock, or Doctrine Status
3. Data updates automatically at 13:00 UTC daily or use "Sync Now" button

## Market Stats Page 📈
**Purpose:** View detailed market data for specific items

**Key Controls:**
- **Category Filter:** Select a market category
- **Item Filter:** Select a specific item to analyze
- **Show All Data:** Toggle to view all market data

**What You'll See:**
- Sell price, stock levels, and days remaining metrics
- Price distribution chart
- 30-day price and volume history
- Fitting information (for ships)

## Low Stock Alert Page ⚠️
**Purpose:** Identify items that need restocking

**Key Controls:**
- **Maximum Days Remaining:** Slider to set threshold (default: 7 days)
- **Doctrine Items Only:** Toggle to focus on doctrine components
- **Category Filter:** Narrow down by item category

**What You'll See:**
- Critical items (≤3 days) count
- Low stock items (3-7 days) count
- Color-coded table (red = critical, orange = low)
- Days remaining chart
- "Used In Fits" column showing which ships use the item

## Doctrine Status Page ⚔️
**Purpose:** Monitor doctrine ship availability and component status

**Key Controls:**
- **Doctrine Status:** Filter by status (All, Critical, Needs Attention, Good)
- **Ship Group:** Filter by ship category
- **Module Status:** Filter by component availability

**What You'll See:**
- Ships grouped by type
- Status badges (green = Good, orange = Needs Attention, red = Critical)
- Progress bars showing availability vs. target
- Low stock modules highlighted by urgency
- Selection checkboxes for creating shopping lists

**Export Features:**
- Select ships/modules using checkboxes
- "Select All" buttons for quick selection
- "Download CSV" for shopping lists
- "Copy to Clipboard" for sharing

## Market Metrics Explained
- **Sell Price:** Minimum sell price on the market
- **Market Stock:** Total volume available
- **Days Remaining:** Estimated days until stock depletes (based on historical volume)
- **Fits on Market:** Number of complete doctrine fits possible with current stock

## Data Updates
- Automatic sync daily at 13:00 UTC
- Manual sync available via "Sync Now" button
- Last update time shown in sidebar