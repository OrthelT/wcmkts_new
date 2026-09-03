"""init_db file-state checks and single-flight bootstrap (spec §1 cold start)."""

import json
import os
import sqlite3
import threading
import time

import pytest

from init_db import ensure_market_db_ready, init_db, verify_db_content

VALID_INFO = (
    '{"version":"v1","client_unique_id":"test-client-id",'
    '"saved_configuration":{"remote_url":"https://example-orthelt.aws-us-east-1.turso.io"}}'
)


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


class TestLibsqlMetadataRejected:
    """A libsql-era -info parses as JSON, so the old checks accepted it and
    the first engine call raised turso.lib.DatabaseError."""

    def test_replica_metadata_valid_rejects_libsql(self, tmp_path):
        import json
        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.path = str(tmp_path / "m.db")
        (tmp_path / "m.db").write_bytes(b"x")
        (tmp_path / "m.db-info").write_text(
            json.dumps({"hash": "0" * 64, "version": 0, "generation": 1})
        )
        assert db._replica_metadata_valid() is False

    def test_verify_db_content_rejects_libsql(self, tmp_path):
        import json
        import sqlite3
        from init_db import verify_db_content

        p = tmp_path / "m.db"
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE t (a INTEGER)")
        con.commit()
        con.close()
        (tmp_path / "m.db-info").write_text(
            json.dumps({"hash": "0" * 64, "version": 0, "generation": 1})
        )
        assert verify_db_content(str(p)) is False

    def test_sync_refuses_live_replica_from_different_remote(self, tmp_path):
        # Valid pyturso metadata naming a test remote + configured production
        # URL must raise before _pull_once() or engine construction.
        import json
        import sqlite3

        import pytest
        from unittest.mock import patch

        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = "primary"
        db.path = str(tmp_path / "m.db")
        db.turso_url = "https://wcmktnewkeep-orthelt.aws-us-east-1.turso.io"
        db.token = "t"
        db._engine = None

        con = sqlite3.connect(db.path)
        con.execute("CREATE TABLE t (a INTEGER)")
        con.commit()
        con.close()

        (tmp_path / "m.db-info").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "client_unique_id": "test-client-id",
                    "saved_configuration": {
                        "remote_url": "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io"
                    },
                }
            )
        )

        with patch("config.tursosync.connect") as connect_mock:
            with pytest.raises(RuntimeError, match="different Turso remote"):
                db.sync()
        connect_mock.assert_not_called()

    def test_restore_refuses_backup_from_different_remote(self, tmp_path):
        # A .db.bak/.db-info.bak pair from test must not be restored after
        # production secrets are configured.
        import json

        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = "primary"
        db.path = str(tmp_path / "m.db")
        db.turso_url = "https://wcmktnewkeep-orthelt.aws-us-east-1.turso.io"
        db.token = "t"
        db._engine = None

        (tmp_path / "m.db.bak").write_bytes(b"x" * 16)
        (tmp_path / "m.db-info.bak").write_text(
            json.dumps(
                {
                    "version": "v1",
                    "client_unique_id": "test-client-id",
                    "saved_configuration": {
                        "remote_url": "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io"
                    },
                }
            )
        )

        assert db.restore_from_backup() is False
        assert not (tmp_path / "m.db").exists()
        assert not (tmp_path / "m.db-info").exists()


class TestRemoteMatchesMetadata:
    """Frontend equivalent of the backend's TestRemoteMatchesMetadata: pins
    remote_matches_metadata()'s netloc+path comparison and None-on-unknown
    semantics against the real frontend DatabaseConfig."""

    PYTURSO_INFO = {
        "version": "v1",
        "client_unique_id": "test-client-id",
        "saved_configuration": {
            "remote_url": "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io"
        },
    }

    def _db(self, tmp_path, url):
        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = "primary"
        db.path = str(tmp_path / "market.db")
        db.turso_url = url
        db.token = "t"
        db._engine = None
        return db

    def _write_info(self, tmp_path, payload):
        import json

        (tmp_path / "market.db-info").write_text(json.dumps(payload))

    def test_matching_remote(self, tmp_path):
        db = self._db(tmp_path, "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io")
        self._write_info(tmp_path, self.PYTURSO_INFO)
        assert db.remote_matches_metadata() is True

    def test_mismatched_remote(self, tmp_path):
        db = self._db(tmp_path, "https://wcmktnewkeep-orthelt.aws-us-east-1.turso.io")
        self._write_info(tmp_path, self.PYTURSO_INFO)
        assert db.remote_matches_metadata() is False

    def test_scheme_and_trailing_slash_ignored(self, tmp_path):
        db = self._db(tmp_path, "libsql://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io/")
        self._write_info(tmp_path, self.PYTURSO_INFO)
        assert db.remote_matches_metadata() is True

    def test_unknown_without_metadata(self, tmp_path):
        db = self._db(tmp_path, "https://anything.turso.io")
        assert db.remote_matches_metadata() is None

    def test_unknown_without_configured_url(self, tmp_path):
        db = self._db(tmp_path, None)
        self._write_info(tmp_path, self.PYTURSO_INFO)
        assert db.remote_matches_metadata() is None

    def test_remote_key_ignores_scheme_and_trailing_slash(self):
        from config import DatabaseConfig

        a = DatabaseConfig._remote_key("https://host.turso.io/")
        b = DatabaseConfig._remote_key("libsql://host.turso.io")
        assert a == b == "host.turso.io"

    def test_remote_key_distinguishes_different_hosts(self):
        from config import DatabaseConfig

        assert DatabaseConfig._remote_key(
            "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io"
        ) != DatabaseConfig._remote_key(
            "https://wcmktnewkeep-orthelt.aws-us-east-1.turso.io"
        )


class TestEngineRemoteGuard:
    """The engine property must refuse a replica bootstrapped against a
    different Turso remote.

    init_db.verify_db_content() returns True for any replica with tables and
    pyturso-shaped metadata without comparing remotes, so init_db() marks it
    initialized and never syncs it — sync()'s guard is not on the read path.
    Without a guard at the engine, pointing secrets.toml at production while
    a `…test` replica sits on disk serves test data indefinitely.
    """

    PYTURSO_INFO = TestRemoteMatchesMetadata.PYTURSO_INFO
    MATCHING_URL = "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io"
    OTHER_URL = "https://wcmktnewkeep-orthelt.aws-us-east-1.turso.io"

    @pytest.fixture(autouse=True)
    def _isolate_engine_cache(self):
        from config import DatabaseConfig

        saved = dict(DatabaseConfig._engines)
        yield
        DatabaseConfig._engines.clear()
        DatabaseConfig._engines.update(saved)

    def _db(self, tmp_path, url, alias):
        from config import DatabaseConfig

        db = DatabaseConfig.__new__(DatabaseConfig)
        db.alias = alias
        db.path = str(tmp_path / "market.db")
        db.url = f"sqlite+turso_sync:///{db.path}"
        db.turso_url = url
        db.token = "t"
        db._connect_args = {"remote_url": url, "auth_token": "t"}
        db._engine = None
        return db

    def _write_info(self, tmp_path):
        (tmp_path / "market.db-info").write_text(json.dumps(self.PYTURSO_INFO))

    def test_engine_refuses_replica_from_a_different_remote(self, tmp_path):
        db = self._db(tmp_path, self.OTHER_URL, "guard-mismatch")
        self._write_info(tmp_path)
        assert db.remote_matches_metadata() is False
        with pytest.raises(RuntimeError, match="different Turso remote"):
            db.engine

    def test_engine_opens_on_a_matching_remote(self, tmp_path):
        db = self._db(tmp_path, self.MATCHING_URL, "guard-match")
        self._write_info(tmp_path)
        assert db.remote_matches_metadata() is True
        assert db.engine is not None

    def test_engine_opens_when_the_remote_is_unknown(self, tmp_path):
        # No -info sidecar: remote_matches_metadata() is None, not False,
        # and an unknown remote must stay a no-op (backend semantics).
        db = self._db(tmp_path, self.MATCHING_URL, "guard-unknown")
        assert db.remote_matches_metadata() is None
        assert db.engine is not None
