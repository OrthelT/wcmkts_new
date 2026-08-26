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
from repositories.build_cost_repo import (
    INVALID_RIG_IDS,
    SUPER_SHIPYARD_ID,
    VALID_STRUCTURE_TYPE_IDS,
    BuildCostRepository,
    _fetch_rigs_impl,
    _get_valid_rigs_impl,
    _get_structure_rigs_impl,
    _get_manufacturing_cost_index_impl,
    _get_all_structures_impl,
    _write_industry_index_impl,
)


def _repo_returning(*dfs):
    """Fake BaseRepository whose read_df returns the given DataFrames in order."""
    repo = MagicMock()
    if len(dfs) == 1:
        repo.read_df.return_value = dfs[0]
    else:
        repo.read_df.side_effect = list(dfs)
    return repo


class TestFetchRigsImpl(unittest.TestCase):
    def test_returns_dict_from_query(self):
        repo = _repo_returning(
            pd.DataFrame({"type_name": ["Rig A", "Rig B"], "type_id": [100, 200]})
        )
        result = _fetch_rigs_impl(repo)
        self.assertEqual(result, {"Rig A": 100, "Rig B": 200})


class TestGetValidRigsImpl(unittest.TestCase):
    def test_filters_invalid_rig_ids(self):
        repo = _repo_returning(
            pd.DataFrame(
                {
                    "type_name": ["Valid Rig", "Invalid Rig"],
                    "type_id": [999, INVALID_RIG_IDS[0]],
                }
            )
        )
        result = _get_valid_rigs_impl(repo)
        self.assertIn("Valid Rig", result)
        self.assertNotIn("Invalid Rig", result)


class TestGetStructureRigsImpl(unittest.TestCase):
    def test_maps_structures_to_clean_rigs(self):
        rigs_df = pd.DataFrame({"type_name": ["Good Rig"], "type_id": [999]})
        structures_df = pd.DataFrame(
            {
                "structure": ["Azbel"],
                "rig_1": ["Good Rig"],
                "rig_2": ["0"],
                "rig_3": [None],
            }
        )
        repo = _repo_returning(rigs_df, structures_df)
        result = _get_structure_rigs_impl(repo)
        self.assertEqual(result, {"Azbel": ["Good Rig"]})

    def test_structure_query_uses_expanding_ids_param(self):
        repo = _repo_returning(
            pd.DataFrame({"type_name": [], "type_id": []}),
            pd.DataFrame({"structure": [], "rig_1": [], "rig_2": [], "rig_3": []}),
        )
        _get_structure_rigs_impl(repo)
        _, kwargs = repo.read_df.call_args
        self.assertEqual(kwargs["params"], {"ids": VALID_STRUCTURE_TYPE_IDS})


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


class TestGetAllStructuresImpl(unittest.TestCase):
    """_get_all_structures_impl returns a DataFrame — the cache layer pickles
    its value, so row conversion happens in the repo method instead."""

    def test_super_mode_filters_by_shipyard(self):
        df = pd.DataFrame({"structure": ["Super Structure"], "system_id": [1]})
        repo = _repo_returning(df)
        result = _get_all_structures_impl(repo, is_super=True)
        _, kwargs = repo.read_df.call_args
        self.assertEqual(kwargs["params"], {"sid": SUPER_SHIPYARD_ID})
        pd.testing.assert_frame_equal(result, df)

    def test_non_super_excludes_shipyard(self):
        df = pd.DataFrame(
            {"structure": ["Structure A", "Structure B"], "system_id": [1, 2]}
        )
        repo = _repo_returning(df)
        result = _get_all_structures_impl(repo, is_super=False)
        _, kwargs = repo.read_df.call_args
        self.assertEqual(
            kwargs["params"],
            {"sid": SUPER_SHIPYARD_ID, "ids": VALID_STRUCTURE_TYPE_IDS},
        )
        self.assertEqual(len(result), 2)


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
        rows = BuildCostRepository.get_all_structures(repo, is_super=False)
        self.assertEqual(rows[0].structure, "Fortizar")


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
