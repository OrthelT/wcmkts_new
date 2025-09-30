"""
Tests for RWLock (Read-Write Lock) implementation in config.py

This test suite validates the concurrency behavior of the RWLock class:
- Multiple concurrent readers should be allowed
- Writers should have exclusive access
- Writers should wait for readers to finish
"""
import unittest
import threading
import time
from config import RWLock


class TestRWLock(unittest.TestCase):
    """Test cases for RWLock functionality"""

    def test_rwlock_multiple_concurrent_readers(self):
        """Test that multiple readers can acquire the lock simultaneously"""
        lock = RWLock()
        readers_active = []
        max_concurrent = 0
        lock_for_tracking = threading.Lock()

        def reader(reader_id):
            nonlocal max_concurrent
            with lock.read_lock():
                with lock_for_tracking:
                    readers_active.append(reader_id)
                    max_concurrent = max(max_concurrent, len(readers_active))

                # Hold the lock briefly
                time.sleep(0.05)

                with lock_for_tracking:
                    readers_active.remove(reader_id)

        # Create 5 reader threads
        threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # At least 2 readers should have been active concurrently
        self.assertGreaterEqual(max_concurrent, 2,
                               "Multiple readers should be able to acquire lock simultaneously")

    def test_rwlock_writer_blocks_readers(self):
        """Test that a writer blocks readers from acquiring the lock"""
        lock = RWLock()
        writer_entered = threading.Event()
        writer_exited = threading.Event()
        reader_blocked = threading.Event()
        reader_entered = threading.Event()

        def writer():
            with lock.write_lock():
                writer_entered.set()
                # Hold write lock for a moment
                time.sleep(0.1)
                writer_exited.set()

        def reader():
            # Wait until writer has the lock
            writer_entered.wait(timeout=1.0)

            # Try to acquire read lock - should be blocked
            reader_blocked.set()
            with lock.read_lock():
                # Should only get here after writer releases
                self.assertTrue(writer_exited.is_set(),
                               "Reader should only acquire lock after writer releases")
                reader_entered.set()

        # Start writer first
        writer_thread = threading.Thread(target=writer)
        writer_thread.start()

        # Give writer time to acquire lock
        writer_entered.wait(timeout=1.0)

        # Now start reader
        reader_thread = threading.Thread(target=reader)
        reader_thread.start()

        # Wait for completion
        writer_thread.join(timeout=2.0)
        reader_thread.join(timeout=2.0)

        self.assertTrue(reader_entered.is_set(), "Reader should eventually acquire lock")

    def test_rwlock_writer_waits_for_readers(self):
        """Test that a writer waits for all readers to finish before acquiring lock"""
        lock = RWLock()
        reader_entered = threading.Event()
        writer_blocked = threading.Event()
        writer_entered = threading.Event()
        reader_exited = threading.Event()

        def reader():
            with lock.read_lock():
                reader_entered.set()
                # Hold lock long enough for writer to attempt acquisition
                time.sleep(0.1)
                reader_exited.set()

        def writer():
            # Wait for reader to get the lock
            reader_entered.wait(timeout=1.0)

            # Try to acquire write lock - should block until reader finishes
            writer_blocked.set()
            with lock.write_lock():
                # Should only get here after reader releases
                self.assertTrue(reader_exited.is_set(),
                               "Writer should only acquire lock after reader releases")
                writer_entered.set()

        # Start reader first
        reader_thread = threading.Thread(target=reader)
        reader_thread.start()

        # Wait for reader to acquire lock
        reader_entered.wait(timeout=1.0)

        # Now start writer
        writer_thread = threading.Thread(target=writer)
        writer_thread.start()

        # Wait for completion
        reader_thread.join(timeout=2.0)
        writer_thread.join(timeout=2.0)

        self.assertTrue(writer_entered.is_set(), "Writer should eventually acquire lock")

    def test_rwlock_writer_has_exclusive_access(self):
        """Test that only one writer can hold the lock at a time"""
        lock = RWLock()
        writers_active = []
        lock_for_tracking = threading.Lock()
        max_concurrent_writers = 0

        def writer(writer_id):
            nonlocal max_concurrent_writers
            with lock.write_lock():
                with lock_for_tracking:
                    writers_active.append(writer_id)
                    max_concurrent_writers = max(max_concurrent_writers, len(writers_active))

                # Hold the lock briefly
                time.sleep(0.02)

                with lock_for_tracking:
                    writers_active.remove(writer_id)

        # Create multiple writer threads
        threads = [threading.Thread(target=writer, args=(i,)) for i in range(3)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Only one writer should be active at a time
        self.assertEqual(max_concurrent_writers, 1,
                        "Only one writer should hold the lock at a time")

    def test_rwlock_context_manager_releases_on_exception(self):
        """Test that the lock is properly released even when an exception occurs"""
        lock = RWLock()

        # Test read lock exception handling
        with self.assertRaises(ValueError):
            with lock.read_lock():
                raise ValueError("Test exception")

        # Lock should be released, so this should not block
        acquired = False
        with lock.read_lock():
            acquired = True

        self.assertTrue(acquired, "Read lock should be released after exception")

        # Test write lock exception handling
        with self.assertRaises(ValueError):
            with lock.write_lock():
                raise ValueError("Test exception")

        # Lock should be released, so this should not block
        acquired = False
        with lock.write_lock():
            acquired = True

        self.assertTrue(acquired, "Write lock should be released after exception")


if __name__ == "__main__":
    unittest.main()
