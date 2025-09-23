"""
Tests for get_market_history function in db_handler.py
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from db_handler import get_market_history


class TestGetMarketHistory:
    """Test cases for get_market_history function"""

    @patch('streamlit.cache_data')
    @patch('db_handler.mkt_db')
    def test_get_market_history_success(self, mock_mkt_db, mock_cache):
        """Test successful retrieval of market history data"""
        # Mock cache decorator
        mock_cache.return_value = lambda func: func

        # Mock data
        mock_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02', '2024-01-03'],
            'average': [100.5, 101.2, 99.8],
            'volume': [1000, 1500, 800]
        })

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        # Mock pd.read_sql_query
        with patch('db_handler.pd.read_sql_query', return_value=mock_data) as mock_read_sql:
            result = get_market_history(12345)

            # Assertions
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 3
            assert list(result.columns) == ['date', 'average', 'volume']
            assert result.iloc[0]['date'] == '2024-01-01'
            assert result.iloc[0]['average'] == 100.5
            assert result.iloc[0]['volume'] == 1000

            # Verify SQL query was called with correct parameters
            mock_read_sql.assert_called_once()
            call_args = mock_read_sql.call_args
            assert call_args[1]['params']['type_id'] == 12345

    @patch('streamlit.cache_data')
    @patch('db_handler.mkt_db')
    def test_get_market_history_empty_result(self, mock_mkt_db, mock_cache):
        """Test handling of empty result set"""
        # Mock cache decorator
        mock_cache.return_value = lambda func: func

        # Mock empty DataFrame
        mock_data = pd.DataFrame(columns=['date', 'average', 'volume'])

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        with patch('db_handler.pd.read_sql_query', return_value=mock_data):
            result = get_market_history(99999)

            # Assertions
            assert isinstance(result, pd.DataFrame)
            assert len(result) == 0
            assert list(result.columns) == ['date', 'average', 'volume']

    @patch('streamlit.cache_data')
    @patch('db_handler.mkt_db')
    def test_get_market_history_function_signature(self, mock_mkt_db, mock_cache):
        """Test that function accepts correct parameters and returns DataFrame"""
        # Mock cache decorator
        mock_cache.return_value = lambda func: func

        # Mock successful database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        # Mock data
        mock_data = pd.DataFrame({
            'date': ['2024-01-01'],
            'average': [100.5],
            'volume': [1000]
        })

        with patch('db_handler.pd.read_sql_query', return_value=mock_data):
            # Test with different type_id values
            result1 = get_market_history(12345)
            result2 = get_market_history(0)
            result3 = get_market_history(-1)

            # All should return DataFrames
            assert isinstance(result1, pd.DataFrame)
            assert isinstance(result2, pd.DataFrame)
            assert isinstance(result3, pd.DataFrame)

    def test_get_market_history_function_exists(self):
        """Test that the function exists and is callable"""
        # Test that the function exists and can be imported
        from db_handler import get_market_history

        # Test that it's callable
        assert callable(get_market_history)

        # Test that it has the expected signature (takes one argument)
        import inspect
        sig = inspect.signature(get_market_history)
        assert len(sig.parameters) == 1
        assert 'type_id' in sig.parameters

    @patch('streamlit.cache_data')
    def test_get_market_history_return_type(self, mock_cache):
        """Test that function returns a DataFrame"""
        # Mock cache decorator
        mock_cache.return_value = lambda func: func

        with patch('db_handler.mkt_db') as mock_mkt_db:
            # Mock database connection
            mock_conn = Mock()
            mock_conn.__enter__ = Mock(return_value=mock_conn)
            mock_conn.__exit__ = Mock(return_value=None)

            mock_engine = Mock()
            mock_engine.connect.return_value = mock_conn

            mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
            mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
            mock_mkt_db.engine = mock_engine

            # Mock data
            mock_data = pd.DataFrame({
                'date': ['2024-01-01'],
                'average': [100.5],
                'volume': [1000]
            })

            with patch('db_handler.pd.read_sql_query', return_value=mock_data):
                result = get_market_history(12345)

                # Should return a DataFrame
                assert isinstance(result, pd.DataFrame)
                assert hasattr(result, 'columns')
                assert hasattr(result, 'index')

    @patch('streamlit.cache_data')
    @patch('db_handler.mkt_db')
    def test_get_market_history_data_types(self, mock_mkt_db, mock_cache):
        """Test that returned data has correct data types"""
        # Mock cache decorator
        mock_cache.return_value = lambda func: func

        # Mock data with various data types
        mock_data = pd.DataFrame({
            'date': ['2024-01-01', '2024-01-02'],
            'average': [100.5, 101.2],
            'volume': [1000, 1500]
        })

        # Mock database connection
        mock_conn = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)

        mock_engine = Mock()
        mock_engine.connect.return_value = mock_conn

        mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
        mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
        mock_mkt_db.engine = mock_engine

        with patch('db_handler.pd.read_sql_query', return_value=mock_data):
            result = get_market_history(12345)

            # Check data types (pandas may return numpy types)
            assert isinstance(result['date'].iloc[0], str)
            assert isinstance(result['average'].iloc[0], (int, float, type(result['average'].iloc[0])))
            assert isinstance(result['volume'].iloc[0], (int, float, type(result['volume'].iloc[0])))


if __name__ == "__main__":
    pytest.main([__file__])