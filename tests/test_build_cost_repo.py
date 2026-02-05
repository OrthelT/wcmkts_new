"""Tests for BuildCostRepository _impl functions."""

import unittest
from unittest.mock import MagicMock, patch

from repositories.build_cost_repo import (
    INVALID_RIG_IDS,
    SUPER_SHIPYARD_ID,
    VALID_STRUCTURE_TYPE_IDS,
    _fetch_rigs_impl,
    _get_valid_rigs_impl,
    _get_manufacturing_cost_index_impl,
    _get_all_structures_impl,
    _get_rig_id_impl,
    _get_system_id_impl,
)


class TestFetchRigsImpl(unittest.TestCase):
    def test_returns_dict_from_query(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("Rig A", 100),
            ("Rig B", 200),
        ]
        result = _fetch_rigs_impl(mock_engine)
        self.assertEqual(result, {"Rig A": 100, "Rig B": 200})


class TestGetValidRigsImpl(unittest.TestCase):
    def test_filters_invalid_rig_ids(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        # Include one invalid rig (46640) and one valid
        mock_conn.execute.return_value.fetchall.return_value = [
            ("Valid Rig", 999),
            ("Invalid Rig", INVALID_RIG_IDS[0]),
        ]
        result = _get_valid_rigs_impl(mock_engine)
        self.assertIn("Valid Rig", result)
        self.assertNotIn("Invalid Rig", result)


class TestGetManufacturingCostIndexImpl(unittest.TestCase):
    def test_returns_float(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        mock_conn.execute.return_value.scalar.return_value = 0.0456
        result = _get_manufacturing_cost_index_impl(mock_engine, 30004759)
        self.assertIsInstance(result, float)
        self.assertAlmostEqual(result, 0.0456)

    def test_raises_on_missing_system(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        mock_conn.execute.return_value.scalar.return_value = None
        with self.assertRaises(ValueError):
            _get_manufacturing_cost_index_impl(mock_engine, 99999)


class TestGetAllStructuresImpl(unittest.TestCase):
    def test_super_mode_filters_by_shipyard(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        mock_conn.execute.return_value.fetchall.return_value = [("Super Structure",)]

        result = _get_all_structures_impl(mock_engine, is_super=True)
        call_args = mock_conn.execute.call_args
        sql = str(call_args[0][0])
        self.assertIn(str(SUPER_SHIPYARD_ID), sql)
        self.assertEqual(len(result), 1)

    def test_non_super_excludes_shipyard(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        mock_conn.execute.return_value.fetchall.return_value = [
            ("Structure A",),
            ("Structure B",),
        ]

        result = _get_all_structures_impl(mock_engine, is_super=False)
        call_args = mock_conn.execute.call_args
        sql = str(call_args[0][0])
        self.assertIn(f"structure_id != {SUPER_SHIPYARD_ID}", sql)
        self.assertEqual(len(result), 2)


class TestGetRigIdImpl(unittest.TestCase):
    def test_none_rig_name(self):
        result = _get_rig_id_impl(MagicMock(), None)
        self.assertIsNone(result)

    def test_zero_rig_name(self):
        result = _get_rig_id_impl(MagicMock(), "0")
        self.assertIsNone(result)


class TestGetSystemIdImpl(unittest.TestCase):
    def test_returns_system_id(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        mock_conn.execute.return_value.scalar.return_value = 30004759
        result = _get_system_id_impl(mock_engine, "4-HWWF")
        self.assertEqual(result, 30004759)

    def test_raises_on_missing(self):
        mock_engine = MagicMock()
        mock_conn = mock_engine.connect().__enter__()
        mock_conn.execute.return_value.scalar.return_value = None
        with self.assertRaises(ValueError):
            _get_system_id_impl(mock_engine, "Nonexistent")


if __name__ == "__main__":
    unittest.main()
