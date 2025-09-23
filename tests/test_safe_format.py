import unittest
from types import SimpleNamespace
import streamlit as st


def _stub_secrets():
    dummy = SimpleNamespace(url="libsql://dummy", token="dummy")
    st.secrets = SimpleNamespace(
        wcmkt2_turso=dummy,
        sde_lite_turso=dummy,
        buildcost_turso=dummy,
    )


class TestSafeFormat(unittest.TestCase):
    def test_safe_format_handles_none_and_nan(self):
        _stub_secrets()
        from db_handler import safe_format
        self.assertEqual(safe_format(None, "{:,.2f}"), "")

        # NaN path
        import math
        self.assertEqual(safe_format(math.nan, "{:,.0f}"), "")

    def test_safe_format_formats_numbers(self):
        _stub_secrets()
        from db_handler import safe_format
        self.assertEqual(safe_format(1234.567, "{:,.1f}"), "1,234.6")


if __name__ == "__main__":
    unittest.main()
