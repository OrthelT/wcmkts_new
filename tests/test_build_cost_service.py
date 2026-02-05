"""Tests for BuildCostService."""

import datetime
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

from services.build_cost_service import (
    BuildCostJob,
    BuildCostService,
    SUPER_GROUP_IDS,
)


class TestBuildCostJob(unittest.TestCase):
    def test_is_super_true_for_titans(self):
        job = BuildCostJob(item="Avatar", item_id=11567, group_id=30, runs=1, me=0, te=0)
        self.assertTrue(job.is_super)

    def test_is_super_true_for_supercarriers(self):
        job = BuildCostJob(item="Nyx", item_id=23913, group_id=659, runs=1, me=0, te=0)
        self.assertTrue(job.is_super)

    def test_is_super_false_for_regular_ship(self):
        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        self.assertFalse(job.is_super)

    def test_default_values(self):
        job = BuildCostJob(item="Test", item_id=1, group_id=1, runs=1, me=0, te=0)
        self.assertEqual(job.security, "NULL_SEC")
        self.assertEqual(job.system_cost_bonus, 0.0)
        self.assertEqual(job.material_prices, "ESI_AVG")


class TestBuildCostServiceBuildUrls(unittest.TestCase):
    def _make_service(self):
        repo = MagicMock()
        return BuildCostService(repo), repo

    def _make_structure(self, name="Test Station", rig1="Rig A", rig2=None, rig3=None):
        s = MagicMock()
        s.structure = name
        s.structure_type = "Sotiyo"
        s.structure_type_id = 35827
        s.rig_1 = rig1
        s.rig_2 = rig2
        s.rig_3 = rig3
        s.system_id = 30004759
        s.tax = 0.1
        return s

    def test_build_urls_returns_list(self):
        service, repo = self._make_service()
        structure = self._make_structure()
        repo.get_all_structures.return_value = [structure]
        repo.get_valid_rigs.return_value = {"Rig A": 100}
        repo.get_manufacturing_cost_index.return_value = 0.05

        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        urls = service.build_urls(job)

        self.assertEqual(len(urls), 1)
        url, name, stype = urls[0]
        self.assertIn("product_id=24690", url)
        self.assertIn("rig_id=100", url)
        self.assertEqual(name, "Test Station")

    def test_build_urls_filters_invalid_rigs(self):
        service, repo = self._make_service()
        structure = self._make_structure(rig1="Invalid Rig", rig2="Valid Rig")
        repo.get_all_structures.return_value = [structure]
        # "Invalid Rig" not in valid_rigs, so it gets filtered
        repo.get_valid_rigs.return_value = {"Valid Rig": 200}
        repo.get_manufacturing_cost_index.return_value = 0.05

        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        urls = service.build_urls(job)

        url = urls[0][0]
        self.assertNotIn("Invalid Rig", url)
        self.assertIn("rig_id=200", url)

    def test_build_urls_no_rigs(self):
        service, repo = self._make_service()
        structure = self._make_structure(rig1=None, rig2=None, rig3=None)
        repo.get_all_structures.return_value = [structure]
        repo.get_valid_rigs.return_value = {}
        repo.get_manufacturing_cost_index.return_value = 0.05

        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        urls = service.build_urls(job)

        url = urls[0][0]
        self.assertNotIn("rig_id=", url)


class TestIsSuperGroup(unittest.TestCase):
    def test_super_groups(self):
        for gid in SUPER_GROUP_IDS:
            self.assertTrue(BuildCostService.is_super_group(gid))

    def test_non_super_group(self):
        self.assertFalse(BuildCostService.is_super_group(25))


class TestCheckAndUpdateIndustryIndex(unittest.TestCase):
    def test_not_expired_returns_none_tuple(self):
        service, repo = self._make_service()
        future = datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)
        result = service.check_and_update_industry_index(expires=future, etag="abc")
        self.assertEqual(result, (None, None, None))

    def test_expired_triggers_fetch(self):
        service, repo = self._make_service()
        past = datetime.datetime.now(datetime.UTC) - datetime.timedelta(hours=1)

        with patch.object(service, '_fetch_and_store_industry_index') as mock_fetch:
            mock_fetch.return_value = (
                datetime.datetime.now(datetime.UTC),
                datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1),
                "new-etag",
            )
            result = service.check_and_update_industry_index(expires=past, etag="old")
            mock_fetch.assert_called_once_with("old")
            self.assertIsNotNone(result[0])

    def test_none_expires_triggers_fetch(self):
        service, repo = self._make_service()

        with patch.object(service, '_fetch_and_store_industry_index') as mock_fetch:
            mock_fetch.return_value = (None, None, None)
            service.check_and_update_industry_index(expires=None, etag=None)
            mock_fetch.assert_called_once()

    def _make_service(self):
        repo = MagicMock()
        return BuildCostService(repo), repo


class TestParseIndustryData(unittest.TestCase):
    def test_parse_valid_data(self):
        sample = [
            {
                "solar_system_id": 30000001,
                "cost_indices": [
                    {"activity": "manufacturing", "cost_index": 0.05},
                    {"activity": "copying", "cost_index": 0.02},
                ],
            },
        ]
        df = BuildCostService._parse_industry_data(sample)
        self.assertIn("solar_system_id", df.columns)
        self.assertIn("manufacturing", df.columns)
        self.assertEqual(len(df), 1)
        self.assertAlmostEqual(df["manufacturing"].iloc[0], 0.05)


class TestGetCostsSync(unittest.TestCase):
    @patch("services.build_cost_service.requests.get")
    def test_sync_with_progress_callback(self, mock_get):
        repo = MagicMock()
        service = BuildCostService(repo)

        structure = MagicMock()
        structure.structure = "Test Station"
        structure.structure_type = "Sotiyo"
        structure.structure_type_id = 35827
        structure.rig_1 = None
        structure.rig_2 = None
        structure.rig_3 = None
        structure.system_id = 30004759
        structure.tax = 0.1
        repo.get_all_structures.return_value = [structure]
        repo.get_valid_rigs.return_value = {}
        repo.get_manufacturing_cost_index.return_value = 0.05

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "manufacturing": {
                "24690": {
                    "units": 1,
                    "total_cost": 100000,
                    "total_cost_per_unit": 100000,
                    "total_material_cost": 80000,
                    "facility_tax": 5000,
                    "scc_surcharge": 3000,
                    "system_cost_index": 2000,
                    "total_job_cost": 10000,
                    "materials": {},
                }
            }
        }
        mock_response.text = "{}"
        mock_get.return_value = mock_response

        progress_calls = []
        def track_progress(c, t, m):
            progress_calls.append((c, t, m))

        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        results, status_log = service._get_costs_sync(job, track_progress)

        self.assertIn("Test Station", results)
        self.assertEqual(status_log["success_count"], 1)
        self.assertTrue(len(progress_calls) >= 1)


if __name__ == "__main__":
    unittest.main()
