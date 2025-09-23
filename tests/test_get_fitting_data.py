"""
Tests for get_fitting_data function in db_handler.py
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from db_handler import get_fitting_data


class TestGetFittingData:
    """Test cases for get_fitting_data function"""

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_success(self, mock_get_all_fitting_data):
        """Test successful retrieval of fitting data"""
        # Mock data with multiple fits for the same fit_id
        mock_data = pd.DataFrame({
            'type_id': [12345, 12345, 12345, 67890, 67890],
            'fit_id': [100, 100, 100, 200, 200],
            'ship_id': [1, 2, 3, 4, 5],
            'hulls': [1, 1, 1, 2, 2],
            'group_id': [1, 1, 1, 2, 2],
            'category_name': ['Ship1', 'Ship1', 'Ship1', 'Ship2', 'Ship2'],
            'id': [1, 2, 3, 4, 5],
            'timestamp': ['2024-01-01', '2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02'],
            'fits_on_mkt': [5, 10, 15, 3, 7]
        })

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)

        # Assertions
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 3  # Should return all rows with fit_id=100
        assert 'ship_id' not in result.columns  # Should be dropped
        assert 'hulls' not in result.columns  # Should be dropped
        assert 'group_id' not in result.columns  # Should be dropped
        assert 'category_name' not in result.columns  # Should be dropped
        assert 'id' not in result.columns  # Should be dropped
        assert 'timestamp' not in result.columns  # Should be dropped
        assert 'Fits on Market' in result.columns  # Should be renamed
        assert result['type_id'].dtype == 'int64'  # Should be converted to int
        assert result['fit_id'].dtype == 'int64'  # Should be converted to int

        # Check sorting by 'Fits on Market' ascending
        assert result['Fits on Market'].tolist() == [5, 10, 15]

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_empty_input(self, mock_get_all_fitting_data):
        """Test handling of empty input data"""
        mock_get_all_fitting_data.return_value = pd.DataFrame()

        result = get_fitting_data(12345)

        assert result is None

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_type_id_not_found(self, mock_get_all_fitting_data):
        """Test handling when type_id is not found in data"""
        mock_data = pd.DataFrame({
            'type_id': [67890, 67890],
            'fit_id': [200, 200],
            'ship_id': [4, 5],
            'hulls': [2, 2],
            'group_id': [2, 2],
            'category_name': ['Ship2', 'Ship2'],
            'id': [4, 5],
            'timestamp': ['2024-01-02', '2024-01-02'],
            'fits_on_mkt': [3, 7]
        })

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)  # type_id not in data

        assert result is None

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_index_error(self, mock_get_all_fitting_data):
        """Test handling of IndexError when accessing first row"""
        # Mock data that will cause IndexError when trying to access iloc[0]
        mock_data = pd.DataFrame(columns=['type_id', 'fit_id', 'ship_id', 'hulls', 'group_id',
                                        'category_name', 'id', 'timestamp', 'fits_on_mkt'])

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)

        assert result is None

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_key_error(self, mock_get_all_fitting_data):
        """Test handling of KeyError when accessing fit_id column"""
        # Mock data without fit_id column
        mock_data = pd.DataFrame({
            'type_id': [12345],
            'ship_id': [1],
            'hulls': [1],
            'group_id': [1],
            'category_name': ['Ship1'],
            'id': [1],
            'timestamp': ['2024-01-01'],
            'fits_on_mkt': [5]
        })

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)

        assert result is None

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_column_dropping(self, mock_get_all_fitting_data):
        """Test that specified columns are properly dropped"""
        mock_data = pd.DataFrame({
            'type_id': [12345],
            'fit_id': [100],
            'ship_id': [1],
            'hulls': [1],
            'group_id': [1],
            'category_name': ['Ship1'],
            'id': [1],
            'timestamp': ['2024-01-01'],
            'fits_on_mkt': [5],
            'extra_column': ['extra']  # This should remain
        })

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)

        # Check that specified columns are dropped
        dropped_columns = ['ship_id', 'hulls', 'group_id', 'category_name', 'id', 'timestamp']
        for col in dropped_columns:
            assert col not in result.columns

        # Check that other columns remain
        assert 'type_id' in result.columns
        assert 'fit_id' in result.columns
        assert 'Fits on Market' in result.columns
        assert 'extra_column' in result.columns

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_data_type_conversion(self, mock_get_all_fitting_data):
        """Test that type_id and fit_id are converted to integers"""
        mock_data = pd.DataFrame({
            'type_id': [12345.0, 12345.7],  # Float values
            'fit_id': [100.0, 100.5],  # Float values
            'ship_id': [1, 2],
            'hulls': [1, 1],
            'group_id': [1, 1],
            'category_name': ['Ship1', 'Ship1'],
            'id': [1, 2],
            'timestamp': ['2024-01-01', '2024-01-01'],
            'fits_on_mkt': [5, 10]
        })

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)

        # Check data type conversion
        assert result['type_id'].dtype == 'int64'
        assert result['fit_id'].dtype == 'int64'

        # Check that values are properly rounded and converted
        assert result['type_id'].iloc[0] == 12345
        assert result['type_id'].iloc[1] == 12346  # 12345.7 rounded to 12346
        assert result['fit_id'].iloc[0] == 100
        assert result['fit_id'].iloc[1] == 101  # 100.5 rounded to 101

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_sorting(self, mock_get_all_fitting_data):
        """Test that results are sorted by 'Fits on Market' in ascending order"""
        mock_data = pd.DataFrame({
            'type_id': [12345, 12345, 12345],
            'fit_id': [100, 100, 100],
            'ship_id': [1, 2, 3],
            'hulls': [1, 1, 1],
            'group_id': [1, 1, 1],
            'category_name': ['Ship1', 'Ship1', 'Ship1'],
            'id': [1, 2, 3],
            'timestamp': ['2024-01-01', '2024-01-01', '2024-01-01'],
            'fits_on_mkt': [15, 5, 10]  # Unsorted values
        })

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)

        # Check that results are sorted by 'Fits on Market' ascending
        assert result['Fits on Market'].tolist() == [5, 10, 15]
        assert result.index.tolist() == [0, 1, 2]  # Index should be reset

    @patch('db_handler.get_all_fitting_data')
    def test_get_fitting_data_multiple_fit_ids(self, mock_get_all_fitting_data):
        """Test behavior when multiple fit_ids exist for the same type_id"""
        mock_data = pd.DataFrame({
            'type_id': [12345, 12345, 12345, 12345],
            'fit_id': [100, 100, 200, 200],
            'ship_id': [1, 2, 3, 4],
            'hulls': [1, 1, 2, 2],
            'group_id': [1, 1, 2, 2],
            'category_name': ['Ship1', 'Ship1', 'Ship2', 'Ship2'],
            'id': [1, 2, 3, 4],
            'timestamp': ['2024-01-01', '2024-01-01', '2024-01-02', '2024-01-02'],
            'fits_on_mkt': [5, 10, 3, 7]
        })

        mock_get_all_fitting_data.return_value = mock_data

        result = get_fitting_data(12345)

        # Should return only rows with the first fit_id found (100)
        assert len(result) == 2
        assert all(result['fit_id'] == 100)
        assert result['Fits on Market'].tolist() == [5, 10]


if __name__ == "__main__":
    pytest.main([__file__])
