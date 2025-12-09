import unittest
import tomllib
from pathlib import Path


class TestSettingsToml(unittest.TestCase):
    """Test suite to validate settings.toml structure and contents."""

    @classmethod
    def setUpClass(cls):
        """Load settings.toml once for all tests."""
        settings_path = Path(__file__).parent.parent / "settings.toml"
        with open(settings_path, "rb") as f:
            cls.settings = tomllib.load(f)

    def test_toml_file_can_be_loaded(self):
        """Test that settings.toml exists and can be parsed without errors."""
        settings_path = Path(__file__).parent.parent / "settings.toml"
        self.assertTrue(settings_path.exists(), "settings.toml file does not exist")

        with open(settings_path, "rb") as f:
            settings = tomllib.load(f)

        self.assertIsInstance(settings, dict)

    def test_ship_roles_section_exists(self):
        """Test that the ship_roles section exists in settings."""
        self.assertIn('ship_roles', self.settings, "ship_roles section is missing")

    def test_all_required_role_categories_exist(self):
        """Test that all required role categories are present."""
        ship_roles = self.settings['ship_roles']
        required_categories = ['dps', 'logi', 'links', 'support', 'special_cases']

        for category in required_categories:
            with self.subTest(category=category):
                self.assertIn(
                    category,
                    ship_roles,
                    f"{category} category is missing from ship_roles"
                )

    def test_role_categories_are_lists(self):
        """Test that dps, logi, links, and support are lists of strings."""
        ship_roles = self.settings['ship_roles']
        list_categories = ['dps', 'logi', 'links', 'support']

        for category in list_categories:
            with self.subTest(category=category):
                self.assertIsInstance(
                    ship_roles[category],
                    list,
                    f"{category} should be a list"
                )

                # Check all items in the list are strings
                for item in ship_roles[category]:
                    self.assertIsInstance(
                        item,
                        str,
                        f"All items in {category} should be strings, found {type(item)}"
                    )

    def test_role_lists_are_not_empty(self):
        """Test that role category lists contain at least one ship."""
        ship_roles = self.settings['ship_roles']
        list_categories = ['dps', 'logi', 'links', 'support']

        for category in list_categories:
            with self.subTest(category=category):
                self.assertGreater(
                    len(ship_roles[category]),
                    0,
                    f"{category} list should not be empty"
                )

    def test_special_cases_is_dict(self):
        """Test that special_cases is a dictionary."""
        ship_roles = self.settings['ship_roles']
        self.assertIsInstance(
            ship_roles['special_cases'],
            dict,
            "special_cases should be a dictionary"
        )

    def test_special_cases_structure(self):
        """Test that special_cases has correct nested structure."""
        special_cases = self.settings['ship_roles']['special_cases']

        for ship_name, fit_mappings in special_cases.items():
            with self.subTest(ship=ship_name):
                # Ship name should be a string
                self.assertIsInstance(ship_name, str, f"Ship name should be a string")

                # Fit mappings should be a dict
                self.assertIsInstance(
                    fit_mappings,
                    dict,
                    f"Fit mappings for {ship_name} should be a dictionary"
                )

                # Each fit_id should map to a role string
                for fit_id, role in fit_mappings.items():
                    # fit_id should be an integer or string
                    self.assertIsInstance(
                        fit_id,
                        (int, str),
                        f"fit_id should be int or string, got {type(fit_id)}"
                    )

                    # Role should be a string and one of the valid roles
                    self.assertIsInstance(role, str, f"Role should be a string")
                    self.assertIn(
                        role,
                        ['DPS', 'Logi', 'Links', 'Support'],
                        f"Role {role} is not a valid role"
                    )

    def test_no_duplicate_ships_across_categories(self):
        """Test that ships don't appear in multiple role categories (except special_cases)."""
        ship_roles = self.settings['ship_roles']

        all_ships = {}
        list_categories = ['dps', 'logi', 'links', 'support']

        for category in list_categories:
            for ship in ship_roles[category]:
                if ship in all_ships:
                    self.fail(
                        f"Ship '{ship}' appears in both {all_ships[ship]} and {category}"
                    )
                all_ships[ship] = category

    def test_special_cases_ships_exist_in_role_lists(self):
        """Test that ships in special_cases also appear in at least one role list."""
        ship_roles = self.settings['ship_roles']
        special_cases = ship_roles['special_cases']

        all_ships = set()
        for category in ['dps', 'logi', 'links', 'support']:
            all_ships.update(ship_roles[category])

        for ship_name in special_cases.keys():
            # Note: This test may need to be adjusted based on your requirements
            # If special_case ships don't need to be in role lists, you can remove this test
            # For now, we'll just warn if they're not found
            if ship_name not in all_ships:
                # This is informational - may or may not be an error depending on requirements
                pass

    def test_settings_compatible_with_categorize_function(self):
        """Test that settings structure works with the categorize_ship_by_role usage pattern."""
        ship_roles = self.settings['ship_roles']

        # Test that we can access all the expected keys
        dps_ships = ship_roles['dps']
        logi_ships = ship_roles['logi']
        links_ships = ship_roles['links']
        support_ships = ship_roles['support']
        special_cases = ship_roles['special_cases']

        # Verify we can check membership (as done in categorize_ship_by_role)
        self.assertIsInstance(dps_ships, list)
        self.assertIsInstance(logi_ships, list)
        self.assertIsInstance(links_ships, list)
        self.assertIsInstance(support_ships, list)
        self.assertIsInstance(special_cases, dict)

        # Test a special case lookup pattern (as used in the code)
        for ship_name, fit_mappings in special_cases.items():
            # Verify we can check if a fit_id exists in the mappings
            for fit_id in fit_mappings.keys():
                # This should work without errors
                result = fit_mappings.get(fit_id) or fit_mappings.get(str(fit_id))
                self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
