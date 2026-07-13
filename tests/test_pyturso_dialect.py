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
