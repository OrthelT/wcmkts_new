"""init_db file-state checks and single-flight bootstrap (spec §1 cold start)."""

import os
import sqlite3
import threading
import time

from init_db import ensure_market_db_ready, init_db, verify_db_content

VALID_INFO = '{"hash":1,"version":0,"durable_frame_num":1,"generation":1}'


def _make_sqlite_db(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()


def test_content_with_valid_info_ok(tmp_path):
    p = str(tmp_path / "a.db")
    _make_sqlite_db(p)
    (tmp_path / "a.db-info").write_text(VALID_INFO)
    assert verify_db_content(p) is True


def test_content_without_info_not_ready(tmp_path):
    """Deploy-day: a libsql-era .db with no pyturso metadata must resync."""
    p = str(tmp_path / "a.db")
    _make_sqlite_db(p)
    assert verify_db_content(p) is False


def test_content_with_invalid_info_not_ready(tmp_path):
    p = str(tmp_path / "a.db")
    _make_sqlite_db(p)
    (tmp_path / "a.db-info").write_bytes(b"\x00binary-libsql-junk")
    assert verify_db_content(p) is False


def test_empty_file_not_ready(tmp_path):
    p = tmp_path / "a.db"
    p.touch()
    (tmp_path / "a.db-info").write_text(VALID_INFO)
    assert verify_db_content(str(p)) is False


class _FakeDB:
    """Stand-in for DatabaseConfig: records sync() calls, never touches network."""

    base_path = None
    sync_events = None  # list of (alias, file_existed_at_sync, start, end)
    sync_sleep = 0.0

    def __init__(self, alias):
        self.alias = alias
        self.path = os.path.join(str(_FakeDB.base_path), f"{alias}.db")

    def sync(self):
        start = time.monotonic()
        existed = os.path.exists(self.path)
        if _FakeDB.sync_sleep:
            time.sleep(_FakeDB.sync_sleep)
        _FakeDB.sync_events.append((self.alias, existed, start, time.monotonic()))


def _patch_init_db(monkeypatch, tmp_path, sync_sleep=0.0):
    _FakeDB.base_path = tmp_path
    _FakeDB.sync_events = []
    _FakeDB.sync_sleep = sync_sleep
    monkeypatch.setattr("init_db.get_all_market_configs", lambda: {})
    monkeypatch.setattr("init_db.DatabaseConfig", _FakeDB)


def test_invalid_db_not_deleted_before_sync(tmp_path, monkeypatch):
    """init_db must NOT delete an invalid replica itself — deleting outside
    _SYNC_LOCK can destroy another session's in-flight bootstrap. Cleanup is
    sync()'s job, under its lock."""
    _patch_init_db(monkeypatch, tmp_path)
    # a .db without -info: invalid per verify_db_content, needs resync
    _make_sqlite_db(str(tmp_path / "sde.db"))

    init_db()

    events = {alias: existed for alias, existed, _, _ in _FakeDB.sync_events}
    assert events["sde"] is True  # file still on disk when sync() ran


def test_ensure_market_db_ready_does_not_delete(tmp_path, monkeypatch):
    _patch_init_db(monkeypatch, tmp_path)
    _make_sqlite_db(str(tmp_path / "mkt.db"))  # no -info → invalid

    ensure_market_db_ready("mkt")

    events = {alias: existed for alias, existed, _, _ in _FakeDB.sync_events}
    assert events["mkt"] is True  # file still on disk when sync() ran


def test_concurrent_init_db_serialized(tmp_path, monkeypatch):
    """Two sessions cold-starting at once must not bootstrap concurrently:
    the second waits, re-verifies, and skips work the first already did."""
    _patch_init_db(monkeypatch, tmp_path, sync_sleep=0.03)

    barrier = threading.Barrier(2)
    errors = []

    def run():
        barrier.wait()
        try:
            init_db()
        except Exception as e:  # pragma: no cover - surfaced via assert below
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    intervals = sorted((start, end) for _, _, start, end in _FakeDB.sync_events)
    for (_, prev_end), (next_start, _) in zip(intervals, intervals[1:]):
        assert next_start >= prev_end, "sync() calls overlapped across threads"
