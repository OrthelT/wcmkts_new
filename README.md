# Winter Coalition Market Stats Viewer (v.0.42)

A Streamlit application for viewing EVE Online market statistics for Winter Coalition. This tool provides real-time market data analysis, historical price tracking, and fitting information for various items in the EVE Online market.

SUPPORT: Join my Discord for support https://discord.gg/87Tb7YP5
CONTRIBUTING: Contributors welcome. This project is fully open source under MIT License. Source code and full documentation available on GitHub: https://github.com/OrthelT/wcmkts_new

## UPDATES: 
*version 0.51(beta)*
- added delectable target multiplier to "Doctrine Report" page.
*version 0.5(beta)*
- implemented "Doctrine Report" page providing a view of market status by doctrine. 
*version 0.42*
- added display of buy orders on market stats page. 
*version 0.41*
- simplified sync scheduling with periodic syncs every three hours. 

*version 0.4*
- Enhanced doctrine status page with:
  - Advanced filtering (ship status, ship group, module stock levels)
  - Item selection via checkboxes
  - Bulk selection/deselection options
  - CSV export functionality for shopping lists
  - Copy to clipboard feature
- Caching and other performance improvements

*version 0.3*
- added low stock analysis
- added additional filtering and export functionality to doctrine status tool

*version 0.2*
- added fitting information features
- added doctrine metrics
- improved history chart behavior

## Features

- **Market Data Visualization**
  - Real-time market order distribution
  - Price and volume history charts
  - Interactive data filtering by category and item type

- **Market Metrics**
  - Minimum sell prices
  - Current market stock levels
  - Days of inventory remaining
  - Number of fits available on market

- **Historical Analysis**
  - 30-day average prices
  - 30-day average volumes
  - Detailed price history charts
  - Volume tracking over time

- **Fitting Information**
  - Doctrine fit details
  - Market availability of fit components
  - Last update timestamps
  - Advanced filtering by status, group, and stock levels 
  - Export functionality for modules and ships

## Data Updates

The app uses Turso's embedded-replica feature to allow a local SQLlite-libsql database that allows extremely fast data fetches. The application automatically syncs with EVE Online market stored on the parent database daily at 13:00 UTC. Users can also trigger manual updates using the sync button in the sidebar to obtain new data, if it is available. 

## Setup

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
Create a `.env` file with the following variables:
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

## Usage

1. **Filtering Data**
   - Use the sidebar filters to select specific categories or items
   - Toggle "Show All Data" to view all market orders

2. **Viewing Market Data**
   - Select an item to view detailed market information
   - View price distribution charts
   - Check historical price and volume data

3. **Analyzing Fits**
   - Select a specific item to view available fits
   - Check market availability of fit components

## Database Structure

The application uses two databases:
- Market Database: Contains current market orders and historical data
- SDE Database: Contains EVE Online static data (items, categories, etc.)

## Maintenance

The application is maintained by Orthel Toralen (orthel.toralen@gmail.com). For issues or feature requests, please contact the maintainer on Discord at orthel_toralen or create an issue in the repository.

## License

This project is provided under the MIT public license.
