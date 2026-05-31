"""
Tests for ModuleEquivalentsService.

Covers the batched/grouped stock resolution introduced in the loading-performance
pass:
- _build_group_map (single cached groups call -> type_id -> group map)
- get_aggregated_stock (grouped ids served from the group, ungrouped batched)
- get_equivalent_lowest_prices
- _get_module_stocks (batch marketstats read; missing id = true 0;
  read failure = OMIT ids, never a fabricated 0 stock)
"""
from unittest.mock import Mock, patch

import pandas as pd

from services.module_equivalents_service import (
    EquivalenceGroup,
    EquivalentModule,
    ModuleEquivalentsService,
)


def _make_service():
    """Service with a mock DatabaseConfig (alias/engine attributes only)."""
    mock_db = Mock()
    mock_db.alias = "wcmkt"
    return ModuleEquivalentsService(mock_db)


def _group(group_id, *modules):
    return EquivalenceGroup(
        equiv_group_id=group_id,
        modules=[EquivalentModule(*m) for m in modules],
    )


class TestBuildGroupMap:
    def test_maps_every_member_type_id_to_its_group(self):
        service = _make_service()
        group_a = _group(1, (100, "A1", 10, 5.0), (101, "A2", 20, 6.0))
        group_b = _group(2, (200, "B1", 3, 9.0))
        service.get_all_equivalence_groups = Mock(return_value=[group_a, group_b])

        group_map = service._build_group_map()

        assert group_map[100] is group_a
        assert group_map[101] is group_a
        assert group_map[200] is group_b
        assert set(group_map) == {100, 101, 200}


class TestGetAggregatedStock:
    def test_grouped_ids_use_total_stock_ungrouped_are_batched(self):
        service = _make_service()
        group = _group(1, (100, "A1", 10, 5.0), (101, "A2", 20, 6.0))  # total_stock=30
        service.get_all_equivalence_groups = Mock(return_value=[group])

        with patch.object(
            service, "_get_module_stocks", return_value={200: 50}
        ) as mock_batch:
            result = service.get_aggregated_stock([100, 101, 200])

        assert result == {100: 30, 101: 30, 200: 50}
        # N+1 elimination: a single batched call for all ungrouped ids.
        mock_batch.assert_called_once_with([200])


class TestGetEquivalentLowestPrices:
    def test_returns_lowest_price_only_for_grouped_in_stock_ids(self):
        service = _make_service()
        group = _group(1, (100, "A1", 10, 7.0), (101, "A2", 20, 5.0))  # lowest=5.0
        service.get_all_equivalence_groups = Mock(return_value=[group])

        result = service.get_lowest_equivalent_prices([100, 101, 999])

        assert result == {100: 5.0, 101: 5.0}  # 999 is ungrouped -> omitted


class TestGetModuleStocks:
    @patch("services.module_equivalents_service.BaseRepository")
    def test_present_ids_get_stock_absent_ids_are_true_zero(self, mock_repo_cls):
        service = _make_service()
        mock_repo = Mock()
        mock_repo.read_df.return_value = pd.DataFrame(
            {"type_id": [34], "total_volume_remain": [1000]}
        )
        mock_repo_cls.return_value = mock_repo

        # 34 present in marketstats -> 1000; 35 absent -> genuine 0.
        result = service._get_module_stocks([34, 35])

        assert result == {34: 1000, 35: 0}

    def test_empty_input_returns_empty_without_query(self):
        service = _make_service()
        with patch("services.module_equivalents_service.BaseRepository") as mock_repo_cls:
            result = service._get_module_stocks([])
        assert result == {}
        mock_repo_cls.assert_not_called()

    @patch("services.module_equivalents_service.BaseRepository")
    def test_read_failure_omits_ids_rather_than_reporting_zero_stock(self, mock_repo_cls):
        """A read failure must NOT report modules as 0 stock.

        Returning {tid: 0} would make a well-stocked doctrine item render as
        out-of-stock when the DB read merely failed (data-integrity rule). The
        ids are omitted so callers treat them as unknown and leave existing
        values untouched, rather than fabricating a zero.
        """
        service = _make_service()
        mock_repo = Mock()
        mock_repo.read_df.side_effect = RuntimeError("database disk image is malformed")
        mock_repo_cls.return_value = mock_repo

        result = service._get_module_stocks([34, 35])

        assert result == {}  # omitted, NOT {34: 0, 35: 0}
