# Watchlist Admin SSO Design

Date: 2026-05-11
Status: Draft for review

## Scope

This prototype adds a gated admin flow for editing only the literal `watchlist`
table in the active market database. It does not edit doctrines, fits,
builder data, `builder_costs`, or any other table.

The first allowed administrator is hard-coded to EVE character ID `2122333361`.

## Goals

- Let the approved EVE character sign in with EVE SSO.
- Request no ESI scopes.
- Provide one admin page for viewing and editing `watchlist`.
- Write to the local SQLite market database during local testing.
- Write to the remote Turso market database when deployed to production.
- Keep write protection in the service layer, not only in the page UI.

## Non-Goals

- No role management.
- No multiple-admin UI.
- No ESI data access.
- No doctrine, fit, builder, build-cost, or market order editing.
- No backend API server for this prototype.

## Configuration

Add explicit configuration for SSO and admin writes.

```toml
[eve_sso]
client_id = "..."
callback_url = "http://localhost:8501/admin_login"
allowed_character_ids = [2122333361]

[admin]
write_target = "local"  # local | remote
session_ttl_minutes = 480
```

The EVE client secret and the internal admin session signing secret live in
Streamlit secrets:

```toml
[eve_sso]
client_secret = "..."

[admin]
session_secret = "..."
```

Local development uses a localhost callback URL. Production uses the deployed
Streamlit callback URL, for example `https://wcmkts.streamlit.app/admin_login`.

## Auth Flow

`pages/admin_login.py` handles both login start and callback completion.

1. If no callback params are present, the page creates a cryptographically
   random OAuth `state`, stores it server-side in Streamlit session state, and
   renders a sign-in button linked to EVE SSO.
2. The EVE authorization request includes no scopes.
3. EVE redirects to the configured callback URL with `code` and `state`.
4. The page rejects the callback unless `state` exactly matches the pending
   server-side value.
5. The app exchanges `code` for tokens server-side using the configured client
   secret.
6. The app verifies the EVE identity response and extracts character ID and
   character name from verified EVE data only.
7. The app rejects the login unless character ID is `2122333361`.
8. The app creates a signed internal admin session containing:
   - `character_id`
   - `character_name`
   - `issued_at`
   - `expires_at`
9. The page clears callback query params and redirects or offers a link to the
   admin page.

The internal admin session uses an HMAC signature with `admin.session_secret`.
Every admin page render and every write operation verifies the signature,
expiry, and allowed character ID.

## Modules

### `state/admin_auth_state.py`

Owns Streamlit session keys for:

- pending EVE OAuth state
- signed admin identity
- logout

It exposes helpers such as:

- `get_admin_identity()`
- `set_pending_oauth_state(state)`
- `consume_pending_oauth_state()`
- `set_admin_identity(identity)`
- `clear_admin_identity()`

### `services/eve_sso_service.py`

Owns EVE SSO behavior:

- build authorization URL
- exchange authorization code
- verify EVE identity
- create and verify signed admin session payloads

The service returns no admin identity unless the EVE response is verified and
the character ID is allow-listed.

### `repositories/admin_repo.py`

Owns write-capable database operations for `watchlist`.

The repository selects its write engine from explicit config:

- `local`: `DatabaseConfig(active_market_alias).engine`
- `remote`: `DatabaseConfig(active_market_alias).remote_engine`

The repository provides:

- `get_watchlist()`
- `replace_watchlist(rows)`

`replace_watchlist(rows)` runs in one transaction. It deletes existing
`watchlist` rows and inserts the validated replacement set. For this prototype,
full-table replacement is simpler and safer than trying to infer partial edits
from Streamlit's table state.

### `services/admin_service.py`

Owns authorization and validation for admin writes.

Responsibilities:

- verify signed admin identity before every write
- validate the requested write target exists and is configured explicitly
- validate every watchlist row
- reject duplicate `type_id`
- call `AdminRepository.replace_watchlist()`
- invalidate market/watchlist caches after successful writes

No page should call `AdminRepository` directly.

### `pages/admin.py`

The only admin editing page for this prototype.

Behavior:

- blocks unauthenticated users
- displays current signed-in EVE character
- renders a logout button
- renders an editable table for `watchlist`
- shows a diff summary before save:
  - added rows
  - changed rows
  - removed rows
- saves only when the user clicks a Save button
- reports validation errors without writing

### `app.py`

Add admin navigation entries:

- `Admin Login`
- `Admin Watchlist`

The admin page remains guarded even if the user navigates to it directly.

## Watchlist Data Rules

Editable columns are exactly:

- `type_id`
- `group_id`
- `type_name`
- `group_name`
- `category_id`
- `category_name`

Validation:

- `type_id` is required and integer-like.
- `type_id` values are unique.
- `group_id` and `category_id` are required and integer-like.
- `type_name`, `group_name`, and `category_name` are required non-empty strings.
- Unknown extra columns are ignored or rejected before writing. The first
  implementation should reject them to prevent accidental schema drift.

Optional enhancement after the prototype: when a user enters a `type_id`, enrich
metadata from SDE. This is not required for the first version.

## Security Notes

The browser never supplies a trusted character ID. Character identity comes only
from verified EVE SSO data.

Admin access is protected by:

- OAuth `state` validation
- server-side authorization code exchange
- verified EVE identity extraction
- hard-coded allow-list containing only `2122333361`
- signed internal admin session
- session expiry
- service-layer write guard

Remaining prototype risks:

- A stolen active browser session can act as the admin until logout or expiry.
- A leaked EVE client secret or admin session secret compromises the flow.
- This is not a multi-admin authorization system.

## Cache Invalidation

After a successful watchlist write, call the existing market cache invalidation
path, including `invalidate_market_caches()`. The goal is to refresh watchlist
read paths without clearing unrelated Streamlit caches.

## Testing

Unit tests:

- SSO service rejects missing, mismatched, and replayed state.
- SSO service rejects non-allow-listed character IDs.
- Signed admin session verification rejects tampered payloads and expired
  sessions.
- Admin service rejects unauthenticated writes.
- Admin service validates required columns, integer IDs, duplicate `type_id`,
  and empty text fields.
- Admin repository writes `watchlist` rows transactionally against a temporary
  SQLite database.

Page-level tests:

- unauthenticated admin page displays a login prompt
- authenticated admin page renders watchlist data
- save with invalid data shows validation errors and does not write

Manual verification:

- local login callback works with the local EVE developer callback URL
- local save writes to local market database when `admin.write_target = "local"`
- deployed save writes to Turso remote when `admin.write_target = "remote"`
