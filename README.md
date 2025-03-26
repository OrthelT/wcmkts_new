# Winter Coalition Market Stats Viewer (v.02)

A Streamlit application for viewing EVE Online market statistics for Winter Coalition. This tool provides real-time market data analysis, historical price tracking, and fitting information for various items in the EVE Online market.

##UPDATES: 
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