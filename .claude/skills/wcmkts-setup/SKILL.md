---
name: wcmkts-setup
description: Local/Streamlit-Cloud environment setup for the Winter Coalition Market Stats Viewer - the .streamlit/secrets.toml Turso credential layout (section-per-database) and local development notes. Use when configuring secrets, adding a new database hub, or setting up a fresh checkout.
---

# Environment Setup

## Required Secrets (Streamlit Cloud & Local Development)

Create `.streamlit/secrets.toml` (section-per-database format):

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

[janice]
api_key = "your_janice_api_key"  # For Pricer page Jita price lookups
```

Note: database aliases in `settings.toml` `[db_paths]` (e.g. `sde`, `build_cost`) may not
match the Turso secret section names above. Use `[db_turso_keys]` in `settings.toml` to map
an alias to its secret section when the `{alias}_turso` convention doesn't hold.

## Local Development Notes

- Ensure local database files exist: `wcmktprod.db`, `sdelite.db`, `buildcost.db`
- The application will use local SQLite files if sync credentials are not available
- Database files are git-ignored (*.db, *.db-shm, *.db-wal)
- Logs are stored in `logs/` directory (git-ignored)

## Security

- **Secrets management**: Store Turso URLs/tokens in `.streamlit/secrets.toml`; NEVER hard-code
- **Environment variables**: `.env` supported via `python-dotenv`
- **API keys**: ESI API is public, but rate-limit aware code is in the backend repo
- **Authentication**: Turso auth tokens required for remote sync
