# Testing Documentation

## Overview

The project uses pytest to test database functions and business logic with a focus on **public API behavior** rather than implementation details.

## Running Tests

```bash
# Install dependencies
uv sync

# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_get_market_history.py -v

# Run with coverage (terminal report)
uv run pytest tests/ --cov=. --cov-report=term-missing

# Run with coverage (HTML report)
uv run pytest tests/ --cov=. --cov-report=html
# Open htmlcov/index.html in browser to view detailed coverage
```

## Test Structure

```
tests/
├── conftest.py                      # Path setup
├── test_get_market_history.py       # Market history functions
├── test_get_fitting_data.py         # Doctrine fitting functions
├── test_get_all_mkt_orders.py       # Market order functions
├── test_get_all_market_history.py   # All market history functions
├── test_clean_mkt_data.py           # Data cleaning utilities
├── test_fetch_industry_indices.py   # Industry index functions
├── test_logging_config.py           # Logging configuration
├── test_safe_format.py              # Number formatting utilities
└── test_settings_toml.py            # Configuration file validation
```

## Current Test Coverage

**34 tests** (24 unit tests + 10 config validation tests) covering core functionality:

- **Success cases**: Normal function operation
- **Data validation**: Return types and structure
- **Edge cases**: Empty inputs, missing data
- **API contracts**: Function signatures and behavior
- **Configuration validation**: TOML structure and schema compliance

## Testing Approach

### What We Test
- ✅ **Function behavior** - Does it return the right data?
- ✅ **Data types** - Are return types correct?
- ✅ **Edge cases** - Empty results, missing inputs
- ✅ **API contracts** - Function signatures
- ✅ **Configuration files** - TOML structure, required fields, data types

### What We Don't Test
- ❌ **Implementation details** - Internal error handling
- ❌ **Database internals** - SQL query structure
- ❌ **Complex error scenarios** - Retry mechanisms, fallbacks

### Mocking Strategy
- Mock `@st.cache_data` decorators with passthrough functions
- Mock database connections at the engine level
- Use realistic test data that matches expected schemas
- Keep mocks simple and focused on the function being tested

## Configuration

**pytest.ini**:
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
pythonpath = .
```

**conftest.py**: Sets up Python path for imports

## Writing New Tests

1. **Test public behavior**, not implementation
2. **Use descriptive test names**: `test_function_name_scenario`
3. **Mock external dependencies** (database, Streamlit cache)
4. **Use realistic test data**
5. **Keep tests simple and focused**

Example:
```python
@patch('streamlit.cache_data')
@patch('db_handler.mkt_db')
def test_function_success(self, mock_db, mock_cache):
    mock_cache.return_value = lambda func: func
    # Setup mocks and test function behavior
```

## Coverage Configuration

The project uses `.coveragerc` to configure code coverage:

- **Focuses on core modules**: `db_handler.py`, `utils.py`, `models.py`, `logging_config.py`, `config.py`
- **Excludes**: Pages, app.py, init scripts, and utility scripts
- **Minimum coverage**: 40% (focused on tested core functions)
- **Current coverage**: ~50% of core modules

## Configuration Testing

### settings.toml Validation

The `test_settings_toml.py` suite ensures `settings.toml` maintains proper structure:

**Validates:**
- File parsing (TOML syntax)
- Required sections (`ship_roles`)
- Required categories (`dps`, `logi`, `links`, `support`, `special_cases`)
- Data types (lists of strings, nested dictionaries)
- Non-empty role lists
- Special cases structure (ship_name -> fit_id -> role mapping)
- No duplicate ships across categories
- Compatibility with code usage patterns

**Benefits:**
- Catches configuration errors before runtime
- Prevents breaking changes during manual edits
- Validates structure matches code expectations
- Ensures role assignments are consistent

**Run configuration tests:**
```bash
uv run pytest tests/test_settings_toml.py -v
```

## Key Metrics

- **Total tests**: 34 (24 unit + 10 config validation)
- **Test types**: Unit tests and configuration validation
- **Run time**: ~0.7 seconds
- **Success rate**: 100%
- **Coverage**: 50.5% of core modules (40%+ required)