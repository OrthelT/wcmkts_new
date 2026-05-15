"""Tests for watchlist admin service validation and auth guards."""

import pandas as pd
import pytest

from services.admin_service import AdminService


class StubRepo:
    def __init__(self):
        self.rows = None
        self.saved_doctrine_fit = None
        self.doctrine_fit = {
            "doctrine_id": 10,
            "fit_id": 20,
            "doctrine_name": "Doctrine Alpha",
            "target": 50,
            "market_flag": "primary",
        }
        self.doctrine_name = "Doctrine Alpha"
        self.fit_id_exists = False
        self.next_fit_id = 99
        self.fit_eft = "[Vedmak, Old Fit]\nDamage Control II"
        self.fit_options = pd.DataFrame(
            [{"doctrine_id": 10, "doctrine_name": "Doctrine Alpha", "fit_id": 20}]
        )
        self.doctrine_options = pd.DataFrame(
            [{"doctrine_id": 10, "doctrine_name": "Doctrine Alpha"}]
        )
        self.next_doctrine_id = 11
        self.doctrine_id_already_exists = False
        self.doctrine_name_already_exists = False
        self.created_doctrine = None
        self.deleted_doctrine_fit = None

    def replace_watchlist(self, rows):
        self.rows = rows

    def get_doctrine_options(self):
        return self.doctrine_options

    def get_doctrine_fit_options(self):
        return self.fit_options

    def get_doctrine_fit_eft(self, fit_id):
        return self.fit_eft

    def get_doctrine_fit(self, doctrine_id, fit_id):
        if doctrine_id == 10 and fit_id == 20:
            return self.doctrine_fit
        return None

    def get_doctrine_name(self, doctrine_id):
        return self.doctrine_name if doctrine_id == 10 else None

    def doctrine_fit_id_exists(self, fit_id):
        return self.fit_id_exists

    def get_next_doctrine_fit_id(self):
        return self.next_fit_id

    def get_next_doctrine_id(self):
        return self.next_doctrine_id

    def doctrine_id_exists(self, doctrine_id):
        return self.doctrine_id_already_exists

    def doctrine_name_exists(self, doctrine_name):
        return self.doctrine_name_already_exists

    def create_doctrine(self, **kwargs):
        self.created_doctrine = kwargs

    def delete_doctrine_fit(self, **kwargs):
        self.deleted_doctrine_fit = kwargs

    def save_doctrine_fit(self, **kwargs):
        self.saved_doctrine_fit = kwargs


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


def test_save_watchlist_rejects_empty_replacement():
    repo = StubRepo()
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )
    df = pd.DataFrame(
        columns=[
            "type_id",
            "group_id",
            "type_name",
            "group_name",
            "category_id",
            "category_name",
        ]
    )

    with pytest.raises(ValueError, match="empty watchlist"):
        service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    assert repo.rows is None


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


def test_get_doctrine_fit_options_delegates_to_repository():
    repo = StubRepo()
    service = AdminService(repo, StubAuthService(None), cache_invalidator=lambda: None)

    result = service.get_doctrine_fit_options()

    assert result.equals(repo.fit_options)


def test_get_doctrine_options_delegates_to_repository():
    repo = StubRepo()
    service = AdminService(repo, StubAuthService(None), cache_invalidator=lambda: None)

    result = service.get_doctrine_options()

    assert result.equals(repo.doctrine_options)


def test_get_doctrine_fit_eft_delegates_to_repository():
    repo = StubRepo()
    service = AdminService(repo, StubAuthService(None), cache_invalidator=lambda: None)

    result = service.get_doctrine_fit_eft(20)

    assert result == repo.fit_eft


def test_create_doctrine_requires_admin_and_persists_empty_doctrine():
    repo = StubRepo()
    invalidated = {"called": False}
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: invalidated.__setitem__("called", True),
    )

    result = service.create_doctrine(
        doctrine_name=" Doctrine Beta ",
        signed_identity={"payload": {}, "signature": "x"},
    )

    assert repo.created_doctrine == {"doctrine_id": 11, "doctrine_name": "Doctrine Beta"}
    assert result == {"doctrine_id": 11, "doctrine_name": "Doctrine Beta"}
    assert invalidated["called"] is True


def test_create_doctrine_rejects_existing_generated_doctrine_id():
    repo = StubRepo()
    repo.doctrine_id_already_exists = True
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )

    with pytest.raises(ValueError, match="already exists"):
        service.create_doctrine(
            doctrine_name="Doctrine Beta",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_create_doctrine_rejects_duplicate_doctrine_name():
    repo = StubRepo()
    repo.doctrine_name_already_exists = True
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )

    with pytest.raises(ValueError, match="doctrine_name already exists"):
        service.create_doctrine(
            doctrine_name="doctrine alpha",
            signed_identity={"payload": {}, "signature": "x"},
        )
    assert repo.created_doctrine is None


def test_update_doctrine_fit_requires_existing_fit_pair():
    service = AdminService(
        StubRepo(),
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )

    with pytest.raises(ValueError, match="No doctrine fit found"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=99,
            target=50,
            market_flag="primary",
            mode="update",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_delete_doctrine_fit_requires_existing_pair_and_invalidates_cache():
    repo = StubRepo()
    invalidated = {"called": False}
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: invalidated.__setitem__("called", True),
    )

    result = service.delete_doctrine_fit(
        doctrine_id=10,
        fit_id=20,
        signed_identity={"payload": {}, "signature": "x"},
    )

    assert repo.deleted_doctrine_fit == {"doctrine_id": 10, "fit_id": 20}
    assert result == {"doctrine_id": 10, "fit_id": 20}
    assert invalidated["called"] is True


def test_delete_doctrine_fit_rejects_missing_fit_pair():
    service = AdminService(
        StubRepo(),
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )

    with pytest.raises(ValueError, match="No doctrine fit found"):
        service.delete_doctrine_fit(
            doctrine_id=10,
            fit_id=99,
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_add_doctrine_fit_requires_existing_doctrine_and_new_fit_id():
    repo = StubRepo()
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )

    result = service.save_doctrine_fit(
        eft_text="[Vedmak, Test]\nDamage Control II",
        doctrine_id=10,
        fit_id=None,
        target=50,
        market_flag="primary",
        mode="add",
        signed_identity={"payload": {}, "signature": "x"},
    )

    assert repo.saved_doctrine_fit["doctrine_name"] == "Doctrine Alpha"
    assert repo.saved_doctrine_fit["fit_id"] == 99
    assert repo.saved_doctrine_fit["fit_name"] == "Test"
    assert result["fit_id"] == 99


def test_add_doctrine_fit_rejects_existing_fit_id():
    repo = StubRepo()
    repo.fit_id_exists = True
    service = AdminService(
        repo,
        StubAuthService({"character_id": 2122333361, "character_name": "Orthel"}),
        cache_invalidator=lambda: None,
    )

    with pytest.raises(ValueError, match="already exists"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=50,
            market_flag="primary",
            mode="add",
            signed_identity={"payload": {}, "signature": "x"},
        )
