"""Tests for the Low Stock page export helpers."""

import io
from unittest.mock import patch

import pandas as pd
import pytest

import state.session_state as session_state_module
from pages.low_stock import (
    EXPORT_CSV_COLUMNS,
    _EDITOR_NONCE_KEY,
    _render_low_stock_export,
    _reset_low_stock_selections,
    compute_restock_qty,
)


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

    def test_nan_input_raises(self):
        # Deliberately unhandled: the service sanitizes avg_volume and
        # total_volume_remain with fillna(0.0) before they reach this function
        # (services/low_stock_service.py). If that upstream invariant breaks,
        # a loud ValueError beats silently exporting a garbage quantity.
        with pytest.raises(ValueError):
            compute_restock_qty(avg_volume=float("nan"), max_days=7.0, current_stock=0.0)
        with pytest.raises(ValueError):
            compute_restock_qty(avg_volume=10.0, max_days=7.0, current_stock=float("nan"))


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

    def test_caption_states_target_days(self):
        # A typo'd i18n key would render the raw key string and still "pass"
        # every widget-call assertion, so pin the actual caption text — this
        # also pins the f"{max_days:g}" formatting (7.0 -> "7").
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(_editor_frame(), max_days=7.0, language_code="en")

        caption = mock_st.caption.call_args.args[0]
        assert "7 days" in caption

    def test_csv_includes_restock_qty_and_joined_ships(self):
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(_editor_frame(), max_days=7.0, language_code="en")

        csv_text = mock_st.download_button.call_args.kwargs["data"]
        rows = pd.read_csv(io.StringIO(csv_text))
        # Pin the exact header so a rename in columns_to_show can't silently
        # drop a column from the export (default mode: no fits_on_mkt).
        assert list(rows.columns) == [
            "type_id", "type_name", "restock_qty", "price", "days_remaining",
            "total_volume_remain", "avg_volume", "category_name", "group_name", "ships",
        ]
        assert list(rows["type_name"]) == ["Tritanium", "Mexallon"]
        assert list(rows["restock_qty"]) == [500, 1]
        # The ships list column is flattened to a single CSV-safe string.
        assert rows.loc[rows["type_name"] == "Mexallon", "ships"].iloc[0] == "Rifter (3); Punisher (1)"

    def test_single_fit_frame_exports_fits_on_mkt(self):
        # In single-fit mode the visible table gains fits_on_mkt; the CSV must
        # include it (in table order) rather than silently dropping it.
        frame = _editor_frame()
        frame.insert(6, "fits_on_mkt", [4, 2, 9])
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(frame, max_days=7.0, language_code="en")

        csv_text = mock_st.download_button.call_args.kwargs["data"]
        rows = pd.read_csv(io.StringIO(csv_text))
        assert list(rows.columns) == EXPORT_CSV_COLUMNS
        assert list(rows["fits_on_mkt"]) == [4, 9]

    def test_missing_required_column_logs_error_and_still_exports(self):
        # A drift between columns_to_show and EXPORT_CSV_COLUMNS must fail
        # loudly (logged) instead of silently shrinking the CSV schema.
        frame = _editor_frame().drop(columns=["price"])
        with patch("pages.low_stock.st") as mock_st, \
                patch("pages.low_stock.logger") as mock_logger:
            _render_low_stock_export(frame, max_days=7.0, language_code="en")

        mock_logger.error.assert_called_once()
        assert "price" in str(mock_logger.error.call_args)
        csv_text = mock_st.download_button.call_args.kwargs["data"]
        rows = pd.read_csv(io.StringIO(csv_text))
        assert "price" not in rows.columns
        assert list(rows["type_name"]) == ["Tritanium", "Mexallon"]

    def test_none_ships_cells_export_as_empty(self):
        # The page fills missing columns with None; a None ships cell must
        # export as an empty CSV cell, not crash or leak "None" text.
        frame = _editor_frame()
        frame["ships"] = None
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(frame, max_days=7.0, language_code="en")

        csv_text = mock_st.download_button.call_args.kwargs["data"]
        rows = pd.read_csv(io.StringIO(csv_text))
        assert rows["ships"].isna().all()

    def test_no_selection_shows_caption_and_skips_export(self):
        frame = _editor_frame()
        frame["select"] = False
        with patch("pages.low_stock.st") as mock_st:
            _render_low_stock_export(frame, max_days=7.0, language_code="en")

        mock_st.caption.assert_called_once()
        mock_st.code.assert_not_called()
        mock_st.download_button.assert_not_called()


class TestResetSelections:
    """Reset must change the data_editor's widget key, not just pop its state.

    Popping the widget's session_state key clears the Python-side return value
    (so the export empties) but leaves the canvas-rendered grid still showing
    the ticks -- the frontend grid is keyed by the stable widget key and reused
    across reruns (verified in-browser, 2026-06-12). The fix bumps a nonce
    baked into the key so Streamlit remounts the grid and clears the checkboxes.
    """

    def test_reset_bumps_nonce_from_default(self, monkeypatch):
        state = {}
        monkeypatch.setattr(session_state_module.st, "session_state", state, raising=False)
        _reset_low_stock_selections()
        # An absent nonce reads as 0, so the first reset moves the editor key
        # from low_stock_editor_0 to low_stock_editor_1.
        assert state[_EDITOR_NONCE_KEY] == 1

    def test_reset_increments_existing_nonce(self, monkeypatch):
        state = {_EDITOR_NONCE_KEY: 4}
        monkeypatch.setattr(session_state_module.st, "session_state", state, raising=False)
        _reset_low_stock_selections()
        assert state[_EDITOR_NONCE_KEY] == 5

    def test_consecutive_resets_each_yield_a_new_key(self, monkeypatch):
        # A key that ever repeats would let the frontend reuse a stale grid and
        # re-strand the ticks, so every reset must produce a distinct key.
        state = {}
        monkeypatch.setattr(session_state_module.st, "session_state", state, raising=False)
        keys = []
        for _ in range(3):
            _reset_low_stock_selections()
            keys.append(f"low_stock_editor_{state[_EDITOR_NONCE_KEY]}")
        assert len(set(keys)) == 3
