"""
Tests for BaseRepository.read_df():
- successful local reads
- malformed error -> sync (rebuild) + retry
- sync failure -> error propagates
- retry-after-sync failure -> that error propagates
- still malformed after sync -> forced rebuild + retry
- recover=False skips recovery entirely
- params passthrough
"""

import unittest
from unittest.mock import MagicMock, PropertyMock, call, patch

import pandas as pd

from repositories.base import BaseRepository


class TestReadDf(unittest.TestCase):
    def _make_repo(self, engine=None):
        mock_db = MagicMock()
        if engine is not None:
            type(mock_db).engine = PropertyMock(return_value=engine)
        return BaseRepository(mock_db), mock_db

    def _mock_engine_with_data(self, df):
        engine = MagicMock()
        conn = MagicMock()
        engine.connect.return_value.__enter__ = MagicMock(return_value=conn)
        engine.connect.return_value.__exit__ = MagicMock(return_value=False)
        return engine, conn

    def test_read_df_local_success(self):
        expected = pd.DataFrame({"id": [1, 2]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, _ = self._make_repo(engine=engine)
        with patch("repositories.base.pd.read_sql_query", return_value=expected):
            result = repo.read_df("SELECT * FROM test")
        pd.testing.assert_frame_equal(result, expected)

    def test_malformed_triggers_sync_and_retry(self):
        expected = pd.DataFrame({"id": [1]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        calls = iter([Exception("database disk image is malformed"), expected])

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        mock_db.sync.assert_called_once()
        pd.testing.assert_frame_equal(result, expected)

    def test_no_such_table_triggers_sync_and_retry(self):
        expected = pd.DataFrame({"id": [1]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        calls = iter([Exception("no such table: marketstats"), expected])

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        mock_db.sync.assert_called_once()
        pd.testing.assert_frame_equal(result, expected)

    def test_disk_io_error_triggers_sync_and_retry(self):
        expected = pd.DataFrame({"id": [1]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        calls = iter([Exception("disk I/O error"), expected])

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        mock_db.sync.assert_called_once()
        pd.testing.assert_frame_equal(result, expected)

    def test_file_is_not_a_database_triggers_sync_and_retry(self):
        expected = pd.DataFrame({"id": [1]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        calls = iter([Exception("file is not a database"), expected])

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        mock_db.sync.assert_called_once()
        pd.testing.assert_frame_equal(result, expected)

    def test_invalid_page_size_triggers_sync_and_retry(self):
        # Observed pyturso error for a junk (non-sqlite) file — see Step 1
        # audit in task-6-report.md. Not covered by any pre-existing marker.
        expected = pd.DataFrame({"id": [1]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        calls = iter(
            [Exception("invalid page size in database header: 29797"), expected]
        )

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        mock_db.sync.assert_called_once()
        pd.testing.assert_frame_equal(result, expected)

    def test_short_read_triggers_sync_and_retry(self):
        """pyturso reports a truncated replica as an I/O "short read"; without
        this marker read_df re-raises to the page instead of rebuilding."""
        expected = pd.DataFrame({"id": [1]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        calls = iter([
            Exception("I/O error: short read on page 1: expected 512 bytes, got 100"),
            expected,
        ])

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        mock_db.sync.assert_called_once()
        pd.testing.assert_frame_equal(result, expected)

    def test_sync_failure_raises(self):
        """Turso is the only source of a good replica; if the rebuild sync
        fails there is nothing left to fall back to."""
        engine, _ = self._mock_engine_with_data(None)
        repo, mock_db = self._make_repo(engine=engine)
        mock_db.sync.side_effect = Exception("turso unreachable")
        with patch(
            "repositories.base.pd.read_sql_query",
            side_effect=Exception("database disk image is malformed"),
        ):
            with self.assertRaises(Exception) as ctx:
                repo.read_df("SELECT * FROM test")
        self.assertIn("turso unreachable", str(ctx.exception))
        mock_db.sync.assert_called_once()

    def test_retry_after_sync_failure_raises_retry_error(self):
        engine, _ = self._mock_engine_with_data(None)
        repo, mock_db = self._make_repo(engine=engine)
        calls = iter([
            Exception("database disk image is malformed"),
            Exception("still broken after rebuild"),
        ])

        def side_effect(*a, **k):
            raise next(calls)

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            with self.assertRaises(Exception) as ctx:
                repo.read_df("SELECT * FROM test")
        self.assertIn("still broken after rebuild", str(ctx.exception))
        mock_db.sync.assert_called_once()

    def test_still_malformed_after_sync_forces_rebuild(self):
        """Corruption in a data page leaves sqlite_master readable, so an
        ordinary sync() preserves the file and an unchanged pull returns
        through the no-change fast path with no integrity check. When the
        retry hits the same page, read_df must force a fresh bootstrap
        rather than surface the error."""
        expected = pd.DataFrame({"id": [7]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        mock_db.integrity_check.return_value = False
        calls = iter([
            Exception("database disk image is malformed"),
            Exception("database disk image is malformed"),
            expected,
        ])

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        self.assertEqual(
            mock_db.sync.call_args_list, [call(), call(force_rebuild=True)]
        )
        pd.testing.assert_frame_equal(result, expected)

    def test_healthy_replica_after_sync_does_not_force_rebuild(self):
        """"no such table" is also what a caller bug looks like (typo'd
        table, or one absent from this hub's schema). A passing integrity
        check means the replica is sound, so re-downloading 147 MB would
        fix nothing."""
        engine, _ = self._mock_engine_with_data(None)
        repo, mock_db = self._make_repo(engine=engine)
        mock_db.integrity_check.return_value = True
        with patch(
            "repositories.base.pd.read_sql_query",
            side_effect=Exception("no such table: typo_table"),
        ):
            with self.assertRaises(Exception) as ctx:
                repo.read_df("SELECT * FROM typo_table")
        self.assertIn("no such table", str(ctx.exception))
        mock_db.sync.assert_called_once_with()

    def test_recover_false_raises_immediately(self):
        engine, _ = self._mock_engine_with_data(None)
        repo, mock_db = self._make_repo(engine=engine)
        with patch(
            "repositories.base.pd.read_sql_query",
            side_effect=Exception("database disk image is malformed"),
        ):
            with self.assertRaises(Exception):
                repo.read_df("SELECT * FROM test", recover=False)
        mock_db.sync.assert_not_called()

    def test_non_malformed_error_raises_without_recovery(self):
        engine, _ = self._mock_engine_with_data(None)
        repo, mock_db = self._make_repo(engine=engine)
        with patch(
            "repositories.base.pd.read_sql_query", side_effect=Exception("syntax error")
        ):
            with self.assertRaises(Exception):
                repo.read_df("SELECT broken")
        mock_db.sync.assert_not_called()

    def test_read_df_passes_params(self):
        """Test that params are forwarded to read_sql_query."""
        expected = pd.DataFrame({"id": [1]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, _ = self._make_repo(engine=engine)

        with patch(
            "repositories.base.pd.read_sql_query", return_value=expected
        ) as mock_read:
            repo.read_df("SELECT * FROM test WHERE id = :id", params={"id": 42})

            call_kwargs = mock_read.call_args
            assert call_kwargs[1]["params"] == {"id": 42}

    def test_db_attribute_accessible(self):
        """Test that the db attribute is publicly accessible."""
        mock_db = MagicMock()
        mock_db.alias = "test_db"
        repo = BaseRepository(mock_db)
        assert repo.db is mock_db


if __name__ == "__main__":
    unittest.main()
