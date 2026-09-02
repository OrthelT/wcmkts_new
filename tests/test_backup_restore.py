"""snapshot_backup / restore_from_backup / degraded registry (spec §1)."""

from unittest.mock import patch

import pytest

import config as config_module
from config import DatabaseConfig, clear_degraded, get_degraded_aliases


@pytest.fixture
def db(tmp_path):
    """A DatabaseConfig pointed at a tmp path, bypassing alias resolution."""
    db = DatabaseConfig.__new__(DatabaseConfig)
    db.alias = "testalias"
    db.path = str(tmp_path / "test.db")
    db.turso_url = "libsql://example.turso.io"
    db.token = "tok"
    yield db
    clear_degraded("testalias")


# pyturso-shaped metadata: version "v1" plus a non-empty client_unique_id.
# restore_from_backup() refuses any other kind, so a libsql-era payload here
# would exercise the refusal instead of the restore path under test.
_PYTURSO_INFO = (
    '{"version":"v1","client_unique_id":"test-client-id",'
    '"durable_frame_num":1,"generation":1}'
)
_LIBSQL_INFO = '{"hash":1,"version":0,"durable_frame_num":1,"generation":1}'


def _write_live_pair(db, content=b"x" * 32, info=_PYTURSO_INFO):
    with open(db.path, "wb") as f:
        f.write(content)
    with open(db.path + "-info", "w") as f:
        f.write(info)


def test_snapshot_backup_copies_pair(db):
    _write_live_pair(db, b"livedata" * 4)
    assert db.snapshot_backup() is True
    with open(db.path + ".bak", "rb") as f:
        assert f.read() == b"livedata" * 4
    with open(db.path + "-info.bak") as f:
        assert '"generation":1' in f.read()
    # atomic copy leaves no temp files behind
    import glob

    assert glob.glob(db.path + "*.tmp") == []


def test_snapshot_backup_missing_source_returns_false(db):
    assert db.snapshot_backup() is False  # no live files at all


def test_restore_without_backup_leaves_live_files_untouched(db):
    _write_live_pair(db, b"malformed!")
    assert db.restore_from_backup() is False
    with open(db.path, "rb") as f:
        assert f.read() == b"malformed!"  # evidence preserved
    assert "testalias" not in get_degraded_aliases()


def test_restore_replaces_live_pair_and_registers_degraded(db):
    _write_live_pair(db, b"goodstate" * 4)
    assert db.snapshot_backup() is True
    _write_live_pair(db, b"corrupted")
    with open(db.path + "-wal", "wb") as f:
        f.write(b"wal")
    with open(db.path + "-changes", "wb") as f:
        f.write(b"chg")

    with patch.object(DatabaseConfig, "integrity_check", return_value=True), patch.object(
        DatabaseConfig, "_dispose_local_connections"
    ):
        assert db.restore_from_backup() is True

    with open(db.path, "rb") as f:
        assert f.read() == b"goodstate" * 4
    import os

    assert not os.path.exists(db.path + "-wal")
    assert not os.path.exists(db.path + "-changes")
    degraded = get_degraded_aliases()
    assert "testalias" in degraded
    assert degraded["testalias"].tzinfo is not None


def test_restore_failing_integrity_returns_false(db):
    _write_live_pair(db)
    db.snapshot_backup()
    with patch.object(DatabaseConfig, "integrity_check", return_value=False), patch.object(
        DatabaseConfig, "_dispose_local_connections"
    ):
        assert db.restore_from_backup() is False
    assert "testalias" not in get_degraded_aliases()


def test_restore_second_copy_failure_leaves_live_files_untouched(db):
    _write_live_pair(db, b"goodstate" * 4)
    assert db.snapshot_backup() is True
    _write_live_pair(db, b"original!")

    real_copy2 = config_module.shutil.copy2
    call_count = {"n": 0}

    def flaky_copy2(src, dst, *args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("disk error on second copy")
        return real_copy2(src, dst, *args, **kwargs)

    with patch.object(config_module.shutil, "copy2", side_effect=flaky_copy2):
        assert db.restore_from_backup() is False

    with open(db.path, "rb") as f:
        assert f.read() == b"original!"
    with open(db.path + "-info") as f:
        assert '"generation":1' in f.read()

    import glob

    assert glob.glob(db.path + "*.tmp") == []
    assert "testalias" not in get_degraded_aliases()


def test_clear_degraded_and_copy_semantics(db):
    config_module._DEGRADED_REGISTRY["testalias"] = None
    snapshot = get_degraded_aliases()
    snapshot["injected"] = None
    assert "injected" not in get_degraded_aliases()  # returns a copy
    clear_degraded("testalias")
    assert "testalias" not in get_degraded_aliases()
    clear_degraded("testalias")  # idempotent, no raise


@pytest.mark.parametrize(
    "info, kind",
    [(_LIBSQL_INFO, "libsql"), ("not json at all", "corrupt")],
)
def test_restore_refuses_non_pyturso_backup_metadata(db, info, kind, caplog):
    """A libsql-era or corrupt -info.bak is not a replica pyturso can open.

    Restoring it would overwrite the live pair and only then fail
    integrity_check(), destroying the diagnostic evidence for nothing.
    """
    import glob
    import os

    _write_live_pair(db, b"goodstate" * 4, info=info)
    assert db.snapshot_backup() is True
    _write_live_pair(db, b"corrupted", info=info)

    with patch.object(DatabaseConfig, "integrity_check", return_value=True), patch.object(
        DatabaseConfig, "_dispose_local_connections"
    ):
        assert db.restore_from_backup() is False

    with open(db.path, "rb") as f:
        assert f.read() == b"corrupted"  # live files untouched
    assert glob.glob(db.path + "*.tmp") == []
    assert "testalias" not in get_degraded_aliases()
    assert f"backup metadata is '{kind}'" in caplog.text
    assert os.path.exists(db.path + ".bak")  # backup left in place
