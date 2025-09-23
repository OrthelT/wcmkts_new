import unittest
from types import SimpleNamespace
import streamlit as st


class DummyResponse:
    def __init__(self, status_code, headers=None, json_data=None):
        self.status_code = status_code
        self.headers = headers or {}
        self._json = json_data

    def json(self):
        return self._json

    def raise_for_status(self):
        raise RuntimeError(f"HTTP {self.status_code}")


class TestFetchIndustryIndices(unittest.TestCase):
    def setUp(self):
        # minimal secrets for modules that expect st.secrets
        dummy = SimpleNamespace(url="libsql://dummy", token="dummy")
        st.secrets = SimpleNamespace(
            wcmkt2_turso=dummy,
            sde_lite_turso=dummy,
            buildcost_turso=dummy,
        )

    def test_304_returns_none(self):
        import utils

        def fake_get(url, headers=None):
            return DummyResponse(304, headers={"Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT", "Expires": "Mon, 01 Jan 2024 02:00:00 GMT"})

        utils.requests.get = fake_get
        out = utils.fetch_industry_system_cost_indices()
        self.assertIsNone(out)

    def test_200_pivots_dataframe(self):
        import utils

        systems = [
            {
                "solar_system_id": 300001,
                "cost_indices": [
                    {"activity": "manufacturing", "cost_index": 0.1},
                    {"activity": "copying", "cost_index": 0.2},
                ],
            }
        ]

        server_headers = {
            "ETag": "W/\"abc\"",
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
            "Expires": "Mon, 01 Jan 2024 02:00:00 GMT",
        }

        def fake_get(url, headers=None):
            return DummyResponse(200, headers=server_headers, json_data=systems)

        utils.requests.get = fake_get
        out = utils.fetch_industry_system_cost_indices()
        # Expect columns pivoted with manufacturing/copying
        self.assertIn("solar_system_id", out.columns)
        self.assertIn("manufacturing", out.columns)
        self.assertIn("copying", out.columns)


if __name__ == "__main__":
    unittest.main()
