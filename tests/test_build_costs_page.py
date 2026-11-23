"""Tests for the network helpers in pages/build_costs.py.

Both helpers are cached so reruns skip the network call. A failed call must
not be cached, or one transient error would pin the fallback for a full TTL.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

import pages.build_costs as build_costs


@pytest.fixture(autouse=True)
def _clear_caches():
    build_costs._check_image_url.clear()
    build_costs._resolve_type_names_from_esi_cached.clear()
    yield
    build_costs._check_image_url.clear()
    build_costs._resolve_type_names_from_esi_cached.clear()


def _image_response():
    return MagicMock(status_code=200, headers={"content-type": "image/png"})


class TestIsValidImageUrl:
    def test_request_error_is_not_cached(self):
        url = "https://images.example/1"
        with patch.object(
            build_costs.requests,
            "head",
            side_effect=[requests.Timeout("slow"), _image_response()],
        ) as head:
            assert build_costs.is_valid_image_url(url) is False
            assert build_costs.is_valid_image_url(url) is True
        assert head.call_count == 2

    def test_answer_is_cached_and_timeout_is_set(self):
        url = "https://images.example/2"
        with patch.object(
            build_costs.requests, "head", return_value=_image_response()
        ) as head:
            assert build_costs.is_valid_image_url(url) is True
            assert build_costs.is_valid_image_url(url) is True
        head.assert_called_once()
        assert head.call_args.kwargs["timeout"]


class TestResolveTypeNamesFromEsi:
    def test_empty_esi_result_is_not_cached(self):
        service = MagicMock()
        service.resolve_type_names.side_effect = [[], [{"id": 7, "name": "Seven"}]]
        with patch.object(build_costs, "get_type_resolution_service", return_value=service):
            assert build_costs._resolve_type_names_from_esi((7,)) == {}
            assert build_costs._resolve_type_names_from_esi((7,)) == {7: "Seven"}
        assert service.resolve_type_names.call_count == 2

    def test_success_is_cached(self):
        service = MagicMock()
        service.resolve_type_names.return_value = [{"id": 8, "name": "Eight"}]
        with patch.object(build_costs, "get_type_resolution_service", return_value=service):
            assert build_costs._resolve_type_names_from_esi((8,)) == {8: "Eight"}
            assert build_costs._resolve_type_names_from_esi((8,)) == {8: "Eight"}
        service.resolve_type_names.assert_called_once()


class TestSyncMaterialSelection:
    """A keyed selectbox ignores ``index`` after its first render, so the page
    writes the material selector's session-state value when the compare
    structure changes."""

    OPTIONS = ["0-YMBJ", "4-HWWF CC", "B Azbel", "C Sotiyo"]

    def _sync(self, state, preferred):
        build_costs.sync_material_selection(state, self.OPTIONS, preferred)
        return state[build_costs.MATERIAL_SELECTOR_KEY]

    def test_follows_preferred_structure_changes(self):
        state = {}
        assert self._sync(state, "4-HWWF CC") == "4-HWWF CC"
        assert self._sync(state, "C Sotiyo") == "C Sotiyo"
        assert self._sync(state, "4-HWWF CC") == "4-HWWF CC"

    def test_keeps_user_pick_while_preferred_is_unchanged(self):
        state = {}
        self._sync(state, "C Sotiyo")
        state[build_costs.MATERIAL_SELECTOR_KEY] = "B Azbel"  # user picks in the selector
        assert self._sync(state, "C Sotiyo") == "B Azbel"

    def test_falls_back_to_first_option(self):
        state = {}
        assert self._sync(state, None) == "0-YMBJ"
        assert self._sync(state, "Not In Results") == "0-YMBJ"

    def test_resets_a_stale_pick_missing_from_new_results(self):
        state = {build_costs.MATERIAL_SELECTOR_KEY: "Gone", "material_structure_preferred": "B Azbel"}
        assert self._sync(state, "B Azbel") == "B Azbel"


class TestVisibleResults:
    """Stored results come from the last calculation, but the structure filters
    ("Show closed structures") can change before the user recalculates."""

    RESULTS = {"Open A": {"total_cost": 1}, "Closed B": {"total_cost": 2}}

    def test_unchecking_closed_drops_closed_results(self):
        # Calculated with closed structures, then the box was unchecked.
        shown, compare = build_costs.visible_results(self.RESULTS, {"Open A"}, None)
        assert shown == {"Open A": {"total_cost": 1}}
        assert compare is None

    def test_compare_structure_without_a_result_is_dropped(self):
        # Calculated without closed structures, then checked and a closed one picked.
        results = {"Open A": {"total_cost": 1}}
        shown, compare = build_costs.visible_results(results, {"Open A", "Closed B"}, "Closed B")
        assert shown == results
        assert compare is None

    def test_compare_structure_with_a_result_is_kept(self):
        shown, compare = build_costs.visible_results(
            self.RESULTS, {"Open A", "Closed B"}, "Closed B"
        )
        assert shown == self.RESULTS
        assert compare == "Closed B"

    def test_compare_structure_hidden_by_filter_is_dropped(self):
        shown, compare = build_costs.visible_results(self.RESULTS, {"Open A"}, "Closed B")
        assert compare is None
