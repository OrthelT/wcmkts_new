import types
import unittest
import pandas as pd
import streamlit as st


def _stub_secrets():
    dummy = types.SimpleNamespace(url="libsql://dummy", token="dummy")
    st.secrets = types.SimpleNamespace(
        wcmkt2_turso=dummy,
        sde_lite_turso=dummy,
        buildcost_turso=dummy,
    )


class TestCleanMktData(unittest.TestCase):
    def test_clean_mkt_data_transforms_dates_and_columns(self):
        _stub_secrets()  # ensure imports that rely on st.secrets succeed

        from db_handler import clean_mkt_data  # import after st.secrets stub

        df = pd.DataFrame(
            [
                {
                    "order_id": 1,
                    "is_buy_order": 0,
                    "typeID": 34,
                    "typeName": "Tritanium",
                    "price": 5.5,
                    "volume_remain": 100,
                    "duration": 2,
                    "issued": "2024-01-01 00:00:00",
                }
            ]
        )

        out = clean_mkt_data(df)

        # Renamed columns exist
        self.assertTrue(set(["type_id", "type_name"]).issubset(out.columns))

        # Computed columns
        self.assertIn("expiry", out.columns)
        self.assertIn("days_remaining", out.columns)

        # Types are coerced/formatted as expected
        self.assertTrue(pd.api.types.is_integer_dtype(out["days_remaining"]))
        self.assertTrue((out["days_remaining"] >= 0).all())


if __name__ == "__main__":
    unittest.main()
