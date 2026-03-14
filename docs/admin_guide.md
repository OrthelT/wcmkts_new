# Winter Coalition Market Stats Viewer - Administrator Guide

This guide is intended for administrators who need to maintain, configure, or deploy the Winter Coalition Market Stats Viewer application.

## System Architecture Overview

The application uses a hybrid database approach:
- **Local SQLite Databases**:
  - `wcmktprod.db`: Main market data (4-HWWF) — synchronized from the Turso remote
  - `wcmktnorth2.db`: Deployment market data (B-9C24) — synchronized from Turso
  - `sdelite.db`: EVE Online Static Data Export (item information, localizations)
  - `buildcost.db`: Manufacturing structures, rigs, and industry indices
- **Turso Cloud Database**:
  - Remote database that collects and processes EVE Online market data
  - Local databases sync with remote using Turso's embedded-replica feature via `DatabaseConfig.sync()`
- **Backend Repository** (`mkts_backend`): Separate repository that handles ESI API calls and updates the Turso remote. This frontend application is read-only for market data.

## Database Schema

Key tables in the market database (`wcmktprod.db` / `wcmktnorth2.db`):
- `marketorders`: Individual sell and buy orders on the market
- `marketstats`: Aggregated statistics about market items
- `market_history`: Historical price and volume data
- `doctrines`: Doctrine fits and their components
- `doctrine_fits`: Doctrine fitting details
- `ship_targets`: Target inventory levels for doctrine ships
- `lead_ships`: Leadership ship configurations
- `watchlist`: Market watchlist items
- `updatelog`: Database update tracking
- `module_equivalents`: Interchangeable faction module mappings (managed by backend, read-only here)

Key tables in the SDE database (`sdelite.db`):
- `invTypes`: Information about all EVE Online items
- `invGroups`: Item groups classification
- `invCategories`: High-level item categories
- `localizations`: Localized item names for 8 languages (~210k rows)

Key tables in the build cost database (`buildcost.db`):
- `structures`: Manufacturing structure data
- `industry_index`: Industry cost indices
- `rigs`: Structure rig configurations

## Configuration

### Environment Variables

Production environments use Streamlit secrets management. Create `.streamlit/secrets.toml` with per-database sections:

```toml
[wcmktprod_turso]
url = "libsql://your-database.turso.io"
token = "your_turso_auth_token"

[wcmktnorth_turso]
url = "libsql://your-north-database.turso.io"
token = "your_turso_auth_token"

[sdelite_turso]
url = "libsql://your-sde.turso.io"
token = "your_sde_auth_token"

[buildcost_turso]
url = "libsql://your-buildcost.turso.io"
token = "your_buildcost_auth_token"
```

Note: The `sde` alias maps to `sdelite_turso` and `build_cost` maps to `buildcost_turso` via `[db_turso_keys]` overrides in `settings.toml`.

### Database Synchronization Settings

Database synchronization is managed by the `DatabaseConfig` class in `config.py`:
- Automatic sync occurs daily at 13:00 UTC
- Manual sync via sidebar button triggers `DatabaseConfig.sync()` on the active market database
- `sync()` serializes via `_SYNC_LOCK` (threading.Lock) and runs `PRAGMA integrity_check` after sync
- CLI sync: `uv run python config.py <alias>` (e.g., `uv run python config.py wcmktprod`)

### Doctrine Targets Configuration

Target inventory levels for doctrine ships are stored in the `ship_targets` table in `wcmktprod.db`. This table is managed via the backend repository (mkts_backend). Each entry has `fit_id`, `ship_target`, and `fit_name` columns.

## Deployment Options

### Local Deployment
1. Clone the repository
2. Install dependencies: `uv sync`
3. Configure secrets in `.streamlit/secrets.toml` (see Configuration section above)
4. Run with: `uv run streamlit run app.py`

### Server Deployment
1. Install `uv` and sync dependencies: `uv sync`
2. Configure `.streamlit/secrets.toml` with Turso credentials
3. Use a process manager like Supervisor:
   ```
   [program:wc_mkts]
   command=/path/to/.venv/bin/streamlit run app.py
   directory=/path/to/wcmkts_new
   autostart=true
   autorestart=true
   ```

### Docker Deployment
1. Create a Dockerfile:
   ```dockerfile
   FROM python:3.12-slim

   WORKDIR /app

   RUN pip install uv
   COPY pyproject.toml uv.lock ./
   RUN uv sync --frozen

   COPY . .

   EXPOSE 8501

   CMD ["uv", "run", "streamlit", "run", "app.py"]
   ```
2. Build and run the container:
   ```bash
   docker build -t wc_mkts .
   docker run -p 8501:8501 -v /path/to/.streamlit:/app/.streamlit wc_mkts
   ```

## Maintenance Tasks

### Database Maintenance
1. **Check database size**:
   ```bash
   ls -la *.db
   ```

2. **Optimize SQLite databases**:
   ```bash
   sqlite3 wcmktprod.db 'VACUUM;'
   sqlite3 sdelite.db 'VACUUM;'
   ```

3. **Backup databases**:
   ```bash
   cp wcmktprod.db wcmktprod.db.backup
   cp sdelite.db sdelite.db.backup
   ```

### Log Management

Logs are configured in `logging_config.py` and stored in the `logs/` directory:
- Review logs for errors: `tail -f logs/app.log`
- Rotate logs periodically to prevent excessive file size

### Managing Doctrine Targets

Doctrine targets are stored in the `ship_targets` table and managed via the backend repository (mkts_backend). After updating the backend database, trigger a sync on the frontend to pick up changes.

### Performance Optimization

If the application becomes slow:
1. Check cache invalidation: use `invalidate_market_caches()` after sync (not global `st.cache_data.clear()`)
2. Consider adding indices to frequently queried database columns
3. Check the `logs/` directory for slow query warnings
4. Ensure the SDE repository is using `@st.cache_resource` (no TTL) for immutable data

## Troubleshooting Common Issues

### Sync Failures
- Check Turso credentials in `.streamlit/secrets.toml`
- Verify secret section names match (e.g., `sde` alias requires `sdelite_turso` section — see `[db_turso_keys]` in `settings.toml`)
- Examine logs in `logs/` directory for detailed error messages
- Run CLI sync to test: `uv run python config.py wcmktprod`
- Check for empty db file artifacts (`.db-info` alongside a 0-byte `.db`): delete both and re-sync

### Missing Data
- Confirm data exists in the remote Turso database (check backend repository logs)
- Verify the active market hub is correctly selected (primary vs deployment)
- Check SDE database has correct item information
- Look for exceptions in log files

### Streamlit Interface Issues
- Clear browser cache or use incognito mode
- Check for JavaScript errors in browser console
- Restart the Streamlit server
- Update dependencies: `uv sync`

## Updating EVE SDE Data

The Static Data Export (SDE) needs periodic updates when EVE Online releases new items:
1. Download latest SDE from EVE Developers portal
2. Convert to SQLite format (if needed)
3. Replace the `sdelite.db` file
4. Restart the application

## Security Considerations

- Keep authentication tokens secure
- Use HTTPS when deploying publicly
- Implement IP restrictions if needed
- Regularly update dependencies
- Consider using CI/CD for automated security scanning
