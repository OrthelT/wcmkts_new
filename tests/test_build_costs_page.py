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
