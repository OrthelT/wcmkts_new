"""DatabaseConfig.get_sde_version must not touch a missing/uninitialized replica."""

import os
from unittest.mock import patch

import pytest

from config import DatabaseConfig


def test_missing_replica_returns_none_without_creating_file(tmp_path):
    db = DatabaseConfig("sde")
    missing = str(tmp_path / "sdelite_missing.db")
    with patch.object(db, "path", missing), patch.object(
        DatabaseConfig, "engine", new_callable=lambda: property(lambda self: pytest.fail("engine opened"))
    ):
        assert db.get_sde_version() is None
    assert not os.path.exists(missing)


def test_wrong_alias_raises():
    with pytest.raises(ValueError):
        DatabaseConfig("build_cost").get_sde_version()
