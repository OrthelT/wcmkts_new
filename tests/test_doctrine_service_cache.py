"""DoctrineService rebuilds its cached result when the replica changes.

The service instance lives in one session's state, but a sync in another
session changes the shared replica without calling this instance's
clear_cache(). The replica version is what marks the cached result stale.
"""

from unittest.mock import MagicMock, patch

import pytest

import services.doctrine_service as doctrine_service
from services.doctrine_service import DoctrineService


@pytest.fixture
def builder():
    """Patch FitDataBuilder so each build returns a distinct result object."""
    with patch.object(doctrine_service, "FitDataBuilder") as builder_cls:
        chain = builder_cls.return_value
        for step in (
            "load_raw_data",
            "apply_module_equivalents",
            "fill_null_prices",
            "aggregate_summaries",
            "calculate_costs",
            "merge_targets",
            "finalize_columns",
        ):
            getattr(chain, step).return_value = chain
        chain.build.side_effect = lambda: MagicMock()
        yield chain


@pytest.fixture
def service():
    repo = MagicMock()
    repo.db_alias = "wcmktnewkeep"
    return DoctrineService(repository=repo)


def test_same_replica_version_reuses_the_cached_result(service, builder):
    with patch.object(doctrine_service, "replica_version", return_value=1):
        first = service.build_fit_data()
        second = service.build_fit_data()
    assert second is first
    builder.build.assert_called_once()


def test_changed_replica_version_rebuilds(service, builder):
    with patch.object(doctrine_service, "replica_version", return_value=1) as version:
        first = service.build_fit_data()
        version.return_value = 2  # another session's sync changed the replica
        second = service.build_fit_data()
        third = service.build_fit_data()
    assert second is not first
    assert third is second
    assert builder.build.call_count == 2
