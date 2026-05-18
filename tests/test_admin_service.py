"""Tests for watchlist admin service validation and auth guards."""

import logging

import pandas as pd
import pytest

from services.admin_service import AdminService, AdminWriteIntegrityError


class StubRepo:
    write_target = "remote"

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
        self.existing_watchlist = pd.DataFrame(
            columns=[
                "type_id",
                "group_id",
                "type_name",
                "group_name",
                "category_id",
                "category_name",
            ]
        )

    def get_watchlist(self):
        # If a prior write happened in this test, reflect it. Read-back
        # verification in AdminService relies on this.
        if self.rows is not None:
            return pd.DataFrame(self.rows)
        return self.existing_watchlist.copy()

    def replace_watchlist(self, rows):
        self.rows = rows

    def get_doctrine_options(self):
        return self.doctrine_options

    def get_doctrine_fit_options(self):
        return self.fit_options

    def get_doctrine_fit_eft(self, fit_id):
        return self.fit_eft

    def get_doctrine_fit(self, doctrine_id, fit_id):
        # Post-delete reads must show the fit gone.
        if self.deleted_doctrine_fit == {"doctrine_id": doctrine_id, "fit_id": fit_id}:
            return None
        # Post-save reads must show the just-saved fit.
        if (
            self.saved_doctrine_fit is not None
            and self.saved_doctrine_fit.get("doctrine_id") == doctrine_id
            and self.saved_doctrine_fit.get("fit_id") == fit_id
        ):
            return {
                "doctrine_id": doctrine_id,
                "fit_id": fit_id,
                "doctrine_name": self.saved_doctrine_fit.get("doctrine_name", ""),
            }
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
        if self.created_doctrine and self.created_doctrine.get("doctrine_id") == doctrine_id:
            return True
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


def _watchlist_row(type_id: int, type_name: str = "Item") -> dict:
    return {
        "type_id": type_id,
        "group_id": 18,
        "type_name": type_name,
        "group_name": "Mineral",
        "category_id": 4,
        "category_name": "Material",
    }


def _make_service(repo, payload=None, cache_called=None):
    payload = payload or {"character_id": 2122333361, "character_name": "Orthel"}
    callback = (lambda: cache_called.__setitem__("called", True)) if cache_called is not None else (lambda: None)
    return AdminService(repo, StubAuthService(payload), cache_invalidator=callback)


def test_save_watchlist_returns_added_and_removed_type_ids_for_add_only():
    repo = StubRepo()
    repo.existing_watchlist = pd.DataFrame([_watchlist_row(34, "Tritanium")])
    service = _make_service(repo)
    df = pd.DataFrame(
        [
            _watchlist_row(34, "Tritanium"),
            _watchlist_row(35, "Pyerite"),
            _watchlist_row(36, "Mexallon"),
        ]
    )

    result = service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    assert result["added_type_ids"] == [35, 36]
    assert result["removed_type_ids"] == []
    assert result["row_count"] == 3


def test_save_watchlist_returns_added_and_removed_type_ids_for_remove_only():
    repo = StubRepo()
    repo.existing_watchlist = pd.DataFrame(
        [_watchlist_row(34, "Tritanium"), _watchlist_row(35, "Pyerite")]
    )
    service = _make_service(repo)
    df = pd.DataFrame([_watchlist_row(34, "Tritanium")])

    result = service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    assert result["added_type_ids"] == []
    assert result["removed_type_ids"] == [35]
    assert result["row_count"] == 1


def test_save_watchlist_returns_added_and_removed_type_ids_for_mixed_change():
    repo = StubRepo()
    repo.existing_watchlist = pd.DataFrame(
        [_watchlist_row(34, "Tritanium"), _watchlist_row(35, "Pyerite")]
    )
    service = _make_service(repo)
    df = pd.DataFrame(
        [_watchlist_row(34, "Tritanium"), _watchlist_row(36, "Mexallon")]
    )

    result = service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    assert result["added_type_ids"] == [36]
    assert result["removed_type_ids"] == [35]


def test_save_watchlist_returns_empty_deltas_for_noop_save():
    repo = StubRepo()
    repo.existing_watchlist = pd.DataFrame([_watchlist_row(34, "Tritanium")])
    service = _make_service(repo)
    df = pd.DataFrame([_watchlist_row(34, "Tritanium")])

    result = service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    assert result["added_type_ids"] == []
    assert result["removed_type_ids"] == []


def test_save_watchlist_emits_info_log_with_character_and_delta(caplog):
    repo = StubRepo()
    repo.existing_watchlist = pd.DataFrame([_watchlist_row(34, "Tritanium")])
    service = _make_service(repo)
    df = pd.DataFrame(
        [_watchlist_row(34, "Tritanium"), _watchlist_row(35, "Pyerite")]
    )

    with caplog.at_level(logging.INFO, logger="services.admin_service"):
        service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert info_records, "Expected at least one INFO log line"
    msg = info_records[0].getMessage()
    assert "watchlist_saved" in msg
    assert "character_id=2122333361" in msg
    assert "character_name=Orthel" in msg
    assert "write_target=remote" in msg
    assert "before=1" in msg
    assert "after=2" in msg
    assert "added=[35]" in msg
    assert "removed=[]" in msg


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


def test_create_doctrine_emits_audit_log(caplog):
    """Doctrine creation must record the acting admin and the new doctrine_id."""
    repo = StubRepo()
    service = _make_service(repo)

    with caplog.at_level(logging.INFO, logger="services.admin_service"):
        service.create_doctrine(
            doctrine_name="Doctrine Beta",
            signed_identity={"payload": {}, "signature": "x"},
        )

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert info_records, "Expected an INFO audit line"
    msg = info_records[0].getMessage()
    assert "doctrine_created" in msg
    assert "character_id=2122333361" in msg
    assert "character_name=Orthel" in msg
    assert "doctrine_id=11" in msg
    assert "'Doctrine Beta'" in msg


def test_save_doctrine_fit_emits_audit_log_for_add_mode(caplog):
    """Adding a fit must record actor, mode=add, doctrine_id, fit_id, market_flag."""
    repo = StubRepo()
    service = _make_service(repo)

    with caplog.at_level(logging.INFO, logger="services.admin_service"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=50,
            market_flag="primary",
            mode="add",
            signed_identity={"payload": {}, "signature": "x"},
        )

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert info_records, "Expected an INFO audit line"
    msg = info_records[0].getMessage()
    assert "doctrine_fit_saved" in msg
    assert "character_id=2122333361" in msg
    assert "mode=add" in msg
    assert "doctrine_id=10" in msg
    assert "fit_id=99" in msg
    assert "market_flag=primary" in msg
    assert "target=50" in msg


def test_delete_doctrine_fit_emits_audit_log(caplog):
    """Doctrine fit delete must record the acting admin and the deleted IDs."""
    repo = StubRepo()
    service = _make_service(repo)

    with caplog.at_level(logging.INFO, logger="services.admin_service"):
        service.delete_doctrine_fit(
            doctrine_id=10,
            fit_id=20,
            signed_identity={"payload": {}, "signature": "x"},
        )

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert info_records, "Expected an INFO audit line"
    msg = info_records[0].getMessage()
    assert "doctrine_fit_deleted" in msg
    assert "character_id=2122333361" in msg
    assert "doctrine_id=10" in msg
    assert "fit_id=20" in msg


# --- Read-back verification (I5) ------------------------------------------------------


def _make_silent_write_repo():
    """A StubRepo whose write methods are no-ops — simulates a phantom commit."""
    repo = StubRepo()
    repo.replace_watchlist = lambda rows: None  # write claims to succeed, no state change
    repo.create_doctrine = lambda **kwargs: None
    repo.save_doctrine_fit = lambda **kwargs: None
    repo.delete_doctrine_fit = lambda **kwargs: None
    return repo


def test_save_watchlist_raises_integrity_error_on_phantom_write():
    """If the read-back row count disagrees with the write, raise — not silently succeed."""
    repo = _make_silent_write_repo()
    invalidated = {"called": False}
    service = _make_service(repo, cache_called=invalidated)
    df = pd.DataFrame([_watchlist_row(34, "Tritanium")])

    with pytest.raises(AdminWriteIntegrityError, match="read-back mismatch"):
        service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})

    # Cache must NOT be invalidated when the write failed verification — otherwise
    # the UI would re-fetch and render the stale (but consistent) cached rows as
    # if the save had taken effect.
    assert invalidated["called"] is False


def test_create_doctrine_raises_integrity_error_on_phantom_write():
    repo = _make_silent_write_repo()
    service = _make_service(repo)

    with pytest.raises(AdminWriteIntegrityError, match="not visible"):
        service.create_doctrine(
            doctrine_name="Doctrine Beta",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_save_doctrine_fit_raises_integrity_error_on_phantom_write():
    repo = _make_silent_write_repo()
    service = _make_service(repo)

    with pytest.raises(AdminWriteIntegrityError, match="not visible"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=50,
            market_flag="primary",
            mode="add",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_delete_doctrine_fit_raises_integrity_error_when_row_still_present():
    repo = _make_silent_write_repo()
    service = _make_service(repo)

    with pytest.raises(AdminWriteIntegrityError, match="still visible"):
        service.delete_doctrine_fit(
            doctrine_id=10,
            fit_id=20,
            signed_identity={"payload": {}, "signature": "x"},
        )


# --- save_doctrine_fit validation-branch coverage (I11) -------------------------------


def test_save_doctrine_fit_rejects_non_positive_target():
    """target <= 0 is nonsensical (zero or negative stock goal) — reject."""
    service = _make_service(StubRepo())

    with pytest.raises(ValueError, match="target must be greater than zero"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=0,
            market_flag="primary",
            mode="add",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_save_doctrine_fit_rejects_negative_target():
    service = _make_service(StubRepo())

    with pytest.raises(ValueError, match="target must be greater than zero"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=-5,
            market_flag="primary",
            mode="add",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_save_doctrine_fit_rejects_unknown_market_flag():
    """market_flag is a closed enum — typos must fail loudly at the service boundary."""
    service = _make_service(StubRepo())

    with pytest.raises(ValueError, match="market_flag"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=50,
            market_flag="wormhole",  # not in {primary, deployment, both}
            mode="add",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_save_doctrine_fit_rejects_unknown_mode():
    """mode is a closed enum — typos must fail loudly at the service boundary."""
    service = _make_service(StubRepo())

    with pytest.raises(ValueError, match="mode must be add or update"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=50,
            market_flag="primary",
            mode="replace",  # not in {add, update}
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_save_doctrine_fit_update_mode_requires_fit_id():
    """An update with fit_id=None is a programming bug — reject before the write."""
    service = _make_service(StubRepo())

    with pytest.raises(ValueError, match="fit_id is required"):
        service.save_doctrine_fit(
            eft_text="[Vedmak, Test]\nDamage Control II",
            doctrine_id=10,
            fit_id=None,
            target=50,
            market_flag="primary",
            mode="update",
            signed_identity={"payload": {}, "signature": "x"},
        )


def test_save_watchlist_rejects_non_integer_type_id():
    """type_id must coerce to int — a stray "abc" must surface as a clear error."""
    service = _make_service(StubRepo())
    df = pd.DataFrame(
        [
            {
                "type_id": "not-a-number",
                "group_id": 18,
                "type_name": "Tritanium",
                "group_name": "Mineral",
                "category_id": 4,
                "category_name": "Material",
            }
        ]
    )

    with pytest.raises(ValueError, match="type_id must be an integer"):
        service.save_watchlist(df, signed_identity={"payload": {}, "signature": "x"})
