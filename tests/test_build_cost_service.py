"""Tests for BuildCostService."""

import pandas as pd
from unittest.mock import MagicMock

from services.build_cost_service import BuildCostService


class TestBuildCostService:
    def test_get_available_costs_sorts_catalog_rows(self):
        repo = MagicMock()
        repo.get_builder_cost_catalog.return_value = pd.DataFrame(
            [
                {"category_name": "Ships", "group_name": "Battlecruiser", "type_name": "Drake"},
                {"category_name": "Charges", "group_name": "Missiles", "type_name": "Scourge"},
            ]
        )

        service = BuildCostService(repo)

        result = service.get_available_costs()

        assert list(result["category_name"]) == ["Charges", "Ships"]

    def test_get_cost_snapshot_builds_quantity_summary(self):
        repo = MagicMock()
        repo.get_builder_cost_by_type.return_value = pd.DataFrame(
            [
                {
                    "type_id": 24698,
                    "type_name": "Drake",
                    "group_id": 419,
                    "group_name": "Battlecruiser",
                    "category_id": 6,
                    "category_name": "Ship",
                    "total_cost_per_unit": 12_500_000.0,
                    "time_per_unit": 900.0,
                    "me": 8,
                    "runs": 3,
                    "fetched_at": "2026-05-04 09:15:00",
                }
            ]
        )

        service = BuildCostService(repo)

        snapshot = service.get_cost_snapshot(24698, quantity=4)

        assert snapshot is not None
        assert snapshot.type_id == 24698
        assert snapshot.type_name == "Drake"
        assert snapshot.quantity == 4
        assert snapshot.total_cost == 50_000_000.0
        assert snapshot.total_time == 3600.0
        assert snapshot.me == 8
        assert snapshot.runs == 3

    def test_get_cost_snapshot_returns_none_for_missing_type(self):
        repo = MagicMock()
        repo.get_builder_cost_by_type.return_value = pd.DataFrame()

        service = BuildCostService(repo)

        assert service.get_cost_snapshot(999999) is None
