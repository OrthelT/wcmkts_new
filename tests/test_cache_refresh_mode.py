"""Tests for refresh_mode="background" on the replica-backed caches.

Background mode serves an expired entry while a worker thread recomputes it.
That is only correct because TTL expiry never brings new data: a sync that
changes the replica clears these caches explicitly, and the next read then
recomputes in the foreground. These tests guard both halves of that argument.
"""

import time
from unittest.mock import patch

import streamlit as st

import repositories.build_cost_repo as build_cost_repo
import repositories.doctrine_repo as doctrine_repo
import repositories.market_repo as market_repo


def _background_caches(module) -> dict[str, object]:
    return {
        name: obj
        for name, obj in vars(module).items()
        if getattr(getattr(obj, "_info", None), "refresh_mode", None) == "background"
    }


class TestBackgroundCachesAreSyncInvalidated:
    def test_expected_caches_use_background_mode(self):
        assert {"_get_all_stats_cached", "_get_all_orders_cached"} <= set(
            _background_caches(market_repo)
        )
        assert {"get_all_fits_with_cache", "get_target_quantities_with_cache"} <= set(
            _background_caches(doctrine_repo)
        )
        assert "_get_builder_cost_catalog_cached" in _background_caches(build_cost_repo)
        assert "_get_all_history_cached" not in _background_caches(market_repo)

    @patch("pages.downloads.clear_download_caches")
    def test_market_sync_invalidation_clears_every_background_cache(self, _mock_downloads):
        from state.market_state import refresh_market_caches

        caches = {**_background_caches(market_repo), **_background_caches(doctrine_repo)}
        patches = [patch.object(fn, "clear") for fn in caches.values()]
        mocks = dict(zip(caches, (p.start() for p in patches)))
        try:
            refresh_market_caches()
        finally:
            for p in patches:
                p.stop()

        not_cleared = sorted(name for name, m in mocks.items() if not m.called)
        assert not_cleared == []

    def test_build_cost_sync_invalidation_clears_every_background_cache(self):
        caches = _background_caches(build_cost_repo)
        patches = [patch.object(fn, "clear") for fn in caches.values()]
        mocks = dict(zip(caches, (p.start() for p in patches)))
        try:
            build_cost_repo.invalidate_build_cost_caches()
        finally:
            for p in patches:
                p.stop()

        not_cleared = sorted(name for name, m in mocks.items() if not m.called)
        assert not_cleared == []


class TestClearBypassesStaleServing:
    def test_clear_recomputes_instead_of_serving_expired_entry(self):
        replica = {"value": "pre-sync"}

        @st.cache_data(ttl=1, refresh_mode="background")
        def cleared_after_sync() -> str:
            return replica["value"]

        @st.cache_data(ttl=1, refresh_mode="background")
        def not_cleared() -> str:
            return replica["value"]

        assert cleared_after_sync() == "pre-sync"
        assert not_cleared() == "pre-sync"

        replica["value"] = "post-sync"
        # Past the 1 s fresh TTL, inside the 2 s hard expiry: entries are stale
        # but still servable.
        time.sleep(1.2)
        cleared_after_sync.clear()

        # Control: without a clear, background mode serves the expired entry.
        assert not_cleared() == "pre-sync"
        assert cleared_after_sync() == "post-sync"
