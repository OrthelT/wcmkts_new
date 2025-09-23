#!/usr/bin/env python3
"""
Example script showing how to run individual tests without pytest.
This demonstrates that the import structure is working correctly.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_simple_test():
    """Run a simple test to demonstrate imports work"""
    try:
        # Import the function we want to test
        from db_handler import get_market_history

        # Import the test class
        from tests.test_get_market_history import TestGetMarketHistory

        print("✅ Successfully imported:")
        print("  - db_handler.get_market_history")
        print("  - tests.test_get_market_history.TestGetMarketHistory")

        # Create test instance
        test_instance = TestGetMarketHistory()

        print("✅ Successfully created test instance")
        print(f"  - Test class: {test_instance.__class__.__name__}")
        print(f"  - Available test methods: {[method for method in dir(test_instance) if method.startswith('test_')]}")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main function"""
    print("Testing import structure...")
    print("=" * 50)

    if run_simple_test():
        print("\n✅ Import structure is working correctly!")
        print("\nYou can now run tests with:")
        print("  uv run pytest tests/ -v")
        print("  uv run python run_tests.py")
    else:
        print("\n❌ Import structure has issues")
        sys.exit(1)

if __name__ == "__main__":
    main()
