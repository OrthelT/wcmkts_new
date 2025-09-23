# Testing Documentation

## Overview

This document describes the testing approach, setup, and usage for the wcmkts_refactor project. The project uses pytest as the testing framework with comprehensive test coverage for database functions and business logic.

## Test Structure

### Directory Organization

```
tests/
├── __init__.py                 # Makes tests a Python package
├── conftest.py                 # Pytest configuration and path setup
├── test_get_market_history.py  # Tests for get_market_history function
├── test_get_fitting_data.py    # Tests for get_fitting_data function
├── test_get_all_mkt_orders.py  # Tests for get_all_mkt_orders function
├── test_get_all_market_history.py # Tests for get_all_market_history function
├── test_clean_mkt_data.py      # Tests for data cleaning functions
├── test_fetch_industry_indices.py # Tests for industry index functions
├── test_logging_config.py      # Tests for logging configuration
├── test_safe_format.py         # Tests for safe formatting functions
└── pages/                      # Tests for pages module (if needed)
    └── __init__.py
```

### Test File Naming Convention

- All test files follow the pattern: `test_*.py`
- Test classes follow the pattern: `Test*`
- Test methods follow the pattern: `test_*`

## Configuration Files

### pytest.ini

Located in the project root, this file configures pytest behavior:

```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
pythonpath = .
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
```

### conftest.py

Located in the `tests/` directory, this file sets up the Python path so tests can import modules from the project root:

```python
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
```

## Test Coverage

### Database Functions

The test suite provides comprehensive coverage for the following database functions:

#### get_market_history(type_id: int)
- ✅ Successful data retrieval
- ✅ Empty result handling
- ✅ Function signature validation
- ✅ Return type validation
- ✅ Data type validation

#### get_fitting_data(type_id)
- ✅ Successful data retrieval with column processing
- ✅ Empty input handling
- ✅ Type ID not found scenarios
- ✅ Error handling (IndexError, KeyError)
- ✅ Column dropping validation
- ✅ Data type conversion (float to int)
- ✅ Sorting validation
- ✅ Multiple fit_ids handling

#### get_all_mkt_orders()
- ✅ Successful data retrieval
- ✅ Integrity check failure handling
- ✅ Malformed database retry mechanism
- ✅ Fallback to remote database
- ✅ Non-malformed error handling
- ✅ Empty result handling
- ✅ Performance timing measurement
- ✅ Integrity check exception handling

#### get_all_market_history()
- ✅ Successful data retrieval
- ✅ Empty result handling
- ✅ Database error retry mechanism
- ✅ Sync failure handling
- ✅ Connection error handling
- ✅ Large dataset handling
- ✅ Data type validation
- ✅ SQL query structure validation
- ✅ Index reset validation

### Utility Functions

Additional tests cover utility functions for:
- Data cleaning and transformation
- Industry index fetching
- Logging configuration
- Safe number formatting

## Running Tests

### Prerequisites

Ensure you have the project dependencies installed:

```bash
uv sync
```

### Basic Test Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_get_market_history.py -v

# Run specific test class
uv run pytest tests/test_get_market_history.py::TestGetMarketHistory -v

# Run specific test method
uv run pytest tests/test_get_market_history.py::TestGetMarketHistory::test_get_market_history_success -v

# Run tests with pattern matching
uv run pytest tests/ -k "test_get_market_history" -v
```

### Test Discovery

```bash
# List all available tests without running them
uv run pytest tests/ --collect-only -q

# Show test collection with more detail
uv run pytest tests/ --collect-only -v
```

### Test Markers

```bash
# Run only unit tests
uv run pytest tests/ -m unit -v

# Run only integration tests
uv run pytest tests/ -m integration -v

# Skip slow tests
uv run pytest tests/ -m "not slow" -v
```

## Test Development Guidelines

### Writing New Tests

1. **Create test file**: Follow the naming convention `test_*.py`
2. **Create test class**: Use `Test*` naming convention
3. **Write test methods**: Use `test_*` naming convention
4. **Use descriptive names**: Test names should clearly indicate what is being tested

Example:

```python
class TestNewFunction:
    """Test cases for new_function"""

    def test_new_function_success(self):
        """Test successful execution of new_function"""
        # Test implementation
        pass

    def test_new_function_error_handling(self):
        """Test error handling in new_function"""
        # Test implementation
        pass
```

### Mocking Guidelines

The tests use extensive mocking to isolate units under test:

```python
from unittest.mock import Mock, patch

@patch('db_handler.mkt_db')
def test_function_with_database(self, mock_mkt_db):
    """Test function that uses database"""
    # Mock database connection
    mock_conn = Mock()
    mock_conn.__enter__ = Mock(return_value=mock_conn)
    mock_conn.__exit__ = Mock(return_value=None)

    mock_engine = Mock()
    mock_engine.connect.return_value = mock_conn

    mock_mkt_db.local_access.return_value.__enter__ = Mock(return_value=None)
    mock_mkt_db.local_access.return_value.__exit__ = Mock(return_value=None)
    mock_mkt_db.engine = mock_engine

    # Test implementation
    pass
```

### Test Data

Use realistic test data that matches the expected data structure:

```python
mock_data = pd.DataFrame({
    'date': ['2024-01-01', '2024-01-02'],
    'type_id': [12345, 67890],
    'average': [100.5, 200.0],
    'volume': [1000, 500]
})
```

## Continuous Integration

### GitHub Actions (Recommended)

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'

    - name: Install uv
      uses: astral-sh/setup-uv@v1

    - name: Install dependencies
      run: uv sync

    - name: Run tests
      run: uv run pytest tests/ -v --tb=short
```

## Test Utilities

### Validation Script

The project includes `run_tests.py` for validating test structure without pytest:

```bash
uv run python run_tests.py
```

This script:
- Validates that all test files can be imported
- Counts test classes and methods
- Provides a summary of test coverage

### Example Test Runner

The project includes `example_test_run.py` demonstrating how to run individual tests:

```bash
uv run python example_test_run.py
```

## Best Practices

### Test Organization

1. **One test class per function/module**
2. **Group related tests together**
3. **Use descriptive test names**
4. **Include docstrings for test methods**

### Assertions

1. **Use specific assertions**: `assert isinstance(result, pd.DataFrame)`
2. **Test both positive and negative cases**
3. **Validate data types and structure**
4. **Check edge cases and error conditions**

### Mocking

1. **Mock external dependencies** (database, APIs, file system)
2. **Use realistic mock data**
3. **Verify mock interactions when relevant**
4. **Keep mocks simple and focused**

### Performance

1. **Use markers for slow tests**
2. **Mock expensive operations**
3. **Run fast tests frequently**
4. **Use parallel execution for large test suites**

## Troubleshooting

### Common Issues

#### Import Errors
```
ModuleNotFoundError: No module named 'db_handler'
```
**Solution**: Ensure `conftest.py` is in the `tests/` directory and properly configured.

#### Test Discovery Issues
```
collected 0 items
```
**Solution**: Check that test files follow naming conventions and are in the correct directory.

#### Mock Issues
```
AssertionError: Expected 'function' to have been called once. Called 0 times.
```
**Solution**: Verify mock setup and ensure the mocked function is actually called in the code path.

### Debug Mode

Run tests with additional debugging information:

```bash
# Show local variables on failure
uv run pytest tests/ -v --tb=long

# Drop into debugger on failure
uv run pytest tests/ -v --pdb

# Show print statements
uv run pytest tests/ -v -s
```

## Metrics and Coverage

### Test Statistics

Current test suite statistics:
- **Total test files**: 8
- **Total test methods**: 38
- **Test categories**:
  - Database functions: 32 tests
  - Utility functions: 6 tests

### Coverage Goals

- **Function coverage**: 100% for critical database functions
- **Branch coverage**: 80%+ for error handling paths
- **Integration coverage**: Key user workflows

## Contributing

When adding new features:

1. **Write tests first** (TDD approach)
2. **Ensure all tests pass**
3. **Add tests for error cases**
4. **Update this documentation**
5. **Run the full test suite before committing**

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- [pandas Testing](https://pandas.pydata.org/docs/development/contributing.html#testing)
- [Python Testing Best Practices](https://docs.python-guide.org/writing/tests/)
