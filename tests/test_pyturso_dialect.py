"""Smoke tests: pyturso dialects are registered and usable."""

import pandas as pd
from sqlalchemy import create_engine, text


def test_turso_dialect_local_roundtrip(tmp_path):
    db_file = tmp_path / "smoke.db"
    engine = create_engine(f"sqlite+turso:///{db_file}")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(text("INSERT INTO t (id, name) VALUES (1, 'a')"))
        conn.commit()
    with engine.connect() as conn:
        df = pd.read_sql_query(text("SELECT id, name FROM t"), conn)
    assert df.to_dict("records") == [{"id": 1, "name": "a"}]
    engine.dispose()


def test_turso_sync_module_importable():
    import turso.sync as tursosync

    assert hasattr(tursosync, "connect")


class TestSyncDialect:
    """Sync-managed replicas must not be opened on the plain dialect: it
    auto-checkpoints the WAL at 1000 frames and destroys the pull baseline."""

    def test_default_dialect_is_sync(self):
        import inspect
        from config import DatabaseConfig

        sig = inspect.signature(DatabaseConfig.__init__)
        assert sig.parameters["dialect"].default == "sqlite+turso_sync"

    def test_every_configured_replica_uses_the_sync_dialect(self):
        from config import DatabaseConfig
        from settings_service import get_all_market_configs

        aliases = [c.database_alias for c in get_all_market_configs().values()]
        aliases += ["sde", "build_cost"]
        for alias in aliases:
            assert DatabaseConfig(alias).url.startswith("sqlite+turso_sync:///"), alias

    def test_plain_dialect_is_absent_from_the_codebase(self):
        """Guard against a reintroduction."""
        import pathlib
        import re

        hits = []
        for p in pathlib.Path(".").rglob("*.py"):
            if ".venv" in p.parts or "tests" in p.parts:
                continue
            if re.search(r'"sqlite\+turso"|\'sqlite\+turso\'', p.read_text()):
                hits.append(str(p))
        assert hits == [], hits

    def test_no_credentials_uses_read_only_sqlite_without_sync_args(self, tmp_path):
        """A replica with no Turso credentials must fall back to an ordinary
        read-only SQLite connection: reads succeed, writes fail, and neither
        the plain sqlite+turso dialect nor the sync dialect with
        remote_url=None is ever used for the actual connection."""
        import sqlite3

        import pytest
        from sqlalchemy import text
        from sqlalchemy.exc import OperationalError

        from config import DatabaseConfig

        db_path = tmp_path / "no_creds.db"
        raw = sqlite3.connect(str(db_path))
        raw.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, val TEXT)")
        raw.execute("INSERT INTO t (id, val) VALUES (1, 'a')")
        raw.commit()
        raw.close()

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = "test_no_creds_alias"
        db.path = str(db_path)
        db.url = f"sqlite+turso_sync:///{db_path}"
        db.turso_url = None
        db.token = None
        db._connect_args = {"remote_url": None, "auth_token": None}

        try:
            assert db.has_remote_credentials is False

            engine = db.engine
            # Never the sync dialect (which would need remote_url) or the
            # plain turso dialect — just ordinary pysqlite.
            assert engine.dialect.driver == "pysqlite"

            with engine.connect() as conn:
                result = conn.execute(text("SELECT val FROM t WHERE id = 1")).scalar()
            assert result == "a"

            with pytest.raises(OperationalError):
                with engine.connect() as conn:
                    conn.execute(text("INSERT INTO t (id, val) VALUES (2, 'b')"))
                    conn.commit()
        finally:
            DatabaseConfig._engines.pop(db._engine_cache_key(), None)
