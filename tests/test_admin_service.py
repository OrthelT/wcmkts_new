"""Tests for watchlist admin service validation and auth guards."""

import pandas as pd
import pytest

from services.admin_service import AdminService


class StubRepo:
    def __init__(self):
        self.rows = None

    def replace_watchlist(self, rows):
        self.rows = rows


class StubAuthService:
    def __init__(self, payload):
        self.payload = payload

    def verify_signed_admin_identity(self, identity):
        return self.payload


def test_save_watchlist_rejects_unauthenticated_write():
    service = AdminService(StubRepo(), StubAuthService(None), cache_invalidator=lambda: None)

    with pytest.raises(PermissionError, match="Admin authentication required"):
        service.save_watchlist(pd.DataFrame(), signed_identity={})


def test_save_watchlist_rejects_duplicate_type_id():
    service = AdminService(
        StubRepo(),
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )
    df = pd.DataFrame(
        [
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "Duplicate Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            },
        ]
    )

    with pytest.raises(ValueError, match="Duplicate type_id"):
        service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})


def test_save_watchlist_rejects_empty_text_field():
    service = AdminService(
        StubRepo(),
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )
    df = pd.DataFrame(
        [
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            }
        ]
    )

    with pytest.raises(ValueError, match="type_name"):
        service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})


def test_save_watchlist_persists_valid_rows_and_invalidates_cache():
    repo = StubRepo()
    invalidated = {"called": False}
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: invalidated.__setitem__("called", True),
    )
    df = pd.DataFrame(
        [
            {
                "type_id": 34,
                "group_id": 18,
                "type_name": "Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            }
        ]
    )

    result = service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    assert repo.rows == [
        {
            "type_id": 34,
            "group_id": 18,
            "type_name": "Tritanium",
            "group_name": "Mineral",
            "category_id": 4,
            "category_name": "Material",
        }
    ]
    assert invalidated["called"] is True
    assert result["row_count"] == 1
