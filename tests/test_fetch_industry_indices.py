"""Tests for industry index fetching logic.

These tests cover the ESI industry index parsing and fetch behavior
that was moved from utils.py to services/build_cost_service.py.
"""

import datetime
import unittest
from unittest.mock import MagicMock, patch

from services.build_cost_service import BuildCostService


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
    def test_304_returns_none_tuple(self):
        """A 304 response means data is current; service returns (None, None, None)."""
        repo = MagicMock()
        service = BuildCostService(repo)

        def fake_get(url, headers=None):
            return DummyResponse(
                304,
                headers={
                    "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
                    "Expires": "Mon, 01 Jan 2024 02:00:00 GMT",
                },
            )

        with patch("services.build_cost_service.requests.get", side_effect=fake_get):
            result = service._fetch_and_store_industry_index(etag="old-etag")

        self.assertEqual(result, (None, None, None))
        repo.write_industry_index.assert_not_called()

    def test_200_pivots_dataframe_and_writes(self):
        """A 200 response parses data, writes to DB, and returns timestamps."""
        repo = MagicMock()
        service = BuildCostService(repo)

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
            "ETag": 'W/"abc"',
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
            "Expires": "Mon, 01 Jan 2024 02:00:00 GMT",
        }

        def fake_get(url, headers=None):
            return DummyResponse(200, headers=server_headers, json_data=systems)

        with patch("services.build_cost_service.requests.get", side_effect=fake_get):
            last_mod, expires, etag = service._fetch_and_store_industry_index(etag=None)

        # Timestamps should be parsed
        self.assertIsNotNone(last_mod)
        self.assertIsNotNone(expires)
        self.assertEqual(etag, 'W/"abc"')

        # Should have written the industry index DataFrame to the repo
        repo.write_industry_index.assert_called_once()
        written_df = repo.write_industry_index.call_args[0][0]
        self.assertIn("solar_system_id", written_df.columns)
        self.assertIn("manufacturing", written_df.columns)
        self.assertIn("copying", written_df.columns)

    def test_parse_industry_data_static(self):
        """The static parser should pivot ESI data correctly."""
        systems = [
            {
                "solar_system_id": 300001,
                "cost_indices": [
                    {"activity": "manufacturing", "cost_index": 0.1},
                    {"activity": "copying", "cost_index": 0.2},
                ],
            }
        ]
        df = BuildCostService._parse_industry_data(systems)
        self.assertIn("solar_system_id", df.columns)
        self.assertIn("manufacturing", df.columns)
        self.assertIn("copying", df.columns)
        self.assertEqual(len(df), 1)


if __name__ == "__main__":
    unittest.main()
