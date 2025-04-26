# Winter Coalition Market Stats Viewer - Administrator Guide

This guide is intended for administrators who need to maintain, configure, or deploy the Winter Coalition Market Stats Viewer application.

## System Architecture Overview

The application uses a hybrid database approach:
- **Local SQLite Databases**:
  - `wcmkt.db`: Contains market data synchronized from the parent Turso database
  - `sde.db`: Contains EVE Online Static Data Export (item information)
- **Turso Cloud Database**:
  - Remote database that collects and processes EVE Online market data
  - Local database syncs with remote using Turso's embedded-replica feature

## Database Schema

Key tables in the market database (`wcmkt.db`):
- `marketorders`: Individual sell and buy orders on the market
- `marketstats`: Aggregated statistics about market items
- `market_history`: Historical price and volume data
- `doctrines`: Doctrine fits and their components
- `ship_targets`: Target inventory levels for doctrine ships

Key tables in the SDE database (`sde.db`):
- `invTypes`: Information about all EVE Online items
- `invGroups`: Item groups classification
- `invCategories`: High-level item categories

## Configuration

### Environment Variables

Production environments should use Streamlit secrets management:
1. Create a `.streamlit/secrets.toml` file with:
   ```toml
   TURSO_DATABASE_URL = "your_turso_database_url"
   TURSO_AUTH_TOKEN = "your_turso_auth_token"
   SDE_URL = "your_sde_url"
   SDE_AUTH_TOKEN = "your_sde_auth_token"
   ```

Development environments can use a `.env` file as described in the README.

### Database Synchronization Settings

Database synchronization is configured in `db_handler.py` and `db_utils.py`:
- Automatic sync occurs daily at 13:00 UTC (configurable in `schedule_db_sync()`)
- Sync state is stored in `last_sync_state.json`
- Manual sync via sidebar button calls `sync_db()` function
- Cache TTL is set to 60 seconds in various functions

### Doctrine Targets Configuration

Target inventory levels for doctrine ships can be configured in two ways:
1. **Using the dictionary in `doctrines.py`**:
   - Modify the `SHIP_TARGETS` dictionary
   - Set default value for ships not explicitly listed

2. **Using the database table** (preferred for production):
   - Use `set_targets.py` functionality to update the `ship_targets` table
   - Each entry has `fit_id`, `ship_target`, and `fit_name` columns

## Deployment Options

### Local Deployment
1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables
4. Run with: `streamlit run app.py`

### Server Deployment
1. Set up a virtual environment: `python -m venv venv`
2. Activate and install dependencies
3. Configure environment variables or secrets
4. Use a process manager like Supervisor:
   ```
   [program:wc_mkts]
   command=/path/to/venv/bin/streamlit run app.py
   directory=/path/to/wc_mkts_streamlit
   autostart=true
   autorestart=true
   ```

### Docker Deployment
1. Create a Dockerfile:
   ```dockerfile
   FROM python:3.10-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install -r requirements.txt

   COPY . .

   EXPOSE 8501

   CMD ["streamlit", "run", "app.py"]
   ```
2. Build and run the container:
   ```bash
   docker build -t wc_mkts .
   docker run -p 8501:8501 -v /path/to/secrets:/app/.streamlit/secrets.toml wc_mkts
   ```

## Maintenance Tasks

### Database Maintenance
1. **Check database size**:
   ```bash
   ls -la *.db
   ```

2. **Optimize SQLite databases**:
   ```bash
   sqlite3 wcmkt.db 'VACUUM;'
   sqlite3 sde.db 'VACUUM;'
   ```

3. **Backup databases**:
   ```bash
   cp wcmkt.db wcmkt.db.backup
   cp sde.db sde.db.backup
   ```

### Log Management

Logs are configured in `logging_config.py` and stored in the `logs/` directory:
- Review logs for errors: `tail -f logs/app.log`
- Rotate logs periodically to prevent excessive file size

### Managing Doctrine Targets

To update doctrine target values:
1. Access the database directly:
   ```python
   from db_utils import update_targets
   
   # Update target for a specific fit
   update_targets(fit_id=1001, target_value=50)
   ```

2. Or use the `set_targets.py` script (if available)

### Performance Optimization

If the application becomes slow:
1. Check and potentially increase caching TTL values (currently 60s for most functions)
2. Consider adding indices to frequently queried database columns
3. Optimize SQL queries in `db_handler.py` for better performance
4. Adjust batch sizes in the `get_mkt_data()` function

## Troubleshooting Common Issues

### Sync Failures
- Check Turso credentials and connectivity
- Examine logs for detailed error messages
- Try clearing cache with `st.cache_data.clear()`
- Verify synchronization URL and auth token

### Missing Data
- Confirm data exists in the remote database
- Check SQL queries for incorrect filters
- Verify SDE database has correct item information
- Look for exceptions in log files

### Streamlit Interface Issues
- Clear browser cache or use incognito mode
- Check for JavaScript errors in browser console
- Restart the Streamlit server
- Update Streamlit to the latest version: `pip install --upgrade streamlit`

## Updating EVE SDE Data

The Static Data Export (SDE) needs periodic updates when EVE Online releases new items:
1. Download latest SDE from EVE Developers portal
2. Convert to SQLite format (if needed)
3. Replace the `sde.db` file
4. Restart the application

## Security Considerations

- Keep authentication tokens secure
- Use HTTPS when deploying publicly
- Implement IP restrictions if needed
- Regularly update dependencies
- Consider using CI/CD for automated security scanning