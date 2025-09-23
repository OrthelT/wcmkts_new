"""
Tests for get_all_mkt_orders function in db_handler.py
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from db_handler import get_all_mkt_orders


class TestGetAllMktOrders:
    """Test cases for get_all_mkt_orders function"""

    @patch('streamlit.cache_data')
    @patch('db_handler.mkt_db')
    @patch('db_handler.pd.read_sql_query')
    @patch('db_handler.time.perf_counter')
    def test_get_all_mkt_orders_success(self, mock_perf_counter, mock_read_sql, mock_mkt_db, mock_cache):
        """Test successful retrieval of all market orders"""
        # Mock cache decorator
        mock_cache.return_value = lambda func: func

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


if __name__ == "__main__":
    pytest.main([__file__])