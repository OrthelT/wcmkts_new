"""
Tests for DatabaseConfig sync serialization

After the RWLock removal (Phase 8), the concurrency model simplifies to:
- a per-alias lock serializes sync operations on the same replica
- Regular reads use no locking (SQLite handles reader concurrency)

This test suite validates that sync serialization still works correctly.
"""
import unittest
from unittest.mock import patch, MagicMock
import threading
import time


class TestDatabaseConfigSyncSerialization(unittest.TestCase):
    """Test cases for DatabaseConfig sync serialization behavior"""

    def test_database_config_no_local_access(self):
        """Test that local_access method has been removed"""
        with patch('config.st'):
            from config import DatabaseConfig
            db = DatabaseConfig("wcmkt")
            self.assertFalse(hasattr(db, 'local_access'),
                           "local_access should be removed after RWLock removal")

    def test_database_config_no_rwlock(self):
        """Test that RWLock class is no longer in config module"""
        import config
        self.assertFalse(hasattr(config, 'RWLock'),
                        "RWLock class should be removed from config module")

    def test_database_config_no_local_locks(self):
        """Test that _local_locks dict is removed"""
        from config import DatabaseConfig
        self.assertFalse(hasattr(DatabaseConfig, '_local_locks'),
                        "_local_locks should be removed after RWLock removal")

    def test_engine_still_accessible(self):
        """Test that engine property still works after lock removal"""
        with patch('config.st'):
            from config import DatabaseConfig
            db = DatabaseConfig("wcmkt")
            # Engine should be accessible without any locking
            engine = db.engine
            self.assertIsNotNone(engine)

    def test_sync_no_streamlit_cache_calls(self):
        """Test that sync() does not call st.cache_data.clear() or st.cache_resource.clear()"""
        import inspect
        from config import DatabaseConfig
        source = inspect.getsource(DatabaseConfig.sync)
        self.assertNotIn("st.cache_data.clear", source,
                        "sync() should not call st.cache_data.clear()")
        self.assertNotIn("st.cache_resource.clear", source,
                        "sync() should not call st.cache_resource.clear()")

    def test_sync_no_streamlit_toast(self):
        """Test that sync() does not call st.toast()"""
        import inspect
        from config import DatabaseConfig
        source = inspect.getsource(DatabaseConfig.sync)
        self.assertNotIn("st.toast", source,
                        "sync() should not call st.toast()")

    def test_sync_no_session_state_mutation(self):
        """Test that sync() does not mutate st.session_state"""
        import inspect
        from config import DatabaseConfig
        source = inspect.getsource(DatabaseConfig.sync)
        self.assertNotIn("st.session_state", source,
                        "sync() should not mutate st.session_state")

    def test_sync_returns_bool_compatible_result(self):
        """Test that sync() returns a SyncResult preserving the legacy bool contract"""
        import inspect
        from config import DatabaseConfig, SyncResult
        sig = inspect.signature(DatabaseConfig.sync)
        self.assertEqual(sig.return_annotation, SyncResult,
                        "sync() should return SyncResult")
        # SyncResult.__bool__ preserves the legacy `if db.sync():` contract
        self.assertTrue(bool(SyncResult(ok=True, changed=False)))
        self.assertFalse(bool(SyncResult(ok=False, changed=False)))


class TestPerAliasSyncLocks(unittest.TestCase):
    """sync() serializes per replica, not process-wide.

    A single process-wide lock made concurrent bootstrap of several
    databases pointless: each alias owns a disjoint set of files, so only
    same-alias syncs need to exclude each other.
    """

    def _make_db(self, alias):
        from config import DatabaseConfig
        db = DatabaseConfig(alias)
        # sync() refuses to run without credentials; the pull itself is mocked.
        db.turso_url = "libsql://test.example"
        db.token = "token"
        return db

    def _run_syncs(self, dbs, pull):
        """Run db.sync() for each db in its own thread; return raised errors."""
        from config import DatabaseConfig
        errors = []

        def run(db):
            try:
                db.sync()
            except Exception as e:  # noqa: BLE001 - reported to the test
                errors.append(e)

        with patch.object(DatabaseConfig, "_dispose_local_connections"), \
             patch.object(DatabaseConfig, "_ensure_replica_consistency"), \
             patch.object(DatabaseConfig, "_pull_once", pull), \
             patch("config.os.path.exists", return_value=True):
            threads = [threading.Thread(target=run, args=(db,)) for db in dbs]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)
            self.assertFalse([t for t in threads if t.is_alive()],
                             "sync() thread never finished")
        return errors

    def test_same_alias_returns_the_same_lock(self):
        from config import _sync_lock
        self.assertIs(_sync_lock("sde"), _sync_lock("sde"))

    def test_different_aliases_get_different_locks(self):
        from config import _sync_lock
        self.assertIsNot(_sync_lock("sde"), _sync_lock("build_cost"))

    def test_sync_of_different_aliases_runs_concurrently(self):
        """Two aliases pull at the same time; a shared lock would deadlock here."""
        barrier = threading.Barrier(2, timeout=5)

        def pull(db_self):
            barrier.wait()  # BrokenBarrierError if the syncs are serialized
            return False

        errors = self._run_syncs(
            [self._make_db("sde"), self._make_db("build_cost")], pull
        )
        self.assertEqual(errors, [], "syncs of different aliases were serialized")

    def test_sync_of_the_same_alias_is_serialized(self):
        """Two threads syncing one replica must not touch its files at once."""
        state = {"live": 0, "peak": 0}
        counter_lock = threading.Lock()

        def pull(db_self):
            with counter_lock:
                state["live"] += 1
                state["peak"] = max(state["peak"], state["live"])
            time.sleep(0.05)
            with counter_lock:
                state["live"] -= 1
            return False

        errors = self._run_syncs(
            [self._make_db("sde"), self._make_db("sde")], pull
        )
        self.assertEqual(errors, [])
        self.assertEqual(state["peak"], 1,
                         "two syncs of the same alias overlapped")


if __name__ == "__main__":
    unittest.main()
