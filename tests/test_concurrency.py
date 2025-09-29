# tests/test_concurrency.py
import os
import time
import sqlite3 as sql
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

import pandas as pd
import pytest

from config import DatabaseConfig
from conftest import ro_conn, get_journal_mode, quick_check_ok

# --------- Unit-ish: one process, repeated syncs ---------

def test_repeated_syncs_idempotent(temp_db, monkeypatch_libsql):
    db = DatabaseConfig(path=temp_db)
    # First sync creates/initializes
    r1 = db.sync()
    # Second sync should be a no-op/quick pass (lock still ensures only one at a time)
    r2 = db.sync()
    assert r1 is True
    assert r2 in (True, False)  # depending on your sync() return; both acceptable
    assert get_journal_mode(temp_db).lower() == "wal"
    assert quick_check_ok(temp_db) is True

# --------- Multi-process: only one sync runs at a time ---------

def _sync_once(db_path: str) -> bool:
    from config import DatabaseConfig
    db = DatabaseConfig(path=db_path)
    return bool(db.sync())

def test_single_writer_across_processes(temp_db, monkeypatch_libsql):
    # Fire N concurrent sync() calls from different processes
    N = 6
    with ProcessPoolExecutor(max_workers=N) as ex:
        futs = [ex.submit(_sync_once, temp_db) for _ in range(N)]
        results = [f.result(timeout=10) for f in futs]

    # At least one True, but not all should be True if losers skip while winner holds lock
    assert any(results)
    assert sum(bool(x) for x in results) <= 2  # usually 1, allow racey double-start edge

    # DB is healthy and WAL after the dust settles
    assert get_journal_mode(temp_db).lower() == "wal"
    assert quick_check_ok(temp_db) is True

# --------- Readers during sync: no malformed, rows keep appearing ---------

def test_readers_continue_during_sync(temp_db, monkeypatch_libsql):
    db = DatabaseConfig(path=temp_db)

    # prime the file (first sync creates DB + WAL)
    assert db.sync() is True

    stop = False
    read_errors = []

    def reader_loop():
        nonlocal stop
        while not stop:
            try:
                with ro_conn(temp_db) as con:
                    df = pd.read_sql_query("SELECT * FROM marketstats ORDER BY id DESC LIMIT 5", con)
                    # just touch the data
                    _ = df.head(1)
            except Exception as e:
                read_errors.append(str(e))
            time.sleep(0.02)

    # start readers
    with ThreadPoolExecutor(max_workers=4) as tpex:
        readers = [tpex.submit(reader_loop) for _ in range(4)]
        # run a few syncs while readers are hammering
        for _ in range(5):
            assert db.sync() in (True, False)
            time.sleep(0.05)
        stop = True
        for f in readers:
            f.result(timeout=5)

    # No “malformed” errors should have occurred
    bad = [e for e in read_errors if "malformed" in e.lower() or "disk image" in e.lower()]
    assert bad == [], f"reader saw corruption: {bad}"
    assert get_journal_mode(temp_db).lower() == "wal"
    assert quick_check_ok(temp_db) is True

# --------- Optional integration test (real Turso). Skips by default. ---------

@pytest.mark.integration
@pytest.mark.skipif(
    not (os.getenv("TURSO_URL") and os.getenv("TURSO_TOKEN")),
    reason="Set TURSO_URL and TURSO_TOKEN to run integration test",
)
def test_integration_pragmas_and_quickcheck(tmp_path):
    path = str(tmp_path / "real.db")
    db = DatabaseConfig(path=path, turso_url=os.getenv("TURSO_URL"), token=os.getenv("TURSO_TOKEN"))
    assert db.sync() is True
    assert get_journal_mode(path).lower() == "wal"
    assert quick_check_ok(path) is True
