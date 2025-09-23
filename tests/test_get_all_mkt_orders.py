"""
Tests for get_all_mkt_orders function in db_handler.py
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from db_handler import get_all_mkt_orders


class TestGetAllMktOrders:
    """Test cases for get_all_mkt_orders function"""

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_success(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test successful retrieval of all market orders"""
        # Mock performance counter
        mock_perf_counter.side_effect = [0.0, 0.1]  # start_time, end_time

        # Mock data
        mock_data = pd.DataFrame({
            'order_id': [1, 2, 3],
            'type_id': [12345, 67890, 11111],
            'price': [100.5, 200.0, 150.75],
            'volume': [1000, 500, 2000],
            'is_buy_order': [True, False, True]
        })

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.integrity_check.return_value = True
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_mkt_orders()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert list(result.columns) == ['order_id', 'type_id', 'price', 'volume', 'is_buy_order']
        assert result.index.tolist() == [0, 1, 2]  # Index should be reset

        # Verify integrity check was called
        mock_mkt_db.integrity_check.assert_called_once()

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_integrity_check_fails(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test behavior when integrity check fails"""
        # Mock performance counter
        mock_perf_counter.side_effect = [0.0, 0.1]

        # Mock data
        mock_data = pd.DataFrame({
            'order_id': [1, 2],
            'type_id': [12345, 67890],
            'price': [100.5, 200.0],
            'volume': [1000, 500],
            'is_buy_order': [True, False]
        })

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        # Mock integrity check failure
        mock_mkt_db.integrity_check.return_value = False
        mock_mkt_db.sync.return_value = None
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_mkt_orders()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

        # Verify sync was called after integrity check failure
        mock_mkt_db.sync.assert_called_once()

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_malformed_db_retry(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test retry mechanism when database is malformed"""
        # Mock performance counter
        mock_perf_counter.side_effect = [0.0, 0.1]

        # Mock data for successful retry
        mock_data = pd.DataFrame({
            'order_id': [1, 2],
            'type_id': [12345, 67890],
            'price': [100.5, 200.0],
            'volume': [1000, 500],
            'is_buy_order': [True, False]
        })

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.integrity_check.return_value = True
        mock_mkt_db.sync.return_value = None
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine
        mock_mkt_db.remote_engine = mock_engine

        # Mock first call fails with malformed DB error, second call succeeds
        mock_read_sql.side_effect = [
            Exception("database disk image is malformed"),
            mock_data
        ]

        result = get_all_mkt_orders()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 2

        # Verify sync was called after malformed DB error
        mock_mkt_db.sync.assert_called_once()

        # Verify read_sql_query was called twice (first fails, second succeeds)
        assert mock_read_sql.call_count == 2

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_malformed_db_fallback_to_remote(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test fallback to remote database when local retry fails"""
        # Mock performance counter
        mock_perf_counter.side_effect = [0.0, 0.1]

        # Mock data for remote fallback
        mock_data = pd.DataFrame({
            'order_id': [1],
            'type_id': [12345],
            'price': [100.5],
            'volume': [1000],
            'is_buy_order': [True]
        })

        # Mock database connections
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.integrity_check.return_value = True
        mock_mkt_db.sync.return_value = None
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine
        mock_mkt_db.remote_engine = mock_engine

        # Mock first call fails, second call fails, third call (remote) succeeds
        mock_read_sql.side_effect = [
            Exception("database disk image is malformed"),
            Exception("database disk image is malformed"),
            mock_data
        ]

        result = get_all_mkt_orders()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1

        # Verify sync was called after first failure
        mock_mkt_db.sync.assert_called_once()

        # Verify read_sql_query was called three times (local fails, retry fails, remote succeeds)
        assert mock_read_sql.call_count == 3

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_non_malformed_error(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test that non-malformed database errors are not retried"""
        # Mock performance counter
        mock_perf_counter.side_effect = [0.0, 0.1]

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.integrity_check.return_value = True
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        # Mock non-malformed error
        mock_read_sql.side_effect = Exception("Connection timeout")

        with pytest.raises(Exception, match="Connection timeout"):
            get_all_mkt_orders()

        # Verify sync was not called for non-malformed errors
        mock_mkt_db.sync.assert_not_called()

        # Verify read_sql_query was called only once
        assert mock_read_sql.call_count == 1

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_empty_result(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test handling of empty result set"""
        # Mock performance counter
        mock_perf_counter.side_effect = [0.0, 0.1]

        # Mock empty DataFrame
        mock_data = pd.DataFrame()

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.integrity_check.return_value = True
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_mkt_orders()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        assert result.index.tolist() == []  # Empty index

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_performance_timing(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test that performance timing is measured and logged"""
        # Mock performance counter with specific timing
        mock_perf_counter.side_effect = [0.0, 0.123]  # 123ms execution time

        # Mock data
        mock_data = pd.DataFrame({
            'order_id': [1],
            'type_id': [12345],
            'price': [100.5],
            'volume': [1000],
            'is_buy_order': [True]
        })

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.integrity_check.return_value = True
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        with patch('db_handler.logger') as mock_logger:
            result = get_all_mkt_orders()

            # Verify performance timing was logged
            mock_logger.info.assert_any_call("TIME get_all_mkt_orders() = 123.0 ms")
            mock_logger.info.assert_any_call("-" * 40)

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_integrity_check_exception(self, mock_perf_counter, mock_read_sql, mock_mkt_db):
        """Test handling of integrity check exception"""
        # Mock performance counter
        mock_perf_counter.side_effect = [0.0, 0.1]

        # Mock data
        mock_data = pd.DataFrame({
            'order_id': [1],
            'type_id': [12345],
            'price': [100.5],
            'volume': [1000],
            'is_buy_order': [True]
        })

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        # Mock integrity check exception
        mock_mkt_db.integrity_check.side_effect = Exception("Integrity check failed")
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        with patch('db_handler.logger') as mock_logger:
            result = get_all_mkt_orders()

            # Should still succeed despite integrity check exception
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1

            # Verify error was logged
            mock_logger.error.assert_any_call("Pre-read sync attempt failed: Integrity check failed")


if __name__ == "__main__":
    pytest.main([__file__])
