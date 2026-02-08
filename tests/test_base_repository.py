"""
Tests for BaseRepository

Tests the foundation repository class with:
- Successful local reads via read_df()
- Malformed DB recovery (sync + retry)
- Remote fallback when sync fails
- Direct remote reads
- Non-malformed errors are re-raised
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from repositories.base import BaseRepository


class TestBaseRepository:
    """Test cases for BaseRepository.read_df()"""

    def _make_repo(self, engine=None, remote_engine=None):
        """Helper to create a BaseRepository with mock DatabaseConfig."""
        mock_db = Mock()
        mock_db.alias = "test_db"

        if engine is not None:
            type(mock_db).engine = PropertyMock(return_value=engine)
        if remote_engine is not None:
            type(mock_db).remote_engine = PropertyMock(return_value=remote_engine)

        return BaseRepository(mock_db), mock_db

    def _mock_engine_with_data(self, data: pd.DataFrame):
        """Create a mock engine whose connect() returns data via read_sql_query."""
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn
        return mock_engine, mock_conn

    def test_read_df_local_success(self):
        """Test that read_df returns data from local engine on success."""
        expected = pd.DataFrame({'id': [1, 2], 'name': ['a', 'b']})
        mock_engine, mock_conn = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=mock_engine)

        with patch('pandas.read_sql_query', return_value=expected) as mock_read:
            result = repo.read_df("SELECT * FROM test")

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 2
            mock_read.assert_called_once()

    def test_read_df_remote_when_local_false(self):
        """Test that read_df reads from remote when local=False."""
        expected = pd.DataFrame({'id': [1]})
        mock_remote_engine, _ = self._mock_engine_with_data(expected)
        mock_local_engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(
            engine=mock_local_engine,
            remote_engine=mock_remote_engine
        )

        with patch('pandas.read_sql_query', return_value=expected):
            result = repo.read_df("SELECT * FROM test", local=False)

            assert isinstance(result, pd.DataFrame)
            # Remote engine should have been used
            mock_remote_engine.connect.assert_called_once()
            mock_local_engine.connect.assert_not_called()

    def test_read_df_malformed_triggers_sync_and_retry(self):
        """Test that malformed DB error triggers sync + retry."""
        expected = pd.DataFrame({'id': [1]})
        mock_engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=mock_engine)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("database disk image is malformed")
            return expected

        with patch('pandas.read_sql_query', side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")

            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1
            mock_db.sync.assert_called_once()

    def test_read_df_no_such_table_triggers_sync(self):
        """Test that 'no such table' error triggers sync + retry."""
        expected = pd.DataFrame({'id': [1]})
        mock_engine, _ = self._mock_engine_with_data(expected)
        repo, mock_db = self._make_repo(engine=mock_engine)

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("no such table: marketstats")
            return expected

        with patch('pandas.read_sql_query', side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")

            assert isinstance(result, pd.DataFrame)
            mock_db.sync.assert_called_once()

    def test_read_df_falls_back_to_remote_on_sync_failure(self):
        """Test that when sync+retry fails, falls back to remote."""
        expected_remote = pd.DataFrame({'id': [99]})

        mock_engine, _ = self._mock_engine_with_data(pd.DataFrame())
        mock_remote_engine, _ = self._mock_engine_with_data(expected_remote)
        repo, mock_db = self._make_repo(
            engine=mock_engine,
            remote_engine=mock_remote_engine
        )

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                # First call: malformed, second call: retry after sync also fails
                raise Exception("database disk image is malformed")
            return expected_remote

        with patch('pandas.read_sql_query', side_effect=side_effect):
            result = repo.read_df("SELECT * FROM test")

            assert isinstance(result, pd.DataFrame)
            assert result.iloc[0]['id'] == 99
            mock_db.sync.assert_called_once()

    def test_read_df_non_malformed_error_raises(self):
        """Test that non-malformed errors are re-raised."""
        mock_engine, _ = self._mock_engine_with_data(pd.DataFrame())
        repo, mock_db = self._make_repo(engine=mock_engine)

        with patch('pandas.read_sql_query', side_effect=ConnectionError("network error")):
            with pytest.raises(ConnectionError, match="network error"):
                repo.read_df("SELECT * FROM test")

            # sync should NOT have been called
            mock_db.sync.assert_not_called()

    def test_read_df_no_fallback_when_disabled(self):
        """Test that fallback is skipped when fallback_remote_on_malformed=False."""
        mock_engine, _ = self._mock_engine_with_data(pd.DataFrame())
        repo, mock_db = self._make_repo(engine=mock_engine)

        with patch('pandas.read_sql_query',
                   side_effect=Exception("database disk image is malformed")):
            with pytest.raises(Exception, match="malformed"):
                repo.read_df("SELECT * FROM test",
                           fallback_remote_on_malformed=False)

            mock_db.sync.assert_not_called()

    def test_read_df_passes_params(self):
        """Test that params are forwarded to read_sql_query."""
        expected = pd.DataFrame({'id': [1]})
        mock_engine, _ = self._mock_engine_with_data(expected)
        repo, _ = self._make_repo(engine=mock_engine)

        with patch('pandas.read_sql_query', return_value=expected) as mock_read:
            repo.read_df("SELECT * FROM test WHERE id = :id",
                        params={"id": 42})

            call_kwargs = mock_read.call_args
            assert call_kwargs[1]['params'] == {"id": 42}

    def test_db_attribute_accessible(self):
        """Test that the db attribute is publicly accessible."""
        mock_db = Mock()
        mock_db.alias = "test_db"
        repo = BaseRepository(mock_db)
        assert repo.db is mock_db


if __name__ == "__main__":
    pytest.main([__file__])
