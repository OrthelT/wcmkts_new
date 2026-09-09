"""Periodic staleness-check gating in pages/components/db_refresh.py.

Two properties are under test, both from the startup performance evaluation:

1. The 600 s guard is process-wide, not per-session. It used to live in
   st.session_state, so every new browser session paid a full multi-database
   sync (~4.3 s) even when another session had just pulled.
2. Only the active market hub is pulled, not all three. Inactive hubs are
   bootstrapped/synced on demand when the user switches to them.
"""

from unittest.mock import MagicMock, patch

import pytest

from config import SyncResult
import pages.components.db_refresh as db_refresh


PRIMARY = "wcmktnewkeep"
OTHER_HUB = "wcmktnorth"
SHARED = "build_cost"


@pytest.fixture(autouse=True)
def reset_check_state():
    """Each test starts with an empty process-wide check registry."""
    db_refresh._last_check_by_alias.clear()
    yield
    db_refresh._last_check_by_alias.clear()


def _market_config(alias):
    cfg = MagicMock()
    cfg.database_alias = alias
    return cfg


@pytest.fixture
def env():
    """Patch the app surface check_db touches; yield the sync-call recorder."""
    synced = []

    def make_db(alias):
        db = MagicMock()
        db.alias = alias
        db.has_remote_credentials = True
        db.sync.side_effect = lambda: (
            synced.append(alias),
            SyncResult(ok=True, changed=False),
        )[1]
        return db

    with patch.object(db_refresh, "DatabaseConfig", side_effect=make_db), patch.object(
        db_refresh, "st", MagicMock()
    ), patch.object(db_refresh, "update_wcmkt_state"), patch.object(
        db_refresh, "refresh_market_caches"
    ), patch.object(db_refresh, "invalidate_build_cost_caches"), patch(
        "settings_service.get_periodic_sync_aliases", return_value=[SHARED]
    ), patch(
        "settings_service.get_all_market_configs",
        return_value={
            "primary": _market_config(PRIMARY),
            "deployment": _market_config(OTHER_HUB),
        },
    ), patch(
        "state.market_state.get_active_market", return_value=_market_config(PRIMARY)
    ) as active:
        yield synced, active


class TestActiveHubOnly:
    def test_check_db_pulls_active_hub_and_shared_dbs_only(self, env):
        synced, _ = env
        db_refresh.check_db()
        assert synced == [PRIMARY, SHARED]

    def test_inactive_hub_is_never_pulled(self, env):
        synced, _ = env
        db_refresh.check_db()
        assert OTHER_HUB not in synced


class TestProcessWideGuard:
    def test_second_session_does_not_repeat_the_check(self, env):
        """A new session inherits the process's last check instead of re-syncing."""
        synced, _ = env
        db_refresh.maybe_run_check()  # session A
        db_refresh.maybe_run_check()  # session B, fresh session_state
        assert synced == [PRIMARY, SHARED]

    def test_check_repeats_once_the_interval_elapses(self, env):
        synced, _ = env
        with patch.object(db_refresh.time, "time", return_value=1000.0):
            db_refresh.maybe_run_check()
        with patch.object(db_refresh.time, "time", return_value=1000.0 + 601):
            db_refresh.maybe_run_check()
        assert synced == [PRIMARY, SHARED, PRIMARY, SHARED]

    def test_check_does_not_repeat_within_the_interval(self, env):
        synced, _ = env
        with patch.object(db_refresh.time, "time", return_value=1000.0):
            db_refresh.maybe_run_check()
        with patch.object(db_refresh.time, "time", return_value=1000.0 + 599):
            db_refresh.maybe_run_check()
        assert synced == [PRIMARY, SHARED]

    def test_newly_selected_hub_is_checked_even_within_the_interval(self, env):
        """Per-alias timestamps: switching hubs must pull the hub just selected,
        not inherit the already-checked hub's timer and serve stale data."""
        synced, active = env
        with patch.object(db_refresh.time, "time", return_value=1000.0):
            db_refresh.maybe_run_check()
            active.return_value = _market_config(OTHER_HUB)
            db_refresh.maybe_run_check()
        assert synced == [PRIMARY, SHARED, OTHER_HUB]

    def test_guard_is_marked_before_syncing(self, env):
        """check_db() may call st.rerun() on a change; if the alias were marked
        only afterwards, the rerun would re-enter and sync in a loop."""
        seen = []

        def make_db(alias):
            db = MagicMock()
            db.alias = alias
            db.has_remote_credentials = True

            def _sync():
                seen.append(db_refresh._last_check_by_alias.get(alias))
                return SyncResult(ok=True, changed=False)

            db.sync.side_effect = _sync
            return db

        with patch.object(db_refresh, "DatabaseConfig", side_effect=make_db):
            db_refresh.maybe_run_check()

        assert all(ts is not None for ts in seen)


class TestConcurrentClaim:
    def test_two_threads_start_only_one_check(self, env):
        """maybe_run_check() claims stale aliases while still holding the lock.

        Marking only inside check_db() left a window in which two sessions
        could both see the same alias as stale and start the same pull.
        """
        import threading

        invocations = []
        barrier = threading.Barrier(2)

        def slow_check_db(aliases=None, manual_override=False):
            invocations.append(aliases)

        def run():
            barrier.wait()
            db_refresh.maybe_run_check()

        with patch.object(db_refresh, "check_db", side_effect=slow_check_db):
            threads = [threading.Thread(target=run) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert invocations == [[PRIMARY, SHARED]]


class TestEnsureActiveMarketFresh:
    def test_runs_the_periodic_check_when_the_db_is_ready(self):
        with patch.object(
            db_refresh, "ensure_market_db_ready", return_value=True
        ) as ready, patch.object(db_refresh, "maybe_run_check") as check:
            assert db_refresh.ensure_active_market_fresh(PRIMARY) is True
        ready.assert_called_once_with(PRIMARY)
        check.assert_called_once_with()

    def test_skips_the_check_when_the_db_is_not_ready(self):
        with patch.object(
            db_refresh, "ensure_market_db_ready", return_value=False
        ), patch.object(db_refresh, "maybe_run_check") as check:
            assert db_refresh.ensure_active_market_fresh(PRIMARY) is False
        check.assert_not_called()
