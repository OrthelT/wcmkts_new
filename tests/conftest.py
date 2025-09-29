"""
Pytest configuration file for the wcmkts_refactor project.
This file sets up the Python path so tests can import modules from the project root.
"""
import sys
import os
from pathlib import Path
import time
import sqlite3 as sql
import threading
import contextlib
import types
import pytest   

# Add the project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


# --- Fake libsql connection that mimics conn.sync() creating the DB ---
class _FakeLibsqlConn:
    def __init__(self, db_path, sync_url=None, auth_token=None, delay=0.15):
        self.db_path = db_path
        self.sync_url = sync_url
        self.auth_token = auth_token
        self.delay = delay

    def sync(self):
        # simulate time spent syncing
        time.sleep(self.delay)
        # create/initialize the db "as Turso would"
        with sql.connect(self.db_path) as con:
            # Set WAL as Turso/libsql would; create a tiny table we can read
            con.execute("PRAGMA journal_mode=WAL;")
            con.execute("CREATE TABLE IF NOT EXISTS marketstats (id INTEGER PRIMARY KEY, note TEXT)")
            con.execute("INSERT INTO marketstats(note) VALUES ('synced')")
            con.execute("PRAGMA wal_checkpoint(PASSIVE);")

    def close(self):
        pass

@pytest.fixture
def monkeypatch_libsql(monkeypatch, tmp_path):
    """
    Monkeypatch libsql.connect(...) to return our fake connection.
    Your production DatabaseConfig.sync() will still run,
    but it'll use this fake instead of hitting the network.
    """
    import types

    def _fake_connect(db_path, sync_url=None, auth_token=None):
        return _FakeLibsqlConn(db_path, sync_url, auth_token)

    fake_libsql = types.SimpleNamespace(connect=_fake_connect)
    monkeypatch.setitem(dict(globals()), "libsql", fake_libsql)  # in case tests import here
    # Also patch the module your app uses:
    monkeypatch.setitem(__import__("sys").modules, "libsql", fake_libsql)
    return fake_libsql

@pytest.fixture
def temp_db(tmp_path):
    # path for a fresh db per test
    return str(tmp_path / "test.db")

@contextlib.contextmanager
def ro_conn(db_path: str):
    uri = f"file:{db_path}?mode=ro"
    con = sql.connect(uri, uri=True, check_same_thread=False)
    try:
        yield con
    finally:
        con.close()

def get_journal_mode(db_path: str) -> str:
    with sql.connect(db_path) as con:
        return con.execute("PRAGMA journal_mode;").fetchone()[0]

def quick_check_ok(db_path: str) -> bool:
    with sql.connect(db_path) as con:
        return con.execute("PRAGMA quick_check;").fetchone()[0] == "ok"
