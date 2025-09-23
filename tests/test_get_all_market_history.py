"""
Tests for get_all_market_history function in db_handler.py
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from db_handler import get_all_market_history


class TestGetAllMarketHistory:
    """Test cases for get_all_market_history function"""

    @patch('streamlit.cache_data')
    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_success(self, mock_read_sql, mock_mkt_db, mock_cache):
        """Test successful retrieval of all market history data"""
        # Mock cache decorator to pass through function
        mock_cache.return_value = lambda func: func

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

    @patch('streamlit.cache_data')
    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    def test_get_all_market_history_index_reset(self, mock_read_sql, mock_mkt_db, mock_cache):
        """Test that DataFrame index is properly reset"""
        # Mock cache decorator
        mock_cache.return_value = lambda func: func

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