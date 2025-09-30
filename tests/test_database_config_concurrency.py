"""
Tests for DatabaseConfig concurrency features

This test suite validates that the DatabaseConfig class properly uses
read-write locks to allow concurrent reads while maintaining exclusive
write access.
"""
import unittest
from unittest.mock import MagicMock, patch
import threading
import time
from config import DatabaseConfig


class TestDatabaseConfigConcurrency(unittest.TestCase):
    """Test cases for DatabaseConfig concurrency behavior"""

    def test_local_access_defaults_to_read_lock(self):
        """Test that local_access() without parameters uses read lock"""
        with patch('config.st'):  # Mock streamlit
            db = DatabaseConfig("wcmkt")
            lock = db._get_local_lock()

            # Mock the lock methods to track calls
            original_read_lock = lock.read_lock
            original_write_lock = lock.write_lock

            read_lock_called = False
            write_lock_called = False

            def track_read():
                nonlocal read_lock_called
                read_lock_called = True
                return original_read_lock()

            def track_write():
                nonlocal write_lock_called
                write_lock_called = True
                return original_write_lock()

            lock.read_lock = track_read
            lock.write_lock = track_write

            # Use local_access without write parameter
            with db.local_access():
                pass

            self.assertTrue(read_lock_called, "Read lock should be used by default")
            self.assertFalse(write_lock_called, "Write lock should not be used by default")

    def test_local_access_write_true_uses_write_lock(self):
        """Test that local_access(write=True) uses write lock"""
        with patch('config.st'):  # Mock streamlit
            db = DatabaseConfig("wcmkt")
            lock = db._get_local_lock()

            # Mock the lock methods to track calls
            original_read_lock = lock.read_lock
            original_write_lock = lock.write_lock

            read_lock_called = False
            write_lock_called = False

            def track_read():
                nonlocal read_lock_called
                read_lock_called = True
                return original_read_lock()

            def track_write():
                nonlocal write_lock_called
                write_lock_called = True
                return original_write_lock()

            lock.read_lock = track_read
            lock.write_lock = track_write

            # Use local_access with write=True
            with db.local_access(write=True):
                pass

            self.assertFalse(read_lock_called, "Read lock should not be used when write=True")
            self.assertTrue(write_lock_called, "Write lock should be used when write=True")

    def test_multiple_database_configs_share_lock(self):
        """Test that multiple DatabaseConfig instances for same alias share lock"""
        with patch('config.st'):  # Mock streamlit
            db1 = DatabaseConfig("wcmkt")
            db2 = DatabaseConfig("wcmkt")

            lock1 = db1._get_local_lock()
            lock2 = db2._get_local_lock()

            # Both should get the same lock instance
            self.assertIs(lock1, lock2,
                         "Multiple instances should share the same lock for same alias")

    def test_different_aliases_have_different_locks(self):
        """Test that different database aliases have separate locks"""
        with patch('config.st'):  # Mock streamlit
            db1 = DatabaseConfig("wcmkt")
            db2 = DatabaseConfig("sde")

            lock1 = db1._get_local_lock()
            lock2 = db2._get_local_lock()

            # Locks should be different instances
            self.assertIsNot(lock1, lock2,
                            "Different aliases should have different locks")

    def test_concurrent_reads_allowed(self):
        """Test that multiple threads can read concurrently"""
        with patch('config.st'):  # Mock streamlit
            db = DatabaseConfig("wcmkt")
            readers_active = []
            max_concurrent = 0
            lock_for_tracking = threading.Lock()

            def reader(reader_id):
                nonlocal max_concurrent
                with db.local_access():  # Default read access
                    with lock_for_tracking:
                        readers_active.append(reader_id)
                        max_concurrent = max(max_concurrent, len(readers_active))

                    time.sleep(0.05)

                    with lock_for_tracking:
                        readers_active.remove(reader_id)

            # Create multiple reader threads
            threads = [threading.Thread(target=reader, args=(i,)) for i in range(3)]

            # Start all threads
            for t in threads:
                t.start()

            # Wait for completion
            for t in threads:
                t.join()

            # Multiple readers should be active concurrently
            self.assertGreaterEqual(max_concurrent, 2,
                                   "Multiple readers should be active simultaneously")

    def test_write_blocks_reads(self):
        """Test that a write operation blocks read operations"""
        with patch('config.st'):  # Mock streamlit
            db = DatabaseConfig("wcmkt")
            writer_has_lock = threading.Event()
            reader_attempted = threading.Event()
            reader_acquired = threading.Event()
            writer_released = threading.Event()

            def writer():
                with db.local_access(write=True):
                    writer_has_lock.set()
                    # Hold lock briefly
                    time.sleep(0.1)
                    writer_released.set()

            def reader():
                # Wait for writer to acquire lock
                writer_has_lock.wait(timeout=1.0)

                # Try to read - should block
                reader_attempted.set()
                with db.local_access():
                    # Should only get here after writer releases
                    reader_acquired.set()
                    self.assertTrue(writer_released.is_set(),
                                   "Reader should acquire lock only after writer releases")

            # Start writer
            writer_thread = threading.Thread(target=writer)
            writer_thread.start()

            # Wait for writer to get lock
            writer_has_lock.wait(timeout=1.0)

            # Start reader
            reader_thread = threading.Thread(target=reader)
            reader_thread.start()

            # Wait for completion
            writer_thread.join(timeout=2.0)
            reader_thread.join(timeout=2.0)

            self.assertTrue(reader_acquired.is_set(),
                           "Reader should eventually acquire lock")

    def test_lock_released_on_exception(self):
        """Test that locks are properly released even when exceptions occur"""
        with patch('config.st'):  # Mock streamlit
            db = DatabaseConfig("wcmkt")

            # Test read lock with exception
            with self.assertRaises(ValueError):
                with db.local_access():
                    raise ValueError("Test exception")

            # Should be able to acquire lock after exception
            acquired = False
            with db.local_access():
                acquired = True

            self.assertTrue(acquired, "Lock should be released after exception")

            # Test write lock with exception
            with self.assertRaises(ValueError):
                with db.local_access(write=True):
                    raise ValueError("Test exception")

            # Should be able to acquire lock after exception
            acquired = False
            with db.local_access(write=True):
                acquired = True

            self.assertTrue(acquired, "Write lock should be released after exception")


if __name__ == "__main__":
    unittest.main()
