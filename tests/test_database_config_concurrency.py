"""
Tests for DatabaseConfig sync serialization

After the RWLock removal (Phase 8), the concurrency model simplifies to:
- _SYNC_LOCK serializes sync operations
- Regular reads use no locking (SQLite handles reader concurrency)

This test suite validates that sync serialization still works correctly.
"""
import unittest
from unittest.mock import patch, MagicMock
import threading
import time


class TestDatabaseConfigSyncSerialization(unittest.TestCase):
    """Test cases for DatabaseConfig sync serialization behavior"""

    def test_sync_lock_exists(self):
        """Test that _SYNC_LOCK exists for sync serialization"""
        from config import _SYNC_LOCK
        self.assertIsInstance(_SYNC_LOCK, type(threading.Lock()))

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

    def test_sync_returns_bool(self):
        """Test that sync() has bool return type annotation"""
        import inspect
        from config import DatabaseConfig
        sig = inspect.signature(DatabaseConfig.sync)
        self.assertEqual(sig.return_annotation, bool,
                        "sync() should return bool")


if __name__ == "__main__":
    unittest.main()
