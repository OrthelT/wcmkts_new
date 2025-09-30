# Repository Guidelines

## Project Structure & Module Organization
- `app.py`: Streamlit entrypoint. UI pages live in `pages/`.
- Core modules: `config.py` (DB config/sync), `db_handler.py`, `doctrines.py`, `models.py`, `utils.py`.
- Data/assets: local SQLite/LibSQL replicas (`*.db*`), CSV seeds, and logs (ignored by Git).
- Docs: `docs/` contains admin/database guides and walkthroughs.
- Config: `.streamlit/` for secrets, `.env` for local overrides.
- Tests: lightweight checks in `tests/` (note: directory is ignored by `.gitignore`).

## Build, Test, and Development Commands
- Install deps (Python 3.12 via uv): `uv sync`
- Run app locally: `uv run streamlit run app.py`
- Lint/format (recommended): `uv run ruff check .` and `uv run ruff format .` (add Ruff if not installed).
- Quick data scripts: `uv run python build_cost_models.py` (rebuilds cost DB), others run similarly.

## Coding Style & Naming Conventions
- Python style: PEP 8, 4‑space indents, max line length 100.
- Naming: modules/functions `snake_case`, classes `PascalCase`, constants `UPPER_SNAKE_CASE`.
- Types/docstrings: prefer type hints; include concise docstrings on public functions.
- Logging: use `logging` with `logging_config.py`; don’t print() in production code.

## Testing Guidelines
- Framework: add `pytest` for new tests; place files under `tests/` named `test_*.py`.
- What to test: data shape/columns, query correctness, and page-level helpers (mock DB where possible).
- Run (after adding pytest): `uv run pytest -q`.

## Commit & Pull Request Guidelines
- Commits: follow Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`). Keep focused, imperative mood.
- PRs: include a clear summary, linked issues, steps to validate, and screenshots/GIFs for UI changes. Note any DB/schema or config impacts.

## Security & Configuration Tips
- Secrets: store Turso URLs/tokens in `.streamlit/secrets.toml`; never hard‑code.
- Local env: `.env` supported by `python-dotenv`.
- Git hygiene: large `*.db*` and `*.log` files are ignored—avoid committing generated artifacts.

## Architecture Overview (Brief)
- Streamlit frontend (`app.py` + `pages/`) backed by local LibSQL replicas synced from Turso via `DatabaseConfig`. Business logic stays in modules; UI files should remain thin and delegate to helpers.

## TODOs
✅ COMPLETED - Refactored concurrency handling to use read-write locks (RWLock) instead of exclusive locks
  - Multiple concurrent reads now allowed
  - Writers maintain exclusive access
  - Sync operations properly block all access
  - Added comprehensive test coverage (12 new tests)

✅ COMPLETED - Updated tests to reflect current state of the codebase
  - All 36 tests passing (24 existing + 12 new)
  - Added test_rwlock.py for RWLock implementation
  - Added test_database_config_concurrency.py for DatabaseConfig concurrency behavior 
