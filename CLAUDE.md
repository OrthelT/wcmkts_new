# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview
Winter Coalition Market Stats Viewer is a Streamlit web application for EVE Online market analysis. It provides real-time market data visualization, doctrine analysis, and inventory management tools for the Winter Coalition.

## Development Commands

### Installation and Setup
```bash
# Install dependencies using uv (preferred package manager)
uv sync

# Alternative: install via pip if uv is not available
pip install -e .
```

### Running the Application
```bash
# Start the Streamlit application
streamlit run app.py

# Development mode with file watching
streamlit run app.py --server.runOnSave true
```

### Database Operations
```bash
# Test database sync functionality
python3 -c "
import sys
sys.path.append('.')
from db_utils import sync_db
sync_db()
"

# Check database connection and schema
python3 -c "
import sys
sys.path.append('.')
from db_handler import get_local_mkt_engine, get_local_sde_engine
print('Market DB:', get_local_mkt_engine())
print('SDE DB:', get_local_sde_engine())
"
```

## Architecture Overview

### Application Structure
- **app.py**: Main Streamlit application entry point with page routing
- **pages/**: Individual page modules for different features
  - `market_stats.py`: Market data visualization and analysis
  - `doctrine_status.py`: Doctrine component tracking
  - `doctrine_report.py`: Doctrine analysis reports
  - `low_stock.py`: Low inventory alerting
  - `build_costs.py`: Manufacturing cost analysis

### Database Layer
- **db_handler.py**: Database connection management and engine creation
- **db_utils.py**: Database synchronization with Turso cloud database
- **models.py**: SQLAlchemy ORM models for database tables
- **build_cost_models.py**: Models specific to manufacturing cost analysis

### Data Management
- **sync_scheduler.py**: Handles automatic database synchronization scheduling
- **Local Databases**:
  - `wcmkt.db`: Market orders and statistics (synced from Turso)
  - `sde.db`: EVE Online Static Data Export
  - `build_cost.db`: Manufacturing and structure data

### Configuration and Utilities
- **config.toml**: Streamlit theme configuration
- **logging_config.py**: Centralized logging setup
- **last_sync_state.json**: Tracks database sync status and scheduling

## Database Architecture

### Turso Embedded Replica Pattern
The application uses Turso's embedded-replica feature for optimal performance:
- Local SQLite databases provide fast reads
- Automatic synchronization with remote Turso database
- Background sync occurs every 3 hours or on manual trigger

### Key Database Tables
**Market Database (wcmkt.db):**
- `marketorders`: Individual buy/sell orders
- `marketstats`: Aggregated market statistics
- `market_history`: Historical price/volume data
- `doctrines`: Fleet doctrine configurations
- `ship_targets`: Target inventory levels

**SDE Database (sde.db):**
- `invTypes`: EVE Online item definitions
- `invGroups`: Item group classifications
- `invCategories`: High-level item categories

## Environment Setup

### Required Secrets (Streamlit Cloud)
```toml
[secrets]
TURSO_DATABASE_URL = "your_turso_database_url"
TURSO_AUTH_TOKEN = "your_turso_auth_token"
SDE_URL = "your_sde_database_url"  
SDE_AUTH_TOKEN = "your_sde_auth_token"
```

### Local Development
- Create `.streamlit/secrets.toml` with the above configuration
- Ensure local database files exist: `wcmkt.db`, `sde.db`, `build_cost.db`
- The application will use local SQLite files if sync credentials are not available

## Development Guidelines

### Adding New Pages
1. Create new page file in `pages/` directory
2. Follow existing naming pattern with emoji prefix
3. Add page registration in `app.py` pages dictionary
4. Import required database engines from `db_handler.py`
5. Use centralized logging from `logging_config.py`

### Database Operations
- Always use SQLAlchemy engines from `db_handler.py`
- Use context managers for database sessions
- Implement proper error handling and logging
- Clear Streamlit cache after database modifications

### Performance Considerations
- Use `@st.cache_data` for expensive computations (TTL: 15 minutes)
- Use `@st.cache_resource` for database connections
- Clear caches during database sync operations
- Implement proper connection pooling

### Data Synchronization
- Manual sync available via sidebar button
- Automatic sync scheduled for 13:00 UTC daily
- Sync status tracked in `last_sync_state.json`
- Use `db_utils.sync_db()` for programmatic sync operations

## Troubleshooting

### Database Connection Issues
- Verify local database files exist and are readable
- Check Turso credentials in secrets configuration
- Review sync logs in application logs

### Performance Issues
- Clear Streamlit cache: `st.cache_data.clear()`
- Check database sync status
- Monitor memory usage during large data operations

### Data Quality Issues
- Verify last sync timestamp
- Check for missing or corrupted local database files
- Review market data freshness in `marketstats` table