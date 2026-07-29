---
name: wcmkts-troubleshooting
description: Diagnosing database connection, sync, performance, and data-quality problems in the Winter Coalition Market Stats Viewer - including the empty-db-on-cold-start trap and Turso credential naming mismatches. Use when sync fails, queries report "no such table", prices look wrong, or data appears stale.
---

# Troubleshooting

## Database Connection Issues

- **Local files missing**: Run `init_db.py` to initialize databases
- **Sync failures**: Check Turso credentials in `.streamlit/secrets.toml`
- **Integrity errors**: DatabaseConfig will auto-recover with `integrity_check()` and sync
- **Malformed database**: Repository functions auto-detect and fallback to remote queries
- **Connection errors**: Review logs in `logs/` directory
- **Empty db file on cold start**: `libsql.connect()` creates the `.db` file before syncing. If credentials are missing or sync fails, the empty file persists and causes "no such table" errors on subsequent runs. `init_db.py` detects this via `verify_db_content()` and removes empty files before re-syncing. If `.db-info` exists alongside an empty `.db`, it indicates a prior interrupted sync.
- **Credential naming mismatch**: Database aliases in `[db_paths]` (e.g., `sde`, `build_cost`) may not match Turso secret section names (e.g., `sdelite_turso`, `buildcost_turso`). Use `[db_turso_keys]` in `settings.toml` to map aliases to their correct secret section names. When adding a new database, ensure its turso key is either `{alias}_turso` or has an override in `[db_turso_keys]`.

## Performance Issues

- **Slow queries**: Use targeted cache invalidation (e.g., `invalidate_market_caches()`)
- **Outdated data**: Check database sync status and last update time
- **Memory usage**: Monitor during large data operations, consider pagination

## Data Quality Issues

- **Missing data**: Check if backend repository (mkts_backend) is running and updating remote DB
- **Incorrect prices**: Verify Jita prices are current, check Fuzzworks API fallback
- **Missing types**: Check SDE database is current and complete
