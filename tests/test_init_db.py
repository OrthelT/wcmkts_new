"""init_db file-state checks (spec §1 cold start)."""

import sqlite3

from init_db import _remove_empty_db, verify_db_content

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


def test_remove_empty_db_covers_pyturso_artifacts(tmp_path):
    p = str(tmp_path / "a.db")
    for suffix in ("", "-shm", "-wal", "-info", "-changes", "-wal-revert"):
        (tmp_path / f"a.db{suffix}").write_bytes(b"x")
    _remove_empty_db(p)
    assert list(tmp_path.iterdir()) == []
