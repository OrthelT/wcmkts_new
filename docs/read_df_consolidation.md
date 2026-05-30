# Read Consolidation: route all DB reads through `BaseRepository.read_df()`

**Status:** proposed (future refactoring project)
**Owner:** TBD
**Related convention:** see *Database Operations → Read Convention* in `CLAUDE.md`.

## Motivation

The app reads SQLite/libSQL three different ways today. Only one of them carries
the resilience guarantees the architecture advertises:

| Pattern | Recovery on malformed/corrupt DB? | Remote fallback? |
|---|---|---|
| `BaseRepository.read_df(text(...))` | ✅ sync-and-retry | ✅ falls back to `remote_engine` |
| Bare `db.engine.connect()` + `pd.read_sql_query` | ❌ | ❌ |
| SQLAlchemy ORM `select()` reads | n/a — **not used anywhere** | n/a |

`read_df()` (`repositories/base.py`) is the intended single chokepoint:
local read → on malformed error `db.sync()` + retry → if still failing, read from
`db.remote_engine`. Every site that calls `engine.connect()` directly silently
opts out of that, so a corrupt local `.db` makes those queries throw
("no such table" / "database disk image is malformed") instead of self-healing —
exactly the failure mode `read_df()` exists to prevent (and that `init_db.py` /
cold-start notes in `CLAUDE.md` reference).

This is a **consistency + resilience** refactor, not a behavior change. No query
logic should change; only *how* each query is executed.

## Decision (already ratified)

- **Reads stay raw SQL** via `sqlalchemy.text(...)`. The ORM is *not* adopted for
  reads — it earns its keep only for schema definition/seeding (`demo_data.py`),
  the single write path (`admin_repo.py`), and as schema documentation.
- **Every read flows through `read_df()`** so recovery + remote fallback are
  uniform.
- Params are **named**; `IN` clauses use `bindparam(name, expanding=True)`.

## Scope: ~39 direct-`engine.connect()` read sites across 10 files

Counts captured at the time of writing (`grep -c "engine.connect()"`):

| File | Sites | Notes |
|---|---:|---|
| `repositories/market_repo.py` | 12 | mix of `wcmkt` and `sde` reads; `_get_watchlist_impl` already shows the correct `read_df()` form to copy |
| `repositories/doctrine_repo.py` | 8 | |
| `repositories/build_cost_repo.py` | 4 | `build_cost` alias |
| `repositories/sde_repo.py` | 3 | `sde` alias; note `@st.cache_resource` (no TTL) on SDE reads |
| `repositories/admin_repo.py` | 3 | **reads** here should move to `read_df`; the **write** path (`DELETE` + `sqlite_insert(Watchlist)`) stays on a direct transactional connection — `read_df` is read-only |
| `repositories/market_orders_repo.py` | 2 | |
| `services/type_resolution_service.py` | 3 | service-level DB access; consider pushing into a repo while here |
| `services/price_service.py` | 2 | `DatabasePriceProvider` reads `jita_prices`; keep provider abstraction, just swap execution |
| `services/import_helper_service.py` | 1 | |
| `services/module_equivalents_service.py` | 1 | `_get_equivalent_type_ids` / equivalence-group cached helpers still use a passed-in `engine`; `_get_module_stocks` was already migrated to `read_df()` |

> Regenerate the live list before starting:
> ```bash
> grep -rn "engine.connect()" repositories/ services/
> ```

## Migration recipe (per site)

Before:
```python
db = DatabaseConfig(db_alias)
query = text("SELECT ... WHERE type_id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)
with db.engine.connect() as conn:
    df = pd.read_sql_query(query, conn, params={"ids": ids})
```

After:
```python
repo = BaseRepository(DatabaseConfig(db_alias), logger)
query = text("SELECT ... WHERE type_id IN :ids").bindparams(
    bindparam("ids", expanding=True)
)
df = repo.read_df(query, params={"ids": ids})
```

Notes:
- `read_df()` accepts a `text()` clause (or a raw SQL string) plus `params`, and
  takes `local=` / `fallback_remote_on_malformed=` kwargs if a site needs to opt
  out of fallback.
- Where a module already holds a `DatabaseConfig` (e.g. services with
  `self._mkt_db`), build `BaseRepository(self._mkt_db, self._logger)` rather than
  constructing a new `DatabaseConfig`.
- Functions that currently wrap the read in `try/except` returning an empty
  DataFrame can keep that outer guard; `read_df()` only adds recovery, it still
  raises on non-malformed errors.

## Explicit non-goals / carve-outs

- **Writes** (`admin_repo.py` `DELETE`/`sqlite_insert`, `demo_data.py`
  `create_all` + seeding) stay as-is — `read_df()` is read-only by design.
- **`config.py` sync/integrity** internals (`libsql.connect`, `PRAGMA`
  `integrity_check`) are infrastructure, not application reads — out of scope.
- The cached `engine`-passing helpers in `module_equivalents_service.py` may need
  a small signature change (pass `DatabaseConfig`/alias instead of a raw
  `engine`) so they can build a `BaseRepository`; do this deliberately, not as a
  blind swap.

## Validation

- `uv run pytest -q` — the suite mostly mocks repositories, so most sites change
  without test churn. Sites that mock `engine.connect()` directly will need their
  mocks updated to the `read_df()` boundary.
- **Coverage gaps to close while here:** there is currently **no test file for
  `ModuleEquivalentsService`** (`get_aggregated_stock`, `_get_module_stocks`,
  equivalence-group aggregation are untested). Add one as part of this work —
  the `_get_module_stocks` → `read_df()` migration done in the perf pass shipped
  without direct coverage.
- Manual smoke: rename/corrupt a local `.db` and confirm pages recover via sync /
  remote fallback instead of surfacing "no such table".

## Suggested sequencing

1. `repositories/` first (highest density, best test coverage) — `market_repo.py`,
   then `doctrine_repo.py`, then the smaller repos.
2. `services/` that hit the DB directly — ideally push those reads down into the
   appropriate repository while migrating, to retire service-level DB access.
3. Add the `ModuleEquivalentsService` test file.
4. Optional: a lightweight lint/CI guard (e.g. grep check) that fails on new
   `engine.connect()` reads outside `base.py` / write paths, to prevent regression.
