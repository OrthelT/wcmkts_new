#!/usr/bin/env python3
"""
Simple test runner that can work without pytest installed.
This script validates that all test files can be imported and have proper structure.
"""
import sys
import os
import importlib.util
from pathlib import Path

def add_project_root_to_path():
    """Add the project root to Python path for imports"""
    project_root = Path(__file__).parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

def validate_test_file(file_path):
    """Validate that a test file can be imported and has proper structure"""
    try:
        # Load the module
        spec = importlib.util.spec_from_file_location("test_module", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Check for test classes
        test_classes = [name for name in dir(module) if name.startswith('Test')]

        print(f"✅ {os.path.basename(file_path)}: {len(test_classes)} test classes found")
        for test_class in test_classes:
            cls = getattr(module, test_class)
            test_methods = [name for name in dir(cls) if name.startswith('test_')]
            print(f"   - {test_class}: {len(test_methods)} test methods")

        return True

    except Exception as e:
        print(f"❌ {os.path.basename(file_path)}: Error - {e}")
        return False

def main():
    """Run validation on all test files"""
    add_project_root_to_path()

    test_files = [
        "test_get_market_history.py",
        "test_get_fitting_data.py",
        "test_get_all_mkt_orders.py",
        "test_get_all_market_history.py",
        "test_clean_mkt_data.py",
        "test_fetch_industry_indices.py",
        "test_logging_config.py",
        "test_safe_format.py"
    ]

    print("Validating test files...")
    print("=" * 60)

    all_passed = True
    total_tests = 0

    for test_file in test_files:
        file_path = os.path.join("tests", test_file)
        if os.path.exists(file_path):
            if validate_test_file(file_path):
                # Count test methods
                spec = importlib.util.spec_from_file_location("test_module", file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                test_classes = [name for name in dir(module) if name.startswith('Test')]
                for test_class in test_classes:
                    cls = getattr(module, test_class)
                    test_methods = [name for name in dir(cls) if name.startswith('test_')]
                    total_tests += len(test_methods)
            else:
                all_passed = False
        else:
            print(f"❌ {test_file}: File not found")
            all_passed = False

    print("=" * 60)
    print(f"Total test methods found: {total_tests}")

    if all_passed:
        print("✅ All test files validated successfully!")
        print("\nTo run tests with pytest:")
        print("  uv run pytest tests/ -v")
        print("  uv run pytest tests/test_get_market_history.py -v")
        print("  uv run pytest tests/ -k 'test_get_market_history_success' -v")
    else:
        print("❌ Some test files failed validation")
        sys.exit(1)

if __name__ == "__main__":
    main()
