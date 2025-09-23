"""
Simple test runner to validate test file structure without pytest
"""
import sys
import importlib.util
import os

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
    test_files = [
        "test_get_market_history.py",
        "test_get_fitting_data.py",
        "test_get_all_mkt_orders.py",
        "test_get_all_market_history.py"
    ]

    print("Validating test files...")
    print("=" * 50)

    all_passed = True
    for test_file in test_files:
        file_path = os.path.join(os.path.dirname(__file__), test_file)
        if os.path.exists(file_path):
            if not validate_test_file(file_path):
                all_passed = False
        else:
            print(f"❌ {test_file}: File not found")
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("✅ All test files validated successfully!")
    else:
        print("❌ Some test files failed validation")
        sys.exit(1)

if __name__ == "__main__":
    main()
