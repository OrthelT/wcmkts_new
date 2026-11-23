"""Tests for BuildCostRepository _impl functions (read_df-based)."""

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from sqlalchemy import create_engine

from repositories import build_cost_repo
from build_cost_models import Base as BuildCostBase, Rig, Structure, StructureRig
from repositories.build_cost_repo import (
    INVALID_RIG_IDS,
    BuildCostRepository,
    _get_structure_rigs_impl,
    _get_manufacturing_cost_index_impl,
    _get_all_structures_impl,
    _write_industry_index_impl,
)


class _SqliteReader:
    """Stands in for BaseRepository: read_df runs the query on a real SQLite DB."""

    def __init__(self, engine):
        self.engine = engine

    def read_df(self, query, params=None):
        with self.engine.connect() as conn:
            return pd.read_sql_query(query, conn, params=params)


def _structure(sid, name, *, m=0, c=0, s=0, is_open=1):
    return Structure(
        structure_id=sid, structure=name, structure_type="Sotiyo",
        structure_type_id=35827, system_id=1, tax=0.01,
        has_manufacturing_plant=m, has_capital_shipyard=c,
        has_supercapital_shipyard=s, is_open=is_open,
    )


@pytest.fixture
def buildcost_reader(tmp_path):
    from sqlalchemy.orm import Session

    engine = create_engine(f"sqlite:///{tmp_path / 'buildcost.db'}")
    BuildCostBase.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all([
            _structure(1, "A Manufacturing", m=1),
            _structure(2, "B Capital", m=1, c=1),
            _structure(3, "C Super", c=0, s=1),
            _structure(4, "D Closed", m=1, is_open=0),
            Rig(type_id=100, type_name="Rig A", icon_id=0),
            Rig(type_id=INVALID_RIG_IDS[0], type_name="Invalid Rig", icon_id=0),
            StructureRig(structure_id=1, rig_type_id=100),
            StructureRig(structure_id=1, rig_type_id=INVALID_RIG_IDS[0]),
            StructureRig(structure_id=2, rig_type_id=100),
        ])
        session.commit()
    yield _SqliteReader(engine)
    engine.dispose()


def _names(df):
    return list(df["structure"])


class TestGetAllStructuresImpl:
    """_get_all_structures_impl returns a DataFrame — the cache layer pickles
    its value, so row conversion happens in the repo method instead."""

    def test_manufacturing_plant_filter_excludes_closed(self, buildcost_reader):
        df = _get_all_structures_impl(buildcost_reader, ("has_manufacturing_plant",), False)
        assert _names(df) == ["A Manufacturing", "B Capital"]

    def test_include_closed_adds_closed_structures(self, buildcost_reader):
        df = _get_all_structures_impl(buildcost_reader, ("has_manufacturing_plant",), True)
        assert _names(df) == ["A Manufacturing", "B Capital", "D Closed"]

    def test_capital_accepts_capital_or_super_shipyard(self, buildcost_reader):
        flags = ("has_capital_shipyard", "has_supercapital_shipyard")
        df = _get_all_structures_impl(buildcost_reader, flags, False)
        assert _names(df) == ["B Capital", "C Super"]

    def test_super_requires_super_shipyard(self, buildcost_reader):
        df = _get_all_structures_impl(buildcost_reader, ("has_supercapital_shipyard",), False)
        assert _names(df) == ["C Super"]

    @pytest.mark.parametrize("flags", [(), ("is_open",), ("1=1 OR has_manufacturing_plant",)])
    def test_rejects_unknown_flags(self, buildcost_reader, flags):
        with pytest.raises(ValueError):
            _get_all_structures_impl(buildcost_reader, flags, False)


class TestGetStructureRigsImpl:
    def test_joins_rig_names_and_drops_invalid_rigs(self, buildcost_reader):
        df = _get_structure_rigs_impl(buildcost_reader)
        rows = list(df[["structure_id", "structure", "rig_type_id", "rig_name"]].itertuples(index=False, name=None))
        assert rows == [(1, "A Manufacturing", 100, "Rig A"), (2, "B Capital", 100, "Rig A")]


class TestStructureRigMethods:
    @patch("repositories.build_cost_repo._get_structure_rigs_cached")
    def test_groups_rigs_by_structure(self, mock_cached):
        mock_cached.return_value = pd.DataFrame({
            "structure_id": [1, 1, 2],
            "structure": ["A", "A", "B"],
            "rig_type_id": [100, 200, 100],
            "rig_name": ["Rig A", "Rig B", "Rig A"],
        })
        repo = BuildCostRepository.__new__(BuildCostRepository)
        repo._cache_key = "url"
        assert repo.get_structure_rigs() == {"A": ["Rig A", "Rig B"], "B": ["Rig A"]}
        assert repo.get_structure_rig_ids() == {1: [100, 200], 2: [100]}


class TestGetManufacturingCostIndexImpl(unittest.TestCase):
    """industry_index reads come from the local ESI cache DB, not through
    BaseRepository/read_df — its recovery ladder syncs the shared replica,
    which is the wrong policy for a disposable local cache."""

    def setUp(self):
        self._orig_cache_db = build_cost_repo._CACHE_DB

    def tearDown(self):
        build_cost_repo._CACHE_DB = self._orig_cache_db
        build_cost_repo._cache_engine.cache_clear()

    def _use_tmp_cache(self, tmp_path):
        build_cost_repo._CACHE_DB = tmp_path / "streamlit_cache.db"
        build_cost_repo._cache_engine.cache_clear()

    def test_returns_float(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._use_tmp_cache(Path(tmp))
            _write_industry_index_impl(
                pd.DataFrame(
                    {"solar_system_id": [30004759], "manufacturing": [0.0456]}
                )
            )
            result = _get_manufacturing_cost_index_impl(30004759)
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 0.0456)

    def test_raises_on_missing_system(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._use_tmp_cache(Path(tmp))
            _write_industry_index_impl(
                pd.DataFrame({"solar_system_id": [1], "manufacturing": [0.01]})
            )
            with self.assertRaises(ValueError):
                _get_manufacturing_cost_index_impl(99999)

    def test_raises_cleanly_when_table_does_not_exist(self):
        """A cache miss (table never created) is a clean ValueError, not a
        DB error surfaced to the page."""
        with tempfile.TemporaryDirectory() as tmp:
            self._use_tmp_cache(Path(tmp))
            with self.assertRaises(ValueError):
                _get_manufacturing_cost_index_impl(99999)


class TestGetAllStructuresMethod(unittest.TestCase):
    @patch("repositories.build_cost_repo._get_all_structures_cached")
    def test_converts_cached_df_to_attribute_rows(self, mock_cached):
        """The cache layer stores a DataFrame (picklable); the repo method
        converts it to attribute-access rows for consumers."""
        mock_cached.return_value = pd.DataFrame(
            {"structure": ["Fortizar"], "system_id": [30004759]}
        )
        repo = BuildCostRepository.__new__(BuildCostRepository)
        repo._cache_key = "url"
        rows = BuildCostRepository.get_all_structures(repo, ["has_manufacturing_plant"])
        self.assertEqual(rows[0].structure, "Fortizar")
        # The cache key must be hashable, so a list of flags becomes a tuple.
        mock_cached.assert_called_once_with("url", ("has_manufacturing_plant",), False)


class TestIndustryIndexIsLocalOnly:
    """industry_index is a per-viewer ESI cache, not shared market data. It
    must not put DDL into the CDC queue of the shared buildcost replica."""

    @pytest.fixture(autouse=True)
    def _reset_cache_engine(self):
        yield
        build_cost_repo._cache_engine.cache_clear()

    def _patch_cache(self, monkeypatch, tmp_path):
        cache_path = tmp_path / "streamlit_cache.db"
        monkeypatch.setattr(build_cost_repo, "_CACHE_DB", cache_path)
        build_cost_repo._cache_engine.cache_clear()
        return cache_path

    @staticmethod
    def _table_exists(db_path, table_name) -> bool:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()
        return row is not None

    def test_written_to_the_cache_db_not_buildcost(self, tmp_path, monkeypatch):
        cache_path = self._patch_cache(monkeypatch, tmp_path)
        buildcost_path = tmp_path / "buildcost.db"
        buildcost_engine = create_engine(f"sqlite:///{buildcost_path}")

        fake_db = MagicMock()
        fake_db.engine = buildcost_engine
        repo = BuildCostRepository.__new__(BuildCostRepository)
        repo.db = fake_db

        df = pd.DataFrame({"solar_system_id": [30004759], "manufacturing": [0.05]})
        repo.write_industry_index(df)

        buildcost_engine.dispose()

        assert not self._table_exists(buildcost_path, "industry_index")
        assert self._table_exists(cache_path, "industry_index")

        with sqlite3.connect(cache_path) as conn:
            rows = conn.execute(
                "SELECT solar_system_id, manufacturing FROM industry_index"
            ).fetchall()
        assert rows == [(30004759, 0.05)]

    def test_buildcost_replica_untouched_by_a_page_load(self, tmp_path, monkeypatch):
        """Run the refresh path end-to-end (service -> repo -> write) and
        confirm the shared buildcost replica never gets the table.

        Do not use mtime as the oracle: opening SQLite can legitimately
        update sidecars without changing application data.
        """
        cache_path = self._patch_cache(monkeypatch, tmp_path)
        buildcost_path = tmp_path / "buildcost.db"
        buildcost_engine = create_engine(f"sqlite:///{buildcost_path}")
        # Make sure the file exists on disk before we assert on it.
        with buildcost_engine.connect():
            pass

        fake_db = MagicMock()
        fake_db.engine = buildcost_engine
        repo = BuildCostRepository.__new__(BuildCostRepository)
        repo.db = fake_db

        from services.build_cost_service import BuildCostService

        service = BuildCostService(repo)

        systems_data = [
            {
                "solar_system_id": 30004759,
                "cost_indices": [
                    {"activity": "manufacturing", "cost_index": 0.0456},
                ],
            }
        ]

        class _FakeResponse:
            status_code = 200
            headers = {
                "ETag": 'W/"abc"',
                "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                "Expires": "Mon, 01 Jan 2024 02:00:00 GMT",
            }

            def json(self):
                return systems_data

            def raise_for_status(self):
                pass

        with patch(
            "services.build_cost_service.requests.get",
            return_value=_FakeResponse(),
        ):
            service.check_and_update_industry_index(expires=None, etag=None)

        buildcost_engine.dispose()

        assert not self._table_exists(buildcost_path, "industry_index")
        assert self._table_exists(cache_path, "industry_index")


if __name__ == "__main__":
    unittest.main()
