"""
Tests for get_all_market_history function in db_handler.py
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from db_handler import get_all_market_history


class TestGetAllMarketHistory:
    """Test cases for get_all_market_history function"""

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_success(self, mock_read_sql, mock_mkt_db):
        """Test successful retrieval of all market history data"""
        # Mock data
        mock_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'type_id': [12345, 67890, 11111],
            'average': [100.5, 200.0, 150.75],
            'volume': [1000, 500, 2000],
            'highest': [105.0, 210.0, 155.0],
            'lowest': [95.0, 190.0, 145.0],
            'order_count': [10, 5, 20]
        })

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_market_history()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3
        assert list(result.columns) == ['date', 'type_id', 'average', 'volume', 'highest', 'lowest', 'order_count']
        assert result.index.tolist() == [0, 1, 2]  # Index should be reset

        # Verify data integrity
        assert result.iloc[0]['date'] == '2024-01-01'
        assert result.iloc[0]['type_id'] == 12345
        assert result.iloc[0]['average'] == 100.5
        assert result.iloc[0]['volume'] == 1000

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_empty_result(self, mock_read_sql, mock_mkt_db):
        """Test handling of empty result set"""
        # Mock empty DataFrame
        mock_data = pd.DataFrame()

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_market_history()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        assert result.index.tolist() == []  # Empty index

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_database_error_retry(self, mock_read_sql, mock_mkt_db):
        """Test retry mechanism when database read fails"""
        # Mock data for successful retry
        mock_data = pd.DataFrame({
            'date': ['2024-01-01'],
            'type_id': [12345],
            'average': [100.5],
            'volume': [1000],
            'highest': [105.0],
            'lowest': [95.0],
            'order_count': [10]
        })

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.sync.return_value = None
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        # Mock first call fails, second call succeeds
        mock_read_sql.side_effect = [
            Exception("Database connection failed"),
            mock_data
        ]

        with patch('db_handler.logger') as mock_logger:
            result = get_all_market_history()

            # Assertions
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 1

            # Verify sync was called after first failure
            mock_mkt_db.sync.assert_called_once()

            # Verify error was logged
            mock_logger.error.assert_any_call("Failed to get market history: Database connection failed")
            mock_logger.error.assert_any_call("Failed to get market history after sync: Database connection failed")

            # Verify read_sql_query was called twice (first fails, second succeeds)
            assert mock_read_sql.call_count == 2

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_sync_failure(self, mock_read_sql, mock_mkt_db):
        """Test handling when sync fails after initial database error"""
        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.sync.side_effect = Exception("Sync failed")
        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        # Mock first call fails
        mock_read_sql.side_effect = Exception("Database connection failed")

        with patch('db_handler.logger') as mock_logger:
            with pytest.raises(Exception, match="Database connection failed"):
                get_all_market_history()

            # Verify sync was called
            mock_mkt_db.sync.assert_called_once()

            # Verify errors were logged
            mock_logger.error.assert_any_call("Failed to get market history: Database connection failed")
            mock_logger.error.assert_any_call("Failed to get market history after sync: Database connection failed")

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_connection_error(self, mock_read_sql, mock_mkt_db):
        """Test handling of database connection errors"""
        # Mock database connection error
        mock_mkt_db.local_access.side_effect = Exception("Connection failed")

        with patch('db_handler.logger') as mock_logger:
            with pytest.raises(Exception, match="Connection failed"):
                get_all_market_history()

            # Verify error was logged
            mock_logger.error.assert_any_call("Failed to get market history: Connection failed")

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_large_dataset(self, mock_read_sql, mock_mkt_db):
        """Test handling of large dataset"""
        # Mock large dataset
        large_data = []
        for i in range(1000):
            large_data.append({
                'date': f'2024-01-{(i % 30) + 1:02d}',
                'type_id': 12345 + (i % 100),
                'average': 100.0 + (i % 50),
                'volume': 1000 + (i % 500),
                'highest': 105.0 + (i % 50),
                'lowest': 95.0 + (i % 50),
                'order_count': 10 + (i % 20)
            })

        mock_data = pd.DataFrame(large_data)
        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_market_history()

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1000
        assert result.index.tolist() == list(range(1000))  # Index should be reset

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_data_types(self, mock_read_sql, mock_mkt_db):
        """Test that returned data has correct data types"""
        # Mock data with various data types
        mock_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'type_id': [12345, 67890],
            'average': [100.5, 200.0],
            'volume': [1000, 500],
            'highest': [105.0, 210.0],
            'lowest': [95.0, 190.0],
            'order_count': [10, 5]
        })

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_market_history()

        # Check data types
        assert isinstance(result['date'].iloc[0], str)
        assert isinstance(result['type_id'].iloc[0], (int, float))
        assert isinstance(result['average'].iloc[0], (int, float))
        assert isinstance(result['volume'].iloc[0], (int, float))
        assert isinstance(result['highest'].iloc[0], (int, float))
        assert isinstance(result['lowest'].iloc[0], (int, float))
        assert isinstance(result['order_count'].iloc[0], (int, float))

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_sql_query_structure(self, mock_read_sql, mock_mkt_db):
        """Test that the correct SQL query is executed"""
        # Mock data
        mock_data = pd.DataFrame({
            'date': ['2024-01-01'],
            'type_id': [12345],
            'average': [100.5],
            'volume': [1000],
            'highest': [105.0],
            'lowest': [95.0],
            'order_count': [10]
        })

        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_market_history()

        # Verify SQL query was called
        mock_read_sql.assert_called_once()
        call_args = mock_read_sql.call_args

        # Check that the query contains the expected table name
        query = call_args[0][0]  # First positional argument
        assert "SELECT * FROM market_history" in str(query)

    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_index_reset(self, mock_read_sql, mock_mkt_db):
        """Test that DataFrame index is properly reset"""
        # Mock data with non-sequential index
        mock_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'type_id': [12345, 67890, 11111],
            'average': [100.5, 200.0, 150.75],
            'volume': [1000, 500, 2000],
            'highest': [105.0, 210.0, 155.0],
            'lowest': [95.0, 190.0, 145.0],
            'order_count': [10, 5, 20]
        })

        # Set non-sequential index
        mock_data.index = [5, 10, 15]
        mock_read_sql.return_value = mock_data

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        result = get_all_market_history()

        # Verify index is reset
        assert result.index.tolist() == [0, 1, 2]


if __name__ == "__main__":
    pytest.main([__file__])
