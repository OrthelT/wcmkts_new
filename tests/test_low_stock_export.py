"""Tests for the Low Stock page export helpers."""

from unittest.mock import patch

import pandas as pd

from pages.low_stock import _render_low_stock_export, compute_restock_qty


class TestComputeRestockQty:
    """compute_restock_qty = round(avg_volume * max_days - current_stock), floored at 1."""

    def test_restocks_to_target_days(self):
        # 10/day * 7 days = 70 target; 20 on market -> buy 50.
        assert compute_restock_qty(avg_volume=10.0, max_days=7.0, current_stock=20.0) == 50

    def test_already_stocked_floors_to_one(self):
        # Target 70, but 200 already on market -> negative need, never below 1.
        assert compute_restock_qty(avg_volume=10.0, max_days=7.0, current_stock=200.0) == 1

    def test_zero_volume_floors_to_one(self):
        # No recent sales: a ticked row still exports at least 1.
        assert compute_restock_qty(avg_volume=0.0, max_days=7.0, current_stock=0.0) == 1

    def test_zero_days_slider_floors_to_one(self):
        # Degenerate slider=0 target yields negative need -> floored to 1.
        assert compute_restock_qty(avg_volume=10.0, max_days=0.0, current_stock=5.0) == 1

    def test_rounds_to_nearest_integer(self):
        # 3.4/day * 2 days = 6.8 -> rounds to 7.
        assert compute_restock_qty(avg_volume=3.4, max_days=2.0, current_stock=0.0) == 7


def _editor_frame():
    """A frame shaped like st.data_editor's return for the Low Stock table."""
    return pd.DataFrame(
        [
            {  # selected: 100/day * 7 - 200 = 500
                "select": True, "type_id": 34, "type_name": "Tritanium",
                "price": 5.0, "days_remaining": 2.0, "total_volume_remain": 200.0,
                "avg_volume": 100.0, "category_name": "Material",
                "group_name": "Mineral", "ships": ["Rifter (3)"],
            },
            {  # not selected -> must be excluded from export
                "select": False, "type_id": 35, "type_name": "Pyerite",
                "price": 8.0, "days_remaining": 1.0, "total_volume_remain": 50.0,
                "avg_volume": 100.0, "category_name": "Material",
                "group_name": "Mineral", "ships": [],
            },
            {  # selected but over-stocked -> qty floors to 1
                "select": True, "type_id": 36, "type_name": "Mexallon",
                "price": 40.0, "days_remaining": 6.0, "total_volume_remain": 1000.0,
                "avg_volume": 10.0, "category_name": "Material",
                "group_name": "Mineral", "ships": ["Rifter (3)", "Punisher (1)"],
            },
        ]
    )


class TestRenderLowStockExport:
    """The renderer builds an EVE-Multibuy block and CSV from the ticked rows."""

    def test_multibuy_block_uses_restock_qty_for_selected_rows(self):
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(_editor_frame(), max_days=7.0, language_code="en")

        multibuy = mock_st.code.call_args.args[0]
        # Only the two ticked rows, name<TAB>restock_qty, unselected row absent.
        assert multibuy == "Tritanium\t500\nMexallon\t1"

    def test_csv_includes_restock_qty_and_joined_ships(self):
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(_editor_frame(), max_days=7.0, language_code="en")

        csv_text = mock_st.download_button.call_args.kwargs["data"]
        rows = pd.read_csv(pd.io.common.StringIO(csv_text))
        assert list(rows["type_name"]) == ["Tritanium", "Mexallon"]
        assert list(rows["restock_qty"]) == [500, 1]
        # The ships list column is flattened to a single CSV-safe string.
        assert rows.loc[rows["type_name"] == "Mexallon", "ships"].iloc[0] == "Rifter (3); Punisher (1)"

    def test_no_selection_shows_caption_and_skips_export(self):
        frame = _editor_frame()
        frame["select"] = False
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(frame, max_days=7.0, language_code="en")

        mock_st.caption.assert_called_once()
        mock_st.code.assert_not_called()
        mock_st.download_button.assert_not_called()
