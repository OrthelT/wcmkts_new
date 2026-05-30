# NiceGUI POC — Streamlit alternative

A runnable proof-of-concept that re-skins the doctrine view of the Market Stats
app on **NiceGUI** instead of Streamlit, to feel the difference on the four pain
points: execution model, performance, SSO, and the pyturso migration.

It **reuses your existing `services/`, `repositories/`, `domain/` and
`EveSSOService` unchanged** — only the presentation file (`app.py`) is new. That
is the whole thesis: the layered architecture means a framework swap is a
re-skin of the top layer, not a rewrite.

## Run it

```bash
# from the repo root
uv run --with nicegui python poc/nicegui_app/app.py
```

Open <http://localhost:8080>.

No databases or secrets are required — if no local DB is synced, the doctrine
table falls back to clearly-labeled **sample data** (we never present sample
data as real). If you have a synced `wcmktprod.db`, it renders live data through
your real `DoctrineService`.

## What to look at

| Pain point | Where it shows up |
|---|---|
| **Execution model** | The "Filter ships…" box filters the grid client-side with **no full-script rerun**. Favorites mutate only their own button. |
| **Performance** | Data is fetched once into server-side state; interactions don't re-query the DB. |
| **SSO / OAuth** | "Log in with EVE" uses your existing `EveSSOService`. Per-user identity lives in `app.storage.user` — real per-session state, impossible cleanly in Streamlit. |
| **pyturso** | `turso_adapter.py` models the `pull()`/`push()` API. Favoriting a fit is a **local write** that pushes to remote — the capability libsql replicas lacked. |

## Real EVE SSO (optional)

By default the login is a **mock identity** so the session features demo without
a CCP app. For the real flow, register an EVE application with callback
`http://localhost:8080/auth/callback` and set:

```bash
export EVE_SSO_CLIENT_ID=...
export EVE_SSO_CLIENT_SECRET=...
export EVE_SSO_ALLOWED_CHARACTER_IDS=90000001,90000002
export POC_SESSION_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(32))")
# optional: export EVE_SSO_CALLBACK_URL=http://localhost:8080/auth/callback
```

Note: `EveSSOService.create_authorization_url` is identity-only (no scopes).
`auth.py` appends `esi-assets.read_assets.v1` + `esi-markets.read_character_orders.v1`
to show what you'd add for the "expose my assets/orders" use case. A production
build would also persist the ESI **refresh token** per character (your current
service keeps only a short-lived signed admin identity).

## pyturso (real) instead of the sqlite fallback

The adapter uses `turso` (pyturso) if importable, else stdlib `sqlite3`. To use
real pyturso once you migrate:

```bash
uv add pyturso
export TURSO_SYNC_URL=libsql://your-db.turso.io
export TURSO_AUTH_TOKEN=...
```

The migration in `config.py` is mechanical:

```python
# libsql (today)                         # pyturso (target)
conn = libsql.connect(                    conn = turso.connect(
    path, sync_url=url, auth_token=tok)       path, sync_url=url, auth_token=tok)
conn.sync()        # remote -> local      conn.pull()   # remote -> local
                                          conn.push()   # local  -> remote  (NEW)
```

## Files

- `app.py` — the NiceGUI app (the only new presentation layer)
- `data.py` — adapter that calls your real `DoctrineService`, falls back to sample
- `auth.py` — reuses `EveSSOService`; builds config from env instead of `st.secrets`
- `turso_adapter.py` — pull/push + local-write demo, pyturso-or-sqlite
