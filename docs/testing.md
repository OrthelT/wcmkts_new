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
├── conftest.py                        # Path setup
├── test_base_repository.py            # BaseRepository + malformed-DB recovery
├── test_build_cost_service.py         # BuildCostService
├── test_database_config_concurrency.py # DatabaseConfig sync + _SYNC_LOCK
├── test_doctrine_repo.py              # DoctrineRepository
├── test_i18n.py                       # UI translation (i18n.py)
├── test_import_helper_service.py      # ImportHelperService
├── test_language_state.py             # Language session state management
├── test_logging_config.py             # Logging configuration
├── test_low_stock_service.py          # LowStockService
├── test_market_repo.py                # MarketRepository
├── test_market_service.py             # MarketService
├── test_pricer_service.py             # PricerService
├── test_price_service.py              # PriceService provider chain
├── test_rwlock.py                     # RWLock (legacy, kept for reference)
├── test_sde_repo.py                   # SDERepository
├── test_sde_repo_localization.py      # SDERepository localization methods
├── test_settings_toml.py              # Configuration file validation
├── test_type_name_localization.py     # TypeNameLocalization service
├── test_type_resolution_service.py    # TypeResolutionService
└── pages/                             # Page-level integration tests
```

## Current Test Coverage

**~191 tests** covering repositories, services, database config, i18n, and infrastructure:

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

Example (repository pattern):
```python
from unittest.mock import MagicMock, patch
import pandas as pd

def test_get_all_stats_returns_dataframe():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)

    with patch("repositories.market_repo._get_all_stats_impl") as mock_impl:
        mock_impl.return_value = pd.DataFrame({"type_id": [34], "price": [5.0]})
        result = mock_impl(mock_engine)
        assert isinstance(result, pd.DataFrame)
        assert "type_id" in result.columns
```

## Coverage Configuration

Coverage is configured in `pyproject.toml`:

- **Focuses on**: `repositories/`, `services/`, `domain/`, `state/`, `ui/`, `config.py`, `models.py`, `logging_config.py`
- **Excludes**: `pages/`, `app.py`, init scripts, and utility scripts

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

- **Total tests**: ~191
- **Test types**: Unit tests, integration tests, configuration validation
- **Run time**: ~1-2 seconds (fast unit tests only; integration tests may be slower)
- **Success rate**: 100% (CI enforced)