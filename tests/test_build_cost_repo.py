"""Tests for BuildCostRepository _impl functions (read_df-based)."""

import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

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
    def test_returns_float(self):
        repo = _repo_returning(pd.DataFrame({"manufacturing": [0.0456]}))
        result = _get_manufacturing_cost_index_impl(repo, 30004759)
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 0.0456)
        _, kwargs = repo.read_df.call_args
        self.assertEqual(kwargs["params"], {"sid": 30004759})

    def test_raises_on_missing_system(self):
        repo = _repo_returning(pd.DataFrame({"manufacturing": []}))
        with self.assertRaises(ValueError):
            _get_manufacturing_cost_index_impl(repo, 99999)


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


if __name__ == "__main__":
    unittest.main()
