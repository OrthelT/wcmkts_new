"""Shape checks for the pyturso -info sidecar.

A libsql-era -info is valid JSON, so an existence check or a bare
json.loads() accepts it and every later engine call raises
turso.lib.DatabaseError. These fixtures pin the discriminators.
"""
import json

import pytest

from replica_metadata import (
    classify_metadata,
    metadata_remote_url,
)

PYTURSO_INFO = {
    "version": "v1",
    "client_unique_id": "turso-sync-py-2d5e3bef-a5f3-407c-a807-e386e2ee1c0e",
    "synced_revision": {"type": "v1", "revision": "{}"},
    "last_pull_unix_time": 1787620313,
    "last_push_unix_time": 1787620467,
    "saved_configuration": {
        "remote_url": "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io"
    },
}
LIBSQL_INFO = {"hash": "0" * 64, "version": 0, "generation": 1}


@pytest.fixture
def db_path(tmp_path):
    p = tmp_path / "sample.db"
    p.write_bytes(b"")
    return p


def write_info(db_path, payload):
    (db_path.parent / f"{db_path.name}-info").write_text(
        payload if isinstance(payload, str) else json.dumps(payload)
    )


def test_pyturso_metadata_classified(db_path):
    write_info(db_path, PYTURSO_INFO)
    assert classify_metadata(db_path) == "pyturso"


def test_libsql_metadata_classified(db_path):
    write_info(db_path, LIBSQL_INFO)
    assert classify_metadata(db_path) == "libsql"


def test_non_json_is_corrupt(db_path):
    write_info(db_path, "not json at all")
    assert classify_metadata(db_path) == "corrupt"


def test_json_of_unknown_shape_is_corrupt(db_path):
    write_info(db_path, {"something": "else"})
    assert classify_metadata(db_path) == "corrupt"


def test_json_scalar_is_corrupt(db_path):
    write_info(db_path, "42")
    assert classify_metadata(db_path) == "corrupt"


def test_absent_metadata_is_missing(db_path):
    assert classify_metadata(db_path) == "missing"


def test_orphaned_metadata_still_classified(tmp_path):
    """No .db beside it. Classification describes the -info only."""
    orphan = tmp_path / "gone.db"
    write_info(orphan, PYTURSO_INFO)
    assert classify_metadata(orphan) == "pyturso"


def test_empty_string_version_is_not_pyturso(db_path):
    write_info(db_path, {**PYTURSO_INFO, "version": ""})
    assert classify_metadata(db_path) == "corrupt"


def test_empty_client_unique_id_is_not_pyturso(db_path):
    write_info(db_path, {**PYTURSO_INFO, "client_unique_id": ""})
    assert classify_metadata(db_path) == "corrupt"


def test_non_string_client_unique_id_is_not_pyturso(db_path):
    write_info(db_path, {**PYTURSO_INFO, "client_unique_id": 123})
    assert classify_metadata(db_path) == "corrupt"


def test_unknown_string_version_is_not_silently_accepted(db_path):
    write_info(db_path, {**PYTURSO_INFO, "version": "v999"})
    assert classify_metadata(db_path) == "corrupt"


def test_remote_url_read_from_metadata(db_path):
    write_info(db_path, PYTURSO_INFO)
    assert metadata_remote_url(db_path) == (
        "https://wcmktnewkeeptest-orthelt.aws-us-east-1.turso.io"
    )


def test_remote_url_none_when_metadata_missing(db_path):
    assert metadata_remote_url(db_path) is None


def test_remote_url_none_when_metadata_libsql(db_path):
    write_info(db_path, LIBSQL_INFO)
    assert metadata_remote_url(db_path) is None

