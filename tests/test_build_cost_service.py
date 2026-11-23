"""Tests for BuildCostService."""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from services.build_cost_service import (
    BuildCostJob,
    BuildCostService,
    CAPITAL_GROUP_IDS,
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
        self.assertFalse(job.include_closed)


class TestBuildCostServiceBuildUrls(unittest.TestCase):
    def _make_service(self):
        repo = MagicMock()
        return BuildCostService(repo), repo

    def _make_structure(self, name="Test Station", structure_id=1):
        s = MagicMock()
        s.structure = name
        s.structure_id = structure_id
        s.structure_type = "Sotiyo"
        s.structure_type_id = 35827
        s.system_id = 30004759
        s.tax = 0.1
        return s

    def test_build_urls_returns_list(self):
        service, repo = self._make_service()
        repo.get_all_structures.return_value = [self._make_structure()]
        repo.get_structure_rig_ids.return_value = {1: [100]}
        repo.get_manufacturing_cost_index.return_value = 0.05

        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        urls = service.build_urls(job)

        self.assertEqual(len(urls), 1)
        url, name, stype = urls[0]
        self.assertIn("product_id=24690", url)
        self.assertIn("rig_id=100", url)
        self.assertEqual(name, "Test Station")

    def test_build_urls_passes_module_flags_and_include_closed(self):
        service, repo = self._make_service()
        repo.get_all_structures.return_value = []
        repo.get_structure_rig_ids.return_value = {}

        job = BuildCostJob(
            item="Naglfar", item_id=19722, group_id=485, runs=1, me=0, te=0,
            include_closed=True,
        )
        service.build_urls(job)

        repo.get_all_structures.assert_called_once_with(
            ("has_capital_shipyard", "has_supercapital_shipyard"), include_closed=True
        )

    def test_build_urls_uses_each_structures_own_rigs(self):
        service, repo = self._make_service()
        repo.get_all_structures.return_value = [
            self._make_structure("A", 1),
            self._make_structure("B", 2),
        ]
        repo.get_structure_rig_ids.return_value = {1: [100, 200], 2: [300]}
        repo.get_manufacturing_cost_index.return_value = 0.05

        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        urls = {name: url for url, name, _ in service.build_urls(job)}

        self.assertIn("&rig_id=100&rig_id=200&", urls["A"])
        self.assertNotIn("rig_id=300", urls["A"])
        self.assertIn("&rig_id=300&", urls["B"])

    def test_build_urls_no_rigs(self):
        service, repo = self._make_service()
        repo.get_all_structures.return_value = [self._make_structure()]
        repo.get_structure_rig_ids.return_value = {}
        repo.get_manufacturing_cost_index.return_value = 0.05

        job = BuildCostJob(item="Drake", item_id=24690, group_id=25, runs=1, me=0, te=0)
        urls = service.build_urls(job)

        url = urls[0][0]
        self.assertNotIn("rig_id=", url)


class TestNoCapitalStructureOverride(unittest.TestCase):
    """no_capital_structure_ids drops a structure from standard capital builds only."""

    def _service(self):
        repo = MagicMock()
        super_only = MagicMock(structure="C-J7CR", structure_id=1046452498926)
        shipyard = MagicMock(structure="Other", structure_id=2)
        repo.get_all_structures.return_value = [super_only, shipyard]
        return BuildCostService(repo, no_capital_structure_ids=[1046452498926]), repo

    def _names(self, structures):
        return [s.structure for s in structures]

    def test_capital_build_excludes_listed_structure(self):
        service, _ = self._service()
        self.assertEqual(self._names(service.get_structures(485)), ["Other"])

    def test_super_build_keeps_listed_structure(self):
        service, _ = self._service()
        self.assertEqual(self._names(service.get_structures(30)), ["C-J7CR", "Other"])

    def test_build_urls_uses_the_override(self):
        service, repo = self._service()
        repo.get_structure_rig_ids.return_value = {}
        repo.get_manufacturing_cost_index.return_value = 0.05
        job = BuildCostJob(item="Naglfar", item_id=19722, group_id=485, runs=1, me=0, te=0)
        self.assertEqual([name for _, name, _ in service.build_urls(job)], ["Other"])

    def test_no_override_by_default(self):
        _, repo = self._service()
        service = BuildCostService(repo)
        self.assertEqual(self._names(service.get_structures(485)), ["C-J7CR", "Other"])


class TestModuleFlagsForGroup(unittest.TestCase):
    def test_supers_need_a_supercapital_shipyard(self):
        for gid in SUPER_GROUP_IDS:
            self.assertEqual(
                BuildCostService.module_flags_for_group(gid), ("has_supercapital_shipyard",)
            )

    def test_capitals_accept_capital_or_supercapital_shipyard(self):
        for gid in CAPITAL_GROUP_IDS:
            self.assertEqual(
                BuildCostService.module_flags_for_group(gid),
                ("has_capital_shipyard", "has_supercapital_shipyard"),
            )

    def test_everything_else_needs_a_manufacturing_plant(self):
        # Battlecruiser, Freighter, Jump Freighter, Sovereignty Hub
        for gid in (25, 513, 902, 1012):
            self.assertEqual(
                BuildCostService.module_flags_for_group(gid), ("has_manufacturing_plant",)
            )


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


if __name__ == "__main__":
    unittest.main()
