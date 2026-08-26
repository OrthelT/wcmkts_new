"""sync() state machine and pull flow (spec §1)."""

import json
import os
import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from config import DatabaseConfig, SyncResult, clear_degraded, get_degraded_aliases


@pytest.fixture
def db(tmp_path):
    db = DatabaseConfig.__new__(DatabaseConfig)
    db.alias = "testalias"
    db.path = str(tmp_path / "test.db")
    db.turso_url = "libsql://example.turso.io"
    db.token = "tok"
    yield db
    clear_degraded("testalias")


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


class TestSync:
    def _run_sync(self, db, conn, integrity=True):
        def fake_pull_side_effect():
            # simulate pull creating/refreshing the replica pair
            _write(db.path)
            _write_info(db)
            return conn.pull.return_value

        with patch("config.tursosync.connect", return_value=conn) as connect_mock, patch.object(
            DatabaseConfig, "integrity_check", return_value=integrity
        ), patch.object(DatabaseConfig, "_dispose_local_connections"), patch.object(
            DatabaseConfig, "snapshot_backup", return_value=True
        ) as snap_mock:
            conn.pull.side_effect = fake_pull_side_effect
            result = db.sync()
        return result, connect_mock, snap_mock

    def test_missing_credentials_raise(self, db):
        db.turso_url = None
        with pytest.raises(ValueError):
            db.sync()

    def test_pull_no_changes(self, db):
        _make_db(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=False)
        result, _, snap = self._run_sync(db, conn)
        assert result == SyncResult(ok=True, changed=False)
        conn.checkpoint.assert_called_once()
        conn.close.assert_called_once()
        snap.assert_called_once()

    def test_pull_with_changes(self, db):
        _make_db(db.path)
        _write_info(db)
        conn = _mock_sync_conn(pull_returns=True)
        result, _, _ = self._run_sync(db, conn)
        assert result == SyncResult(ok=True, changed=True)

    def test_fresh_bootstrap_counts_as_changed(self, db):
        conn = _mock_sync_conn(pull_returns=False)  # bootstrap then no-op pull
        result, _, _ = self._run_sync(db, conn)
        assert result.changed is True

    def test_success_clears_degraded(self, db):
        import config as config_module

        config_module._DEGRADED_REGISTRY["testalias"] = None
        _make_db(db.path)
        _write_info(db)
        result, _, _ = self._run_sync(db, _mock_sync_conn())
        assert result.ok
        assert "testalias" not in get_degraded_aliases()

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
        ), patch.object(DatabaseConfig, "_dispose_local_connections"), patch.object(
            DatabaseConfig, "snapshot_backup", return_value=True
        ):
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
