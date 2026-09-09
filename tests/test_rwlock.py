"""
Tests for RWLock - DEPRECATED

RWLock was removed from config.py in Phase 8 of the architecture refactoring.
The underlying libsql bug that required RWLock has been fixed.

Sync serialization is now handled by a per-alias threading.Lock
(config._sync_lock(alias)).
Regular database reads require no locking as SQLite handles its own
reader concurrency.

These tests are kept as a placeholder to document the removal.
"""
import unittest


class TestRWLockRemoved(unittest.TestCase):
    """Verify RWLock has been removed from config module"""

    def test_rwlock_class_removed(self):
        """RWLock class should no longer exist in config module"""
        import config
        self.assertFalse(hasattr(config, 'RWLock'),
                        "RWLock should be removed from config module")

    def test_sync_lock_still_exists(self):
        """Per-alias sync locks should still exist for sync serialization"""
        from config import _sync_lock
        import threading
        self.assertIsInstance(_sync_lock("sde"), type(threading.Lock()))


if __name__ == "__main__":
    unittest.main()
