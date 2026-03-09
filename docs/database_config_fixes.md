# database_config.md — Required Fixes

Tracked separately from PR #32. The current `docs/database_config.md` has significant drift from `config.py`.

## Discrepancies to Fix

| What's Wrong | Current (Wrong) | Correct |
|---|---|---|
| Alias throughout | `wcmkt2` | `wcmktprod` (and mention `wcmktnorth`) |
| File name | `wcmkt2.db` | `wcmktprod.db` |
| `wcdbmap` value | Hardcoded `"wcmkt2"` | Dynamic from `settings.toml`: `env_db_aliases[env.env]` |
| `local_access()` examples | Context manager shown | Method doesn't exist — remove all examples using it |
| Secret names | `[wcmkt2_turso]`, `[sde_aws_turso]` | `[wcmktprod_turso]`, `[sdelite_turso]` |
| Constructor docs | Simple alias mapping | Show `_resolve_active_alias()` behavior for deprecated aliases |

## Missing Features to Document

- **Multi-market support**: `[markets.primary]` and `[markets.deployment]` in settings.toml
- **`ro_engine` property**: Read-only SQLAlchemy engine with `NullPool`
- **`has_remote_credentials` property**: Bool check for Turso URL/token availability
- **`get_most_recent_update()` method**: Queries `UpdateLog` table for last update timestamp
- **Deprecated alias handling**: `wcmkt`, `wcmkt2`, `wcmkt3` all resolve via `_resolve_active_alias()`
- **`_dispose_local_connections()`**: Cleanup before sync
- **`_local_matches_remote()`**: Post-sync validation comparing local/remote timestamps
- **`_cleanup_empty_db_file()`**: Removes empty db + WAL artifacts after failed sync
- **`integrity_check()`**: PRAGMA integrity_check wrapper
- **`sync()` return value**: Returns `bool`, callers handle UI feedback and cache invalidation
