"""sync() state machine and pull flow (spec §1)."""

import json
import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from config import DatabaseConfig, SyncResult


@pytest.fixture
def db(tmp_path):
    db = DatabaseConfig.__new__(DatabaseConfig)
    db.alias = "testalias"
    db.path = str(tmp_path / "test.db")
    db.turso_url = "libsql://example.turso.io"
    db.token = "tok"
    return db


def _write(path, data=b"x" * 32):
    with open(path, "wb") as f:
        f.write(data)


def _make_db(path, tables=True):
    """Create a real sqlite database, optionally with a user table."""
    conn = sqlite3.connect(path)
    if tables:
        conn.execute("CREATE TABLE t (id INTEGER)")
    conn.commit()
    conn.close()


def _write_info(db, valid=True):
    """Write a real pyturso-shaped -info (valid=True) or corrupt bytes.

    The "valid" content deliberately matches the shape classify_metadata
    accepts (version "v1" + client_unique_id) and records db.turso_url as
    its bootstrap remote, so the fail-closed remote-identity check in
    _ensure_replica_consistency does not spuriously trip these fixtures.
    """
    if valid:
        content = json.dumps(
            {
                "version": "v1",
                "client_unique_id": "test-client-id",
                "saved_configuration": {"remote_url": db.turso_url},
            }
        )
    else:
        content = "libsql-binary-garbage\x00"
    with open(db.path + "-info", "w") as f:
        f.write(content)


def _mock_sync_conn(pull_returns=False):
    conn = MagicMock()
    conn.pull.return_value = pull_returns
    return conn


class TestEnsureReplicaConsistency:
    def test_both_valid_untouched(self, db):
        _make_db(db.path)
        _write_info(db)
        db._ensure_replica_consistency()
        assert os.path.exists(db.path)
        assert os.path.exists(db.path + "-info")

    def test_paired_but_tableless_db_nuked(self, db):
        """A valid pairing whose .db has no user tables cannot serve reads and
        an incremental pull won't fix it — must be nuked for fresh bootstrap."""
        _make_db(db.path, tables=False)
        _write_info(db)
        db._ensure_replica_consistency()
        assert not os.path.exists(db.path)
        assert not os.path.exists(db.path + "-info")

    def test_paired_zero_byte_db_nuked(self, db):
        """A 0-byte .db beside valid -info (interrupted sync) must be nuked."""
        open(db.path, "wb").close()
        _write_info(db)
        db._ensure_replica_consistency()
        assert not os.path.exists(db.path)
        assert not os.path.exists(db.path + "-info")

    def test_garbage_db_with_valid_info_nuked(self, db):
        """A non-sqlite .db beside valid -info must be nuked."""
        _write(db.path)
        _write_info(db)
        db._ensure_replica_consistency()
        assert not os.path.exists(db.path)
        assert not os.path.exists(db.path + "-info")

    def test_neither_exists_noop(self, db):
        db._ensure_replica_consistency()
        assert not os.path.exists(db.path)

    def test_db_without_info_nuked(self, db):
        _write(db.path)
        db._ensure_replica_consistency()
        assert not os.path.exists(db.path)

    def test_orphaned_info_nuked(self, db):
        _write_info(db)
        db._ensure_replica_consistency()
        assert not os.path.exists(db.path + "-info")

    def test_invalid_info_json_nuked(self, db):
        """Deploy-day upgrade: a non-pyturso -info means nuke + fresh bootstrap."""
        _write(db.path)
        _write_info(db, valid=False)
        db._ensure_replica_consistency()
        assert not os.path.exists(db.path)
        assert not os.path.exists(db.path + "-info")


def _corrupt_data_page(path, page_size=4096, page=601, rows=3000):
    """Build a real sqlite db and scribble over one data page.

    Page 1 (sqlite_master) stays intact, so the file still opens and reports
    its tables -- this is the corruption shape _db_has_tables() cannot see.
    """
    conn = sqlite3.connect(path)
    conn.execute(f"PRAGMA page_size={page_size}")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, payload BLOB)")
    conn.executemany(
        "INSERT INTO t (payload) VALUES (randomblob(1200))", [()] * rows
    )
    conn.commit()
    conn.close()
    with open(path, "r+b") as f:
        f.seek((page - 1) * page_size)
        f.write(b"\xde\xad\xbe\xef" * (page_size // 4))


class TestCorruptDataPage:
    """Characterizes the gap that sync(force_rebuild=True) closes.

    A replica corrupt only in a data page opens fine and lists its tables,
    so _ensure_replica_consistency() preserves it; an unchanged pull then
    returns through the no-change fast path with no integrity check. Only a
    caller that already saw a read fail can know a rebuild is needed.
    """

    def test_consistency_check_preserves_it_but_reads_fail(self, db):
        _corrupt_data_page(db.path)
        _write_info(db)

        assert db._db_has_tables() is True
        db._ensure_replica_consistency()
        assert os.path.exists(db.path), "consistency check kept the corrupt file"

        conn = sqlite3.connect(f"file:{db.path}?mode=ro", uri=True)
        try:
            with pytest.raises(sqlite3.DatabaseError, match="malformed"):
                conn.execute("SELECT count(*) FROM t").fetchone()
        finally:
            conn.close()

    def test_force_rebuild_removes_the_corrupt_file(self, db):
        _corrupt_data_page(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=False)
        seen = {}

        def fake_pull():
            seen["db_present_at_pull"] = os.path.exists(db.path)
            _make_db(db.path)
            _write_info(db)
            return conn.pull.return_value

        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "integrity_check", return_value=True
        ) as integrity_mock, patch.object(DatabaseConfig, "_dispose_local_connections"):
            conn.pull.side_effect = fake_pull
            result = db.sync(force_rebuild=True)

        assert seen["db_present_at_pull"] is False
        assert result == SyncResult(ok=True, changed=True)
        integrity_mock.assert_called_once()


class TestSync:
    def _run_sync(self, db, conn, integrity=True):
        def fake_pull_side_effect():
            # simulate pull creating/refreshing the replica pair
            _write(db.path)
            _write_info(db)
            return conn.pull.return_value

        with patch("config.tursosync.connect", return_value=conn) as connect_mock, patch.object(
            DatabaseConfig, "integrity_check", return_value=integrity
        ), patch.object(DatabaseConfig, "_dispose_local_connections"):
            conn.pull.side_effect = fake_pull_side_effect
            result = db.sync()
        return result, connect_mock

    def test_missing_credentials_raise(self, db):
        db.turso_url = None
        with pytest.raises(ValueError):
            db.sync()

    def test_pull_no_changes(self, db):
        _make_db(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=False)
        result, _ = self._run_sync(db, conn)
        assert result == SyncResult(ok=True, changed=False)
        conn.checkpoint.assert_called_once()
        conn.close.assert_called_once()

    def test_pull_with_changes(self, db):
        _make_db(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=True)
        result, _ = self._run_sync(db, conn)
        assert result == SyncResult(ok=True, changed=True)

    def test_fresh_bootstrap_counts_as_changed(self, db):
        conn = _mock_sync_conn(pull_returns=False)  # bootstrap then no-op pull
        result, _ = self._run_sync(db, conn)
        assert result.changed is True

    def test_force_rebuild_nukes_replica_and_checks_integrity(self, db):
        """A .db whose data pages are corrupt still satisfies
        _ensure_replica_consistency (sqlite_master reads fine), and an
        unchanged pull would return through the no-change fast path with no
        integrity check. force_rebuild removes the files first, so the pull
        is a fresh bootstrap and the check runs."""
        _make_db(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=False)
        seen = {}

        def fake_pull():
            seen["db_present_at_pull"] = os.path.exists(db.path)
            _write(db.path)
            _write_info(db)
            return conn.pull.return_value

        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "integrity_check", return_value=True
        ) as integrity_mock, patch.object(DatabaseConfig, "_dispose_local_connections"):
            conn.pull.side_effect = fake_pull
            result = db.sync(force_rebuild=True)

        assert seen["db_present_at_pull"] is False
        assert result == SyncResult(ok=True, changed=True)
        integrity_mock.assert_called_once()

    def test_ordinary_sync_keeps_a_consistent_replica(self, db):
        """The force_rebuild path must not leak into normal syncs: a valid
        replica is pulled into, never removed first."""
        _make_db(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=False)
        seen = {}

        def fake_pull():
            seen["db_present_at_pull"] = os.path.exists(db.path)
            return conn.pull.return_value

        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "integrity_check", return_value=True
        ), patch.object(DatabaseConfig, "_dispose_local_connections"):
            conn.pull.side_effect = fake_pull
            result = db.sync()

        assert seen["db_present_at_pull"] is True
        assert result == SyncResult(ok=True, changed=False)

    def test_pull_failure_on_fresh_file_cleans_up_and_raises(self, db):
        conn = MagicMock()

        def failing_pull():
            _write(db.path)  # connect created the file before dying
            raise RuntimeError("network down")

        conn.pull.side_effect = failing_pull
        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "_dispose_local_connections"
        ):
            with pytest.raises(RuntimeError):
                db.sync()
        assert not os.path.exists(db.path)  # no empty-file landmine left behind

    def test_pull_failure_on_existing_file_preserves_it(self, db):
        _make_db(db.path)
        _write_info(db)
        conn = MagicMock()
        conn.pull.side_effect = RuntimeError("network down")
        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "_dispose_local_connections"
        ):
            with pytest.raises(RuntimeError):
                db.sync()
        # network blip must not nuke a healthy file
        check = sqlite3.connect(f"file:{db.path}?mode=ro", uri=True)
        tables = check.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        check.close()
        assert tables == 1

    def test_integrity_failure_triggers_one_nuke_retry(self, db):
        _write(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=False)
        integrity_results = iter([False, True])

        def fake_pull():
            _write(db.path)
            _write_info(db)
            return False

        conn.pull.side_effect = fake_pull
        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "integrity_check", side_effect=lambda self=None: next(integrity_results)
        ), patch.object(DatabaseConfig, "_dispose_local_connections"):
            result = db.sync()
        assert result == SyncResult(ok=True, changed=True)
        assert conn.pull.call_count == 2

    def test_integrity_retry_pull_failure_cleans_up_landmine(self, db):
        """First pull succeeds but fails integrity; the retry pull then dies
        mid-flight (e.g. network drop). The exception must propagate, and no
        partial replica (.db / .db-info) may be left behind as a landmine."""
        _write(db.path)
        _write_info(db)
        conn = MagicMock()
        call_count = {"n": 0}

        def fake_pull():
            call_count["n"] += 1
            if call_count["n"] == 1:
                _write(db.path)
                _write_info(db)
                return False
            raise RuntimeError("network down mid-retry")

        conn.pull.side_effect = fake_pull
        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "integrity_check", return_value=False
        ), patch.object(DatabaseConfig, "_dispose_local_connections"):
            with pytest.raises(RuntimeError):
                db.sync()
        assert conn.pull.call_count == 2
        assert not os.path.exists(db.path)
        assert not os.path.exists(db.path + "-info")


class TestNoChangeFastPath:
    """A pull that applied nothing must not re-verify the replica.

    integrity_check reads the whole file (2.3 s on the 147 MB primary hub),
    which is pure waste when pull() reports that no byte of the replica
    changed -- see the startup performance evaluation.
    """

    def _run(self, db, pull_returns, integrity=True):
        conn = _mock_sync_conn(pull_returns=pull_returns)

        def fake_pull():
            _write(db.path)
            _write_info(db)
            return pull_returns

        conn.pull.side_effect = fake_pull
        with patch("config.tursosync.connect", return_value=conn), patch.object(
            DatabaseConfig, "integrity_check", return_value=integrity
        ) as integrity_mock, patch.object(
            DatabaseConfig, "_dispose_local_connections"
        ):
            result = db.sync()
        return result, integrity_mock

    def test_no_change_pull_skips_integrity_check(self, db):
        _make_db(db.path)
        _write_info(db)
        result, integrity_mock = self._run(db, pull_returns=False)
        integrity_mock.assert_not_called()
        assert result == SyncResult(ok=True, changed=False)

    def test_changed_pull_still_verifies(self, db):
        _make_db(db.path)
        _write_info(db)
        result, integrity_mock = self._run(db, pull_returns=True)
        integrity_mock.assert_called_once()
        assert result == SyncResult(ok=True, changed=True)

    def test_fresh_bootstrap_still_verifies(self, db):
        """No prior file: pull() reports changed=False but this is new data."""
        result, integrity_mock = self._run(db, pull_returns=False)
        integrity_mock.assert_called_once()
        assert result.changed is True
