"""
Tests for BaseRepository.read_df():
- successful local reads
- malformed error -> sync + retry
- sync failure -> restore_from_backup + retry
- restore failure -> original error raised
- recover=False skips recovery entirely
- params passthrough
"""

import unittest
from unittest.mock import MagicMock, PropertyMock, patch

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

    def test_sync_failure_falls_back_to_backup_restore(self):
        expected = pd.DataFrame({"id": [99]})
        engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=engine)
        mock_db.sync.side_effect = Exception("turso unreachable")
        mock_db.restore_from_backup.return_value = True
        calls = iter([Exception("no such table: marketstats"), expected])

        def side_effect(*a, **k):
            v = next(calls)
            if isinstance(v, Exception):
                raise v
            return v

        with patch("repositories.base.pd.read_sql_query", side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")
        mock_db.restore_from_backup.assert_called_once()
        pd.testing.assert_frame_equal(result, expected)

    def test_restore_failure_raises_original_error(self):
        engine, _ = self._mock_engine_with_data(None)
        repo, mock_db = self._make_repo(engine=engine)
        mock_db.sync.side_effect = Exception("turso unreachable")
        mock_db.restore_from_backup.return_value = False
        with patch(
            "repositories.base.pd.read_sql_query",
            side_effect=Exception("database disk image is malformed"),
        ):
            with self.assertRaises(Exception) as ctx:
                repo.read_df("SELECT * FROM test")
        self.assertIn("malformed", str(ctx.exception))
        mock_db.restore_from_backup.assert_called_once()

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
        mock_db.restore_from_backup.assert_not_called()

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
