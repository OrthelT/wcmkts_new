"""
Tests for TypeResolutionService

Tests type resolution with mocked SDE repository and HTTP APIs.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestResolveTypeId:
    def test_returns_id_from_sde(self):
        from services.type_resolution_service import TypeResolutionService
        mock_repo = Mock()
        mock_repo.get_type_id.return_value = 34
        service = TypeResolutionService(mock_repo)

        result = service.resolve_type_id("Tritanium")

        assert result == 34
        mock_repo.get_type_id.assert_called_once_with("Tritanium")

    @patch("services.type_resolution_service.requests.get")
    def test_falls_back_to_fuzzworks_on_sde_miss(self, mock_get):
        from services.type_resolution_service import TypeResolutionService
        mock_repo = Mock()
        mock_repo.get_type_id.return_value = None

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"typeID": 34}
        mock_get.return_value = mock_response

        service = TypeResolutionService(mock_repo)
        result = service.resolve_type_id("Tritanium")

        assert result == 34

    @patch("services.type_resolution_service.requests.get")
    def test_returns_none_when_both_fail(self, mock_get):
        from services.type_resolution_service import TypeResolutionService
        mock_repo = Mock()
        mock_repo.get_type_id.return_value = None
        mock_get.side_effect = Exception("Network error")

        service = TypeResolutionService(mock_repo)
        result = service.resolve_type_id("NonexistentItem")

        assert result is None


class TestResolveTypeNames:
    @patch("services.type_resolution_service.requests.post")
    def test_returns_names_from_esi(self, mock_post):
        from services.type_resolution_service import TypeResolutionService
        mock_repo = Mock()
        service = TypeResolutionService(mock_repo)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"id": 34, "name": "Tritanium", "category": "inventory_type"},
            {"id": 35, "name": "Pyerite", "category": "inventory_type"},
        ]
        mock_post.return_value = mock_response

        result = service.resolve_type_names([34, 35])

        assert len(result) == 2
        assert result[0]["name"] == "Tritanium"

    @patch("services.type_resolution_service.requests.post")
    def test_chunks_large_requests(self, mock_post):
        from services.type_resolution_service import TypeResolutionService
        mock_repo = Mock()
        service = TypeResolutionService(mock_repo)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "Item", "category": "inventory_type"}]
        mock_post.return_value = mock_response

        # 1500 IDs should result in 2 API calls (chunks of 1000)
        type_ids = list(range(1, 1501))
        result = service.resolve_type_names(type_ids)

        assert mock_post.call_count == 2

    @patch("services.type_resolution_service.requests.post")
    def test_handles_esi_error(self, mock_post):
        from services.type_resolution_service import TypeResolutionService
        mock_repo = Mock()
        service = TypeResolutionService(mock_repo)

        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = service.resolve_type_names([34, 35])
        assert result == []


class TestFetchTypeIdFromFuzzworks:
    @patch("services.type_resolution_service.requests.get")
    def test_returns_type_id(self, mock_get):
        from services.type_resolution_service import TypeResolutionService

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"typeID": 34}
        mock_get.return_value = mock_response

        result = TypeResolutionService._fetch_type_id_from_fuzzworks("Tritanium")
        assert result == 34

    @patch("services.type_resolution_service.requests.get")
    def test_returns_none_on_http_error(self, mock_get):
        from services.type_resolution_service import TypeResolutionService

        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = TypeResolutionService._fetch_type_id_from_fuzzworks("NonexistentItem")
        assert result is None

    @patch("services.type_resolution_service.requests.get")
    def test_returns_none_on_exception(self, mock_get):
        from services.type_resolution_service import TypeResolutionService
        mock_get.side_effect = Exception("Network timeout")

        result = TypeResolutionService._fetch_type_id_from_fuzzworks("Tritanium")
        assert result is None
