"""Tests for the doctrine_status selection state and market-data export.

The selection is derived from the checked fit checkboxes, so an uncheck can
lower a quantity. Export stock figures are queried per item and per market hub;
an item with no data shows blanks, never zeros.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import pages.doctrine_status as ds


class _SessionState(dict):
    """dict with attribute access, like st.session_state."""

    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


@pytest.fixture
def state():
    ss = _SessionState(
        selected_type_ids=set(),
        type_id_info={},
        checkbox_items={},
        rendered_export_data={},
    )
    with patch.object(ds.st, "session_state", ss):
        yield ss


def _check(state, cb_key, type_id, qty, checked=True):
    ds._register_checkbox(cb_key, type_id, f"Item {type_id}", 3, qty)
    state[cb_key] = checked


class TestRebuildSelections:
    def test_qty_is_max_over_checked_fits(self, state):
        _check(state, "mod_1_0_100", 100, qty=5)
        _check(state, "mod_2_0_100", 100, qty=10)
        ds._rebuild_selections()
        assert state.selected_type_ids == {100}
        assert state.type_id_info[100]["qty_needed"] == 10

    def test_uncheck_lowers_qty_to_remaining_fit(self, state):
        _check(state, "mod_1_0_100", 100, qty=5)
        _check(state, "mod_2_0_100", 100, qty=10)
        ds._rebuild_selections()

        state["mod_2_0_100"] = False
        ds._rebuild_selections()

        assert state.selected_type_ids == {100}
        assert state.type_id_info[100]["qty_needed"] == 5

    def test_last_uncheck_removes_item(self, state):
        _check(state, "ship_1_603", 603, qty=2)
        ds._rebuild_selections()
        state["ship_1_603"] = False
        ds._rebuild_selections()
        assert state.selected_type_ids == set()
        assert state.type_id_info == {}

    def test_unrendered_checkbox_is_not_selected(self, state):
        # Registered in an earlier run, but its widget key is gone now.
        ds._register_checkbox("mod_9_0_200", 200, "Gone", 0, 4)
        ds._rebuild_selections()
        assert state.selected_type_ids == set()


class TestRenderExportData:
    @pytest.fixture
    def repo(self):
        repo = MagicMock()
        svc = SimpleNamespace(repository=repo)
        with patch.object(ds, "get_doctrine_service", return_value=svc), patch.object(
            ds, "get_active_market_key", return_value="primary"
        ):
            yield repo

    def test_queries_only_items_not_loaded(self, state, repo):
        state.rendered_export_market = "primary"
        state.rendered_export_data = {100: {"total_stock": 9, "fits_on_mkt": 1}}
        state.selected_type_ids = {100, 200}
        repo.get_module_stock.return_value = SimpleNamespace(total_stock=40, fits_on_mkt=4)

        ds.render_export_data()

        repo.get_module_stock.assert_called_once_with(200)
        assert state.rendered_export_data[200] == {"total_stock": 40, "fits_on_mkt": 4}

    def test_unknown_item_is_none_not_zero(self, state, repo):
        state.selected_type_ids = {300}
        repo.get_module_stock.return_value = None
        ds.render_export_data()
        assert state.rendered_export_data[300] is None

    def test_query_error_stores_nothing(self, state, repo):
        state.selected_type_ids = {300}
        repo.get_module_stock.side_effect = RuntimeError("db locked")
        ds.render_export_data()
        assert 300 not in state.rendered_export_data

    def test_hub_switch_drops_previous_hub_figures(self, state, repo):
        state.rendered_export_market = "deployment"
        state.rendered_export_data = {100: {"total_stock": 9, "fits_on_mkt": 1}}
        state.selected_type_ids = {100}
        repo.get_module_stock.return_value = SimpleNamespace(total_stock=2, fits_on_mkt=0)

        ds.render_export_data()

        repo.get_module_stock.assert_called_once_with(100)
        assert state.rendered_export_data == {100: {"total_stock": 2, "fits_on_mkt": 0}}
        assert state.rendered_export_market == "primary"
