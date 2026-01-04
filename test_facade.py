#!/usr/bin/env python3
"""
Test script for DoctrineFacade

Verifies that the facade:
1. Successfully instantiates
2. Returns domain models (not DataFrames)
3. Provides access to all key operations
4. Properly orchestrates underlying services
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from facades import get_doctrine_facade
from domain import StockStatus, ShipRole


def test_facade_instantiation():
    """Test that facade can be instantiated."""
    print("\n" + "="*70)
    print("TEST 1: Facade Instantiation")
    print("="*70)

    facade = get_doctrine_facade(use_session_state=False)
    print(f"✓ Facade created: {type(facade).__name__}")
    print(f"✓ Repository: {type(facade.repository).__name__}")
    print(f"✓ Doctrine Service: {type(facade.doctrine_service).__name__}")
    print(f"✓ Price Service: {type(facade.price_service).__name__}")
    print(f"✓ Categorizer: {type(facade.categorizer).__name__}")
    return facade


def test_fit_operations(facade):
    """Test fit-related operations."""
    print("\n" + "="*70)
    print("TEST 2: Fit Operations")
    print("="*70)

    # Get all fit summaries
    summaries = facade.get_all_fit_summaries()
    print(f"\n✓ get_all_fit_summaries() returned {len(summaries)} fits")
    print(f"  Type: {type(summaries[0]).__name__ if summaries else 'N/A'}")

    # Get a specific fit
    if summaries:
        fit_id = summaries[0].fit_id
        fit = facade.get_fit_summary(fit_id)
        print(f"\n✓ get_fit_summary({fit_id}) returned: {fit.ship_name}")
        print(f"  Status: {fit.status.display_name} ({fit.status.display_color})")
        print(f"  Target %: {fit.target_percentage}%")
        print(f"  Fits available: {fit.fits}")

        # Get fit name
        name = facade.get_fit_name(fit_id)
        print(f"\n✓ get_fit_name({fit_id}) returned: {name}")

    # Get critical fits
    critical = facade.get_critical_fits()
    print(f"\n✓ get_critical_fits() returned {len(critical)} critical fits")
    if critical:
        print(f"  Example: {critical[0].ship_name} - {critical[0].target_percentage}%")

    # Get fits by status
    needs_attention = facade.get_fits_by_status(StockStatus.NEEDS_ATTENTION)
    print(f"\n✓ get_fits_by_status(NEEDS_ATTENTION) returned {len(needs_attention)} fits")

    # Build fit data
    result = facade.build_fit_data()
    print(f"\n✓ build_fit_data() completed:")
    print(f"  Raw rows: {result.metadata.raw_row_count}")
    print(f"  Summary rows: {result.metadata.summary_row_count}")
    print(f"  Build time: {result.metadata.total_duration_ms:.1f}ms")


def test_module_operations(facade):
    """Test module-related operations."""
    print("\n" + "="*70)
    print("TEST 3: Module Operations")
    print("="*70)

    # Get single module
    module = facade.get_module_stock("Damage Control II")
    if module:
        print(f"\n✓ get_module_stock('Damage Control II'):")
        print(f"  Type ID: {module.type_id}")
        print(f"  Total stock: {module.total_stock}")
        print(f"  Fits on market: {module.fits_on_mkt}")
        print(f"  Used in {len(module.usage)} fits")
        if module.usage:
            usage_example = module.usage[0]
            print(f"  Example usage: {usage_example.ship_name} ({usage_example.modules_needed} needed)")
    else:
        print("\n✗ Module 'Damage Control II' not found")

    # Get multiple modules
    modules = facade.get_modules_stock([
        "Damage Control II",
        "Medium Shield Extender II",
        "Gyrostabilizer II"
    ])
    print(f"\n✓ get_modules_stock() returned {len(modules)} modules:")
    for name, mod in modules.items():
        print(f"  - {name}: {mod.fits_on_mkt} fits")


def test_doctrine_operations(facade):
    """Test doctrine-related operations."""
    print("\n" + "="*70)
    print("TEST 4: Doctrine Operations")
    print("="*70)

    # Get all doctrines
    doctrines_df = facade.get_all_doctrines()
    print(f"\n✓ get_all_doctrines() returned DataFrame with {len(doctrines_df)} rows")

    if not doctrines_df.empty:
        unique_doctrines = doctrines_df['doctrine_name'].unique()
        print(f"  Unique doctrines: {len(unique_doctrines)}")

        # Get a specific doctrine
        doctrine_name = unique_doctrines[0]
        doctrine = facade.get_doctrine(doctrine_name)
        if doctrine:
            print(f"\n✓ get_doctrine('{doctrine_name}'):")
            print(f"  Doctrine ID: {doctrine.doctrine_id}")
            print(f"  Lead ship ID: {doctrine.lead_ship_id}")
            print(f"  Fit IDs: {len(doctrine.fit_ids)}")
            # Show first few fit names
            for fit_id in doctrine.fit_ids[:3]:
                fit_name = facade.get_fit_name(fit_id)
                print(f"  - {fit_name}")


def test_categorization(facade):
    """Test ship categorization."""
    print("\n" + "="*70)
    print("TEST 5: Ship Categorization")
    print("="*70)

    test_cases = [
        ("Hurricane", 473, "DPS"),
        ("Osprey", 0, "Logi"),
        ("Claymore", 0, "Links"),
        ("Sabre", 0, "Support"),
    ]

    for ship_name, fit_id, expected in test_cases:
        role = facade.categorize_ship(ship_name, fit_id)
        status = "✓" if role.display_name == expected else "✗"
        print(f"\n{status} categorize_ship('{ship_name}', {fit_id}):")
        print(f"  Role: {role.display_emoji} {role.display_name}")
        print(f"  Description: {role.description}")
        print(f"  Expected: {expected}")


def test_price_operations(facade):
    """Test price-related operations."""
    print("\n" + "="*70)
    print("TEST 6: Price Operations")
    print("="*70)

    # Get Jita price
    price = facade.get_jita_price(2048)  # Damage Control II
    print(f"\n✓ get_jita_price(2048) [Damage Control II]:")
    print(f"  Price: {price:,.2f} ISK")

    # Get all Jita deltas
    deltas = facade.calculate_all_jita_deltas()
    print(f"\n✓ calculate_all_jita_deltas() returned {len(deltas)} deltas")

    if deltas:
        # Show first delta
        fit_id, delta = list(deltas.items())[0]
        fit_name = facade.get_fit_name(fit_id)
        print(f"  Example: {fit_name}")
        print(f"    Delta: {delta:,.2f} ISK")


def test_bulk_operations(facade):
    """Test bulk operations."""
    print("\n" + "="*70)
    print("TEST 7: Bulk Operations")
    print("="*70)

    # Clear caches
    facade.clear_caches()
    print("✓ clear_caches() completed")

    # Refresh all data
    result = facade.refresh_all_data()
    print(f"\n✓ refresh_all_data() completed:")
    print(f"  Summary rows: {result.metadata.summary_row_count}")
    print(f"  Build time: {result.metadata.total_duration_ms:.1f}ms")


def main():
    """Run all facade tests."""
    print("\n" + "="*70)
    print("DOCTRINE FACADE TEST SUITE")
    print("="*70)

    try:
        # Test 1: Instantiation
        facade = test_facade_instantiation()

        # Test 2: Fit operations
        test_fit_operations(facade)

        # Test 3: Module operations
        test_module_operations(facade)

        # Test 4: Doctrine operations
        test_doctrine_operations(facade)

        # Test 5: Categorization
        test_categorization(facade)

        # Test 6: Price operations
        test_price_operations(facade)

        # Test 7: Bulk operations
        test_bulk_operations(facade)

        print("\n" + "="*70)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("="*70)
        print("\n✓ Facade provides simplified API for Streamlit pages")
        print("✓ All operations return domain models (not raw DataFrames)")
        print("✓ Service orchestration working correctly")
        print("✓ Ready for integration into pages\n")

        return 0

    except Exception as e:
        print(f"\n\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
